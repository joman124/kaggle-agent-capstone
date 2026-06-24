# -*- coding: utf-8 -*-
"""
The Writer agent: drafts publication-ready social content in John's voice.
Promoted from step1_writer.py during the Step 2 package refactor.

Uses its own model (GEMINI_WRITER_MODEL), separate from GEMINI_MODEL which
other agents (Scout, Strategist, Analyst) will use. Defaults to a -pro model
since draft quality matters most here; override in .env if your key does not
have access to one (run check_setup.py to see what is available).

Run:  python -m agents.writer
"""

import os
import time

from voice_profile import VOICE_SYSTEM_PROMPT, ANTI_AI_TELL_PROMPT
from guardrails import run_guardrails
from gemini_client import generate

# Writer defaults to a pro-tier model regardless of GEMINI_MODEL (used by
# other agents); override with GEMINI_WRITER_MODEL in .env if needed.
MODEL = os.getenv("GEMINI_WRITER_MODEL", "gemini-pro-latest")
SYSTEM_INSTRUCTION = VOICE_SYSTEM_PROMPT + "\n\n" + ANTI_AI_TELL_PROMPT


def write_linkedin_post(topic: str) -> str:
    prompt = f"""Write a LinkedIn text post about this topic:

TOPIC: {topic}

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
    return generate(MODEL, prompt, system_instruction=SYSTEM_INSTRUCTION)


if __name__ == "__main__":
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
        post = write_linkedin_post(topic)
        print(post)
        print()
        g = run_guardrails(post)
        if g["clean"]:
            print("[GUARDRAILS] Clean. No AI tells or banned phrases detected.")
        else:
            print("[GUARDRAILS] Flags:")
            if g["banned_phrases"]:
                print(f"   banned phrases: {g['banned_phrases']}")
            if g["em_dash_count"] > 1:
                print(f"   em dashes: {g['em_dash_count']} (limit 1)")
            if g["has_curly_quotes"]:
                print("   curly quotes present (should be straight)")
            if g["negative_parallelisms"]:
                print(f"   review - possible negative parallelism: {g['negative_parallelisms']}")
        print()
