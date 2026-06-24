# Status — as of Step 2 refactor (June 24, 2026)

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
  `guardrails.py` (shared, importable by future agents). Writer now reads
  its model from `GEMINI_WRITER_MODEL` (defaults to a `-pro` model) instead
  of sharing `GEMINI_MODEL` with other agents, since draft quality matters
  most for the Writer.
- `.gitignore` added (`.env`, `__pycache__/`, venv dirs) — there was none
  before; a real `.env` had never been committed, but nothing protected one.
- Verified output: a real in-voice post generated and passed guardrails clean
  (under the old `step1_writer.py`; re-verify under `agents/writer.py` next
  time the API key is available).

## Not done
- Steps 3-12 (see BUILD_PLAN.md): Scout, Strategist, Orchestrator, full
  guardrails, Analyst, observability, Streamlit UI, deploy, writeup, video,
  submit.
- No memory/state JSON files yet (Step 4).
- LinkedIn account will be linked by John; Substack page not created yet.
  No real posts published.
- $10 API budget set; usage negligible so far.

## Resolved decisions
- `step1_writer.py` retired, folded into `agents/writer.py`. (was open)
- Writer uses a `-pro` model (`GEMINI_WRITER_MODEL`, default
  `gemini-pro-latest`); other agents will use `GEMINI_MODEL` (Flash) once
  built. (was open)

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

## Immediate next step
Build the Scout agent (Step 3): `agents/scout.py`, Gemini + Google Search
grounding, outputs a JSON briefing of 3-5 trending topics.

## Voice feedback still pending
John has not yet given line-level feedback on whether the generated voice fully
matches his. Worth getting before locking the Writer, since the voice profile
propagates to every agent.
