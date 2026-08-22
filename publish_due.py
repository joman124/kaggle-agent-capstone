# -*- coding: utf-8 -*-
"""
Publishes scheduled LinkedIn posts whose time has arrived.

LinkedIn's API cannot hold a post for later (native scheduling is a LinkedIn
UI-only feature), so scheduling here means: the post waits in the ledger with
status "scheduled", and this script -- run every few minutes by Windows Task
Scheduler -- is what actually fires it. That is why a scheduled post goes out
even when the Streamlit app is closed, as long as the PC is on and online.

Three behaviours worth knowing:

  1. In DRY RUN it does not consume anything. It reports what *would* go out
     and leaves the items scheduled, so flipping to live later still sends
     them. (Marking them posted during dry run would silently eat real plans.)
  2. It refuses to publish anything more than MAX_LATE_HOURS overdue, marking
     it "missed" instead. Without this, turning live posting on after a quiet
     weekend would blast every stale item at once.
  3. One failing item never kills the batch. linkedin_publisher raises
     SystemExit on API errors, so that is caught per item and recorded.

Run:  python publish_due.py            # honors LINKEDIN_DRY_RUN in .env
      python publish_due.py --dry      # force a preview, never posts
"""

import os
import sys
from datetime import datetime, timezone
from typing import Optional

import posts_ledger
import publish_settings
from observability import log_decision

REPO_DIR = os.path.dirname(os.path.abspath(__file__))

# A post more than this many hours late is not worth firing blind.
MAX_LATE_HOURS = 12


def _acquire_lock():
    """Return an open, exclusively-locked file handle, or None if another run
    already holds it. Windows-native (msvcrt); the handle must stay open for
    the lock to hold."""
    try:
        os.makedirs("logs", exist_ok=True)
        handle = open(os.path.join("logs", "publish_due.lock"), "a+")
    except OSError:
        return None
    try:
        import msvcrt
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return handle
    except (OSError, ImportError):
        handle.close()
        return None


def _release_lock(handle) -> None:
    try:
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    except (OSError, ImportError, ValueError):
        pass
    finally:
        try:
            handle.close()
        except OSError:
            pass


def _redact(value) -> str:
    """Never let the access token reach a log file or the ledger, both of which
    sit in plain text on disk."""
    text = str(value)[:500]
    token = os.getenv("LINKEDIN_ACCESS_TOKEN", "").strip()
    if token and token in text:
        text = text.replace(token, "[redacted token]")
    return text


def _breadcrumb(item_id: str, post_id) -> None:
    """Record a post that definitely went live but could not be written to the
    ledger, so it can be reconciled by hand instead of silently reposted."""
    try:
        os.makedirs("logs", exist_ok=True)
        with open(os.path.join("logs", "UNRECORDED_POSTS.txt"), "a",
                  encoding="utf-8") as handle:
            handle.write("%s %s %s\n" % (datetime.now(timezone.utc).isoformat(),
                                         item_id, post_id))
    except OSError:
        pass  # best effort; the console line above is the other record


def _local(timestamp: str) -> str:
    """Render a stored UTC timestamp in local time for console output."""
    parsed = posts_ledger._parse(timestamp)
    if parsed is None:
        return str(timestamp)
    return parsed.astimezone().strftime("%Y-%m-%d %H:%M")


