# -*- coding: utf-8 -*-
"""
The approval queue. The scheduled cycle (run_cycle.py) drafts content and puts
it here with status "queued" instead of posting straight to LinkedIn. John then
reviews and approves what goes live -- fast reaction, but a human still says yes
before the brand speaks.

Commands:
  python review.py list                 # show what is waiting
  python review.py show <id>            # print one item in full
  python review.py edit <id> <text>     # replace the draft text before posting
  python review.py approve <id>         # post it live (LinkedIn) / mark done
  python review.py reject <id>          # drop it

Approving a LinkedIn item posts it through linkedin_publisher (which honors
LINKEDIN_DRY_RUN). Substack items cannot be auto-posted, so approving one just
records it as done and reminds you to paste it into Substack.
"""

import json
import os
import sys
from datetime import datetime, timezone

import posts_ledger

EDIT_HISTORY_PATH = os.path.join("memory", "edit_history.json")


def _log_edit(record_id: str, before: str, after: str) -> None:
    """Append one edit event to memory/edit_history.json -- a plain record of
    what John changed by hand before approving, so a repeated pattern across
    edits can be turned into a permanent voice_learnings.py rule later (see
    the Streamlit "Voice Rules" tab). Best-effort: a logging failure must
    never block saving the actual edit."""
    entry = {
        "record_id": record_id,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "before": before,
        "after": after,
    }
    try:
        history = []
        if os.path.exists(EDIT_HISTORY_PATH):
            with open(EDIT_HISTORY_PATH, "r", encoding="utf-8") as fh:
                history = json.load(fh)
        history.append(entry)
        os.makedirs("memory", exist_ok=True)
        with open(EDIT_HISTORY_PATH, "w", encoding="utf-8") as fh:
            json.dump(history, fh, indent=2)
    except (OSError, json.JSONDecodeError):
        pass


def _find(record_id: str):
    for r in posts_ledger.load():
        if r["id"] == record_id:
            return r
    return None


def approve_item(record_id: str) -> dict:
    """Approve one queued item. Posts LinkedIn items via the publisher (honors
    dry run); marks Substack items done for manual posting. Returns a structured
    result dict so both the CLI and the UI can report cleanly:
      {"ok": bool, "msg": str, "posted": bool, "dry_run": bool, "post_id": str}"""
    record = _find(record_id)
    if not record:
        return {"ok": False, "msg": f"No item with id {record_id}."}
    if record["status"] != "queued":
        return {"ok": False, "msg": f"{record_id} is '{record['status']}', not queued."}

    if record["platform"] == "linkedin":
        from linkedin_publisher import post_text
        try:
            result = post_text(record["text"])
        except SystemExit as exc:
            # linkedin_publisher exits on auth/version/network errors. Without
            # this the SystemExit would tear down the Streamlit script run and
            # John would see a raw traceback instead of what went wrong, and
            # the item would be left queued with no explanation. publish_due.py
            # already catches this on the unattended path; the UI needs it too.
            posts_ledger.update(record_id, status="failed", error=str(exc))
            return {"ok": False, "posted": False,
                    "msg": "%s could not be posted: %s" % (record_id, str(exc).strip())}
        except Exception as exc:  # noqa: BLE001 - the UI must not crash
            posts_ledger.update(record_id, status="failed", error=str(exc))
            return {"ok": False, "posted": False,
                    "msg": "%s could not be posted: %s" % (record_id, exc)}
        if result["dry_run"]:
            posts_ledger.update(record_id, status="posted", urn="dry-run-simulated")
            return {"ok": True, "posted": False, "dry_run": True,
                    "msg": f"{record_id} approved (DRY RUN -- not actually posted)."}
        posts_ledger.mark_posted(record_id, result["post_id"])
        return {"ok": True, "posted": True, "dry_run": False,
                "post_id": result["post_id"],
                "msg": f"{record_id} posted to LinkedIn (id {result['post_id']})."}
    posts_ledger.update(record_id, status="posted")
    return {"ok": True, "posted": False, "manual": True,
            "msg": f"{record_id} marked done. Paste it into Substack yourself."}


def edit_item(record_id: str, new_text: str) -> dict:
    """Replace the draft text of one queued item. Editing is only allowed while
    the item is still queued: once it is posted, its text is the record of what
    actually went live and must not change. Returns a structured result dict so
    the CLI and the UI can report the same way."""
    record = _find(record_id)
    if not record:
        return {"ok": False, "msg": f"No item with id {record_id}."}
    if record["status"] != "queued":
        return {"ok": False,
                "msg": f"{record_id} is '{record['status']}', not queued -- cannot edit."}
    text = (new_text or "").strip()
    if not text:
        return {"ok": False, "msg": "Cannot save an empty post."}
    if text == (record.get("text") or "").strip():
        return {"ok": True, "unchanged": True, "msg": f"{record_id} unchanged."}
    _log_edit(record_id, record.get("text") or "", text)
    posts_ledger.update(record_id, text=text)
    return {"ok": True, "msg": f"{record_id} updated."}


