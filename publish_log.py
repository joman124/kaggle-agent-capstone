# -*- coding: utf-8 -*-
"""
Write-back for publish events: the missing half of the learning loop.

Until now nothing ever wrote to memory/content_history.json after John
actually posted a draft, so the Strategist's rolling 30-day pillar balance
always read an empty history and every weekly plan started from zero.
mark_published() closes that loop: one entry per real post, matching the
schema compute_pillar_distribution() reads ("date" ISO string + "pillar";
"title" and "platform" kept for the record, per ARCHITECTURE.md).

Used by the Streamlit UI's "Mark as published" button (app.py), or from
the command line:

    python publish_log.py "<draft heading>" "<pillar>" "<platform>"
"""

import json
import os
import sys
from datetime import date

MEMORY_DIR = "memory"
CONTENT_HISTORY_PATH = os.path.join(MEMORY_DIR, "content_history.json")

PILLARS = [
    "Clinical Window",
    "The Thesis",
    "Personal",
    "Applied Philosophy",
    "Current Events",
]


def load_history() -> list:
    """Return the content history list, [] if the file is missing/corrupt."""
    if not os.path.exists(CONTENT_HISTORY_PATH):
        return []
    try:
        with open(CONTENT_HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def is_published(title: str) -> bool:
    """True if a post with this exact title was already marked published.
    Draft headings include the draft date, so the same topic redrafted on
    a later day is a different title and can be published separately."""
    return any(e.get("title") == title for e in load_history())


def mark_published(title: str, pillar: str, platform: str,
                   published_date: str = None) -> dict:
    """Append one publish event to content_history.json and return it.
    Idempotent: a title that is already in the history is not re-appended
    (returns the existing entry instead), so a double-click on the UI
    button cannot skew the Strategist's pillar counts."""
    if pillar not in PILLARS:
        raise ValueError(
            "Unknown pillar %r. Expected one of: %s" % (pillar, ", ".join(PILLARS))
        )

    history = load_history()
    for entry in history:
        if entry.get("title") == title:
            return entry

    entry = {
        "title": title,
        "date": published_date or date.today().isoformat(),
        "pillar": pillar,
        "platform": platform,
    }
    history.append(entry)
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with open(CONTENT_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)
    return entry


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python publish_log.py \"<title>\" \"<pillar>\" \"<platform>\"")
        print("Pillars: " + ", ".join(PILLARS))
        sys.exit(1)
    saved = mark_published(sys.argv[1], sys.argv[2], sys.argv[3])
    print("Recorded: " + json.dumps(saved, indent=2))
