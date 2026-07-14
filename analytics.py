# -*- coding: utf-8 -*-
"""
The learning loop, pure logic over the posts ledger. Once metrics have been
synced (linkedin_metrics.sync_ledger), this turns them into:

  - summarize(): per-pillar performance (post count, average engagement), and
  - performance_multipliers(): a {pillar: multiplier} map that ranking.py uses
    to gently favor pillars that have been earning engagement and pull back on
    ones that have not.

Engagement per post is reactions + 2*comments (comments are the stronger signal
of reach on LinkedIn). No Gemini; safe to run any time.
"""

import posts_ledger

# How far a pillar's multiplier can swing from neutral, so one lucky post does
# not dominate the ranking.
MAX_BOOST = 1.5
MIN_BOOST = 0.6


def _engagement(metrics: dict) -> float:
    if not metrics:
        return 0.0
    return (metrics.get("reactions") or 0) + 2 * (metrics.get("comments") or 0)


def summarize(path: str = posts_ledger.LEDGER_PATH) -> dict:
    """Return {pillar: {"posts": n, "with_metrics": m, "avg_engagement": x}}."""
    records = [r for r in posts_ledger.load(path) if r.get("status") == "posted"]
    by_pillar = {}
    for r in records:
        pillar = r.get("pillar") or "unassigned"
        slot = by_pillar.setdefault(pillar, {"posts": 0, "with_metrics": 0, "_sum": 0.0})
        slot["posts"] += 1
        if r.get("metrics"):
            slot["with_metrics"] += 1
            slot["_sum"] += _engagement(r["metrics"])
    for slot in by_pillar.values():
        slot["avg_engagement"] = round(
            slot["_sum"] / slot["with_metrics"], 2) if slot["with_metrics"] else 0.0
        del slot["_sum"]
    return by_pillar


def performance_multipliers(path: str = posts_ledger.LEDGER_PATH) -> dict:
    """Return {pillar: multiplier} centered on 1.0. A pillar above the overall
    average engagement gets a boost (up to MAX_BOOST); below gets a cut (down to
    MIN_BOOST). Pillars without metrics stay neutral (1.0)."""
    summary = summarize(path)
    scored = {p: s["avg_engagement"] for p, s in summary.items()
              if s["with_metrics"] > 0}
    if not scored:
        return {}
    overall = sum(scored.values()) / len(scored)
    if overall <= 0:
        return {}
    mult = {}
    for pillar, avg in scored.items():
        raw = avg / overall
        mult[pillar] = round(max(MIN_BOOST, min(MAX_BOOST, raw)), 2)
    return mult


if __name__ == "__main__":
    import json
    print("Per-pillar performance:")
    print(json.dumps(summarize(), indent=2))
    print("\nRanking multipliers:")
    print(json.dumps(performance_multipliers(), indent=2))
