# Publishing Handoff -- After Work Social Presence Agent

This file briefs a fresh Claude Code chat on building the flow that takes
an approved draft and actually posts it to LinkedIn and/or Substack. It
exists so that chat does not need you to re-explain context it can read
itself.

## Read first, in this order
1. `CLAUDE.md` -- project orientation, hard technical constraints.
2. `STATUS.md` -- exactly where the system stands right now.
3. `ARCHITECTURE.md` -- the agent pipeline and memory files.
4. This file.

Then say to the new chat: "Read CLAUDE.md, STATUS.md, ARCHITECTURE.md,
then this file, then propose Phase 1 before writing any code."

## Critical framing -- read this before designing anything

Two things already on record in this repo cut against building this as a
silent, fully-automatic pipeline:

- `CAPSTONE_REQUIREMENTS.md` lists "direct-publish APIs" under future
  directions for the writeup -- it is explicitly NOT a required deliverable
  for the Kaggle submission. The submission's actual closing line is "the
  first posts on my Substack were drafted by this system," not "posted by."
- `CLAUDE.md` states the working principle directly: "John reviews and
  posts. The system does everything else." The decision to skip direct
  auto-publish was made deliberately earlier in this project (see
  STATUS.md's "Added" section on `run_weekly.bat`), specifically because
  it would remove the human review step that the whole voice-guardrail
  system exists to gate.

None of this means "don't build it" -- John may have good reasons beyond
the capstone. It means: **the new chat should treat "should this publish
without a human looking at it first" as an open decision to confirm with
John, not an assumption to build around.** See "Decisions to get from
John" below.

## Current state, in one paragraph

Scout finds topics, Strategist plans a 7-day week (5 LinkedIn : 2
Substack, raised from 5 days/3:2 on June 26), Analyst feeds pillar
performance back into Strategist, Writer and Substack Specialist draft
through a shared generate-evaluate-revise loop (`guardrails.py`,
`draft_with_guardrails()`) that scores voice/tone and retries up to 3
times. Everything lands in `LinkedIn Posts.docx` / `Substack Essays.docx`
via `doc_output.py`. The Orchestrator (`agents/orchestrator.py`) routes
natural-language requests across all of it and logs every decision to
`logs/agent_trace.jsonl`. `run_weekly.bat` runs the whole batch unattended
on a schedule, output only, no publishing. None of this writes to
`memory/content_history.json` -- it is seeded empty and stays empty,
because nothing currently marks a draft as actually posted.

## The real gap: drafts have no structured identity

`doc_output.append_to_doc()` only ever writes to the `.docx` files, keyed
by a free-text heading (`f"{topic} -- {date}"`). There is no JSON record
anywhere that says "this exact text, for this date, on this platform, in
this pillar, currently in this state (drafted / approved / published)."
`memory/calendar.json` holds the day's pillar/platform/topic plan but not
the generated text itself.

This means a publish step has nothing reliable to act on yet. Before any
API integration, the new chat's first real task should be:

**Phase 1 -- structured draft store.** Add `memory/drafts.json`: a list of
records like
```json
{
  "id": "2026-06-29-linkedin",
  "date": "2026-06-29",
  "platform": "linkedin",
  "pillar": "Clinical Window",
  "topic": "...",
  "text": "...",
  "status": "drafted"
}
```
Write a record here alongside (not instead of) the existing docx append,
every time the Writer or Substack Specialist produces a final draft. Keep
the docx as-is -- it is how John actually reads drafts today, and that
should not change. `status` moves drafted -> approved -> published as the
new flow's later phases act on it. The moment a publish call succeeds is
also the right moment to finally append to `memory/content_history.json`
(date + pillar, the field Strategist's rolling-window balance has been
missing this whole time) -- this closes a gap that has existed since Step
4 and matters more now that weekly volume is higher.

## Platform realities (do not assume either of these, verify them)

**LinkedIn.** Has a real posting API (Posts API / UGC Posts), but it needs
a registered Developer App, OAuth2, and the `w_member_social` scope --
getting that scope approved for a personal app has historically required
LinkedIn's review and is not guaranteed to be instant. The one-time setup
is an interactive OAuth consent flow to get a refresh token; after that,
posting is a normal authenticated POST. This is real engineering work but
a real, finishable path.

**Substack.** Has no official posting API, full stop. The only ways to
post programmatically are unofficial, cookie-based, ToS-risk methods --
already considered and explicitly rejected once in this project (see
STATUS.md's `run_weekly.bat` note). Do not silently build one of these.
The honest options are: (a) leave Substack posting manual indefinitely and
only automate LinkedIn, or (b) revisit the ToS-risk methods with John's
explicit, informed sign-off on that risk. Default to (a) unless told
otherwise.

## Recommended phased plan

1. **Structured draft store** (above) -- no API calls yet, just data
   modeling. Low risk, immediately useful regardless of what comes next.
2. **LinkedIn publish, behind a manual approval gate.** A small CLI
   command (e.g. `python -m agents.publisher --approve 2026-06-29-linkedin`
   then `--publish 2026-06-29-linkedin`, or combine into one
   `--publish-approved` step) that John runs after reading the docx --
   not something `run_weekly.bat` calls automatically. Get one real post
   live this way before wiring anything further.
3. **Substack** -- revisit only after Phase 2 works and only with John's
   explicit decision on the ToS-risk question above.
4. **UI wiring** -- Step 9 (Streamlit) is not built yet. An "Approve &
   Publish" button there is a natural home for this later, but do not
   block Phases 1-2 on the UI existing first.

## Decisions to get from John before writing publish code

Ask these directly; do not guess:
1. Should publishing ever happen without John looking at the final text
   first, or does every post go through an explicit approve step no
   matter how good the guardrail scores look?
2. For Substack specifically: leave it fully manual, or is John willing to
   accept the ToS risk of an unofficial method?
3. Should `run_weekly.bat`'s unattended schedule ever be allowed to call
   publish, or should it only ever draft (with publishing always a
   separate, manually-triggered step)?

## Constraints that still apply (from CLAUDE.md, unchanged)

- Pure ASCII in every `.py` file; `# -*- coding: utf-8 -*-` header.
- `google-genai`, not `google-generativeai` (not directly relevant to a
  publish step, but applies to anything else touched in the same files).
- No secrets in code. New credentials (LinkedIn client ID/secret/refresh
  token) go in `.env`, documented in `.env.example` with no real values,
  same pattern as `GEMINI_API_KEY`.
- Follow `gemini_client.py`'s existing retry/backoff and plain-English
  error pattern for any new HTTP client code -- do not let a raw API
  traceback reach John.
- Do not change `doc_output.py`'s docx behavior; John's review habit
  depends on it staying exactly as it is.
