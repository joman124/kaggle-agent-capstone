# Build Plan — After Work Social Presence Agent

12 steps, sequenced so each is independently testable. Steps 1-8 are done.
Each step maps to a course concept for the capstone writeup.

## Phase 1 — Foundation [DONE]

**Step 1: Writer agent (single-agent prototype).** DONE.
- `step1_writer.py` (since promoted to `agents/writer.py`) generates
  LinkedIn posts in John's voice.
- Loads `voice_profile.py` (voice + anti-AI-tell layers).
- First-pass guardrails: banned-phrase scan, em-dash count, curly-quote check,
  negative-parallelism flags.
- Retry-with-backoff on 503; plain-English errors on quota/model/auth.
- Model and key read from `.env` (`.env.example` documents the required vars).
- Generated posts are appended to `LinkedIn Posts.docx` (via `doc_output.py`)
  instead of being dumped as console text, since John reviews from the docx.
  Verified working end to end.

## Phase 2 — Multi-agent [DONE]

**Step 2: Refactor into a package.** [DONE] Shared code moved into `agents/`
and `guardrails.py`. `step1_writer.py` logic promoted into `agents/writer.py`
and the original file retired. Writer reads its model from
`ANTHROPIC_WRITER_MODEL` (defaults to a `-pro` model), separate from
`ANTHROPIC_MODEL` which other agents will use.

**Step 3: Scout agent.** [DONE] `agents/scout.py`. Claude + server-side web
search via `WEB_SEARCH_TOOL` from `anthropic_client`. Input:
optional topic (CLI arg). Output: JSON array of 3-5 topics (headline, source,
relevance_score, suggested_angle, suggested_pillar, suggested_platform). Uses
`ANTHROPIC_MODEL`, not the Writer's stronger model. Shares the new
`anthropic_client.generate()` retry/error wrapper with the Writer. Test by
running it with a real API key: `python -m agents.scout` for trending topics,
or `python -m agents.scout "AI layoffs"` to focus the search.

**Step 4: Strategist agent.** [DONE] `agents/strategist.py` + `memory/` JSON
(`content_history.json`, `pillar_tracker.json`, `calendar.json`, all seeded).
Pure logic, no model calls. Reads content history, computes a rolling
30-day pillar distribution, optionally consumes a Scout briefing, and writes
a 5-day plan (pillar + platform per day) to `memory/calendar.json`. Platform
follows a fixed cadence pattern (3 LinkedIn : 2 Substack) regardless of what
Scout suggests, so Strategist keeps control of platform balance. Verified:
with empty history, `plan_week()` assigns each of the 5 pillars exactly once
with no repeats; with a mock Scout briefing, a matching day's pillar picks
up that topic's angle and headline.

**Step 5: Orchestrator.** [DONE] `agents/orchestrator.py`. `route()` classifies
a natural-language request into an intent + topic via deterministic keyword
matching (no model call, fully unit-tested without an API key).
`handle_request()` then runs the matched pipeline: weekly-plan requests wire
Scout -> Strategist -> Writer, and any day the calendar assigns to Substack
also runs through the new Substack Specialist (see Step 5b below); single
LinkedIn-post and trending-topic requests go straight to Writer/Scout; essay
requests go Writer -> Substack Specialist. Verified: all 6 routing test
cases (weekly plan, trending, LinkedIn post + topic extraction, essay +
topic extraction, engagement, unrecognized) classify correctly.

**Step 5b: Substack Specialist agent (added, not in the original 12).**
[DONE] `agents/substack_specialist.py`. Expands a Writer-drafted LinkedIn
post into a long-form Substack essay -- goes deeper into the same stories
and arguments rather than padding the same paragraph. Shares the Writer's
the Writer's model and voice/anti-AI-tell layers; applies the `substack_essay`
entry from `PLATFORM_RULES` (800-1500 words, no hashtags, up to 4 em
dashes). `guardrails.run_guardrails()` gained a `max_em_dashes` parameter
(defaulted to the existing LinkedIn limit of 1) so this agent's essay
em-dash allowance does not require a second guardrail function. Saves to
`Substack Essays.docx`. Like Scout and Writer, needs a real API key to
verify the actual model call end to end; not yet run against one in this
session.

## Phase 3 — Quality & memory [DONE]

**Step 6: Full guardrails.** [DONE] `guardrails.py` gained `judge_voice()`
(LLM-as-a-judge against `REFERENCE_PASSAGES`, using `ANTHROPIC_MODEL`
since this is evaluation, not generation), `evaluate()` (combines first-pass
checks + the judge score into a single pass/fail with a feedback string),
and `draft_with_guardrails()` -- the shared generate-evaluate-revise loop
(up to 3 attempts, judge feedback fed into the next prompt) used by both
`agents/writer.py` (`draft_linkedin_post()`) and
`agents/substack_specialist.py` (`draft_essay()`). `write_linkedin_post()`
and `expand_to_essay()` stay as thin wrappers returning just the final text,
so the Orchestrator's existing calls did not need to change. Verified by
stubbing `anthropic_client.generate` and monkeypatching `guardrails.judge_voice`
to fail twice then pass: confirmed 3 logged attempts, judge feedback
propagated into each successive prompt, and an early stop on the first pass;
a second run where the judge never passes confirmed it stops at
`max_attempts` and returns `passed: False` rather than looping forever.

**Step 7: Analyst agent.** [DONE] `agents/analyst.py` +
`memory/engagement_data.json` (seeded empty). Pure logic, no model calls.
`compute_performance()` aggregates an impressions-weighted engagement rate
per pillar; `compare_to_target()` classifies each against
`DEFAULT_TARGET_RATE` (a 3% placeholder until John has real targets);
`pillar_adjustments()` / `get_pillar_adjustments()` turn that into a
`{pillar: +1/-1/0}` map the Strategist consumes; `weekly_summary()` produces
a human-readable report, now returned by the Orchestrator for
"engagement"-intent requests. Verified with mock data (5 posts across all 5
pillars): overperforming pillars classified "above" -> +1, underperforming
"below" -> -1.

**Step 8: Observability.** [DONE] `observability.py`'s `log_decision()`
appends one JSON object per agent decision to `logs/agent_trace.jsonl`
(agent, action, timestamp, plus whatever inputs/decision/scores the caller
passes). Wired into `guardrails.draft_with_guardrails()` (one line per draft
attempt, with voice score and tone) and `agents/orchestrator.py`'s
`handle_request()` (one line per routing decision). `route()` itself stays
free of logging so it keeps its no-side-effects, fully-unit-tested property.
Verified directly: `log_decision()` writes a valid, parseable JSON line with
the expected fields. `logs/` added to `.gitignore` since the trace is
regenerated every run, like the generated `.docx` files.

## Phase 4 — Polish, deploy, submit [TODO]

**Step 9: Streamlit UI.** `app.py`. Text input for requests; formatted output;
sidebar showing calendar + pillar balance; tab for engagement-data entry and
analytics. Test locally.

**Step 10: Deploy.** Google Cloud Run (or document local-run). Produce the
public project link required by the capstone.

**Step 11: Writeup + video.** Write the Kaggle Writeup (mirror the rubric — see
CAPSTONE_REQUIREMENTS.md). Record the 3-5 minute video (script in
CAPSTONE_REQUIREMENTS.md). By this point John should have real posts published,
so the demo is genuine.

**Step 12: Submit** before July 6, 2026, 11:59 PM PT. Public codebase + writeup
+ video + project link.

## Guidance

- Build outward; do not over-polish Step 1.
- After each step, give John a one-line "run this / expect this" instruction.
- Keep every file pure ASCII. Keep secrets in `.env`.
