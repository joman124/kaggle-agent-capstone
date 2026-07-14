# -*- coding: utf-8 -*-
"""
Ranking helpers, pure logic (no Gemini):

  - pick_best(results): given several drafted candidates, choose the one most
    likely to perform -- highest combined voice + engagement score, preferring
    drafts that passed all gates. This powers "variant-and-pick": generate a
    few, keep the best.
  - rank_topics(briefing, ...): order Scout's hot topics by how worth reacting
    to they are -- relevance (from Scout) + novelty (not a near-duplicate of
    something recent) + brand safety + a boost for pillars that have performed
    well (the learning loop). Sensitive or duplicate topics sink to the bottom.
"""

import posting_policy
import safety


def _score_result(result: dict) -> float:
    """Combined quality score for one drafted candidate. Voice is 0-10 (scaled
    to 0-100), engagement is already 0-100; a passing draft gets a large bonus
    so it always beats a non-passing one."""
    ev = result.get("evaluation", {}) or {}
    voice = (ev.get("voice_score") or 0) * 10
    extra = ev.get("extra") or {}
    engagement = extra.get("score") or 0
    passed_bonus = 1000 if ev.get("passed") else 0
    return passed_bonus + voice + engagement


def pick_best(results: list) -> dict:
    """Return the best candidate result (by _score_result). results is a list of
    dicts shaped like draft_with_guardrails output. Empty -> None."""
    if not results:
        return None
    return max(results, key=_score_result)


def rank_topics(briefing: list, performance: dict = None, ledger=None) -> list:
    """Score and sort Scout topics best-first. Each returned item is the
    original topic dict plus a "_rank" block:
      {"score": float, "novelty": float, "safe": bool, "reasons": [...]}.
    performance is an optional {pillar: multiplier} map from analytics (a pillar
    that has been earning engagement gets a gentle boost)."""
    performance = performance or {}
    ranked = []
    for topic in briefing or []:
        text = topic.get("suggested_angle") or topic.get("headline") or ""
        pillar = topic.get("suggested_pillar")
        relevance = float(topic.get("relevance_score", 5))

        dup = posting_policy.is_duplicate(text, ledger=ledger)
        novelty = 1.0 - dup["overlap"]
        safe = safety.assess(text)
        perf_mult = float(performance.get(pillar, 1.0))

        reasons = []
        score = relevance * novelty * perf_mult
        if dup["duplicate"]:
            score *= 0.1
            reasons.append(f"near-duplicate of '{dup['match']}'")
        if not safe["safe"]:
            score *= 0.05
            reasons.append("flagged sensitive: " + safe["reason"])
        if perf_mult > 1.0:
            reasons.append(f"pillar '{pillar}' has been performing")

        item = dict(topic)
        item["_rank"] = {
            "score": round(score, 3),
            "novelty": round(novelty, 2),
            "safe": safe["safe"],
            "reasons": reasons,
        }
        ranked.append(item)

    ranked.sort(key=lambda t: t["_rank"]["score"], reverse=True)
    return ranked