def reject_item(record_id: str) -> dict:
    updated = posts_ledger.update(record_id, status="rejected")
    if updated:
        return {"ok": True, "msg": f"{record_id} rejected."}
    return {"ok": False, "msg": f"No item with id {record_id}."}


def schedule_item(record_id: str, when_utc_iso: str) -> dict:
    """Hold a queued LinkedIn item until when_utc_iso, then let publish_due.py
    fire it. Substack cannot be auto-posted, so scheduling one is refused
    rather than silently doing nothing at the scheduled time."""
    record = _find(record_id)
    if not record:
        return {"ok": False, "msg": f"No item with id {record_id}."}
    if record["platform"] != "linkedin":
        return {"ok": False,
                "msg": ("Only LinkedIn items can be scheduled. Substack has no "
                        "API -- approve it and paste it in yourself.")}
    if record["status"] not in ("queued", "scheduled", "failed", "missed"):
        return {"ok": False,
                "msg": f"{record_id} is '{record['status']}' and cannot be scheduled."}

    # Validated here too, not just in the UI, so a future CLI or cron caller
    # cannot park a post in the past (which would fire on the next check).
    from datetime import datetime, timezone
    when = posts_ledger._parse(when_utc_iso)
    if when is None:
        return {"ok": False, "msg": f"'{when_utc_iso}' is not a valid timestamp."}
    if when <= datetime.now(timezone.utc):
        return {"ok": False, "msg": "That time is in the past. Pick a future time."}

    posts_ledger.schedule(record_id, when_utc_iso)
    return {"ok": True, "msg": f"{record_id} scheduled."}


def requeue_item(record_id: str) -> dict:
    """Put a failed or missed item back in the approval queue, clearing the
    old error and any stale schedule so it cannot fire unexpectedly."""
    record = _find(record_id)
    if not record:
        return {"ok": False, "msg": f"No item with id {record_id}."}
    if record["status"] not in ("failed", "missed", "rejected", "publishing"):
        return {"ok": False,
                "msg": f"{record_id} is '{record['status']}'; nothing to requeue."}
    posts_ledger.update(record_id, status="queued", scheduled_for=None, error=None)
    return {"ok": True, "msg": f"{record_id} is back in the queue."}


def cancel_schedule(record_id: str) -> dict:
    """Pull a scheduled item back into the queue so it will not auto-post."""
    record = _find(record_id)
    if not record:
        return {"ok": False, "msg": f"No item with id {record_id}."}
    if record["status"] != "scheduled":
        return {"ok": False, "msg": f"{record_id} is not scheduled."}
    posts_ledger.unschedule(record_id)
    return {"ok": True, "msg": f"{record_id} unscheduled and back in the queue."}


def cmd_list() -> None:
    pending = posts_ledger.by_status("queued")
    if not pending:
        print("[REVIEW] Nothing queued.")
        return
    print(f"[REVIEW] {len(pending)} item(s) queued:\n")
    for r in pending:
        first_line = (r.get("text") or "").strip().splitlines()[0:1]
        preview = first_line[0] if first_line else ""
        print(f"  {r['id']}  [{r['platform']}] {r.get('pillar') or '-'}  {r['topic']}")
        print(f"        {preview[:80]}")
    print("\nApprove with:  python review.py approve <id>")


def cmd_show(record_id: str) -> None:
    for r in posts_ledger.load():
        if r["id"] == record_id:
            print(f"[REVIEW] {r['id']} [{r['platform']}] status={r['status']}")
            print(f"Topic: {r['topic']}\n")
            print(r.get("text") or "")
            return
    print(f"[REVIEW] No item with id {record_id}.")


def cmd_edit(record_id: str, new_text: str) -> None:
    print("[REVIEW] " + edit_item(record_id, new_text)["msg"])


def cmd_approve(record_id: str) -> None:
    record = _find(record_id)
    result = approve_item(record_id)
    print("[REVIEW] " + result["msg"])
    if result.get("manual") and record:
        print("\n" + (record.get("text") or ""))


def cmd_reject(record_id: str) -> None:
    print("[REVIEW] " + reject_item(record_id)["msg"])


def main(argv) -> None:
    if not argv:
        cmd_list()
        return
    cmd = argv[0].lower()
    arg = argv[1] if len(argv) > 1 else None
    if cmd == "list":
        cmd_list()
    elif cmd == "show" and arg:
        cmd_show(arg)
    elif cmd == "edit" and arg:
        cmd_edit(arg, " ".join(argv[2:]))
    elif cmd == "approve" and arg:
        cmd_approve(arg)
    elif cmd == "reject" and arg:
        cmd_reject(arg)
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
