# -*- coding: utf-8 -*-
"""
Shared rule-based guardrail checks, used by every agent that drafts content.
These are first-pass checks only (string matching). LLM-as-a-judge voice
scoring against REFERENCE_PASSAGES is Step 6 of BUILD_PLAN.md, not yet built.
"""

from voice_profile import BANNED_PHRASES, NEGATIVE_PARALLELISM_FLAGS

EM_DASH = chr(0x2014)
CURLY_CHARS = [chr(0x2018), chr(0x2019), chr(0x201C), chr(0x201D)]


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