def _process_one(record: dict, now: datetime, dry_run: bool, path: str) -> tuple:
    """Handle one due record. Returns (outcome, message) where outcome is one
    of previewed / missed / failed / posted. All ledger writes happen here."""
    item_id = record["id"]
    when = posts_ledger._parse(record.get("scheduled_for"))
    late_hours = (now - when).total_seconds() / 3600.0 if when else 0.0
    too_late = late_hours > MAX_LATE_HOURS

    # Dry run is checked FIRST and writes nothing at all -- not even a "missed"
    # marking. Anything persisted here would quietly consume a real plan that
    # the user expects to still go out once they switch to live.
    if dry_run:
        if too_late:
            return "previewed", ("DRY RUN -- %s would be marked MISSED (was due "
                                 "%s, %.0f hours ago); still scheduled."
                                 % (item_id, _local(record.get("scheduled_for")),
                                    late_hours))
        return "previewed", ("DRY RUN -- %s would post now (scheduled %s):\n%s\n"
                             % (item_id, _local(record.get("scheduled_for")),
                                (record.get("text") or "")[:300]))

    if too_late:
        reason = ("was due %s (%.0f hours ago) -- too late to post "
                  "automatically; reschedule it if you still want it."
                  % (_local(record.get("scheduled_for")), late_hours))
        posts_ledger.mark_missed(item_id, reason, path=path)
        return "missed", "%s SKIPPED: %s" % (item_id, reason)

    # Claim the item BEFORE calling the API. If this process dies between the
    # post going out and the ledger being updated, the record is left
    # "publishing" rather than "scheduled", so the next run will not see it as
    # due and publish it a second time.
    if posts_ledger.update(item_id, path=path, status="publishing") is None:
        return "failed", "%s could not be claimed in the ledger; skipped." % item_id

    # Imported lazily so --dry and the tests run without requests installed.
    from linkedin_publisher import post_text
    try:
        # No dry_run argument on purpose: this lets linkedin_publisher apply
        # its own independent "anything but false means do not post" check, so
        # the unattended path has two agreeing gates rather than one.
        result = post_text(record["text"])
    except SystemExit as exc:
        # linkedin_publisher exits on auth/network/API errors. Catch it so the
        # remaining scheduled posts still get their turn.
        posts_ledger.mark_failed(item_id, _redact(exc), path=path)
        return "failed", "%s FAILED: %s" % (item_id, _redact(exc))
    except Exception as exc:  # noqa: BLE001 - an unattended run must not crash
        posts_ledger.mark_failed(item_id, _redact(exc), path=path)
        return "failed", "%s FAILED: %s" % (item_id, _redact(exc))

    if result.get("dry_run"):
        # The two gates disagreed. Put it back and post nothing.
        posts_ledger.schedule(item_id, record.get("scheduled_for"), path=path)
        return "previewed", ("%s aborted: the publisher resolved to dry run; "
                             "left scheduled." % item_id)

    if posts_ledger.mark_posted(item_id, result.get("post_id"), path=path) is None:
        # The post is already public and permanent, so the ledger write failing
        # is the dangerous case: leave a breadcrumb rather than let anything
        # conclude it still needs sending.
        _breadcrumb(item_id, result.get("post_id"))
        return "posted", ("%s POSTED (id %s) but the ledger write failed -- see "
                          "logs/UNRECORDED_POSTS.txt"
                          % (item_id, result.get("post_id")))
    return "posted", ("%s posted to LinkedIn (id %s)."
                      % (item_id, result.get("post_id")))


def publish_due(now: Optional[datetime] = None,
                force_dry_run: Optional[bool] = None,
                path: Optional[str] = None) -> dict:
    """Publish every due scheduled LinkedIn post. Returns a summary dict.
    `path` overrides the ledger file, which keeps tests off real state."""
    now = now or datetime.now(timezone.utc)
    dry_run = publish_settings.is_live() is False if force_dry_run is None else force_dry_run
    path = path or posts_ledger.LEDGER_PATH

    summary = {"due": 0, "posted": [], "missed": [], "failed": [],
               "previewed": [], "dry_run": dry_run, "messages": []}

    # One publisher at a time. The scheduled task fires every 10 minutes and
    # does not wait for the previous run, so a slow run (several items, a 30s
    # API timeout each) could otherwise overlap the next one -- both would see
    # the same record as due and post it twice, publicly.
    lock = _acquire_lock()
    if lock is None:
        print("[PUBLISH] Another publish run is already in progress; skipping.")
        return summary

    try:
        return _run(now, dry_run, path, summary)
    finally:
        _release_lock(lock)


def _run(now: datetime, dry_run: bool, path: str, summary: dict) -> dict:
    due = posts_ledger.due_scheduled(now_iso=now.isoformat(), path=path)
    summary["due"] = len(due)

    if not due:
        print("[PUBLISH] Nothing due at %s." % now.astimezone().strftime("%Y-%m-%d %H:%M"))
        return summary

    for record in due:
        outcome, message = _process_one(record, now, dry_run, path)
        summary[outcome].append(record["id"])
        summary["messages"].append(message)
        print("[PUBLISH] " + message)

    log_decision(agent="publish_due", action="run",
                 inputs={"due": summary["due"], "dry_run": dry_run},
                 decision={"posted": summary["posted"], "failed": summary["failed"],
                           "missed": summary["missed"],
                           # keep the reason, not just the id, or a failure's
                           # cause survives only in memory/posts.json
                           "messages": summary["messages"]})
    return summary


def main(argv) -> int:
    # Task Scheduler starts a job in whatever folder it likes, and every path
    # in this project (memory/posts.json, .env, logs/) is relative to the repo
    # root. Anchor here rather than at import time, so importing this module
    # (from tests, say) has no hidden effect on the whole process.
    os.chdir(REPO_DIR)
    force_dry = "--dry" in argv
    summary = publish_due(force_dry_run=True if force_dry else None)
    if summary["failed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
