# -*- coding: utf-8 -*-
"""
The reaction cycle: the piece that makes the system actually run on its own.
One invocation = one pass of "what's hot right now -> draft the best reaction
-> queue it for John." Schedule this (Windows Task Scheduler / cron) every few
hours and the platform stays reactive without anyone typing a command.

What it does, in order:
  1. Scout: find hot topics (Google Search grounding).
  2. Rank them (ranking.rank_topics) by relevance x novelty x learned pillar
     performance, dropping duplicates and brand-unsafe topics.
  3. Cadence check (posting_policy): stop if we have already posted enough today.
  4. Draft the top topic with variant-and-pick (best of N), plus a Substack Note.
  5. Enqueue both to the approval queue (posts_ledger, status "queued").
     It does NOT post -- a human approves via review.py.

Run:  python run_cycle.py ["optional focus topic"]
"""

import sys

import posts_ledger
import posting_policy
import ranking
import safety


def run(focus: str = None, variants: int = 2) -> dict:
    from agents.scout import find_topics
    from agents.viral import draft_best_of_linkedin, draft_note
    import analytics

    # 3. Cadence first -- cheap, and skips the Gemini spend if we are capped.
    gate = posting_policy.can_post_now()
    if not gate["allowed"]:
        print(f"[CYCLE] Holding: {gate['reason']}.")
        return {"queued": [], "reason": gate["reason"]}

    # 1 + 2. Scout, then rank with the learned pillar performance.
    briefing = find_topics(focus)
    performance = analytics.performance_multipliers()
    ranked = ranking.rank_topics(briefing, performance=performance)
    if not ranked:
        print("[CYCLE] Scout found nothing to react to.")
        return {"queued": [], "reason": "no topics"}

    top = ranked[0]
    rank = top["_rank"]
    topic = top.get("suggested_angle") or top.get("headline")
    pillar = top.get("suggested_pillar")

    if not rank["safe"]:
        print(f"[CYCLE] Top topic flagged sensitive; skipping to protect the "
              f"brand: {topic}")
        return {"queued": [], "reason": "top topic unsafe"}

    print(f"[CYCLE] Reacting to: {topic}\n  (pillar {pillar}, "
          f"rank score {rank['score']}, novelty {rank['novelty']})")

    # 4. Draft best-of LinkedIn + a Note.
    li = draft_best_of_linkedin(topic, variants=variants)
    note = draft_note(topic)

    # 5. Enqueue both for human approval.
    queued = []
    queued.append(posts_ledger.add(topic, li["text"], "linkedin", pillar=pillar))
    queued.append(posts_ledger.add(topic, note["text"], "substack", pillar=pillar))

    print(f"[CYCLE] Queued {len(queued)} item(s) for review. "
          "Approve with:  python review.py list")
    return {"queued": [q["id"] for q in queued], "topic": topic}


if __name__ == "__main__":
    run(" ".join(sys.argv[1:]) or None)
