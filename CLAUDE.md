# CLAUDE.md — After Work Social Presence Agent

This file orients Claude Code to the project. Read it first, then read
`PROJECT_BRIEF.md` and `BUILD_PLAN.md` before writing code.

## What this project is

A multi-agent AI system that researches, plans, drafts, and optimizes social
media content for John Mansoor, PsyD — a clinical psychologist and author of
the book *After Work*. The book is about the psychological cost of AI displacing
human labor. The agent builds John's author platform on Substack and LinkedIn.

John reviews and posts. The system does everything else.

This is also a submission for the Kaggle "AI Agents: Intensive Vibe Coding
Capstone Project" (deadline July 6, 2026). The build must demonstrate specific
course concepts — see `CAPSTONE_REQUIREMENTS.md`.

## Who the user is

John Mansoor, PsyD. Clinical psychologist, business owner. He prompts and
reviews; he is not a developer. Write code that runs cleanly the first time and
explain what to run in plain steps. He is on Windows, Python 3.14, building
locally in a venv, deploying later to GitHub + Kaggle + Cloud Run.

## Critical voice rule

All generated content must sound like John, not like generic AI. There are two
layers, both already built in `voice_profile.py`:

1. `VOICE_SYSTEM_PROMPT` — the positive target (sound like John).
2. `ANTI_AI_TELL_PROMPT` — the negative target (strip machine fingerprints).

The full reference is `STYLE_GUIDE.md`. When in doubt about voice, that file
governs. The banned-phrase list and guardrails enforce it mechanically.

## Hard technical constraints (learned the hard way)

1. **All source files must be pure ASCII.** Windows saved files in a non-UTF-8
   encoding and Python crashed on em-dashes and curly quotes. Never put a raw
   em-dash, curly quote, or other non-ASCII byte in a .py file. Use `chr(0x2014)`
   etc. Put `# -*- coding: utf-8 -*-` at the top of every .py file as a guard.
2. **Use the `google-genai` SDK, not `google-generativeai`.** The latter is
   deprecated. Import as `from google import genai`.
3. **Model name lives in `.env` as `GEMINI_MODEL`.** Currently `gemini-2.5-flash`.
   Never hard-code model names; the user's available models can be listed with
   `check_setup.py`. The Writer agent uses a separate `GEMINI_WRITER_MODEL`
   (defaults to `gemini-pro-latest`) since draft quality matters most there;
   other agents use `GEMINI_MODEL`.
4. **Free tier rate-limits aggressively.** Add retry-with-backoff on 503/500
   ServerError and a pause between rapid calls. Fail with plain-English messages
   on 429 (quota), 404 (bad model), and auth errors — never a raw traceback.
5. **Never put secrets in code.** API key is in `.env`, which is gitignored.

## Current state

Steps 1-5 of 12 are done, plus one agent added beyond the original plan.
The Writer agent (`agents/writer.py`) generates LinkedIn posts in John's
voice, passes first-pass guardrails (`guardrails.py`), and saves them to
`LinkedIn Posts.docx` via `doc_output.py` since John reviews from the
docx, not the console. The Scout agent (`agents/scout.py`) finds trending
topics via Gemini + Google Search grounding and returns a JSON briefing.
The Strategist agent (`agents/strategist.py`) reads `memory/` JSON state,
balances pillar coverage on a rolling 30-day window, applies a fixed
platform cadence, and writes a 5-day plan to `memory/calendar.json` --
pure logic, no Gemini calls. The Substack Specialist agent
(`agents/substack_specialist.py`) expands a Writer-drafted LinkedIn post
into a long-form Substack essay, sharing the Writer's pro-tier model and
voice layers, saved to `Substack Essays.docx`. The Orchestrator
(`agents/orchestrator.py`) routes natural-language requests across all of
the above -- its keyword-based `route()` step has no Gemini call and is
fully unit-tested. All agents share retry/error handling through
`gemini_client.py`. Steps 6-12 (full guardrails, Analyst, observability,
UI, deploy, writeup, video) are not built yet. See `BUILD_PLAN.md` for the
sequence and `STATUS.md` for exactly where things stand.

## Working relationship

John engages directly with critique and makes clear decisions. Honest pushback
is welcomed. Do not pad responses. Build outward — resist over-polishing any
one step. The highest-value next step is verifying the Orchestrator end to
end against a real API key, then Step 6 (full guardrails).
