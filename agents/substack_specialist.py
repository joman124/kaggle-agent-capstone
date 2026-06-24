# -*- coding: utf-8 -*-
"""
The Substack Specialist agent: expands a LinkedIn post into a long-form
Substack essay. Uses the LinkedIn post as a seed and goes deeper into the
stories, concepts, and arguments it only had room to gesture at, rather
than just padding the same paragraph longer.

Uses the same pro-tier model as the Writer (GEMINI_WRITER_MODEL) since
draft quality matters here too. Saves essays to "Substack Essays.docx" via
doc_output.py instead of printing markdown, since John reviews from the
docx.

Run:  python -m agents.substack_specialist
"""

import os
import time

from voice_profile import VOICE_SYSTEM_PROMPT, ANTI_AI_TELL_PROMPT, PLATFORM_RULES
from guardrails import run_guardrails
from gemini_client import generate
from doc_output import append_to_doc
from agents.writer import write_linkedin_post

# Shares the Writer's pro-tier model since this is also publication-quality
# long-form content, not a quick draft.
MODEL = os.getenv("GEMINI_WRITER_MODEL", "gemini-pro-latest")
SYSTEM_INSTRUCTION = VOICE_SYSTEM_PROMPT + "\n\n" + ANTI_AI_TELL_PROMPT
SUBSTACK_DOC = "Substack Essays.docx"
ESSAY_RULES = PLATFORM_RULES["substack_essay"]


def expand_to_essay(linkedin_post: str, topic: str = None) -> str:
    """Expand a LinkedIn post into a long-form Substack essay."""
    topic_line = f"\nORIGINAL TOPIC: {topic}\n" if topic else ""
    prompt = f"""Expand this LinkedIn post into a long-form Substack essay.
{topic_line}
LINKEDIN POST:
{linkedin_post}

This is not a longer version of the same post. Use it as a seed: keep its
core story and thesis, then go deeper into the specific moments, patients,
and arguments it only had room to gesture at. Add a second example or
counterpoint the LinkedIn post did not have space for. Develop the idea to
its actual conclusion instead of stopping early.

Requirements:
- {ESSAY_RULES['min_words']} to {ESSAY_RULES['max_words']} words
- First person
- Open with a scene or specific clinical detail, not a thesis statement
- No hashtags
- No emoji
- End on something unresolved or a quiet observation, not a neat bow

Write only the essay. No title, no preamble, no explanation."""
    return generate(MODEL, prompt, system_instruction=SYSTEM_INSTRUCTION)


if __name__ == "__main__":
    print(f"Using model: {MODEL}\n")
    seed_topic = "A patient who felt embarrassed to grieve a job he lost to an AI pipeline"

    print("=" * 70)
    print(f"Generating seed LinkedIn post for: {seed_topic}")
    print("=" * 70)
    post = write_linkedin_post(seed_topic)
    print(post)
    print()

    # Free-tier allows only a few requests per minute; pause between calls.
    time.sleep(20)

    print("=" * 70)
    print("Expanding into a Substack essay")
    print("=" * 70)
    essay = expand_to_essay(post, seed_topic)
    g = run_guardrails(essay, max_em_dashes=ESSAY_RULES["max_em_dashes"])
    append_to_doc(SUBSTACK_DOC, seed_topic, essay)
    print(f"[SAVED] Appended to '{SUBSTACK_DOC}'")

    word_count = len(essay.split())
    print(f"[LENGTH] {word_count} words "
          f"(target {ESSAY_RULES['min_words']}-{ESSAY_RULES['max_words']})")

    if g["clean"]:
        print("[GUARDRAILS] Clean. No AI tells or banned phrases detected.")
    else:
        print("[GUARDRAILS] Flags:")
        if g["banned_phrases"]:
            print(f"   banned phrases: {g['banned_phrases']}")
        if g["em_dash_count"] > ESSAY_RULES["max_em_dashes"]:
            print(f"   em dashes: {g['em_dash_count']} (limit {ESSAY_RULES['max_em_dashes']})")
        if g["has_curly_quotes"]:
            print("   curly quotes present (should be straight)")
        if g["negative_parallelisms"]:
            print(f"   review - possible negative parallelism: {g['negative_parallelisms']}")
