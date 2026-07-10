# -*- coding: utf-8 -*-
"""
The Orchestrator: routes natural-language requests to the right agent(s).

Routing itself (route()) is deterministic keyword matching, not a Gemini
call, so it is fully unit-testable without an API key. Only the agent
pipelines it dispatches to (handle_request()) need one.

Run:  python -m agents.orchestrator "What should I publish this week?"
"""

import json
import re
import sys
import time

_TOPIC_PATTERNS = [
    re.compile(r"\babout\s+(.+)$", re.IGNORECASE),
    re.compile(r"\breact(?:ing)? to\s+(.+)$", re.IGNORECASE),
    re.compile(r"\bon\s+(.+)$", re.IGNORECASE),
]


def _extract_topic(request: str):
    """Pull a topic out of phrasing like 'write a linkedin post about X'.
    Returns None if nothing matches, so callers can fall back to Scout."""
    for pattern in _TOPIC_PATTERNS:
        match = pattern.search(request)
        if match:
            return match.group(1).strip().strip(".\"'")
    return None


def route(request: str):
    """Classify a request into (intent, topic). Checked in this order so
    more specific phrasing (weekly plan, trending) wins over a bare
    platform-name match ('linkedin', 'essay')."""
    lowered = request.lower()

    if any(p in lowered for p in ("what should i publish", "plan my week", "weekly plan", "this week")):
        return "weekly_plan", None

    # Viral wins over the plain platform branches below: "go viral about the
    # trending X" is a viral request, not a trending lookup.
    if any(p in lowered for p in ("viral", "go viral", "react to", "hot take")):
        return "viral", _extract_topic(request)

    if "trending" in lowered:
        return "trending", _extract_topic(request)

    if "essay" in lowered or "substack" in lowered:
        return "essay", _extract_topic(request)

    if "linkedin" in lowered:
        return "linkedin_post", _extract_topic(request)

    if any(p in lowered for p in ("last week", "engagement", "numbers", "metrics")):
        return "engagement", None

    return "unknown", _extract_topic(request)


def handle_request(request: str) -> str:
    """Route the request and run the matched agent pipeline. Imports agents
    lazily inside each handler so routing stays importable without an API
    key; only the branch that actually runs needs GEMINI_API_KEY set."""
    from observability import log_decision

    intent, topic = route(request)
    log_decision(
        agent="orchestrator", action="route",
        inputs={"request": request},
        decision={"intent": intent, "topic": topic},
    )

    if intent == "weekly_plan":
        return _handle_weekly_plan()
    if intent == "viral":
        return _handle_viral(topic)
    if intent == "trending":
        return _handle_trending(topic)
    if intent == "linkedin_post":
        return _handle_linkedin_post(topic)
    if intent == "essay":
        return _handle_essay(topic)
    if intent == "engagement":
        return _handle_engagement()
    return ("[ORCHESTRATOR] Did not recognize that request. Try things like "
            "\"What should I publish this week?\", \"What's trending?\", "
            "\"Go viral about X\", \"Write me a LinkedIn post about X\", or "
            "\"Draft an essay about X\".")


def _handle_weekly_plan() -> str:
    from agents.scout import find_topics
    from agents.strategist import plan_week
    from agents.analyst import get_pillar_adjustments
    from agents.writer import write_linkedin_post, generate_seed_post
    from agents.substack_specialist import expand_to_essay
    from doc_output import append_to_doc
    from guardrails import CALL_PACING_SECONDS

    briefing = find_topics()
    adjustments = get_pillar_adjustments()
    plan = plan_week(scout_briefing=briefing, pillar_adjustments=adjustments)

    lines = ["[ORCHESTRATOR] Weekly plan:"]
    for i, day in enumerate(plan):
        if i > 0:
            # Each day below makes several Gemini calls of its own (Writer's
            # revise loop, plus the Substack expansion on Substack days);
            # pause between days too so a 7-day plan does not burst the
            # free tier's per-minute rate limit.
            time.sleep(CALL_PACING_SECONDS)

        topic = day["topic"] or day["pillar"]
        lines.append(f"  {day['day']}: {day['pillar']} on {day['platform']} - {topic}")

        if day["platform"] == "linkedin":
            post = write_linkedin_post(topic)
            append_to_doc("LinkedIn Posts.docx", topic, post)
        else:
            # The seed post here is never shown to John, so skip its
            # guardrail loop entirely - only the essay below is the real
            # deliverable, and it runs its own full revise loop.
            seed = generate_seed_post(topic)
            time.sleep(CALL_PACING_SECONDS)
            essay = expand_to_essay(seed, topic)
            append_to_doc("Substack Essays.docx", topic, essay)

    lines.append("Drafts saved to 'LinkedIn Posts.docx' and 'Substack Essays.docx'.")
    return "\n".join(lines)


