# Status — as of Step 3 (June 24, 2026)

## Done
- Project scaffolded locally on Windows (venv, Python 3.14).
- `google-genai` SDK installed and working. API key valid.
- `check_setup.py` lists 37 available models; using `gemini-2.5-flash`.
- `voice_profile.py` complete: VOICE_SYSTEM_PROMPT, ANTI_AI_TELL_PROMPT,
  BANNED_PHRASES (47, includes "quietly"), NEGATIVE_PARALLELISM_FLAGS,
  REFERENCE_PASSAGES (3, from the preface), PLATFORM_RULES.
- `STYLE_GUIDE.md` complete: Part 1 (John's voice), Part 2 (anti-AI tells).
- **Step 2 refactor done.** `step1_writer.py` is retired; its logic is fully
  folded into `agents/writer.py`. First-pass guardrail checks moved to
  `guardrails.py` (shared, importable by future agents). Writer reads its
  model from `GEMINI_WRITER_MODEL` (defaults to a `-pro` model) instead of
  sharing `GEMINI_MODEL` with other agents, since draft quality matters most
  for the Writer.
- **Step 3 done.** `agents/scout.py`: Gemini + Google Search grounding
  (`types.Tool(google_search=types.GoogleSearch())`), uses `GEMINI_MODEL`
  (Flash). Takes an optional topic argument; returns a JSON array of 3-5
  briefings (headline, source, relevance_score, suggested_angle,
  suggested_pillar, suggested_platform). The retry/error-handling logic
  that used to live only in the Writer was pulled out into
  `gemini_client.generate()` so Scout (and future agents) share it instead
  of duplicating it.
- `.gitignore` added (`.env`, `__pycache__/`, venv dirs) — there was none
  before; a real `.env` had never been committed, but nothing protected one.
- Verified output: a real in-voice post generated and passed guardrails clean
  (under the old `step1_writer.py`; re-verify Writer and Scout under the new
  module layout next time the API key is available).

## Not done
- Steps 4-12 (see BUILD_PLAN.md): Strategist, Orchestrator, full guardrails,
  Analyst, observability, Streamlit UI, deploy, writeup, video, submit.
- No memory/state JSON files yet (Step 4).
- LinkedIn account will be linked by John. Substack page created
  (`drjohnmansoor`) but no real posts published yet on either platform.
- $10 API budget set; usage negligible so far.

## Resolved decisions
- `step1_writer.py` retired, folded into `agents/writer.py`. (was open)
- Writer uses a `-pro` model (`GEMINI_WRITER_MODEL`, default
  `gemini-pro-latest`); other agents use `GEMINI_MODEL` (Flash). (was open)

## Open decisions
- Per-content-type temperature tuning (essays lower, notes higher).

## Known gotchas (do not relearn these)
- Pure ASCII in every .py file (Windows non-UTF-8 save crashes on em-dash/curly).
- `google-genai`, not `google-generativeai`.
- Free tier rate-limits hard; keep retry/backoff and pacing.
- Model name and key in `.env`, never in code.
- If `gemini-pro-latest` is not in your key's available models, run
  `check_setup.py` and set `GEMINI_WRITER_MODEL` in `.env` to a pro model
  that is.
- Scout has not yet been run against a real API key/quota in this session
  (no key available in the dev sandbox). Run `python -m agents.scout` once
  you're back on your machine to confirm the JSON parses cleanly - if
  Gemini wraps the array in markdown fences or adds commentary despite the
  prompt, `_parse_json_array()` should strip fences but will raise a clear
  error showing the raw output if the model still doesn't return valid JSON.

## Immediate next step
Build the Strategist agent (Step 4): `agents/strategist.py` + `memory/`
JSON state. Reads content history and pillar distribution, consumes a
Scout briefing, outputs a balanced 5-day plan.

## Voice feedback still pending
John has not yet given line-level feedback on whether the generated voice fully
matches his. Worth getting before locking the Writer, since the voice profile
propagates to every agent.
