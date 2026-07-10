# Status — as of Step 8 (June 24, 2026)

## Added after Step 8: Viral agent (fast hot-topic reactions)
- `agents/viral.py`: turns a hot topic into a short LinkedIn post
  (`PLATFORM_RULES["linkedin_viral"]`, 50-150 words) and a Substack Note
  (`PLATFORM_RULES["substack_note"]`), both through the same
  `draft_with_guardrails()` loop the Writer uses, so viral content still
  passes the voice judge.
- `linkedin_publisher.py`: posts the LinkedIn post via the official Posts API
  as a member. Defaults to DRY RUN (`LINKEDIN_DRY_RUN=true`) so nothing goes
  live until a real token + `LINKEDIN_ACTOR_URN` are set. The Substack Note is
  saved to `Substack Notes.docx` for John to post by hand (Substack has no API).
- Orchestrator routes "go viral about X" / "react to X" to `_handle_viral`.
  Requires the LinkedIn OAuth token described in `.env.example` before live
  posting; runs end to end in dry run without it.

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
  least-used-first, applies a fixed platform cadence (originally 3 LinkedIn :
  2 Substack per 5-day plan -- raised since, see below), deliberately not
  overridden by Scout's suggested_platform so Strategist keeps
  platform-balance control. Optionally matches a Scout briefing topic to
  each day's pillar, and writes the plan to `memory/calendar.json`.
  Verified locally (no API key needed): empty history produces all 5
  pillars exactly once with no repeats; a mock Scout briefing's matching
  day picks up that topic's angle/headline while platform still follows
  Strategist's own cadence. `memory/` seeded with empty/zeroed JSON and
  committed.
- **Cadence raised (June 26).** John asked about running the weekly batch
  4x/week; the actual goal turned out to be more total volume, not more
  frequent scheduling. A scheduling change alone would not have done
  anything, since nothing yet writes back to `memory/content_history.json`
  after a real post goes out (Strategist's rolling-window balance has no
  way to see what was actually published, so re-running the same week's
  batch produces near-identical output -- see "Open decisions" below).
  The real fix was in `agents/strategist.py`: `PLATFORM_PATTERN` went from
  5 days (3 LinkedIn : 2 Substack) to 7 days (5 LinkedIn : 2 Substack), and
  `plan_week()`'s `num_days` default went from 5 to 7 to match. Substack
  was deliberately held at 2/week rather than also increased -- essays are
  long-form and the most expensive thing for John to review per item, so
  the added volume went into LinkedIn, which is cheap to draft and quick
  to review. The Orchestrator needed no change: `_handle_weekly_plan()`
  calls `plan_week()` with no explicit `num_days`, so the new default
  propagates automatically. Verified locally: empty history now produces
  exactly 5 linkedin + 2 substack across 7 days. Note: this also means
  roughly 40% more Gemini calls per weekly run (7 days of drafting instead
  of 5, each with up to 3 revise attempts) - watch the prepaid balance at
  https://ai.studio/projects more closely than before, given the June 25
  depletion.
- **Credit-usage fix (June 26), found while answering "how do I minimize
  credits."** Every Substack day was paying for two full pro-tier
  draft_with_guardrails() revise loops, not one: `_handle_weekly_plan()`
  and `_handle_essay()` both generated a full LinkedIn-post seed through
  the Writer's complete guardrail loop, then threw that post away (never
  saved to a docx) and fed it into the Substack Specialist's own complete
  guardrail loop for the essay. Only the essay is ever shown to John, so
  gating the seed too was pure waste. Fixed by adding
  `agents/writer.py`'s `generate_seed_post()`: one ungated Gemini call, no
  judge, no revise attempts. Both Orchestrator call sites now use it for
  the throwaway seed and keep the essay's own full guardrail loop as the
  real quality gate. Roughly halves the cost of every Substack day with no
  change to what John actually sees. Verified by stubbing
  `gemini_client.generate`: `generate_seed_post()` makes exactly one call.
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