def _handle_viral(topic) -> str:
    """Fast reaction to a hot topic: draft a viral LinkedIn post and auto-post
    it (dry run unless LINKEDIN_DRY_RUN=false), then draft a Substack Note for
    John to post by hand. If no topic was given, Scout picks the hottest one."""
    from agents.viral import draft_viral_linkedin, draft_note
    from linkedin_publisher import post_text
    from doc_output import append_to_doc
    from guardrails import CALL_PACING_SECONDS

    if not topic:
        from agents.scout import find_topics
        briefing = find_topics()
        if not briefing:
            return ("[ORCHESTRATOR] Scout found nothing hot to react to. Try "
                    "again with a specific topic, e.g. \"go viral about X.\"")
        topic = briefing[0].get("suggested_angle") or briefing[0].get("headline")
        time.sleep(CALL_PACING_SECONDS)

    li = draft_viral_linkedin(topic)
    append_to_doc("LinkedIn Posts.docx", topic, li["text"])
    publish = post_text(li["text"])

    time.sleep(CALL_PACING_SECONDS)
    note = draft_note(topic)
    append_to_doc("Substack Notes.docx", topic, note["text"])

    if publish["dry_run"]:
        li_status = ("Drafted and saved to 'LinkedIn Posts.docx' (DRY RUN -- not "
                     "posted; set LINKEDIN_DRY_RUN=false to go live).")
    else:
        li_status = f"Posted to LinkedIn (id {publish['post_id']})."

    return (
        f"[ORCHESTRATOR] Viral reaction to: {topic}\n\n"
        f"LINKEDIN POST:\n{li['text']}\n\n{li_status}\n\n"
        f"SUBSTACK NOTE (saved to 'Substack Notes.docx' for you to post):\n"
        f"{note['text']}"
    )


def _handle_trending(topic) -> str:
    from agents.scout import find_topics
    briefing = find_topics(topic)
    return "[ORCHESTRATOR] Trending topics:\n" + json.dumps(briefing, indent=2)


def _handle_linkedin_post(topic) -> str:
    from agents.writer import write_linkedin_post
    from doc_output import append_to_doc

    if not topic:
        return ("[ORCHESTRATOR] Tell me what to write about, e.g. "
                 "\"Write me a LinkedIn post about burnout.\"")

    post = write_linkedin_post(topic)
    append_to_doc("LinkedIn Posts.docx", topic, post)
    return f"[ORCHESTRATOR] Draft saved to 'LinkedIn Posts.docx':\n\n{post}"


def _handle_essay(topic) -> str:
    from agents.scout import find_topics
    from agents.writer import generate_seed_post
    from agents.substack_specialist import expand_to_essay
    from doc_output import append_to_doc
    from guardrails import CALL_PACING_SECONDS

    if not topic:
        briefing = find_topics()
        if not briefing:
            return "[ORCHESTRATOR] Scout found nothing to react to. Try again with a specific topic."
        topic = briefing[0]["suggested_angle"]

    # The seed post is never shown to John, so skip its guardrail loop -
    # only the essay below is the real deliverable.
    post = generate_seed_post(topic)
    time.sleep(CALL_PACING_SECONDS)  # seed call, then substack specialist's draft+judge calls below
    essay = expand_to_essay(post, topic)
    append_to_doc("Substack Essays.docx", topic, essay)
    return f"[ORCHESTRATOR] Essay saved to 'Substack Essays.docx':\n\n{essay}"


def _handle_engagement() -> str:
    from agents.analyst import weekly_summary
    return weekly_summary()


if __name__ == "__main__":
    user_request = " ".join(sys.argv[1:]) or "What should I publish this week?"
    print(f"Request: {user_request}\n")
    print(handle_request(user_request))
