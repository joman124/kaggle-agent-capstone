# -*- coding: utf-8 -*-
"""
The Scout agent: finds trending topics at the intersection of AI, work, and
psychology using Claude with server-side web search, so results reflect
current events rather than the model's training-data recall.

Run:  python -m agents.scout ["optional topic to focus the search"]
"""

import json
import os
import re
import sys

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5")

PILLARS = [
    "Clinical Window",
    "The Thesis",
    "Personal",
    "Applied Philosophy",
    "Current Events",
]
PLATFORMS = ["substack", "linkedin"]

SYSTEM_INSTRUCTION = (
    "You are a research scout for John Mansoor, PsyD, a clinical psychologist "
    "writing the book \"After Work,\" about the psychological cost of AI "
    "displacing human labor. Find current, real news and discussion at the "
    "intersection of AI, work, and psychology that John could write about.\n\n"
    "Content pillars (every suggestion must map to exactly one):\n"
    "- Clinical Window: composite, anonymized patient stories\n"
    "- The Thesis: the book's core argument from a new angle\n"
    "- Personal: John's own relationship with AI\n"
    "- Applied Philosophy: Frankl, Aristotle, Stoics, Ubuntu, made accessible\n"
    "- Current Events: react to AI news as a clinician\n\n"
    "Target platforms: substack (long-form home base, weekly essay + daily "
    "Notes) or linkedin (professional amplifier, 3-4 posts/week)."
)


def find_topics(topic: str = None, count: int = 5) -> list:
    """Return a list of topic briefings, each a dict with: headline, source,
    relevance_score, suggested_angle, suggested_pillar, suggested_platform."""
    focus = (
        f' Focus specifically on: "{topic}".' if topic
        else " Find what is trending in the past 48 hours."
    )
    prompt = f"""Search for {count} current, real news items or discussions at the
intersection of AI, work, and psychology.{focus}

For each one, return an object with exactly these six keys:
- headline: the real headline or topic, in your own words
- source: the publication or site name
- relevance_score: integer 1-10, how relevant to a clinical-psychology
  audience writing about AI's effect on human meaning and work
- suggested_angle: one specific sentence John could take, not a generic take
- suggested_pillar: exactly one of {PILLARS}
- suggested_platform: exactly one of {PLATFORMS}

Return ONLY a JSON array of {count} objects. No markdown code fences, no
preamble, no explanation - just the raw JSON array."""

    # Imported lazily so the module imports without the anthropic SDK
    # installed (routing/tests do not need it); only this grounded call does.
    from anthropic_client import generate, WEB_SEARCH_TOOL

    # Claude's server-side web search replaces Gemini's Google Search
    # grounding: the search runs on Anthropic's side and the results come
    # back in the same response, so nothing else here changes.
    raw = generate(
        MODEL,
        prompt,
        system_instruction=SYSTEM_INSTRUCTION,
        tools=[WEB_SEARCH_TOOL],
    )
    return _parse_json_array(raw)


def _parse_json_array(raw: str) -> list:
    """Strip markdown fences and any preamble text the model added despite
    being told not to, then parse. If the array itself got cut off by the
    model's output limit mid-object, salvage the complete objects that came
    before the cut rather than discarding the whole response. Fails with the
    raw output shown rather than a bare JSONDecodeError."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    # Anchor on "[" immediately followed by "{" -- the start of an array of
    # objects -- rather than the first "[" anywhere. Web-search grounded
    # replies often cite sources as "[1]" in the preamble before the real
    # array; a bare find("[") would lock onto that citation and either fail
    # or (worse) successfully parse it as a throwaway one-element array,
    # silently discarding the real data.
    match = re.search(r"\[\s*\{", text)
    if not match:
        raise SystemExit(
            "\n[SCOUT] Claude did not return valid JSON. Raw output:\n" + raw[:800]
        )
    text = text[match.start():]

    data = None
    try:
        # raw_decode stops at the end of the first JSON value, so trailing
        # prose after a complete array (e.g. the model adding a sign-off) is
        # ignored instead of breaking the parse.
        data, _ = json.JSONDecoder().raw_decode(text)
    except json.JSONDecodeError:
        # The array was cut off before its closing bracket (hit MAX_TOKENS
        # mid-object). Walk backward through "}," candidates -- the rightmost
        # one is not always a real object boundary (it can land inside a
        # string) so keep trying earlier ones until a close actually parses,
        # instead of giving up on the first attempt.
        pos = len(text)
        while True:
            pos = text.rfind("},", 0, pos)
            if pos == -1:
                break
            try:
                data, _ = json.JSONDecoder().raw_decode(text[:pos + 1] + "]")
                break
            except json.JSONDecodeError:
                continue

    if data is None:
        raise SystemExit(
            "\n[SCOUT] Claude did not return valid JSON. Raw output:\n" + raw[:800]
        )
    if not isinstance(data, list):
        raise SystemExit(f"\n[SCOUT] Expected a JSON array of topics, got: {type(data)}")
    if not data:
        raise SystemExit(
            "\n[SCOUT] Claude's response was cut off before any complete topic. "
            "Raw output:\n" + raw[:800]
        )
    return data


if __name__ == "__main__":
    requested_topic = " ".join(sys.argv[1:]) or None
    print(f"Using model: {MODEL}")
    print(f"Topic filter: {requested_topic or '(none - trending past 48 hours)'}\n")
    briefing = find_topics(requested_topic)
    print(json.dumps(briefing, indent=2))
