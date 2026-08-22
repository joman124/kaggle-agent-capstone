# -*- coding: utf-8 -*-
"""
The posts ledger: one JSON store (memory/posts.json) that every part of the
fast-reaction pipeline reads and writes. It is the backbone for four features:

  - the approval queue (a record with status "queued" is waiting for review),
  - de-duplication (recent topics live here, so we do not react to the same
    thing twice),
  - cadence control (timestamps here bound how often we post),
  - the performance loop (once a post is live we store its LinkedIn URN, then
    fill in real metrics later so the system can learn what actually landed).

Each record:
  {
    "id": short id,
    "created": ISO timestamp,
    "platform": "linkedin" | "substack",
    "pillar": str | None,
    "topic": str,
    "text": str,
    "status": "queued" | "posted" | "rejected" | "skipped",
    "urn": str | None,          # LinkedIn post id, once posted
    "posted_at": ISO | None,
    "metrics": {"impressions", "reactions", "comments", "shares"} | None
  }

Pure file I/O + plain dicts, no model calls. Safe to import and unit-test anywhere.
"""

import json
import os
import tempfile
from datetime import datetime, timezone

LEDGER_PATH = os.path.join("memory", "posts.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load(path: str = LEDGER_PATH) -> list:
    """Return the ledger as a list of records (empty list if none yet)."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return []
    return data if isinstance(data, list) else []


def save(records: list, path: str = LEDGER_PATH) -> None:
    """Write the ledger atomically: a reader (the Streamlit app, or the
    background publisher running at the same moment) sees either the whole old
    file or the whole new one, never a half-written one. A truncated read here
    used to be able to look like an empty ledger, which is how a posted item
    could revert to 'scheduled' and get published a second time."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    directory = os.path.dirname(path) or "."
    handle, temp_path = tempfile.mkstemp(dir=directory, prefix=".posts.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    except BaseException:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def _new_id(records: list) -> str:
    """Short, sortable, human-readable: p0001, p0002, ...

    Derived from the highest existing id rather than len(records): with a
    count, removing any record would reissue a live id, and update() patches
    only the first match -- which would leave a genuinely posted record still
    marked 'scheduled' and let it publish again."""
    highest = 0
    for record in records:
        rid = str(record.get("id") or "")
        if rid.startswith("p") and rid[1:].isdigit():
            highest = max(highest, int(rid[1:]))
    return "p%04d" % (highest + 1)


def add(topic: str, text: str, platform: str, pillar: str = None,
        status: str = "queued", path: str = LEDGER_PATH,
        source: str = None) -> dict:
    """Append a record and return it (with its new id).

    source is an optional origin marker -- the Drafts tab passes the docx
    heading, which carries a date and so stays unique even when several
    drafts share one topic (days with no Scout topic fall back to the bare
    pillar name). Kept separate from topic because posting_policy does fuzzy
    word-overlap matching on topic, which a date suffix would dilute."""
    records = load(path)
    record = {
        "id": _new_id(records),
        "created": _now(),
        "platform": platform,
        "pillar": pillar,
        "topic": topic,
        "text": text,
        "status": status,
        "urn": None,
        "posted_at": None,
        "metrics": None,
        "source": source,
    }
    records.append(record)
    save(records, path)
    return record


def update(record_id: str, path: str = LEDGER_PATH, **fields) -> dict:
    """Merge fields into one record by id. Returns the updated record, or None
    if the id was not found."""
    records = load(path)
    updated = None
    for r in records:
        if r.get("id") == record_id:
            r.update(fields)
            updated = r
            break
    if updated is not None:
        save(records, path)
    return updated


def mark_posted(record_id: str, urn: str, path: str = LEDGER_PATH) -> dict:
    return update(record_id, path=path, status="posted", urn=urn, posted_at=_now())


def by_status(status: str, path: str = LEDGER_PATH) -> list:
    return [r for r in load(path) if r.get("status") == status]


# --------------------------------------------------------------------------
# Scheduling
#
# LinkedIn's API has no scheduled-post endpoint for member posts, so a
# scheduled item just waits here with status "scheduled" and a UTC timestamp
# in scheduled_for. publish_due.py (run by Task Scheduler) is what actually
# fires it. Timestamps are always stored UTC; the UI converts to/from local.
# --------------------------------------------------------------------------

def _parse(timestamp: str):
    """Parse an ISO timestamp to an aware datetime, or None if unparseable.
    A naive timestamp is assumed to be UTC rather than silently mis-compared."""
    if not timestamp:
        return None
    try:
        parsed = datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def schedule(record_id: str, when_utc_iso: str, path: str = LEDGER_PATH) -> dict:
    """Queue a record to publish at a UTC time. Clears any previous error."""
    return update(record_id, path=path, status="scheduled",
                  scheduled_for=when_utc_iso, error=None)


def unschedule(record_id: str, path: str = LEDGER_PATH) -> dict:
    """Pull a scheduled record back into the approval queue."""
    return update(record_id, path=path, status="queued", scheduled_for=None)


def mark_failed(record_id: str, error: str, path: str = LEDGER_PATH) -> dict:
    """A publish attempt errored. Kept visible rather than retried forever."""
    return update(record_id, path=path, status="failed", error=str(error)[:500])


def mark_missed(record_id: str, reason: str, path: str = LEDGER_PATH) -> dict:
    """Was due but too stale to publish safely (see publish_due.MAX_LATE_HOURS).
    Deliberately not posted -- John reschedules it if he still wants it."""
    return update(record_id, path=path, status="missed", error=str(reason)[:500])


def scheduled(path: str = LEDGER_PATH) -> list:
    """All scheduled records, soonest first."""
    items = by_status("scheduled", path=path)
    items.sort(key=lambda r: r.get("scheduled_for") or "")
    return items


def due_scheduled(now_iso: str = None, platform: str = "linkedin",
                  path: str = LEDGER_PATH) -> list:
    """Scheduled records whose time has arrived, soonest first. Compares real
    datetimes, not strings, so mixed offsets cannot cause a false 'due'."""
    now = _parse(now_iso) or datetime.now(timezone.utc)
    due = []
    for record in load(path):
        if record.get("status") != "scheduled":
            continue
        if platform and record.get("platform") != platform:
            continue
        when = _parse(record.get("scheduled_for"))
        if when is not None and when <= now:
            due.append(record)
    due.sort(key=lambda r: r.get("scheduled_for") or "")
    return due
