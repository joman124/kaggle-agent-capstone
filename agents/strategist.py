# -*- coding: utf-8 -*-
"""
The Strategist agent: plans what to publish, when, and on which platform.
Reads persistent state from memory/ (content history + rolling pillar
distribution), balances pillar coverage across the week, and writes the
plan to memory/calendar.json. Pure logic, no Gemini calls.

Run:  python -m agents.strategist
"""

import json
import os
from datetime import date, timedelta

MEMORY_DIR = "memory"
CONTENT_HISTORY_PATH = os.path.join(MEMORY_DIR, "content_history.json")
PILLAR_TRACKER_PATH = os.path.join(MEMORY_DIR, "pillar_tracker.json")
CALENDAR_PATH = os.path.join(MEMORY_DIR, "calendar.json")

PILLARS = [
    "Clinical Window",
    "The Thesis",
    "Personal",
    "Applied Philosophy",
    "Current Events",
]
# Platform cadence target: Substack ~1 essay/week, LinkedIn 3-4 posts/week.
PLATFORM_PATTERN = ["linkedin", "substack", "linkedin", "linkedin", "substack"]
ROLLING_WINDOW_DAYS = 30


def _load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: str, data) -> None:
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def compute_pillar_distribution(history: list, window_days: int = ROLLING_WINDOW_DAYS) -> dict:
    """Count posts per pillar within the rolling window. Pillars with no
    posts in the window stay at zero, so they rank first for balancing."""
    counts = {p: 0 for p in PILLARS}
    cutoff = date.today() - timedelta(days=window_days)
    for entry in history:
        try:
            entry_date = date.fromisoformat(entry["date"])
        except (KeyError, ValueError):
            continue
        if entry_date < cutoff:
            continue
        pillar = entry.get("pillar")
        if pillar in counts:
            counts[pillar] += 1
    return counts


def _match_scout_topic(pillar: str, used_headlines: set, scout_briefing: list):
    for topic in scout_briefing or []:
        if topic.get("suggested_pillar") == pillar and topic.get("headline") not in used_headlines:
            return topic
    return None


def plan_week(scout_briefing: list = None, num_days: int = 5,
              pillar_adjustments: dict = None) -> list:
    """Build a balanced content plan. Least-used pillars in the rolling
    window go first; platform follows a fixed cadence pattern so Strategist
    keeps control of platform balance even when Scout suggests otherwise.
    If a Scout briefing is supplied, each day's pillar is matched to a topic
    from it when one is available. pillar_adjustments (from
    agents.analyst.get_pillar_adjustments(), +1/-1/0 per pillar) shifts a
    pillar earlier (+1, it is overperforming, do more) or later (-1) in the
    ranking without overriding the rolling-window balance entirely."""
    history = _load_json(CONTENT_HISTORY_PATH, [])
    distribution = compute_pillar_distribution(history)
    _save_json(PILLAR_TRACKER_PATH, distribution)

    adjustments = pillar_adjustments or {}
    ranked_pillars = sorted(
        PILLARS,
        key=lambda p: (distribution[p] - adjustments.get(p, 0), PILLARS.index(p)),
    )
    used_headlines = set()
    plan = []
    for i in range(num_days):
        pillar = ranked_pillars[i % len(ranked_pillars)]
        platform = PLATFORM_PATTERN[i % len(PLATFORM_PATTERN)]
        match = _match_scout_topic(pillar, used_headlines, scout_briefing)
        if match:
            used_headlines.add(match["headline"])
        plan.append({
            "day": f"Day {i + 1}",
            "pillar": pillar,
            "platform": platform,
            "topic": match["suggested_angle"] if match else None,
            "source_headline": match["headline"] if match else None,
        })

    _save_json(CALENDAR_PATH, plan)
    return plan


if __name__ == "__main__":
    weekly_plan = plan_week()
    print(json.dumps(weekly_plan, indent=2))
