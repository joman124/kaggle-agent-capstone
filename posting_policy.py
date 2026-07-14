# -*- coding: utf-8 -*-
"""
Posting policy: pure-logic guards that keep a fast-reaction system from posting
the same thing twice or posting too often (which reads as botty and burns
reach). Reads the posts ledger; no Gemini.

Two checks:
  - is_duplicate(topic): have we already posted/queued something about this in
    the recent window? Uses normalized word-overlap, so "AI writes most code"
    and "most code is now written by AI" collide.
  - can_post_now(): are we under the per-day and minimum-spacing limits?
"""

import re
from datetime import datetime, timezone, timedelta

import posts_ledger

# Defaults; callers can override. Tuned for "active but not spammy."
DEDUP_WINDOW_DAYS = 14
DUP_OVERLAP = 0.6          # fraction of shared significant words to call it a dup
MAX_PER_DAY = 3
MIN_HOURS_BETWEEN = 3

_STOP = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "is",
    "are", "was", "were", "be", "with", "that", "this", "it", "as", "at", "by",
    "about", "how", "why", "what", "your", "you", "we", "our", "new", "now",
}


def _sig_words(text: str) -> set:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if w not in _STOP and len(w) > 2}


def _overlap(a: str, b: str) -> float:
    wa, wb = _sig_words(a), _sig_words(b)
    if not wa or not wb:
        return 0.0
    inter = len(wa & wb)
    return inter / min(len(wa), len(wb))


def _parse(ts: str):
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def is_duplicate(topic: str, window_days: int = DEDUP_WINDOW_DAYS,
                 threshold: float = DUP_OVERLAP, ledger=None) -> dict:
    """Return {"duplicate": bool, "match": <topic>|None, "overlap": float}.
    Compares against posted/queued records within the window."""
    records = ledger if ledger is not None else posts_ledger.load()
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    best = (0.0, None)
    for r in records:
        if r.get("status") in ("rejected", "skipped"):
            continue
        created = _parse(r.get("created", ""))
        if created and created < cutoff:
            continue
        ov = _overlap(topic, r.get("topic", ""))
        if ov > best[0]:
            best = (ov, r.get("topic"))
    return {"duplicate": best[0] >= threshold, "match": best[1], "overlap": round(best[0], 2)}


def can_post_now(now=None, max_per_day: int = MAX_PER_DAY,
                 min_hours: int = MIN_HOURS_BETWEEN, ledger=None) -> dict:
    """Return {"allowed": bool, "reason": str}. Counts only records already
    posted (status 'posted'), by posted_at."""
    now = now or datetime.now(timezone.utc)
    records = ledger if ledger is not None else posts_ledger.load()
    posted_times = []
    for r in records:
        if r.get("status") != "posted":
            continue
        t = _parse(r.get("posted_at") or r.get("created", ""))
        if t:
            posted_times.append(t)

    today = [t for t in posted_times if t.date() == now.date()]
    if len(today) >= max_per_day:
        return {"allowed": False,
                "reason": f"already posted {len(today)} today (max {max_per_day})"}

    if posted_times:
        last = max(posted_times)
        gap_hours = (now - last).total_seconds() / 3600.0
        if gap_hours < min_hours:
            return {"allowed": False,
                    "reason": f"last post was {gap_hours:.1f}h ago "
                              f"(min {min_hours}h between)"}

    return {"allowed": True, "reason": "ok"}
