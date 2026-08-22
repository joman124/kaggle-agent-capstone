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
import re
import time

from voice_profile import (BANNED_PHRASES, NEGATIVE_PARALLELISM_FLAGS,
                           REFERENCE_PASSAGES, ANTITHESIS_PATTERNS)

# Compiled once. Case-insensitive so "It's not..." and "it's not..." both hit.
_ANTITHESIS_RES = [re.compile(p, re.IGNORECASE) for p in ANTITHESIS_PATTERNS]

# Pause between back-to-back model calls. Defaults to 0 now that we are on
# Anthropic: the SDK backs off and retries 429s on its own, so the old 8s
# sleep was pure latency (it existed to stay under Gemini's free-tier
# per-minute burst limit). Set LLM_CALL_PACING_SECONDS in .env to reintroduce
# a pause if a low rate limit ever makes the SDK's own retries insufficient.
CALL_PACING_SECONDS = float(os.getenv("LLM_CALL_PACING_SECONDS", "0"))

EM_DASH = chr(0x2014)
CURLY_CHARS = [chr(0x2018), chr(0x2019), chr(0x201C), chr(0x201D)]

JUDGE_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5")

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


def find_antithesis(text: str) -> list:
    """Return the antithesis / 'it's not X, it's Y' reversal constructions
    found in text (one representative match per pattern). This is the single
    most persistent AI rhythm and John wants it gone, so run_guardrails
    treats any hit as a hard fail -- unlike the softer
    NEGATIVE_PARALLELISM_FLAGS, which only flag for review."""
    hits = []
    for rgx in _ANTITHESIS_RES:
        m = rgx.search(text)
        if m:
            hits.append(" ".join(m.group(0).split()))
    return hits


def find_fragment_triads(text: str, max_words: int = 6, run_length: int = 3) -> list:
    """Return runs of `run_length`+ consecutive sentences of <= max_words
    (john-voice Part 3, sweep 4). Short sentences ARE the voice, so this is a
    soft flag, not a hard fail -- three in a row is the machine rhythm, one or
    two is John. Returns each offending run as a single joined string."""
    # Split on sentence-ending punctuation; keep it simple and dependency-free.
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    triads, run = [], []
    for s in sentences:
        if len(s.split()) <= max_words:
            run.append(s)
            continue
        if len(run) >= run_length:
            triads.append(" ".join(run))
        run = []
    if len(run) >= run_length:
        triads.append(" ".join(run))
    return triads


