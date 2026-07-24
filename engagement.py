# -*- coding: utf-8 -*-
"""
Engagement critic: fast, rule-based feedback on whether a short post is built
to earn views and comments. This is the "virality" counterpart to the voice
judge in guardrails.py -- but where the voice judge is an LLM call, this is
pure logic (no Gemini, no cost, fully testable), so it can run on every draft
for free and feed concrete fixes back into the revise loop.

It does NOT try to guarantee a post goes viral (nothing can). It catches the
mechanical things that reliably kill reach on LinkedIn / Substack Notes:

  - a hook (first line) that is too long to survive the "see more" truncation,
  - opening on a question or a limp hedge instead of a concrete claim,
  - emoji where the platform rule forbids them,
  - the wrong number of hashtags,
  - a post that blew past its length budget.

check() returns a dict shaped like the other guardrail results so it can be
handed to guardrails.draft_with_guardrails(..., extra_checks=...):
  {"passed": bool, "feedback": str, "score": int 0-100, "flags": [str, ...]}

"passed" is only False on the hard problems above; softer suggestions go into
"feedback" without failing, so the revise loop is nudged, not thrashed.
"""

import re

# LinkedIn truncates the feed preview around here; a hook longer than this is
# cut off with "...see more", so the payoff has to land before it.
HOOK_HARD_LIMIT = 160
HOOK_SOFT_LIMIT = 120

# Limp openers that bury the lede. Soft-flagged (feedback, not failure).
WEAK_OPENERS = (
    "maybe ", "i think ", "in today's", "in a world", "we all know",
    "it's no secret", "there's no denying", "let's face it", "picture this",
    "imagine ", "have you ever",
)

_HASHTAG_RE = re.compile(r"#\w+")


def _has_emoji(text: str) -> bool:
    """True if text contains an emoji. Checked by codepoint so this source file
    stays pure ASCII (no literal emoji bytes)."""
    for ch in text:
        cp = ord(ch)
        if (0x1F000 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x27BF
                or 0x2B00 <= cp <= 0x2BFF or cp in (0x2705, 0x2764, 0x2728)
                or 0xFE00 <= cp <= 0xFE0F or 0x1F1E6 <= cp <= 0x1F1FF):
            return True
    return False


def _first_line(text: str) -> str:
    for line in text.strip().splitlines():
        if line.strip():
            return line.strip()
    return ""


def check(text: str, rules: dict) -> dict:
    """Score a draft against engagement heuristics for one platform rule.
    rules is a PLATFORM_RULES entry (min/max words, hashtag range, emoji
    policy). Returns {"passed", "feedback", "score", "flags"}."""
    hard = []   # cause a fail
    soft = []   # feedback only
    penalty = 0

    words = len(text.split())
    min_w = rules.get("min_words", 0)
    max_w = rules.get("max_words", 0)
    # Enforce the ceiling firmly (short is the whole point) and the floor gently.
    if max_w and words > max_w * 1.15:
        hard.append(f"too long at {words} words; cut to under {max_w}")
        penalty += 25
    if min_w and words < min_w * 0.6:
        hard.append(f"too thin at {words} words; build it out toward {min_w}")
        penalty += 20

    hook = _first_line(text)
    if hook.endswith("?"):
        hard.append("the first line is a question; open on a concrete claim or "
                    "image instead so it stops the scroll")
        penalty += 20
    if len(hook) > HOOK_HARD_LIMIT:
        hard.append(f"the hook is {len(hook)} characters; LinkedIn cuts the "
                    f"preview near {HOOK_HARD_LIMIT}, so front-load a single "
                    "punchy line")
        penalty += 20
    elif len(hook) > HOOK_SOFT_LIMIT:
        soft.append(f"tighten the first line (now {len(hook)} chars) so the "
                    "payoff lands before the 'see more' cut")
        penalty += 8
    lowered_hook = hook.lower()
    if any(lowered_hook.startswith(w) for w in WEAK_OPENERS):
        soft.append("the opener hedges; lead with the sharp claim, not a warm-up")
        penalty += 8

    tags = _HASHTAG_RE.findall(text)
    min_h = rules.get("min_hashtags", 0)
    max_h = rules.get("max_hashtags", 0)
    if len(tags) < min_h:
        hard.append(f"add hashtags ({len(tags)} of {min_h}-{max_h})")
        penalty += 10
    elif len(tags) > max_h:
        # max_h == 0 is a real limit (Notes take none), not "unlimited".
        if max_h == 0:
            hard.append(f"remove the {len(tags)} hashtag(s); this format uses none")
        else:
            hard.append(f"too many hashtags ({len(tags)}; keep {min_h}-{max_h})")
        penalty += 10

    if not rules.get("allow_emoji_in_body", False) and _has_emoji(text):
        hard.append("remove the emoji; this format posts without them")
        penalty += 12

    flags = hard + soft
    feedback = "; ".join(flags) if flags else "none"
    score = max(0, 100 - penalty)
    return {
        "passed": not hard,
        "feedback": feedback,
        "score": score,
        "flags": flags,
    }
