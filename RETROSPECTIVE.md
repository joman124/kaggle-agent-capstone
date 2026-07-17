# Retrospective — What Built This Project, and What Would Have Caught Its Bugs Sooner

A reanalysis of the After Work Social Presence Agent build (Steps 1-9,
March-July 2026), answering three questions: what kind of thinking produced
this quality of project, what planning approach led to it, and what
verification steps would have caught the issues before they appeared.

The evidence base is the repo itself: `STATUS.md` (which recorded every bug
with its full diagnosis chain), the commit log (which shows three revised
root-cause theories committed in sequence during the June 25 quota saga),
and `BUILD_PLAN.md` vs. what actually shipped.

---

## 1. The thinking that produced the quality

Five habits show up consistently, and they account for most of what went
right.

### Separate deterministic logic from LLM calls — the single biggest decision

The Strategist, the Analyst, and the Orchestrator's `route()` contain zero
Gemini calls. That was deliberate, and it paid off three ways:

- They were fully verifiable in a sandbox with no API key, no installed SDK,
  and no cost. Every one of their behaviors listed in STATUS.md ("empty
  history produces all 5 pillars exactly once", "all 6 routing cases
  classify correctly") was tested the day it was written.
- They never participated in the quota saga. When the API was down for a
  day, half the system was still provably correct.
- The parts that DO call Gemini (Scout, Writer, Substack Specialist, judge)
  all funnel through one client (`gemini_client.generate()`) and one loop
  (`guardrails.draft_with_guardrails()`), so every API-side fix — retry,
  pacing, `[QUOTA]` messaging, the `None`-text guard, `disable_thinking` —
  was made once and inherited everywhere.

The generalizable rule: an LLM call is a liability (cost, latency, quota,
nondeterminism). Keep the liability surface as small and as centralized as
possible, and make everything around it pure functions.

### Treat documentation as system memory

The project is a memory architecture (agents reading/writing `memory/`
JSON), and the build process mirrored it: `STATUS.md` was the build's own
`content_history.json`. It carried state across chat sessions with
sections that map directly to agent-memory concepts — "Known gotchas (do
not relearn these)", "Open decisions", "Resolved decisions". A new session
could resume without re-deriving anything, and (critically) without
re-learning the encoding crash or the SDK deprecation the hard way.

### Label verification honestly

STATUS.md consistently distinguished "control flow verified by stubbing
`gemini_client.generate`" from "verified end to end against the real key",
and tracked the unverified remainder as explicit caveats until July 5,
when a real full-pipeline run cleared them by name. Most projects conflate
these two states; keeping them separate is why the project always knew
exactly what it did not know. (Section 3 covers the cost of how LATE the
real-key runs happened — but the bookkeeping itself was right.)

### Build for the actual user, not the developer

John reviews from a docx, so output goes to `LinkedIn Posts.docx`, not the
console. Errors exit with plain-English messages naming the fix, not
tracebacks. The weekly run is a double-clickable .bat with Task Scheduler
setup steps written for someone who has never opened Task Scheduler, and it
writes a one-line `[OK]`/`[FAILED]` status file because "read the log" is
not a real instruction for this user. Every step ended with a "run this /
expect this" instruction. None of this is architecturally interesting, and
all of it is why the system actually got used.

### Re-diagnose in public instead of defending a theory

The June 25 quota saga produced three committed, mutually contradicting
diagnoses (pacing bug -> per-model daily cap -> wrong Cloud project ->
actually: prepaid credits depleted). Each revision was committed with a
corrected message rather than quietly amended, and the final lesson was
written down where it changes future behavior: "Google's SDK error text is
frequently already specific and correct — read it first." The willingness
to say "the previous commit's theory was wrong" is what let the saga end
in one day instead of a week.

## 2. The planning approach that led here

- **Rubric-first decomposition.** `CAPSTONE_REQUIREMENTS.md` was written
  before the code, and the 12-step `BUILD_PLAN.md` maps each step to a
  scored course concept. Nothing was built that the rubric would not
  reward; the one unplanned agent (Substack Specialist) was added because
  the real workflow needed it, and it strengthened the pitch rather than
  diluting it.
- **Every step independently testable, sequenced outward.** "Build
  outward; do not over-polish Step 1" is in the plan verbatim. The system
  reached a full working skeleton (Steps 1-8) before any polish (UI,
  writeup, video), which meant the deadline crunch hit polish, not core
  function.
- **Specification as data before agents.** The voice was specified as a
  two-layer artifact (`VOICE_SYSTEM_PROMPT` positive target,
  `ANTI_AI_TELL_PROMPT` negative target, plus banned phrases and reference
  passages) before any agent consumed it. Because the spec was data, every
  later agent inherited it for free, and voice fixes (the antithesis rule)
  were one-place edits.
- **Defer decisions explicitly, not implicitly.** Auto-publish was
  considered, researched (no Substack API; LinkedIn needs an approved app),
  and deliberately deferred with the reasoning recorded — instead of being
  half-built. Open questions lived in a tracked "Open decisions" list until
  they were resolved, and the resolution was recorded with its rationale.
- **Interrogate the request before implementing it.** When John asked to
  run the weekly batch 4x/week, the response was not a cron change — it
  was noticing that (a) the real goal was volume, not frequency, and (b) a
  frequency change would have been a no-op anyway because nothing wrote
  back to content history. The right fix (7-day cadence) and a latent
  design gap both came out of refusing to take the request literally.

## 3. The verification steps that would have caught the issues earlier

Every significant bug in this project maps to a verification step that was
missing at the time and, in most cases, was added immediately after. This
is the checklist the next project should start with on day one.

### One real API call per step ("live smoke test" rule)