def run_guardrails(text: str, max_em_dashes: int = 1) -> dict:
    """Scan generated text for banned phrases, antithesis reversals, AI-tell
    punctuation, and possible negative-parallelism rhythm. Returns a dict of
    findings plus a 'clean' flag. Banned phrases, antithesis reversals,
    em-dash overuse, and curly quotes cause a fail; the softer parallelism
    fragments are flagged for review, not auto-rejected. max_em_dashes
    defaults to the LinkedIn rule; pass a platform's own
    PLATFORM_RULES[...]['max_em_dashes'] for other formats (e.g. essays
    allow more)."""
    lowered = text.lower()
    banned_hits = [p for p in BANNED_PHRASES if p in lowered]
    parallelism_hits = [p for p in NEGATIVE_PARALLELISM_FLAGS if p in lowered]
    antithesis_hits = find_antithesis(text)
    fragment_hits = find_fragment_triads(text)
    em_dash_count = text.count(EM_DASH)
    curly = any(ch in text for ch in CURLY_CHARS)
    return {
        "banned_phrases": banned_hits,
        "negative_parallelisms": parallelism_hits,
        "antithesis": antithesis_hits,
        "fragment_triads": fragment_hits,
        "em_dash_count": em_dash_count,
        "has_curly_quotes": curly,
        # fragment_triads is deliberately NOT part of 'clean': the skill says
        # short sentences are the voice and only a run of them is the machine,
        # with real exceptions (dialogue, deliberate hammering). Flag for
        # review; do not burn a redraft cycle on it.
        "clean": (not banned_hits and not antithesis_hits
                  and em_dash_count <= max_em_dashes and not curly),
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
    """Ask Claude to score a draft's voice/tone against REFERENCE_PASSAGES.
    Returns {"voice_score": int 0-10, "tone": str, "feedback": str}."""
    from anthropic_client import generate

    references = "\n\n".join(f"- {p}" for p in REFERENCE_PASSAGES)
    prompt = f"""REFERENCE PASSAGES (John's real writing):
{references}

DRAFT TO SCORE:
{text}

Score the draft against the reference voice above."""
    # Judge runs deterministic: it scores, it does not generate, so a fixed
    # low temperature keeps the same draft from swinging pass/fail run to run.
    raw = generate(model or JUDGE_MODEL, prompt,
                   system_instruction=JUDGE_SYSTEM_INSTRUCTION, temperature=0.0)
    return _parse_json_object(raw)


def evaluate(text: str, max_em_dashes: int = 1, min_voice_score: int = 7,
             model: str = None, extra_checks=None) -> dict:
    """Run both guardrail layers and decide pass/fail. Returns the combined
    findings plus 'passed' and a human-readable 'feedback' string describing
    whatever failed, so a caller can feed it back into the next draft attempt.

    extra_checks is an optional callable(text) -> {"passed", "feedback",
    "score", ...}. It layers an additional, caller-supplied gate on top of the
    voice checks -- the Viral agent passes engagement.check here so a draft must
    also be built for reach, not just be on-voice. Its failure blocks passing
    and its feedback is folded into the returned feedback string; the result is
    attached under the 'extra' key (e.g. for the engagement score)."""
    first_pass = run_guardrails(text, max_em_dashes=max_em_dashes)
    judged = judge_voice(text, model=model)
    voice_score = judged.get("voice_score", 0)
    tone = judged.get("tone", "generic")

    extra = extra_checks(text) if extra_checks else None

    passed = first_pass["clean"] and voice_score >= min_voice_score and tone == "authentic"
    if extra is not None:
        passed = passed and extra.get("passed", True)

    problems = []
    if first_pass["banned_phrases"]:
        problems.append(f"remove these banned phrases: {first_pass['banned_phrases']}")
    if first_pass["antithesis"]:
        problems.append(
            "remove the 'it's not X, it's Y' / 'not just X but Y' antithesis "
            f"construction (found: {first_pass['antithesis']}); state the point "
            "once, plainly, without setting up a negation to reverse"
        )
    if first_pass["em_dash_count"] > max_em_dashes:
        problems.append(
            f"too many em dashes ({first_pass['em_dash_count']}, limit {max_em_dashes})"
        )
    if first_pass["has_curly_quotes"]:
        problems.append("uses curly quotes, must be straight quotes")
    if first_pass["fragment_triads"]:
        # Advisory only -- does not set passed=False (see run_guardrails).
        problems.append(
            "three or more very short sentences in a row reads as machine "
            f"rhythm: {first_pass['fragment_triads'][:1]}; keep the real short "
            "sentences but rewrite verbless filler into one full sentence"
        )
    if voice_score < min_voice_score:
        problems.append(f"voice score {voice_score}/10 too low: {judged.get('feedback', 'none')}")
    if tone != "authentic":
        problems.append(f"tone read as '{tone}', not authentic")
    if extra is not None and not extra.get("passed", True):
        problems.append(f"engagement: {extra.get('feedback', 'weak hook')}")

    return {
        "first_pass": first_pass,
        "voice_score": voice_score,
        "tone": tone,
        "judge_feedback": judged.get("feedback", "none"),
        "extra": extra,
        "passed": passed,
        "feedback": "; ".join(problems) if problems else "none",
    }


def draft_with_guardrails(model: str, build_prompt, system_instruction: str,
                           max_em_dashes: int = 1, max_attempts: int = 3,
                           min_voice_score: int = 7, agent: str = "writer",
                           temperature: float = None, extra_checks=None) -> dict:
    """Shared generate-evaluate-revise loop. build_prompt(feedback) returns
    the prompt for one attempt (feedback is None on the first attempt, then
    the previous attempt's failure feedback string). temperature is the
    per-content-type sampling temperature for the draft calls (the judge
    inside evaluate() always runs deterministic regardless). extra_checks is
    an optional callable(text) -> result dict passed straight to evaluate(); the
    Viral agent uses it to add the pure-logic engagement gate. Logs every
    attempt via observability.log_decision(). Stops on the first pass or
    after max_attempts, returning the last attempt either way."""
    from anthropic_client import generate
    from observability import log_decision

    feedback = None
    history = []
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            time.sleep(CALL_PACING_SECONDS)
        prompt = build_prompt(feedback)
        text = generate(model, prompt, system_instruction=system_instruction,
                        temperature=temperature)
        time.sleep(CALL_PACING_SECONDS)  # draft call, then the judge call below
        result = evaluate(text, max_em_dashes=max_em_dashes,
                          min_voice_score=min_voice_score, extra_checks=extra_checks)

        extra = result.get("extra") or {}
        log_decision(
            agent=agent,
            action="draft_attempt",
            inputs={"attempt": attempt, "max_attempts": max_attempts},
            decision={"passed": result["passed"], "feedback": result["feedback"]},
            scores={"voice_score": result["voice_score"], "tone": result["tone"],
                    "engagement_score": extra.get("score")},
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
