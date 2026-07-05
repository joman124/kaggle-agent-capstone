# -*- coding: utf-8 -*-
"""
Streamlit UI for the After Work Social Presence Agent (Step 9).

This is the front door judges and John see. It wraps the Orchestrator so a
natural-language request ("What should I publish this week?") runs the whole
agent pipeline, and it renders the system's real state -- the planned calendar,
the generated drafts, and the observability trace -- without needing any API
call. Those read-only views make a clean, fast demo and cost nothing to show.

Run:  streamlit run app.py

Kept pure ASCII on purpose (see CLAUDE.md): Windows non-UTF-8 saves crash
Python on em-dashes and curly quotes, so this file uses plain ASCII only.
"""

import json
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

CALENDAR_PATH = os.path.join("memory", "calendar.json")
TRACE_PATH = os.path.join("logs", "agent_trace.jsonl")
LINKEDIN_DOC = "LinkedIn Posts.docx"
SUBSTACK_DOC = "Substack Essays.docx"

PILLARS = [
    "Clinical Window",
    "The Thesis",
    "Personal",
    "Applied Philosophy",
    "Current Events",
]


# --------------------------------------------------------------------------
# Data helpers (read-only; no Gemini calls, safe to run anytime)
# --------------------------------------------------------------------------
def load_calendar():
    """Return the planned week as a list of day dicts, or [] if none yet."""
    if not os.path.exists(CALENDAR_PATH):
        return []
    try:
        with open(CALENDAR_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return []


def load_drafts(doc_path):
    """Parse a generated .docx into a list of {heading, body} entries.

    doc_output.append_to_doc() writes a level-1 title once, then a level-2
    heading per post followed by body paragraphs. We group on the level-2
    headings and skip the top title.
    """
    if not os.path.exists(doc_path):
        return []
    try:
        from docx import Document
    except ImportError:
        return []
    try:
        doc = Document(doc_path)
    except OSError:
        return []

    entries = []
    current = None
    for para in doc.paragraphs:
        text = para.text.strip()
        style = para.style.name if para.style else ""
        if style == "Heading 1":
            continue  # the document title, e.g. "LinkedIn Posts"
        if style == "Heading 2":
            if current:
                entries.append(current)
            current = {"heading": text, "body": []}
        elif current is not None and text:
            current["body"].append(text)
    if current:
        entries.append(current)

    for e in entries:
        e["body"] = "\n\n".join(e["body"])
    return entries


def load_trace(limit=40):
    """Return the last `limit` parsed decisions from the JSONL trace."""
    if not os.path.exists(TRACE_PATH):
        return []
    rows = []
    try:
        with open(TRACE_PATH, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return rows[-limit:]


def has_api_key():
    return bool(os.getenv("GEMINI_API_KEY"))


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------
st.set_page_config(page_title="After Work - Social Presence Agent", layout="wide")

st.title("After Work: Social Presence Agent")
st.caption(
    "A multi-agent system that researches, plans, and drafts social content in "
    "John Mansoor's voice. John reviews and posts; the system does the rest."
)

# ---- Sidebar: system status -----------------------------------------------
with st.sidebar:
    st.header("System status")
    if has_api_key():
        st.success("GEMINI_API_KEY loaded")
    else:
        st.error("No GEMINI_API_KEY found. Live runs are disabled.")
        st.caption("Set it in .env, then restart. Read-only views still work.")

    st.write("**Models**")
    st.write("- Agents / judge: `%s`" % (os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"))
    st.write("- Writer: `%s`" % (os.getenv("GEMINI_WRITER_MODEL") or "gemini-pro-latest"))

    st.divider()
    st.header("The five agents")
    st.markdown(
        "1. **Scout** - Google Search grounding, finds trends\n"
        "2. **Strategist** - plans the week over memory state\n"
        "3. **Writer** - drafts in-voice through guardrails\n"
        "4. **Substack Specialist** - expands posts into essays\n"
        "5. **Analyst** - learns from engagement, adjusts pillars"
    )
    st.divider()
    st.caption("Kaggle AI Agents Capstone - Agents for Business")


# ---- Main: ask the agent ---------------------------------------------------
st.subheader("Ask the agent")

col_a, col_b = st.columns([3, 1])
with col_a:
    request = st.text_input(
        "Request",
        value="What should I publish this week?",
        label_visibility="collapsed",
        placeholder="e.g. What should I publish this week?",
    )
with col_b:
    run = st.button("Run", type="primary", use_container_width=True, disabled=not has_api_key())

st.caption(
    "Examples: \"What should I publish this week?\" (full weekly plan), "
    "\"What's trending?\", \"Write me a LinkedIn post about burnout\", "
    "\"Draft an essay about AI and meaning\"."
)

with st.expander("Note on live runs (cost + time)"):
    st.markdown(
        "A full weekly plan makes many live Gemini calls (Scout, then the "
        "Writer's revise loop per post, plus Substack expansions) and can take "
        "a few minutes with rate-limit pacing. It also draws on the prepaid "
        "API balance. For a fast, free demo, use the **This Week's Plan**, "
        "**Drafts**, and **Agent Trace** tabs below -- they render the system's "
        "real output with no API calls."
    )

if run and request.strip():
    from agents.orchestrator import route

    intent, topic = route(request)
    st.info("Routed to intent: **%s**%s"
            % (intent, ("  |  topic: %s" % topic) if topic else ""))
    with st.spinner("Running the agent pipeline... this can take a few minutes for a full plan."):
        try:
            from agents.orchestrator import handle_request
            result = handle_request(request)
            st.success("Done. Drafts (if any) were saved to the Word documents.")
            st.text_area("Response", value=result, height=360)
        except SystemExit as exc:
            # gemini_client raises SystemExit with a plain-English message on
            # quota / auth / empty-response failures. Show it, do not crash.
            st.error(str(exc))
        except Exception as exc:  # noqa: BLE001 - surface anything else cleanly
            st.error("Run failed: %s" % exc)

st.divider()

# ---- Tabs: real state, no API calls ---------------------------------------
tab_plan, tab_drafts, tab_trace = st.tabs(
    ["This Week's Plan", "Drafts", "Agent Trace"]
)

with tab_plan:
    calendar = load_calendar()
    if not calendar:
        st.info("No plan yet. Run \"What should I publish this week?\" to generate one.")
    else:
        planned = sum(1 for d in calendar if d.get("topic"))
        st.caption("%d days planned, %d with a Scout-matched topic." % (len(calendar), planned))
        rows = []
        for d in calendar:
            rows.append({
                "Day": d.get("day", ""),
                "Pillar": d.get("pillar", ""),
                "Platform": d.get("platform", ""),
                "Topic / Headline": d.get("source_headline") or d.get("topic") or "(open)",
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)

with tab_drafts:
    left, right = st.columns(2)
    with left:
        st.markdown("### LinkedIn Posts")
        posts = load_drafts(LINKEDIN_DOC)
        if not posts:
            st.info("No LinkedIn drafts yet.")
        else:
            st.caption("%d draft(s) in %s" % (len(posts), LINKEDIN_DOC))
            for e in reversed(posts):
                with st.expander(e["heading"][:90] + ("..." if len(e["heading"]) > 90 else "")):
                    st.write(e["body"])
    with right:
        st.markdown("### Substack Essays")
        essays = load_drafts(SUBSTACK_DOC)
        if not essays:
            st.info("No Substack drafts yet.")
        else:
            st.caption("%d draft(s) in %s" % (len(essays), SUBSTACK_DOC))
            for e in reversed(essays):
                with st.expander(e["heading"][:90] + ("..." if len(e["heading"]) > 90 else "")):
                    st.write(e["body"])

with tab_trace:
    trace = load_trace()
    if not trace:
        st.info("No trace yet. It fills in as the agents make decisions.")
    else:
        st.caption("Last %d decisions from logs/agent_trace.jsonl" % len(trace))
        rows = []
        for r in trace:
            scores = r.get("scores") or {}
            decision = r.get("decision") or {}
            rows.append({
                "Time (UTC)": (r.get("timestamp", "") or "")[:19].replace("T", " "),
                "Agent": r.get("agent", ""),
                "Action": r.get("action", ""),
                "Passed": decision.get("passed", ""),
                "Voice": scores.get("voice_score", ""),
                "Tone": scores.get("tone", ""),
                "Intent": decision.get("intent", ""),
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)