**What happened:** the dev sandbox had no API key and no `google-genai`
install, so real-API verification bunched up: stubs proved control flow in
June, but the first true end-to-end run happened July 5 — one day before
the deadline. Three real bugs were hiding in that gap and all surfaced at
the worst time: the `response.text is None` crash, the
thinking-model-plus-grounding empty response (finish_reason=STOP, all
thought parts, no answer), and the judge's real-JSON-parseability question.
Stubs cannot catch any of these, because they are facts about the live
API's behavior, not about the code's logic.

**The rule:** every step that adds or changes an LLM call gets one cheap
real call on the target machine before the step is marked done. Stub tests
prove your logic; one live call proves the API behaves the way your stubs
assume. Neither substitutes for the other.

### Adversarial fixtures at guardrail creation, not after the leak

**What happened:** "it's not X, it's Y" antithesis leaked into drafts for
weeks because `NEGATIVE_PARALLELISM_FLAGS` were advisory substrings — they
flagged but never failed, so the revise loop was never forced to fix the
pattern. The fix (June 27) came with exactly the test harness that should
have existed on day one: 7 known-bad tells (all must fail), 5
legitimate-negation controls (all must pass), and the 3 reference passages
(all must pass).

**The rule:** a guardrail without a known-bad fixture that it demonstrably
rejects is untested, and a "flag for review" severity is a decision to let
the pattern through. For every rule, keep a small fixture set of
must-catch and must-not-catch examples and run it when the rule changes.

### Verify the failure path of anything unattended, before scheduling it

**What happened:** a full week of drafts silently failed to generate.
`run_weekly.bat` swallowed exit codes, so Task Scheduler reported success
and nothing told John anything was wrong. The system's failure mode was
indistinguishable from its idle state.

**The rule:** before scheduling any unattended job, break it on purpose
(wrong key, no network) and confirm a human would find out. The question
to ask at design time is not "does it work?" but "how does John learn it
didn't?" The eventual fix — a one-line `[OK]`/`[FAILED]` status file plus
real exit codes — is 15 minutes of work that would have saved a week.

### Every memory file needs a writer (close the loop on paper first)

**What happened:** `content_history.json` had readers (Strategist's
rolling 30-day balance) but no writer for the entire build — nothing
recorded that a post actually went out, so every weekly plan started from
zero and re-running a week produced near-identical output. The gap was
noticed in late June and not closed until July 5 (`publish_log.py` and the
"Mark as published" button).

**The rule:** at design time, audit every state file with two questions —
who writes this, and when? A learning loop where the "learning" input is
never written is decoration. (`engagement_data.json` still fails this
audit today: the Analyst reads it, nothing feeds it. That is the next
loop to close.)

### Count the API calls before running the pipeline on paid credits

**What happened twice:** (1) every Substack day paid for two full pro-tier
guardrail loops because the throwaway LinkedIn seed post was gated as if
John would ever see it — pure waste, roughly double the cost of every
essay; (2) the June 25 debugging session itself burned the entire $10
prepaid balance, partly because each failed retry-cycle still cost money.

**The rule:** before running a multi-agent pipeline against a paid key,
write down the call count per run (calls per attempt x max attempts x
items x agents) and check which calls produce output a human actually
sees. Any gated call whose output is discarded is waste by definition. And
budget the debugging itself — retries on a broken config spend real money.

### Read the provider's raw error before theorizing

**What happened:** the quota saga went through pacing-bug, per-model-cap,
and wrong-project theories while Google's raw error text said, plainly,
"Your prepayment credits are depleted." Two real secondary bugs were found
along the way (dotenv not overriding a stale env var; a key from the wrong
Cloud project), but the primary diagnosis was available in the first
error body.

**The rule:** surface the provider's raw error text first, verbatim, in
every error handler — then add interpretation as a fallback. And after any
credential swap, print a fingerprint of what actually loaded (the last 4
chars of the key is how the stale-env-var bug was caught).

### Enforce environment constraints mechanically, not by memory

**What happened:** Windows saved a file in a non-UTF-8 encoding and Python
crashed on an em-dash. The rule "pure ASCII in every .py file" has been
carried by discipline (a header comment and a CLAUDE.md warning) ever
since.

**The rule:** a constraint that a human must remember on every save will
eventually be forgotten; a one-line check (`open(f, encoding='ascii')`
sweep as a pre-commit or in `check_setup.py`) makes it structural. The
same applies to the SDK-deprecation trap: `check_setup.py` — verify the
environment before debugging the code — was the right idea and should have
been the first file written, not a response to the first failure.

### Never dot-chain into an optional API field

**What happened:** `response.text.strip()` crashed a scheduled run because
`.text` is `None` when a candidate is blocked or a thinking model spends
its whole budget on reasoning. The fix (`_extract_text()` guarding None,
walking parts, skipping `thought` parts, and a diagnostic `[EMPTY]` error
that dumps the response structure) is the pattern to start with.

**The rule:** treat every field of a provider response as optional until
the SDK's types say otherwise, and make the empty case produce a
diagnosis, not a traceback. Fail fast on deterministic emptiness instead
of retrying — retries on a non-blip cost money and hide the cause.

---

## The one-paragraph version

The quality came from centralizing the LLM liability surface, keeping
everything else deterministic and testable, specifying voice as data
before building agents, writing state down (STATUS.md) the way the system
itself writes memory, and building relentlessly for the real user. The
plan that produced it was rubric-first, decomposed into independently
testable steps, built outward, with decisions deferred explicitly. And
every bug that got through maps to one missing check: one live API call
per step, known-bad fixtures for every guardrail, an intentionally-broken
dry run for every scheduled job, a writer for every memory file, a call
count before every paid run, the raw error before the theory, and a
mechanical check for every environment constraint. None of those checks
takes more than half an hour; together they would have absorbed
essentially every incident in the log.
