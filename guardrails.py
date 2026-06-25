# -*- coding: utf-8 -*-
"""
Shared guardrail checks, used by every agent that drafts content. Two layers:
first-pass rule-based checks (string matching), and an LLM-as-a-judge voice/
tone score against REFERENCE_PASSAGES. draft_with_guardrails() ties both into
a single generate-evaluate-revise loop shared by the Writer and the Substack
Specialist.
"""

import json
import os
import time

from voice_profile import BANNED_PHRASES, NEGATIVE_PARALLELISM_FLAGS, REFERENCE_PASSAGES

# Pause between back-to-back Gemini calls so a single draft_with_guardrails()
# run (draft + judge, possibly x3 attempts) does not burst past the free
# tier's per-minute rate limit. Override with GEMINI_CALL_PACING_SECONDS in
# .env if your tier allows faster calls (or needs more room).
CALL_PACING_SECONDS = float(os.getenv("GEMINI_CALL_PACING_SECONDS", "8"))

EM_DASH = chr(0x2014)
CURLY_CHARS = [chr(0x2018), chr(0x2019), chr(0x201C), chr(0x201D)]

JUDGE_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

JUDGE_SYSTEM_INSTRUCTION = (
    "You are a strict editor judging whether a draft sounds like John "
    "Mansoor, PsyD, a clinical psychologist, versus generic AI-written "
    "content. You are given reference passages of John's real writing. "
    "Score the draft against that voice, not against generic 'good writing'.\n\n"
    "Return ONLY a JSON object with exactly these keys:\n"
    '- "voice_score": integer 0-10, how closely the draft matches the '
    "reference voice (sentence rhythm, first-person clinical specificity, "
    "restraint, ending on an unresolved note rather than a neat takeaway)\n"
    '- "tone": exactly one of "authentic", "promotional", "preachy", "generic"\n'
    '- "feedback": one or two sentences on the single biggest thing to fix, '
    "or \"none\" if there is nothing to fix\n\n"
    "No markdown code fences, no preamble - just the raw JSON object."
)


def run_guardrails(text: str, max_em_dashes: int = 1) -> dict:
    """Scan generated text for banned phrases, AI-tell punctuation, and
    possible negative-parallelism rhythm. Returns a dict of findings plus
    a 'clean' flag (only banned phrases, em-dash overuse, and curly quotes
    cause a fail; parallelism is flagged for review, not auto-rejected).
    max_em_dashes defaults to the LinkedIn rule; pass a platform's own
    PLATFORM_RULES[...]['max_em_dashes'] for other formats (e.g. essays
    allow more)."""
    lowered = text.lower()
    banned_hits = [p for p in BANNED_PHRASES if p in lowered]
    parallelism_hits = [p for p in NEGATIVE_PARALLELISM_FLAGS if p in lowered]
    em_dash_count = text.count(EM_DASH)
    curly = any(ch in text for ch in CURLY_CHARS)
    return {
        "banned_phrases": banned_hits,
        "negative_parallelisms": parallelism_hits,
        "em_dash_count": em_dash_count,
        "has_curly_quotes": curly,
        "clean": not banned_hits and em_dash_count <= max_em_dashes and not curly,
    }


def _parse_json_object(raw: str) -> dict:
    """Strip markdown fences if the model added them anyway, then parse.
    Fails with the raw output shown rather than a bare JSONDecodeError."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise SystemExit(
            "\n[GUARDRAILS] Judge did not return valid JSON. Raw output:\n" + raw[:800]
        )
    if not isinstance(data, dict):
        raise SystemExit(f"\n[GUARDRAILS] Expected a JSON object, got: {type(data)}")
    return data


def judge_voice(text: str, model: str = None) -> dict:
    """Ask Gemini to score a draft's voice/tone against REFERENCE_PASSAGES.
    Returns {"voice_score": int 0-10, "tone": str, "feedback": str}."""
    from gemini_client import generate

    references = "\n\n".join(f"- {p}" for p in REFERENCE_PASSAGES)
    prompt = f"""REFERENCE PASSAGES (John's real writing):
{references}

DRAFT TO SCORE:
{text}

Score the draft against the reference voice above."""
    raw = generate(model or JUDGE_MODEL, prompt, system_instruction=JUDGE_SYSTEM_INSTRUCTION)
    return _parse_json_object(raw)


def evaluate(text: str, max_em_dashes: int = 1, min_voice_score: int = 7,
             model: str = None) -> dict:
    """Run both guardrail layers and decide pass/fail. Returns the combined
    findings plus 'passed' and a human-readable 'feedback' string describing
    whatever failed, so a caller can feed it back into the next draft attempt."""
    first_pass = run_guardrails(text, max_em_dashes=max_em_dashes)
    judged = judge_voice(text, model=model)
    voice_score = judged.get("voice_score", 0)
    tone = judged.get("tone", "generic")

    passed = first_pass["clean"] and voice_score >= min_voice_score and tone == "authentic"

    problems = []
    if first_pass["banned_phrases"]:
        problems.append(f"remove these banned phrases: {first_pass['banned_phrases']}")
    if first_pass["em_dash_count"] > max_em_dashes:
        problems.append(
            f"too many em dashes ({first_pass['em_dash_count']}, limit {max_em_dashes})"
        )
    if first_pass["has_curly_quotes"]:
        problems.append("uses curly quotes, must be straight quotes")
    if voice_score < min_voice_score:
        problems.append(f"voice score {voice_score}/10 too low: {judged.get('feedback', 'none')}")
    if tone != "authentic":
        problems.append(f"tone read as '{tone}', not authentic")

    return {
        "first_pass": first_pass,
        "voice_score": voice_score,
        "tone": tone,
        "judge_feedback": judged.get("feedback", "none"),
        "passed": passed,
        "feedback": "; ".join(problems) if problems else "none",
    }


def draft_with_guardrails(model: str, build_prompt, system_instruction: str,
                           max_em_dashes: int = 1, max_attempts: int = 3,
                           min_voice_score: int = 7, agent: str = "writer") -> dict:
    """Shared generate-evaluate-revise loop. build_prompt(feedback) returns
    the prompt for one attempt (feedback is None on the first attempt, then
    the previous attempt's failure feedback string). Logs every attempt via
    observability.log_decision(). Stops on the first pass or after
    max_attempts, returning the last attempt either way."""
    from gemini_client import generate
    from observability import log_decision

    feedback = None
    history = []
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            time.sleep(CALL_PACING_SECONDS)
        prompt = build_prompt(feedback)
        text = generate(model, prompt, system_instruction=system_instruction)
        time.sleep(CALL_PACING_SECONDS)  # draft call, then the judge call below
        result = evaluate(text, max_em_dashes=max_em_dashes, min_voice_score=min_voice_score)

        log_decision(
            agent=agent,
            action="draft_attempt",
            inputs={"attempt": attempt, "max_attempts": max_attempts},
            decision={"passed": result["passed"], "feedback": result["feedback"]},
            scores={"voice_score": result["voice_score"], "tone": result["tone"]},
        )

        history.append({"text": text, "evaluation": result})
        feedback = result["feedback"]
        if result["passed"]:
            break

    last = history[-1]
    return {
        "text": last["text"],
        "attempts": len(history),
        "evaluation": last["evaluation"],
        "history": history,
    }
