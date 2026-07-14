# Roadmap - reaction system

Goal: post fast in reaction to hot topics to earn views and engagement, without
losing John's voice or the brand's judgment.

## Shipped

- **Viral agent** - hot topic -> short LinkedIn post + Substack Note, through the
  voice guardrails (`agents/viral.py`).
- **Engagement critic** - pure-logic reach gate on every draft (`engagement.py`).
- **Variant-and-pick** - draft N candidates, keep the best by voice+engagement
  score (`agents/viral.py:draft_best_of_linkedin`, `ranking.py:pick_best`).
- **Posts ledger** - one store behind everything (`posts_ledger.py`,
  `memory/posts.json`).
- **Approval queue** - drafts wait for a human; `python review.py list|approve|reject`.
- **Scheduled reaction cycle** - `run_cycle.py`: Scout -> rank -> draft -> queue.
  Schedule it (Task Scheduler / cron) to make the system run on its own.
- **Brand-safety gate** - `safety.py` holds sensitive topics for a human instead
  of auto-posting.
- **De-dup + cadence** - `posting_policy.py` blocks near-duplicate topics and
  caps posts/day + spacing.
- **Ranking with learning** - `ranking.py` orders topics by relevance x novelty x
  learned pillar performance.
- **Performance loop** - `linkedin_metrics.py` pulls real reactions/comments back
  into the ledger; `analytics.py` turns them into per-pillar multipliers that
  feed ranking.
- **First-comment link strategy** - `linkedin_publisher.post_text(first_comment=)`
  keeps external links out of the post body for reach.
- **Tests + CI** - `test_agents.py`, `test_system.py`, GitHub Actions.

## Next (not yet built)

- **Timing** - post at high-engagement hours instead of on-cycle.
- **Real Streamlit review UI** - approve/reject from a screen instead of the CLI.
- **Comment/DM follow-through** - the reach multiplier is replying fast to early
  comments; not automated yet.
- **Native video pipeline** - reposting *links* under-distributes vs native
  video; decide between an owned/licensed native-upload path or generating
  original short clips.
- **Shared infra package** - `gemini_client` / `guardrails` / `engagement` /
  ledger / policy are duplicated across the two repos; extract a shared package
  or add a sync check so a fix in one does not drift.

## How the pieces connect

```
Scout (hot topics)
  -> ranking.rank_topics  (relevance x novelty x learned performance; drops unsafe/dupes)
  -> viral.draft_best_of_linkedin + draft_note   (voice + engagement gates, best of N)
  -> posts_ledger (status "queued")              <- run_cycle.py does the above unattended
  -> review.py approve  -> linkedin_publisher    (honors LINKEDIN_DRY_RUN)
  -> linkedin_metrics.sync_ledger -> analytics   (feeds performance back into ranking)
```
