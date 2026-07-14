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

Pure file I/O + plain dicts, no Gemini. Safe to import and unit-test anywhere.
"""

import json
import os
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
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)


def _new_id(records: list) -> str:
    # Short, sortable, human-readable: p0001, p0002, ...
    return "p%04d" % (len(records) + 1)


def add(topic: str, text: str, platform: str, pillar: str = None,
        status: str = "queued", path: str = LEDGER_PATH) -> dict:
    """Append a record and return it (with its new id)."""
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
