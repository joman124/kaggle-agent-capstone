# Session Handoff -- After Work Social Presence Agent

Snapshot for starting a fresh session. Read `CLAUDE.md` then `STATUS.md`
first; this file is the short version of where things stand as of July 5,
2026, on branch `claude/repo-summary-tasks-rdr5kj`.

## Headline

The content pipeline runs end to end against a real Gemini key. A real
`run_weekly.bat` run succeeded: Scout -> Strategist -> Analyst -> Writer ->
Substack Specialist, drafts saved to `LinkedIn Posts.docx` /
`Substack Essays.docx`. This is the first fully verified run -- Steps 3-8
are no longer stubbed/mocked.

## Done this session (branch `claude/repo-summary-tasks-rdr5kj`)

Commits, newest last:
- `462234f` Raise weekly cadence 5 -> 7 days (5 LinkedIn + 2 Substack).
- `e2a1376` Skip the guardrail loop on throwaway Substack seed posts
  (~halves the Gemini cost of each Substack day; the seed is never shown to
  John, only the essay it feeds is gated).
- `6152af4` Add `PUBLISHING_HANDOFF.md` (brief for the draft-to-post flow).
- `62aae37` Hard-fail the "it's not X, it's Y" antithesis construction and
  add per-content-type temperature (essays 0.6, LinkedIn 0.8, notes 0.95;
  voice judge pinned at 0.0).
- `ccaec36` Make the scheduled run report PASS/FAIL loudly
  (`logs\weekly_last_status.txt` + real exit code) instead of failing
  silently.
- `6bbe9ff` Fix the `AttributeError` crash when Gemini returns a response
  with no text (guard `response.text` being None; report the real cause).
- `8cc01be` Disable "thinking" on Scout's grounded call -- the real cause of
  the empty responses (gemini-2.5-flash is a thinking model and was
  spending the whole grounded turn on thought parts, finish_reason=STOP,
  empty text). Writer/Substack keep thinking for draft quality.
- `8dffd4d` Save drafts to a fallback "(unsaved - original was open)" doc
  when the target docx is locked open in Word, so an unattended run never
  discards drafts that already cost credits.

The week-long "no posts came through" saga is fully resolved. Root causes,
in the order they were peeled back: stale local code on John's machine (the
fixes existed on the branch but he had not pulled), then a None-text crash,
then Scout's thinking-model empty responses, then a docx file lock. All
fixed. It was never a credit/billing problem (confirmed: $9.79 left).

## Still to do

### Immediate
- Nothing blocking. John has confirmed a green run; drafts are in the docx
  files for review and manual posting.

### Capstone deliverables (Kaggle, deadline July 6 2026 11:59pm PT) -- NOT built
1. Step 9: Streamlit UI (`app.py`). The demo is now easy: `run_weekly.bat`
   produces real drafts to show.
2. Step 10: Deploy (Cloud Run) or document local-run.
3. Step 11: Writeup + demo video (see `CAPSTONE_REQUIREMENTS.md` for the
   rubric and the required closing line).
4. Step 12: Submit.

Highest-leverage remaining work for an actual submission: the writeup and a
short demo video, since the pipeline itself is done and demoable.

### Known open items (not blocking the deadline)
- **Publishing flow** (drafts -> live LinkedIn/Substack posts): scoped in
  `PUBLISHING_HANDOFF.md`, not started. Needs 3 decisions from John first
  (manual approval gate? Substack has no official API -- accept ToS risk or
  stay manual? should the unattended scheduler ever auto-publish?). This is
  a future-directions item in `CAPSTONE_REQUIREMENTS.md`, not a required
  deliverable.
- **`memory/content_history.json` is never written.** Nothing logs a
  "published" event, so the Strategist's rolling-30-day pillar balance
  always reads an empty history. Closing this is folded into Phase 1 of the
  publishing flow.
- **Voice feedback pending.** John has not given line-level feedback on
  whether the generated drafts truly match his voice; worth doing before
  locking the Writer, since the voice profile propagates to every agent.
- **Per-content-type temperature values** (0.6/0.8/0.95) are a first guess,
  not tuned against real output yet.
- **Branch not merged.** Everything above lives on
  `claude/repo-summary-tasks-rdr5kj`, not `main`. Merge once the deadline
  crunch passes.

## How to run / check (John's Windows machine)

- Generate a week of drafts: `run_weekly.bat` (or wait for the Friday Task
  Scheduler job). Output goes to `logs\weekly_run.log`.
- Did the last run work? Open `logs\weekly_last_status.txt` -- one line,
  `[OK]` or `[FAILED]` with the likely cause.
- Get the latest code before running: `git pull` on branch
  `claude/repo-summary-tasks-rdr5kj`. (Several past failures were just stale
  local code.)
- Reminder: this system only DRAFTS into the docx files. It does not post to
  LinkedIn or Substack -- "nothing on my feed" is expected; look in the docx.

## Constraints that still apply (from CLAUDE.md)

- Pure ASCII in every `.py` file; `# -*- coding: utf-8 -*-` header.
- `google-genai`, not `google-generativeai`.
- Secrets only in `.env` (gitignored); model names in `.env`, never in code.
- Keep retry/backoff + pacing for the free tier; surface Google's own error
  text before generic quota speculation.
