# Status — as of handoff to Claude Code (June 23, 2026)

## Done
- Project scaffolded locally on Windows (venv, Python 3.14).
- `google-genai` SDK installed and working. API key valid.
- `check_setup.py` lists 37 available models; using `gemini-2.5-flash`.
- `voice_profile.py` complete: VOICE_SYSTEM_PROMPT, ANTI_AI_TELL_PROMPT,
  BANNED_PHRASES (47, includes "quietly"), NEGATIVE_PARALLELISM_FLAGS,
  REFERENCE_PASSAGES (3, from the preface), PLATFORM_RULES.
- `STYLE_GUIDE.md` complete: Part 1 (John's voice), Part 2 (anti-AI tells).
- `step1_writer.py` working: generates LinkedIn posts in-voice, first-pass
  guardrails, retry-on-503, plain-English error handling, temperature=1.0 with
  a "fresh angle" prompt steer for variation.
- Verified output: a real in-voice post generated and passed guardrails clean.

## Not done
- Steps 2-12 (see BUILD_PLAN.md): refactor to package, Scout, Strategist,
  Orchestrator, full guardrails, Analyst, observability, Streamlit UI, deploy,
  writeup, video, submit.
- No public repo yet (local only).
- No memory/state JSON files yet.
- Substack and LinkedIn accounts not yet live; no real posts published.
- $10 API budget set; usage negligible so far.

## Open decisions
- Whether to keep `step1_writer.py` as a smoke test or fold into `agents/writer.py`.
- Whether the Writer should use a `-pro` model for higher quality while other
  agents use Flash.
- Per-content-type temperature tuning (essays lower, notes higher).

## Known gotchas (do not relearn these)
- Pure ASCII in every .py file (Windows non-UTF-8 save crashes on em-dash/curly).
- `google-genai`, not `google-generativeai`.
- Free tier rate-limits hard; keep retry/backoff and pacing.
- Model name and key in `.env`, never in code.

## Immediate next step
Build the Scout agent (Step 3) — or refactor to a package first (Step 2) if
preferred. Confirm with John before large refactors.

## Voice feedback still pending
John has not yet given line-level feedback on whether the generated voice fully
matches his. Worth getting before locking the Writer, since the voice profile
propagates to every agent.
