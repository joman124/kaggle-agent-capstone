# -*- coding: utf-8 -*-
"""
The Analyst agent: ingests engagement data, computes performance per pillar
and platform, compares it against a target engagement rate, and produces
recommendations the Strategist can use to adjust pillar weighting over time.
Pure logic, no model calls.

Each entry in memory/engagement_data.json is one published post's metrics:
{"pillar": str, "platform": "linkedin"|"substack", "likes": int,
 "comments": int, "shares": int, "impressions": int}

DEFAULT_TARGET_RATE is a placeholder benchmark (3%) until John has real
per-platform targets to replace it with.

Run:  python -m agents.analyst
"""

import json
import os

MEMORY_DIR = "memory"
ENGAGEMENT_PATH = os.path.join(MEMORY_DIR, "engagement_data.json")

DEFAULT_TARGET_RATE = 0.03  # (likes + comments + shares) / impressions

PILLARS = [
    "Clinical Window", "The Thesis", "Personal",
    "Applied Philosophy", "Current Events",
]


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _engagement_rate(entry: dict) -> float:
    impressions = entry.get("impressions", 0)
    if impressions <= 0:
        return 0.0
    return (entry.get("likes", 0) + entry.get("comments", 0) + entry.get("shares", 0)) / impressions


def compute_performance(engagement_data: list) -> dict:
    """Aggregate engagement by pillar. Returns
    {pillar: {"post_count": int, "rate": float}}, where rate is the
    impressions-weighted engagement rate across all of that pillar's posts."""
    totals = {}
    for entry in engagement_data:
        pillar = entry.get("pillar")
        if not pillar:
            continue
        bucket = totals.setdefault(pillar, {"engaged": 0, "impressions": 0, "post_count": 0})
        bucket["engaged"] += entry.get("likes", 0) + entry.get("comments", 0) + entry.get("shares", 0)
        bucket["impressions"] += entry.get("impressions", 0)
        bucket["post_count"] += 1

    performance = {}
    for pillar, bucket in totals.items():
        rate = bucket["engaged"] / bucket["impressions"] if bucket["impressions"] > 0 else 0.0
        performance[pillar] = {"post_count": bucket["post_count"], "rate": rate}
    return performance


def compare_to_target(performance: dict, target_rate: float = DEFAULT_TARGET_RATE) -> list:
    """Classify each pillar's rate against target_rate. Returns a list of
    {"pillar", "rate", "target", "status"} where status is "above", "below",
    or "at" (within 10% of target either way)."""
    comparison = []
    for pillar, stats in performance.items():
        rate = stats["rate"]
        if rate >= target_rate * 1.1:
            status = "above"
        elif rate <= target_rate * 0.9:
            status = "below"
        else:
            status = "at"
        comparison.append({
            "pillar": pillar,
            "post_count": stats["post_count"],
            "rate": rate,
            "target": target_rate,
            "status": status,
        })
    return comparison


def pillar_adjustments(comparison: list) -> dict:
    """Turn a comparison list into {pillar: +1/-1/0} for the Strategist:
    +1 means do more of this pillar (it overperforms), -1 means do less."""
    adjustments = {}
    for row in comparison:
        if row["status"] == "above":
            adjustments[row["pillar"]] = 1
        elif row["status"] == "below":
            adjustments[row["pillar"]] = -1
        else:
            adjustments[row["pillar"]] = 0
    return adjustments


def get_pillar_adjustments(engagement_data: list = None, target_rate: float = DEFAULT_TARGET_RATE) -> dict:
    """Convenience entry point for the Orchestrator: load engagement data
    (or use what was passed in), compute performance, and return adjustments.
    Pillars with no data yet are simply absent (adjustment 0 by default)."""
    if engagement_data is None:
        engagement_data = _load_json(ENGAGEMENT_PATH, [])
    performance = compute_performance(engagement_data)
    comparison = compare_to_target(performance, target_rate=target_rate)
    return pillar_adjustments(comparison)


def weekly_summary(engagement_data: list = None, target_rate: float = DEFAULT_TARGET_RATE) -> str:
    """Human-readable performance report, one line per pillar with data."""
    if engagement_data is None:
        engagement_data = _load_json(ENGAGEMENT_PATH, [])
    performance = compute_performance(engagement_data)
    comparison = compare_to_target(performance, target_rate=target_rate)

    if not comparison:
        return "[ANALYST] No engagement data yet. Nothing to report."

    comparison.sort(key=lambda row: row["rate"], reverse=True)
    lines = [f"[ANALYST] Weekly summary (target rate: {target_rate:.1%}):"]
    for row in comparison:
        lines.append(
            f"  {row['pillar']}: {row['rate']:.1%} engagement over {row['post_count']} "
            f"post(s) - {row['status']} target"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    data = _load_json(ENGAGEMENT_PATH, [])
    if not data:
        print("[ANALYST] memory/engagement_data.json is empty; using mock data for this run.\n")
        data = [
            {"pillar": "Clinical Window", "platform": "linkedin", "likes": 80, "comments": 12,
             "shares": 5, "impressions": 2000},
            {"pillar": "The Thesis", "platform": "substack", "likes": 15, "comments": 3,
             "shares": 1, "impressions": 1200},
            {"pillar": "Personal", "platform": "linkedin", "likes": 140, "comments": 30,
             "shares": 20, "impressions": 2500},
            {"pillar": "Applied Philosophy", "platform": "substack", "likes": 20, "comments": 4,
             "shares": 2, "impressions": 1500},
            {"pillar": "Current Events", "platform": "linkedin", "likes": 30, "comments": 5,
             "shares": 1, "impressions": 1800},
        ]

    print(weekly_summary(data))
    print()
    print("[ANALYST] Pillar adjustments for the Strategist:")
    print(json.dumps(get_pillar_adjustments(data), indent=2))
