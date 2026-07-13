# -*- coding: utf-8 -*-
"""
The Viral agent: turns a hot topic into fast-reaction content built to earn
views and engagement, without dropping John's voice.

Two formats, both drafted through the same generate-evaluate-revise loop the
Writer uses (guardrails.draft_with_guardrails), so "viral" still means "sounds
like John and passes the voice judge," just shorter and punchier:

  - a short LinkedIn post (PLATFORM_RULES["linkedin_viral"])
  - a Substack Note (PLATFORM_RULES["substack_note"])

The LinkedIn post is meant to be auto-posted (see linkedin_publisher.py); the
Substack Note is saved for John to post by hand, since Substack has no API.

Each draft must clear TWO gates before it is accepted (up to 3 attempts):
  1. the voice judge in guardrails.py (sounds like John, tone authentic), and
  2. engagement.check() -- a pure-logic reach gate (hook length, no question
     opener, hashtag count, length budget). Its feedback is fed back into the
     next redraft, same as the voice feedback.

TUNING (where to adjust behavior):
  - Length / hashtags / temperature: PLATFORM_RULES["linkedin_viral"] and
    ["substack_note"] in voice_profile.py.
  - What counts as a weak hook / the "see more" cutoff: engagement.py
    (HOOK_SOFT_LIMIT, HOOK_HARD_LIMIT, WEAK_OPENERS).
  - What sounds like John / banned phrases: voice_profile.py.
  - If drafts keep failing after 3 tries, the trace in logs/agent_trace.jsonl
    shows which gate (voice_score, tone, or engagement) rejected each attempt.

Run:  python -m agents.viral ["optional hot topic"]
"""

import os
import sys
import time

from voice_profile import VOICE_SYSTEM_PROMPT, ANTI_AI_TELL_PROMPT, PLATFORM_RULES
from guardrails import draft_with_guardrails, CALL_PACING_SECONDS
import engagement

# Shares the Writer's pro-tier model: this is still publication-quality voice
# work, just short. Override with GEMINI_WRITER_MODEL in .env.
MODEL = os.getenv("GEMINI_WRITER_MODEL", "gemini-pro-latest")
SYSTEM_INSTRUCTION = VOICE_SYSTEM_PROMPT + "\n\n" + ANTI_AI_TELL_PROMPT

LINKEDIN_DOC = "LinkedIn Posts.docx"
NOTE_DOC = "Substack Notes.docx"

VIRAL_RULES = PLATFORM_RULES["linkedin_viral"]
NOTE_RULES = PLATFORM_RULES["substack_note"]


def _build_viral_linkedin_prompt(topic: str, feedback: str = None) -> str:
    revision_note = (
        f"\nA previous draft was rejected. Fix this before writing: {feedback}\n"
        if feedback else ""
    )
    return f"""Write a short, high-engagement LinkedIn post reacting to this hot topic:

TOPIC: {topic}
{revision_note}
This is a fast reaction meant to stop the scroll and pull comments. Make it
land in the first line. Take a real, specific stance a clinical psychologist
would take on what this does to people, not a safe summary of the news.

Requirements:
- {VIRAL_RULES['min_words']} to {VIRAL_RULES['max_words']} words
- Open with one sharp, concrete line (a stance or an image), not a question
  and not "I have been thinking about"
- First person
- Short sentences. White space is fine.
- End on a line that invites disagreement or reflection, not a neat takeaway
- Add {VIRAL_RULES['min_hashtags']} to {VIRAL_RULES['max_hashtags']} relevant
  hashtags on the last line
- No external links in the body
- No emoji

Write only the post. No preamble, no explanation."""


def _build_note_prompt(topic: str, feedback: str = None) -> str:
    revision_note = (
        f"\nA previous draft was rejected. Fix this before writing: {feedback}\n"
        if feedback else ""
    )
    return f"""Write a Substack Note reacting to this hot topic:

TOPIC: {topic}
{revision_note}
A Note is a single quick thought, the length of a good text message. Punchy,
specific, in John's voice. One idea, stated once, well.

Requirements:
- {NOTE_RULES['min_words']} to {NOTE_RULES['max_words']} words
- First person
- Open on the concrete, not an abstraction
- No hashtags
- End on something unresolved, not a summary

Write only the Note. No preamble, no explanation."""


def draft_viral_linkedin(topic: str, max_attempts: int = 3) -> dict:
    """Generate-evaluate-revise loop for a viral LinkedIn post. Returns
    {"text", "attempts", "evaluation", "history"} from draft_with_guardrails."""
    return draft_with_guardrails(
        MODEL,
        build_prompt=lambda feedback: _build_viral_linkedin_prompt(topic, feedback),
        system_instruction=SYSTEM_INSTRUCTION,
        max_em_dashes=VIRAL_RULES["max_em_dashes"],
        max_attempts=max_attempts,
        agent="viral",
        temperature=VIRAL_RULES["temperature"],
        # Also require the draft to be built for reach (hook, length, hashtags),
        # not just on-voice.
        extra_checks=lambda t: engagement.check(t, VIRAL_RULES),
    )


def draft_note(topic: str, max_attempts: int = 3) -> dict:
    """Generate-evaluate-revise loop for a Substack Note. Returns
    {"text", "attempts", "evaluation", "history"} from draft_with_guardrails."""
    return draft_with_guardrails(
        MODEL,
        build_prompt=lambda feedback: _build_note_prompt(topic, feedback),
        system_instruction=SYSTEM_INSTRUCTION,
        max_em_dashes=NOTE_RULES["max_em_dashes"],
        max_attempts=max_attempts,
        agent="viral",
        temperature=NOTE_RULES["temperature"],
        extra_checks=lambda t: engagement.check(t, NOTE_RULES),
    )


def write_viral_post(topic: str) -> str:
    """Thin wrapper for callers (e.g. the Orchestrator) that only want the
    final LinkedIn text, not the full evaluation history."""
    return draft_viral_linkedin(topic)["text"]


def write_note(topic: str) -> str:
    """Thin wrapper for callers that only want the final Note text."""
    return draft_note(topic)["text"]


if __name__ == "__main__":
    from doc_output import append_to_doc

    hot_topic = " ".join(sys.argv[1:]) or (
        "A new study says AI now writes most first-draft code at big tech firms"
    )
    print(f"Using model: {MODEL}")
    print(f"Hot topic: {hot_topic}\n")

    print("=" * 70)
    print("VIRAL LINKEDIN POST")
    print("=" * 70)
    li = draft_viral_linkedin(hot_topic)
    print(li["text"])
    append_to_doc(LINKEDIN_DOC, hot_topic, li["text"])
    e = li["evaluation"]
    status = "passed" if e["passed"] else "did not pass"
    print(f"\n[GUARDRAILS] {status} after {li['attempts']} attempt(s). "
          f"voice_score={e['voice_score']}/10, tone={e['tone']}")

    # Free-tier allows only a few requests per minute; pause between formats.
    time.sleep(CALL_PACING_SECONDS)

    print("\n" + "=" * 70)
    print("SUBSTACK NOTE")
    print("=" * 70)
    note = draft_note(hot_topic)
    print(note["text"])
    append_to_doc(NOTE_DOC, hot_topic, note["text"])
    e = note["evaluation"]
    status = "passed" if e["passed"] else "did not pass"
    print(f"\n[GUARDRAILS] {status} after {note['attempts']} attempt(s). "
          f"voice_score={e['voice_score']}/10, tone={e['tone']}")
    print(f"\n[SAVED] '{LINKEDIN_DOC}' and '{NOTE_DOC}'.")
