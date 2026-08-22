# -*- coding: utf-8 -*-
"""
The Substack Specialist agent: expands a LinkedIn post into a long-form
Substack essay. Uses the LinkedIn post as a seed and goes deeper into the
stories, concepts, and arguments it only had room to gesture at, rather
than just padding the same paragraph longer.

Uses the same pro-tier model as the Writer (ANTHROPIC_WRITER_MODEL) since
draft quality matters here too. Saves essays to "Substack Essays.docx" via
doc_output.py instead of printing markdown, since John reviews from the
docx.

Step 6: drafting now runs through guardrails.draft_with_guardrails(), same
generate-evaluate-revise loop as the Writer, using the essay's looser
em-dash allowance from PLATFORM_RULES.

Run:  python -m agents.substack_specialist
"""

import os
import time

from voice_profile import VOICE_SYSTEM_PROMPT, ANTI_AI_TELL_PROMPT, PLATFORM_RULES
from guardrails import draft_with_guardrails
from agents.writer import write_linkedin_post

# Shares the Writer's pro-tier model since this is also publication-quality
# long-form content, not a quick draft.
MODEL = os.getenv("ANTHROPIC_WRITER_MODEL", "claude-opus-5")
SYSTEM_INSTRUCTION = VOICE_SYSTEM_PROMPT + "\n\n" + ANTI_AI_TELL_PROMPT
SUBSTACK_DOC = "Substack Essays.docx"
ESSAY_RULES = PLATFORM_RULES["substack_essay"]


def _build_essay_prompt(linkedin_post: str, topic: str = None, feedback: str = None) -> str:
    topic_line = f"\nORIGINAL TOPIC: {topic}\n" if topic else ""
    revision_note = (
        f"\nA previous draft was rejected. Fix this before writing: {feedback}\n"
        if feedback else ""
    )
    return f"""Expand this LinkedIn post into a long-form Substack essay.
{topic_line}
LINKEDIN POST:
{linkedin_post}
{revision_note}
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


def draft_essay(linkedin_post: str, topic: str = None, max_attempts: int = 3) -> dict:
    """Generate-evaluate-revise loop for a Substack essay. Returns
    {"text", "attempts", "evaluation", "history"} from draft_with_guardrails."""
    return draft_with_guardrails(
        MODEL,
        build_prompt=lambda feedback: _build_essay_prompt(linkedin_post, topic, feedback),
        system_instruction=SYSTEM_INSTRUCTION,
        max_em_dashes=ESSAY_RULES["max_em_dashes"],
        max_attempts=max_attempts,
        agent="substack_specialist",
        temperature=ESSAY_RULES["temperature"],
    )


def expand_to_essay(linkedin_post: str, topic: str = None) -> str:
    """Thin wrapper kept for callers (e.g. the Orchestrator) that only want
    the final text, not the full evaluation history."""
    return draft_essay(linkedin_post, topic)["text"]


if __name__ == "__main__":
    from doc_output import append_to_doc

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
    result = draft_essay(post, seed_topic)
    essay = result["text"]
    append_to_doc(SUBSTACK_DOC, seed_topic, essay)
    print(f"[SAVED] Appended to '{SUBSTACK_DOC}' after {result['attempts']} attempt(s)")

    word_count = len(essay.split())
    print(f"[LENGTH] {word_count} words "
          f"(target {ESSAY_RULES['min_words']}-{ESSAY_RULES['max_words']})")

    e = result["evaluation"]
    if e["passed"]:
        print(f"[GUARDRAILS] Passed. voice_score={e['voice_score']}/10, tone={e['tone']}")
    else:
        print(f"[GUARDRAILS] Did not pass after {result['attempts']} attempts: {e['feedback']}")
