# -*- coding: utf-8 -*-
"""
Brand-safety gate. A system that reacts fast to hot topics can wander into news
where a quick take reads as tone-deaf or exploitative (a tragedy, a death, an
active crisis, an individual being piled on). This is a first-pass, pure-logic
screen -- no Gemini -- that flags a topic as sensitive so the pipeline routes it
to a human instead of auto-posting.

It is intentionally conservative: false positives just mean "a person looks at
it," which for a public brand account is the safe direction. assess() returns
{"safe": bool, "reason": str, "flags": [...]}.
"""

import re

# Categories of topic a brand should not fast-react to without a human.
SENSITIVE_TERMS = {
    "death/tragedy": [
        "died", "death", "dead", "killed", "kills", "fatal", "suicide",
        "shooting", "shooter", "massacre", "terror", "bombing", "crash",
        "disaster", "earthquake", "hurricane", "wildfire", "funeral", "obituary",
    ],
    "violence/crime": [
        "assault", "abuse", "arrested", "charged", "lawsuit", "sued",
        "indicted", "fraud charges", "scandal", "harassment", "misconduct",
    ],
    "conflict/politics": [
        "war", "invasion", "airstrike", "hostage", "genocide", "election fraud",
        "coup", "protest turns", "riot",
    ],
    "layoffs/harm": [
        "layoffs", "laid off", "mass layoff", "job cuts", "fired thousands",
        "bankruptcy", "shuts down",
    ],
}


def assess(topic: str) -> dict:
    """Screen a topic string. Returns {"safe", "reason", "flags"}. 'flags' lists
    (category, term) pairs that tripped. layoffs/harm is allowed but noted,
    since the brands legitimately discuss work loss -- it is flagged for
    awareness, not blocked."""
    lowered = " " + (topic or "").lower() + " "
    flags = []
    blocking = []
    for category, terms in SENSITIVE_TERMS.items():
        for term in terms:
            if re.search(r"\b" + re.escape(term) + r"\b", lowered):
                flags.append((category, term))
                if category != "layoffs/harm":
                    blocking.append((category, term))

    if blocking:
        cats = sorted({c for c, _ in blocking})
        return {
            "safe": False,
            "reason": ("topic touches sensitive material (" + ", ".join(cats) +
                       "); route to a human before posting"),
            "flags": flags,
        }
    if flags:
        return {
            "safe": True,
            "reason": "mentions job loss (on-theme, but keep the tone careful)",
            "flags": flags,
        }
    return {"safe": True, "reason": "ok", "flags": []}
