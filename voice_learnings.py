# -*- coding: utf-8 -*-
"""
Learned voice rules: John's permanent feedback on how the agents should
write. Unlike voice_profile.py (the hand-tuned original profile, edited by
touching code), entries here are meant to be added from the Streamlit
"Voice Rules" tab (app.py) without editing any file directly, and every
drafting agent picks them up on the very next draft -- no restart needed.

Two tiers, same split as voice_profile.py's own BANNED_PHRASES vs
ANTITHESIS_PATTERNS:
  - "rule" text is always injected into the system prompt every drafting
    agent uses (via guardrails.draft_with_guardrails), as plain-English
    guidance the model reads before writing.
  - Optional "banned_snippets" (literal, case-insensitive substrings) and
    "regex_patterns" turn a rule into a HARD guardrail fail, same as
    BANNED_PHRASES / find_antithesis in guardrails.py -- the revise loop is
    forced to fix it, not just nudged. The Streamlit form only ever writes
    plain rule text and literal snippets, never regex, since asking a
    non-developer to type a safe regex into a web form is a bad idea.
    Regex-backed rules (structural tells a substring cannot catch) are
    added by hand, in code, the way the seed entry below was.

Stored as a single JSON array in memory/voice_learnings.json.
"""

import json
import os
import re
from datetime import datetime, timezone

LEARNINGS_PATH = os.path.join("memory", "voice_learnings.json")


def load_learnings() -> list:
    """Return the learned-rules list, [] if the file is missing/corrupt."""
    if not os.path.exists(LEARNINGS_PATH):
        return []
    try:
        with open(LEARNINGS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save(learnings: list) -> None:
    os.makedirs(os.path.dirname(LEARNINGS_PATH), exist_ok=True)
    with open(LEARNINGS_PATH, "w", encoding="utf-8") as fh:
        json.dump(learnings, fh, indent=2)


def add_learning(rule: str, banned_snippets=None, regex_patterns=None,
                 source: str = "manual") -> dict:
    """Append a new permanent voice rule and return the stored entry.
    rule is required plain-English guidance. banned_snippets/regex_patterns
    are optional and make the rule a hard guardrail fail in addition to
    prompt guidance. Nothing here is ever removed automatically -- a rule
    stays in effect for every future draft until someone edits the JSON
    file by hand."""
    rule = (rule or "").strip()
    if not rule:
        raise ValueError("rule text cannot be empty")
    learnings = load_learnings()
    entry = {
        "id": "L%d" % (len(learnings) + 1),
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "rule": rule,
        "banned_snippets": [s.strip().lower() for s in (banned_snippets or []) if s.strip()],
        "regex_patterns": list(regex_patterns or []),
        "source": source,
    }
    learnings.append(entry)
    _save(learnings)
    return entry


def learnings_prompt_block() -> str:
    """Render all learned rules as one prompt-injectable block, empty string
    if none exist yet so agents' prompts are unchanged until John adds the
    first rule. guardrails.draft_with_guardrails() appends this to every
    drafting agent's system_instruction on every call, reading the file
    fresh each time -- so a rule added in the UI applies to the very next
    draft with no restart."""
    learnings = load_learnings()
    if not learnings:
        return ""
    lines = ["JOHN'S PERMANENT VOICE FEEDBACK -- apply every one of these:"]
    for entry in learnings:
        lines.append("- %s" % entry["rule"])
    return "\n".join(lines)


def check_learned_snippets(text: str) -> list:
    """Return the learned banned_snippets found in text (case-insensitive
    substring match), same style as voice_profile.BANNED_PHRASES."""
    lowered = text.lower()
    found = []
    for entry in load_learnings():
        for snippet in entry.get("banned_snippets", []):
            if snippet in lowered:
                found.append(snippet)
    return found


def check_learned_patterns(text: str) -> list:
    """Return [{"id", "rule", "match"}] for every learned regex pattern
    found in text. Mirrors guardrails.find_antithesis, but over the learned-
    rules store instead of the fixed voice_profile.ANTITHESIS_PATTERNS list,
    so a new structural tell John flags does not require touching
    guardrails.py -- only this file's data."""
    found = []
    for entry in load_learnings():
        for pattern in entry.get("regex_patterns", []):
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                found.append({
                    "id": entry["id"], "rule": entry["rule"],
                    "match": " ".join(m.group(0).split()),
                })
    return found
