# Build Plan — After Work Social Presence Agent

12 steps, sequenced so each is independently testable. Step 1 is done.
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

## Phase 2 — Multi-agent

**Step 2: Refactor into a package.** [DONE] Shared code moved into `agents/`
and `guardrails.py`. `step1_writer.py` logic promoted into `agents/writer.py`
and the original file retired. Writer reads its model from
`GEMINI_WRITER_MODEL` (defaults to a `-pro` model), separate from
`GEMINI_MODEL` which other agents will use.

[TODO below]

**Step 3: Scout agent.** [DONE] `agents/scout.py`. Gemini + Google Search
grounding via `types.Tool(google_search=types.GoogleSearch())`. Input:
optional topic (CLI arg). Output: JSON array of 3-5 topics (headline, source,
relevance_score, suggested_angle, suggested_pillar, suggested_platform). Uses
`GEMINI_MODEL` (Flash), not the Writer's pro model. Shares the new
`gemini_client.generate()` retry/error wrapper with the Writer. Test by
running it with a real API key: `python -m agents.scout` for trending topics,
or `python -m agents.scout "AI layoffs"` to focus the search.

**Step 4: Strategist agent.** [DONE] `agents/strategist.py` + `memory/` JSON
(`content_history.json`, `pillar_tracker.json`, `calendar.json`, all seeded).
Pure logic, no Gemini calls. Reads content history, computes a rolling
30-day pillar distribution, optionally consumes a Scout briefing, and writes
a 5-day plan (pillar + platform per day) to `memory/calendar.json`. Platform
follows a fixed cadence pattern (3 LinkedIn : 2 Substack) regardless of what
Scout suggests, so Strategist keeps control of platform balance. Verified:
with empty history, `plan_week()` assigns each of the 5 pillars exactly once
with no repeats; with a mock Scout briefing, a matching day's pillar picks
up that topic's angle and headline.

**Step 5: Orchestrator.** `agents/orchestrator.py`. Routes natural-language
requests to agents. Wire Scout -> Strategist -> Writer for "what should I
publish this week?" Test the full pipeline end to end.

## Phase 3 — Quality & memory [TODO]

**Step 6: Full guardrails.** `guardrails.py`. Promote the first-pass checks and
add LLM-as-a-judge voice-consistency scoring against `REFERENCE_PASSAGES`
(0-10; reject < 7) and a tone check (reject promotional/preachy/generic). Writer
revises and re-checks up to 3 times. Test: feed deliberately off-voice content,
confirm rejection + revision.

**Step 7: Analyst agent.** `agents/analyst.py` + `memory/engagement_data.json`.
Ingest metrics, compute per-pillar/platform/format performance, compare to
targets, output recommendations + weekly summary. Test with mock data.

**Step 8: Observability.** Structured logging of every agent decision (agent,
inputs, decision, scores). This is a Day 4/5 talking point. Test: a full run
produces a readable trace.

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
