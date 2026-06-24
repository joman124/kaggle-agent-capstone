# Status — as of Step 5 (June 24, 2026)

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
- `.env.example` added, documenting `GEMINI_API_KEY`, `GEMINI_MODEL`, and
  `GEMINI_WRITER_MODEL` with no real values. This does not give Claude a
  working key in the dev sandbox; Scout and Writer still need John's real
  `.env` to verify their actual Gemini calls.
- Writer now saves posts via `doc_output.py` (`append_to_doc()`) into
  `LinkedIn Posts.docx` instead of printing markdown, since John reviews
  from the docx. Creates the doc with a title heading on first run, appends
  a dated H2 section per post after that. Verified in an isolated venv
  (create + two appends, no overwrite). `*.docx` is gitignored.
- **Step 4 done.** `agents/strategist.py`: pure logic, no Gemini calls.
  Reads `memory/content_history.json`, computes a rolling 30-day pillar
  distribution, writes it to `memory/pillar_tracker.json`, ranks pillars
  least-used-first, applies a fixed platform cadence (3 LinkedIn :
  2 Substack per 5-day plan, deliberately not overridden by Scout's
  suggested_platform so Strategist keeps platform-balance control),
  optionally matches a Scout briefing topic to each day's pillar, and
  writes the plan to `memory/calendar.json`. Verified locally (no API key
  needed): empty history produces all 5 pillars exactly once with no
  repeats; a mock Scout briefing's matching day picks up that topic's
  angle/headline while platform still follows Strategist's own cadence.
  `memory/` seeded with empty/zeroed JSON and committed.
- **Step 5 done.** `agents/orchestrator.py`: `route()` classifies a
  natural-language request into an intent + topic via deterministic
  keyword matching (no Gemini call) so it is fully unit-tested without an
  API key. `handle_request()` then runs the matched pipeline. Verified:
  all 6 routing cases (weekly plan, trending, LinkedIn post + topic,
  essay + topic, engagement, unrecognized) classify correctly.
- **Added (not in the original 12-step plan): Substack Specialist agent.**
  `agents/substack_specialist.py`. Expands a Writer-drafted LinkedIn post
  into a long-form Substack essay -- goes deeper into the same stories and
  arguments instead of padding the same paragraph. Shares the Writer's
  pro-tier model and voice/anti-AI-tell layers; applies the `substack_essay`
  entry from `PLATFORM_RULES` (800-1500 words, no hashtags, up to 4 em
  dashes). Saves to `Substack Essays.docx`. The Orchestrator's weekly-plan
  pipeline runs every Substack-assigned day through it; its own "draft an
  essay about X" route also goes Writer -> Substack Specialist directly.
  `guardrails.run_guardrails()` gained a `max_em_dashes` parameter
  (default 1, the LinkedIn rule) so the essay's looser limit did not need
  a second guardrail function.

## Not done
- Steps 6-12 (see BUILD_PLAN.md): full guardrails, Analyst, observability,
  Streamlit UI, deploy, writeup, video, submit.
- `memory/engagement_data.json` not created yet (Step 7).
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
- Same caveat for the Orchestrator's pipelines and the Substack Specialist:
  the routing logic (`route()`) is verified, but the actual Gemini calls
  inside `handle_request()`'s pipelines and `expand_to_essay()` have not
  been run end to end yet. Also, `google-genai` and `python-docx` are not
  installed in the dev sandbox, so only `ast.parse()` syntax checks were
  possible on the new files, not a real import.

## Immediate next step
Run the Orchestrator end to end on your machine with a real `.env`:
`python -m agents.orchestrator "What should I publish this week?"`. That
single command now exercises the whole pipeline (Scout, Strategist,
Writer, Substack Specialist) and is the first time any of Steps 3-5b get
verified against a real key. After that, Step 6: full guardrails
(LLM-as-judge voice scoring, length enforcement, revise-and-recheck loop).

## Voice feedback still pending
John has not yet given line-level feedback on whether the generated voice fully
matches his. Worth getting before locking the Writer, since the voice profile
propagates to every agent.