- **Step 6 done.** `guardrails.py` gained `judge_voice()` (LLM-as-a-judge
  against `REFERENCE_PASSAGES`, scores voice_score 0-10 and tone, on
  `GEMINI_MODEL`/Flash since this is evaluation not generation), `evaluate()`
  (combines first-pass checks + the judge into one pass/fail + feedback
  string), and `draft_with_guardrails()` -- the shared generate-evaluate-
  revise loop (up to 3 attempts, judge feedback fed into the next prompt's
  revision note). `agents/writer.py` and `agents/substack_specialist.py`
  both route their drafting through it now (`draft_linkedin_post()` /
  `draft_essay()`); `write_linkedin_post()` and `expand_to_essay()` stay as
  thin wrappers so the Orchestrator's calls did not need to change.
  Verified by stubbing `gemini_client.generate` and monkeypatching
  `guardrails.judge_voice` to fail twice then pass: 3 logged attempts,
  feedback correctly propagated into each next prompt, early stop on pass;
  a second run where the judge never passes confirmed it stops at
  `max_attempts` with `passed: False` instead of looping forever.
- **Step 7 done.** `agents/analyst.py` + `memory/engagement_data.json`
  (seeded empty). Pure logic, no Gemini calls. Computes an impressions-
  weighted engagement rate per pillar, compares it to a placeholder 3%
  target rate, and turns the comparison into a `{pillar: +1/-1/0}`
  adjustment map the Strategist now consumes (`plan_week()` gained a
  `pillar_adjustments` parameter that shifts the least-used-first ranking
  without overriding the rolling-window balance outright). The
  Orchestrator's "engagement" intent now returns `weekly_summary()` instead
  of the old "Analyst not built yet" message, and its weekly-plan pipeline
  calls `get_pillar_adjustments()` before `plan_week()`. Verified with mock
  data (5 posts, one per pillar): overperforming pillars correctly
  classified "above" -> +1, underperforming "below" -> -1; verified
  separately that `plan_week()` actually moves a +1 pillar to the front of
  the ranking with an otherwise-empty history.
- **Step 8 done.** `observability.py`'s `log_decision()` appends one JSON
  object per agent decision to `logs/agent_trace.jsonl`. Wired into
  `draft_with_guardrails()` (one line per draft attempt, with voice score
  and tone) and into `orchestrator.handle_request()` (one line per routing
  decision, right after `route()` -- which itself stays free of logging so
  it keeps its no-side-effects, fully-unit-tested property). `logs/` added
  to `.gitignore` since the trace regenerates every run. Verified directly:
  `log_decision()` writes one valid, parseable JSON line with the expected
  fields.

## Not done
- Steps 10-12 (see BUILD_PLAN.md): deploy, video, submit. (Step 9 UI done,
  see below; the Kaggle Writeup is drafted in `WRITEUP.md`.)
- **Step 9 DONE (July 5): `app.py` Streamlit UI.** A natural-language request
  box wraps `orchestrator.handle_request()` (shows the routed intent, runs the
  pipeline in a spinner, surfaces `SystemExit` quota/auth messages cleanly
  instead of crashing), plus three read-only tabs that render the system's real
  state with NO API calls -- This Week's Plan (from `memory/calendar.json`),
  Drafts (parsed from the two .docx files), and Agent Trace (from
  `logs/agent_trace.jsonl`, with voice_score/tone columns). The read-only tabs
  are the safe, free, fast path for the video demo. Pure ASCII. Verified: boots
  headless on a port with HTTP 200 and no errors; draft/calendar parsers tested
  against the real files (6 LinkedIn drafts, 3 essays, 7 calendar days). Run
  with `streamlit run app.py`.
- LinkedIn account will be linked by John. Substack page created
  (`drjohnmansoor`) but no real posts published yet on either platform.
