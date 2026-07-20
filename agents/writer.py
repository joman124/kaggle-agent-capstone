# -*- coding: utf-8 -*-
"""
The Writer agent: drafts publication-ready social content in John's voice.
Promoted from step1_writer.py during the Step 2 package refactor.

Uses its own model (GEMINI_WRITER_MODEL), separate from GEMINI_MODEL which
other agents (Scout, Strategist, Analyst) will use. Defaults to a -pro model
since draft quality matters most here; override in .env if your key does not
have access to one (run check_setup.py to see what is available).

Step 6: drafting now runs through guardrails.draft_with_guardrails(), which
generates, scores (first-pass rule checks + LLM-as-judge voice/tone), and
re-drafts with the judge's feedback up to 3 times before giving up.

Run:  python -m agents.writer
"""

import os
import time

from voice_profile import VOICE_SYSTEM_PROMPT, ANTI_AI_TELL_PROMPT, PLATFORM_RULES
from guardrails import draft_with_guardrails

# Writer defaults to a pro-tier model regardless of GEMINI_MODEL (used by
# other agents); override with GEMINI_WRITER_MODEL in .env if needed.
MODEL = os.getenv("GEMINI_WRITER_MODEL", "gemini-2.5-pro")
SYSTEM_INSTRUCTION = VOICE_SYSTEM_PROMPT + "\n\n" + ANTI_AI_TELL_PROMPT
LINKEDIN_DOC = "LinkedIn Posts.docx"
LINKEDIN_RULES = PLATFORM_RULES["linkedin_text_post"]


def _build_linkedin_prompt(topic: str, feedback: str = None) -> str:
    revision_note = (
        f"\nA previous draft was rejected. Fix this before writing: {feedback}\n"
        if feedback else ""
    )
    return f"""Write a LinkedIn text post about this topic:

TOPIC: {topic}
{revision_note}
Find a fresh angle. Do not default to the most obvious patient or scenario;
vary the person, the setting, and the specific detail each time.

Requirements:
- 100 to 300 words
- Open with a specific moment or clinical detail, not an abstraction
- First person
- End on something unresolved or a quiet observation
- Add 3 to 5 relevant hashtags on the last line
- No external links in the body
- No emoji

Write only the post. No preamble, no explanation."""


def generate_seed_post(topic: str) -> str:
    """One ungated Gemini call, no guardrail loop. For callers (the
    Substack Specialist's expand_to_essay) that only need raw seed
    material and never show this text to John directly - the essay it
    feeds into runs its own full draft_with_guardrails() pass, so gating
    this draft too would pay for a second pro-tier revise loop on text
    nobody reads."""
    from gemini_client import generate

    return generate(MODEL, _build_linkedin_prompt(topic),
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=LINKEDIN_RULES["temperature"])


def draft_linkedin_post(topic: str, max_attempts: int = 3) -> dict:
    """Generate-evaluate-revise loop for a LinkedIn post. Returns
    {"text", "attempts", "evaluation", "history"} from draft_with_guardrails."""
    return draft_with_guardrails(
        MODEL,
        build_prompt=lambda feedback: _build_linkedin_prompt(topic, feedback),
        system_instruction=SYSTEM_INSTRUCTION,
        max_em_dashes=LINKEDIN_RULES["max_em_dashes"],
        max_attempts=max_attempts,
        agent="writer",
        temperature=LINKEDIN_RULES["temperature"],
    )


def write_linkedin_post(topic: str) -> str:
    """Thin wrapper kept for callers (e.g. the Orchestrator) that only want
    the final text, not the full evaluation history."""
    return draft_linkedin_post(topic)["text"]


if __name__ == "__main__":
    from doc_output import append_to_doc

    print(f"Using model: {MODEL}\n")
    test_topics = [
        "A patient who felt embarrassed to grieve a job he lost to an AI pipeline",
        "Why the financial loss of a job is survivable but the identity loss breaks people",
        "My brother started talking to ChatGPT more than to me, and I'm a psychologist",
    ]

    for i, topic in enumerate(test_topics, 1):
        print("=" * 70)
        print(f"TEST {i}: {topic}")
        print("=" * 70)
        # Free-tier allows only a few requests per minute; pause between calls.
        if i > 1:
            time.sleep(20)
        result = draft_linkedin_post(topic)
        append_to_doc(LINKEDIN_DOC, topic, result["text"])
        print(f"[SAVED] Appended to '{LINKEDIN_DOC}' after {result['attempts']} attempt(s)")
        e = result["evaluation"]
        if e["passed"]:
            print(f"[GUARDRAILS] Passed. voice_score={e['voice_score']}/10, tone={e['tone']}")
        else:
            print(f"[GUARDRAILS] Did not pass after {result['attempts']} attempts: {e['feedback']}")
        print()