- $10 prepaid API budget depleted by the quota-debugging session on
  June 25; needs topping up at https://ai.studio/projects before the next
  real run (see gotchas below for the full story).

## Added (not in the original 12-step plan)
- **Weekly draft generation is now scheduled, not manual.**
  `run_weekly.bat` (project root) activates the venv and runs
  `python -m agents.orchestrator "What should I publish this week?"`,
  appending output to `logs\weekly_run.log` so John can check what
  happened without a terminal open. Set up as a Windows Task Scheduler
  job (Friday afternoon, see setup steps below) so Scout/Strategist/
  Analyst/Writer/Substack Specialist run automatically and drafts are
  waiting in the .docx files for review. This does NOT publish anything
  to LinkedIn or Substack - John still reviews and posts manually, by
  design (see CLAUDE.md: "John reviews and posts. The system does
  everything else."). Direct auto-publish was explicitly considered and
  deferred: Substack has no official posting API (only fragile,
  ToS-risky unofficial methods), and LinkedIn's posting API requires an
  approved developer app - both also bypass the human review step that
  is the whole point of the voice-guardrail system, so this needs a
  deliberate future decision, not a default.

  **One-time Windows Task Scheduler setup** (do this once on John's
  machine):
  1. Press the Windows key, type "Task Scheduler", open it.
  2. In the Actions pane (right side), click "Create Basic Task...".
  3. Name it "After Work Weekly Content Plan", click Next.
  4. Trigger: choose "Weekly", click Next. Set the start date/time (e.g.
     next Friday, 3:00 PM), check "Friday", leave recurrence at every 1
     week, click Next.
  5. Action: choose "Start a program", click Next.
  6. Program/script: Browse to
     `C:\Projects\kaggle-agent-capstone\run_weekly.bat`. Leave
     "Add arguments" and "Start in" blank. Click Next, then Finish.
  7. Optional: right-click the new task in the Task Scheduler list >
     Properties > General tab > check "Run whether user is logged on or
     not" if you want it to run even when you are not logged into
     Windows (it will prompt for your Windows password once to save it).
     If left unchecked, the task only runs while you are logged in,
     which is fine for most setups.
  Each run draws on the prepaid Gemini balance - keep an eye on
  https://ai.studio/projects so a scheduled run does not silently fail
  the same way the manual runs did during the June 25 debugging session.

  **Checking whether a scheduled run worked (added July 5, after a week
  where drafts silently did not generate).** `run_weekly.bat` now writes
  `logs\weekly_last_status.txt` every run: one line, either `[OK] ...
  succeeded ...` or `[FAILED] ... exit code N ...` with the most likely
  cause. Open that file first - it is the fastest way to tell if the last
  run worked without reading the whole `weekly_run.log`. The batch also
  returns the real exit code now, so Task Scheduler's "Last Run Result"
  column reflects success/failure. If a week goes by with no new drafts:
  (1) check `weekly_last_status.txt`; (2) if it says FAILED with a quota/
  prepay message, top up credits at https://ai.studio/projects and rerun;
  (3) if the file is missing or has no line dated that week, the task
  never fired - check Task Scheduler > the task > Last Run Result and the
  History tab (common causes: PC asleep/off at the trigger time, or "Run
  only when user is logged on" while you were not). Reminder: this whole
  job only DRAFTS into the .docx files; it never posts to LinkedIn or
  Substack, so "no posts on my feed" is expected - look in the docx, not
  on the platforms.

## Resolved decisions
- `step1_writer.py` retired, folded into `agents/writer.py`. (was open)
- Writer uses a `-pro` model (`GEMINI_WRITER_MODEL`, default
  `gemini-pro-latest`); other agents use `GEMINI_MODEL` (Flash). (was open)
- **Per-content-type temperature tuning (June 27). (was open)** Each
  `PLATFORM_RULES` entry now carries a `temperature`: essays 0.6 (cooler,
  for control and consistency across 800-1500 words), LinkedIn posts 0.8,
  short notes 0.95 (hotter, to stay punchy and varied). `generate()` takes
  an optional `temperature`; Writer and Substack Specialist pass their
  platform's value through `draft_with_guardrails()`. The voice judge
  always runs at temperature 0.0 (it scores, does not generate, so the
  same draft should not swing pass/fail between runs).
- **Antithesis / "it's not X, it's Y" is now a hard guardrail fail (June
  27). (John flagged it still leaking)** The old `NEGATIVE_PARALLELISM_FLAGS`
  only *flagged* parallelism for review and were plain substrings, so the
  structural reversal slipped through and the revise loop was never forced
  to fix it. Added `voice_profile.ANTITHESIS_PATTERNS` (7 regexes for the
  reversal frames) and `guardrails.find_antithesis()`; any match now fails
  `run_guardrails()` like a banned phrase and feeds an explicit rewrite
  instruction into the next revise attempt. Patterns require the
  reassertion pivot, so John's own trailing negations ("..., not from the
  other side of it") do NOT trip it -- verified against all three
  REFERENCE_PASSAGES (clean) plus 7 known tells (all caught) and 5
  legit-negation controls (all clean). Anti-AI-tell prompt rule 5 was also
  sharpened to name the exact frame.

## Open decisions
- (none currently)

## More resolved decisions
- **"Mark as published" write-back built (July 5). (was open)** The gap:
  nothing ever wrote a "published" event to `memory/content_history.json`,
  so the Strategist's rolling-30-day pillar balance always read an empty
  history and every `plan_week()` started the ranking from zero. Now:
  `publish_log.py` (`mark_published()` / `is_published()`) appends one
  entry per real post in exactly the schema
  `compute_pillar_distribution()` reads (title, ISO date, pillar,
  platform). Idempotent -- re-marking the same draft title does not
  duplicate, so a double-click cannot skew pillar counts; unknown pillars
  raise. The Streamlit Drafts tab (app.py) grew a per-draft "Mark as
  published" button with a pillar selectbox (pre-guessed by matching the
  draft heading back to `memory/calendar.json`; platform comes from which
  docx the draft lives in); published drafts show a "recorded" badge
  instead of the button. Also usable headless:
  `python publish_log.py "<title>" "<pillar>" "<platform>"`. Verified:
  append + idempotency + bad-pillar rejection, and that
  `compute_pillar_distribution()` actually counts the new entry; history
  file restored to `[]` after the test. Workflow: John posts a draft to
  the real platform, then clicks the button -- next week's plan finally
  reacts to what actually went out. (`engagement_data.json` is still
  manual/empty; a paste-in engagement form is a possible follow-up so the
  Analyst gets real numbers too.)

## Known gotchas (do not relearn these)
- Pure ASCII in every .py file (Windows non-UTF-8 save crashes on em-dash/curly).
- `google-genai`, not `google-generativeai`.
- Free tier rate-limits hard; keep retry/backoff and pacing.
- A "[QUOTA]"/429 message can mean two different things and they need
  different fixes. (1) A per-minute throttle from bursting too many calls
  at once - clears in under 60s. The weekly-plan pipeline alone can fire
  dozens of calls (Writer's revise loop x3 attempts x2 calls/attempt, x5
  days, plus Substack expansion), so `gemini_client.generate()` retries
  429/RESOURCE_EXHAUSTED with backoff and `CALL_PACING_SECONDS`
  (guardrails.py, 8s default, override via `GEMINI_CALL_PACING_SECONDS` in
  `.env`) paces calls inside `draft_with_guardrails()` and between
  days/agents in the Orchestrator's `_handle_weekly_plan()` and
  `_handle_essay()`. (2) A real account/project-level daily quota cap.
  Confirmed in testing on John's key: NOT specific to one model - both
  `gemini-pro-latest` and `gemini-flash-latest` hit the identical wall
  (429 persisting through the full 5-attempt, 225s retry budget on each).
  A real per-minute throttle clears in well under 60s, so failing across
  225s rules that out; failing on two different model tiers rules out a
  single model's quota. Most likely cause: the key/project's overall daily
  quota was used up by repeated debugging runs earlier the same day (every
  failed attempt still counts against quota), combined with billing not
  actually being linked/enabled on that key's specific Cloud project (an
  AI Studio prepaid balance is not the same thing as enabled Cloud
  Billing). Diagnostic: if 429 persists after the full retry budget
  regardless of which model is set, it is case (2), not case (1). Fix:
  check real usage at https://ai.dev/rate-limit, confirm Cloud Billing is
  linked AND enabled on that project (not just an AI Studio balance), and
  if quota is genuinely exhausted for the day, wait for the
  reset (around midnight Pacific) and retry a single small call before
  the full weekly plan. The error message in `gemini_client.py` names the
  failing model and walks through all of this instead of guessing
  per-minute or per-model-tier. Root cause this time turned out to be
  simpler than all of the above: the `.env` key belonged to a different,
  unbilled Cloud project than the one billing was actually set up on -
  confirmed via https://ai.dev/rate-limit showing 0 usage with >0 limits
  (which rules out a real quota/billing problem and points at "wrong
  project" instead). Fixed by creating a new key under the correct
  project via "Use existing project" (not "Create API key in new
  project") at https://aistudio.google.com/app/apikey.
- `load_dotenv()` in `check_setup.py` and `gemini_client.py` now passes
  `override=True`. Without it, python-dotenv will NOT overwrite a
  `GEMINI_API_KEY` that is already set as a real Windows environment
  variable (System/User variables, or a leftover `set GEMINI_API_KEY=...`
  from an earlier cmd session) - editing `.env` then silently does
  nothing, and the old key keeps getting used. This bit John directly
  after swapping to a new key: `.env` was updated but `check_setup.py`
  kept reporting the old key's last 4 chars. `override=True` makes `.env`
  the single source of truth, matching the "key lives in .env" rule below.
- **Final root cause of the whole quota saga, found after fixing the two
  bugs above**: it was neither pacing, nor wrong project, nor daily quota.
  Once the correct, billed key was actually loading, Google's raw error
  said plainly: "Your prepayment credits are depleted." This is a Gemini
  API billing mode where a project pays from a prepaid balance (the "$10
  on it" John mentioned) instead of open-ended pay-as-you-go, and that
  balance had simply run out from real usage across this debugging
  session. Fix: add more prepaid credit (or switch the project off prepay
  billing) at https://ai.studio/projects. Lesson for next time: Google's
  SDK error text is frequently already specific and correct - read it
  first before reasoning about per-minute vs per-model vs per-day quota.
  `gemini_client.py`'s `[QUOTA]` message now prints Google's raw text up
  front and only adds the generic per-minute/per-project/per-day checklist
  as a fallback when that text is not already self-explanatory.
- **`response.text` can be `None` -- do not call `.strip()` on it blind
  (bug found July 5, from a real scheduled-run traceback).** The July 3
  scheduled run crashed with `AttributeError: 'NoneType' object has no
  attribute 'strip'` at `gemini_client.generate()`'s `response.text.strip()`,
  inside the Scout call. Gemini returns no text part (so `.text` is None)
  when a candidate is blocked OR when a "thinking" model like
  `gemini-2.5-flash` spends its whole output-token budget on internal
  reasoning before writing an answer (finish_reason=MAX_TOKENS). Fixed:
  `generate()` now goes through `_extract_text()` (guards None, walks
  candidate parts) and, on a genuinely empty response, raises a clear
  `[EMPTY]` SystemExit that names the block_reason / finish_reason and the
  fix, instead of a raw traceback. It fails fast rather than retrying, to
  protect credits (an empty response is usually deterministic, not a blip).
  The next real run answered it: finish_reason=STOP (not MAX_TOKENS), empty
  text, reproducible, with $9.79 credit left -- so neither tokens nor
  billing. That is the thinking-model-plus-grounding trap: gemini-2.5-flash
  is a thinking model, and on the Scout call (Google Search grounding) it
  spent the whole turn on thought parts and stopped with no answer text.
  Fixed (July 5): `generate()` gained `disable_thinking`, which attaches a
  `ThinkingConfig(thinking_budget=0)` (guarded so an older google-genai
  without ThinkingConfig degrades to a no-op instead of crashing); Scout's
  grounded call now passes `disable_thinking=True`. Writer/Substack keep
  thinking, since reasoning helps draft quality there. Also hardened:
  `_extract_text()` now skips `thought` parts (so reasoning is never
  returned as the answer), and the `[EMPTY]` message appends a one-line
  `Response structure:` dump of the candidates/parts so any future empty
  completion is diagnosable straight from the log. If Scout still comes
  back empty after this, that structure line will say whether it is
  thought-only, grounding-metadata-only, or genuinely zero parts.
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
- Same caveat again for Step 6's `judge_voice()` and `draft_with_guardrails()`
  loop: the control flow (retry on fail, feedback propagation, stop on pass
  or at max_attempts, one log line per attempt) was verified by stubbing
  `gemini_client.generate` and monkeypatching `guardrails.judge_voice`
  directly in the dev sandbox, since `google-genai` is not installed there.
  This proves the loop logic is correct; it does not prove the judge prompt
  itself reliably returns parseable JSON or sensible scores from a real
  Gemini call. Run `python -m agents.writer` on your machine and check
  `logs/agent_trace.jsonl` to confirm that against the real model.

## Immediate next step
**DONE (July 5) -- Steps 3-8 now verified end to end against the real key.**
`python -m agents.orchestrator "What should I publish this week?"` ran the
whole pipeline (Scout, Analyst, Strategist, Writer with the revise loop,
Substack Specialist) successfully. `logs/weekly_last_status.txt` reads
`[OK] ... weekly run succeeded`; `logs/agent_trace.jsonl` shows the expected
`route` entry plus one `draft_attempt` per Writer/Substack Specialist draft --
every draft passed the guardrail/judge loop on attempt 1 with voice_score 8-9
and tone "authentic". `memory/calendar.json` is populated with real Scout
topics/headlines, and both `LinkedIn Posts.docx` / `Substack Essays.docx` were
regenerated. This clears the "verified only via stubs" caveats listed above for
Scout, the Orchestrator pipelines, the Substack Specialist, and Step 6's
`judge_voice()`/`draft_with_guardrails()` loop -- they have now all run against
real Gemini calls.

Next: Step 9, Streamlit UI. Still pending: John's line-level voice feedback on
the generated drafts (see "Voice feedback still pending" below) and the
draft-to-post flow (see `PUBLISHING_HANDOFF.md`) -- neither blocks Step 9.

**Separately, a new chat (June 27) is starting on the actual draft-to-post
flow.** See `PUBLISHING_HANDOFF.md` for the full brief -- it covers what
that chat needs to know, the real LinkedIn API vs. Substack-has-no-API
constraint, the missing structured draft store
(`memory/drafts.json`, not built yet), and three decisions it needs from
John before writing any publish code (manual approval gate, Substack's
ToS risk, whether the unattended weekly batch should ever auto-publish).
This is explicitly scoped in `CAPSTONE_REQUIREMENTS.md` as a future
direction for the writeup, not a required deliverable -- it does not block
Steps 9-12 below.

## Voice feedback still pending
John has not yet given line-level feedback on whether the generated voice fully
matches his. Worth getting before locking the Writer, since the voice profile
propagates to every agent.
