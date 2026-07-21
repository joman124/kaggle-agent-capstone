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


def render_draft_column(doc_path, platform):
    """One Drafts-tab column: every draft in an expander, each with a
    'Mark as published' control that appends the publish event to
    memory/content_history.json -- the write-back that lets the
    Strategist's rolling pillar balance see what actually went out."""
    from publish_log import is_published, mark_published

    drafts = load_drafts(doc_path)
    if not drafts:
        st.info("No drafts yet in %s." % doc_path)
        return

    st.caption("%d draft(s) in %s" % (len(drafts), doc_path))

    # Guess each draft's pillar from the calendar: the Orchestrator uses the
    # day's topic (or bare pillar name) as the docx heading, so a match here
    # recovers the pillar the Strategist assigned. Ad-hoc drafts won't match
    # and fall back to a manual pick.
    topic_to_pillar = {}
    for d in load_calendar():
        key = d.get("topic") or d.get("pillar")
        if key:
            topic_to_pillar[key] = d.get("pillar")

    for i, e in enumerate(reversed(drafts)):
        label = e["heading"][:90] + ("..." if len(e["heading"]) > 90 else "")
        with st.expander(label):
            st.write(e["body"])
            st.divider()
            if is_published(e["heading"]):
                st.success("Published -- recorded in content history.")
            else:
                topic = e["heading"].rsplit(" -- ", 1)[0]
                guess = topic_to_pillar.get(topic)
                default_idx = PILLARS.index(guess) if guess in PILLARS else 0
                col_p, col_b = st.columns([2, 1])
                with col_p:
                    pillar = st.selectbox(
                        "Pillar", PILLARS, index=default_idx,
                        key="pillar-%s-%d" % (doc_path, i),
                        label_visibility="collapsed",
                    )
                with col_b:
                    if st.button(
                        "Mark as published",
                        key="publish-%s-%d" % (doc_path, i),
                        width="stretch",
                    ):
                        mark_published(e["heading"], pillar, platform)
                        st.rerun()


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
    st.header("The agents")
    st.markdown(
        "1. **Scout** - Google Search grounding, finds trends\n"
        "2. **Strategist** - plans the week over memory state\n"
        "3. **Writer** - drafts in-voice through guardrails\n"
        "4. **Substack Specialist** - expands posts into essays\n"
        "5. **Analyst** - learns from engagement, adjusts pillars\n"
        "6. **Viral** - fast hot-topic reactions, auto-posts to LinkedIn"
    )
    # Live/dry-run switch. Seed from .env once, then this toggle owns it for the
    # session. We re-apply to os.environ on every rerun because load_dotenv(
    # override=True) at the top would otherwise reset it to the .env value, and
    # the publisher reads LINKEDIN_DRY_RUN from the environment at post time.
    if "linkedin_live" not in st.session_state:
        st.session_state.linkedin_live = (
            os.getenv("LINKEDIN_DRY_RUN", "true").strip().lower() == "false"
        )
    # Bound by key (no value=): the widget's state lives in session_state under
    # "linkedin_live", so flipping it either way sticks.
    st.toggle(
        "Post to LinkedIn for real",
        key="linkedin_live",
        help=(
            "OFF = DRY RUN: the agent builds and logs the exact post but sends "
            "nothing (the safe default). ON = approving an item posts it live to "
            "LinkedIn. Needs a LinkedIn token in .env -- see LINKEDIN_SETUP.md."
        ),
    )
    os.environ["LINKEDIN_DRY_RUN"] = (
        "false" if st.session_state.linkedin_live else "true"
    )
    if st.session_state.linkedin_live:
        if os.getenv("LINKEDIN_ACCESS_TOKEN", "").strip():
            st.warning("LIVE: approving an item will post it to LinkedIn.")
        else:
            st.error(
                "LIVE is on but no LINKEDIN_ACCESS_TOKEN in .env -- posting will "
                "fail. See LINKEDIN_SETUP.md, or switch the toggle off."
            )
    else:
        st.caption("DRY RUN: nothing posts. Flip the toggle on to go live.")
    st.caption("This toggle lasts for the session; .env sets the startup default.")
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
    run = st.button("Run", type="primary", width="stretch", disabled=not has_api_key())

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

# ---- Fast reaction: draft a hot-topic post into the approval queue ---------
st.subheader("Fast reaction")
st.caption(
    "React to a hot topic now. Each reaction is drafted best-of-N (voice + "
    "engagement scored) and lands in the Approval Queue below -- nothing posts "
    "to LinkedIn until you approve it."
)
rc_a, rc_b, rc_c = st.columns([3, 1, 1])
with rc_a:
    hot = st.text_input(
        "Hot topic", label_visibility="collapsed",
        placeholder="e.g. a study says AI writes most first-draft code",
    )
with rc_b:
    draft_btn = st.button("Draft + queue", width="stretch", disabled=not has_api_key())
with rc_c:
    cycle_btn = st.button("Auto: find + queue", width="stretch", disabled=not has_api_key())

if draft_btn and hot.strip():
    with st.spinner("Drafting best-of reaction and queuing..."):
        try:
            import run_cycle
            res = run_cycle.queue_topic(hot.strip())
            note = "" if res.get("safe", True) else " (flagged sensitive -- review carefully)"
            st.success("Queued %d item(s) for review%s. See the Approval Queue tab."
                       % (len(res["queued"]), note))
        except SystemExit as exc:
            st.error(str(exc))
        except Exception as exc:  # noqa: BLE001
            st.error("Failed: %s" % exc)

if cycle_btn:
    with st.spinner("Scouting hot topics, ranking, drafting the best one..."):
        try:
            import run_cycle
            res = run_cycle.run()
            if res.get("queued"):
                st.success("Reacted to '%s' and queued %d item(s). See the "
                           "Approval Queue tab." % (res.get("topic", ""), len(res["queued"])))
            else:
                st.warning("Nothing queued: %s" % res.get("reason", "(no topics)"))
        except SystemExit as exc:
            st.error(str(exc))
        except Exception as exc:  # noqa: BLE001
            st.error("Failed: %s" % exc)

st.divider()

# ---- Tabs: real state, no API calls ---------------------------------------
tab_plan, tab_queue, tab_drafts, tab_perf, tab_trace = st.tabs(
    ["This Week's Plan", "Approval Queue", "Drafts", "Performance", "Agent Trace"]
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
        st.dataframe(rows, width="stretch", hide_index=True)

with tab_queue:
    import posts_ledger
    import review

    queued = posts_ledger.by_status("queued")
    st.caption(
        "Reactions waiting for your approval. Edit the text right here, then "
        "approve: **Approve + post** publishes exactly what is in the box "
        "(honors LINKEDIN_DRY_RUN), so you can autopost everything from the "
        "dashboard. A Substack Note is marked done for you to paste in. "
        "%d item(s) queued." % len(queued)
    )
    if not queued:
        st.info("Nothing queued. Use 'Fast reaction' above, or run the cycle.")
    for r in reversed(queued):
        head = "[%s] %s" % (r["platform"], r["topic"])
        with st.expander(head[:100]):
            edited = st.text_area(
                "Edit before posting",
                value=r.get("text") or "",
                height=220,
                key="edit-%s" % r["id"],
            )
            st.caption("%d characters" % len(edited))
            with st.expander("Copy for manual posting"):
                st.caption(
                    "Use the copy icon at the top-right of the box below, then "
                    "paste it into LinkedIn (or Substack) yourself. Handy while "
                    "auto-posting is off or the API is still pending."
                )
                st.code(edited or "", language=None)
            sv, ap, rj = st.columns(3)
            with sv:
                if st.button("Save edits", key="sv-%s" % r["id"], width="stretch"):
                    res = review.edit_item(r["id"], edited)
                    (st.success if res["ok"] else st.error)(res["msg"])
                    st.rerun()
            with ap:
                if st.button("Approve + post", key="ap-%s" % r["id"], width="stretch"):
                    # Save whatever is in the box first, so we post the edited
                    # version, then publish.
                    saved = review.edit_item(r["id"], edited)
                    if not saved["ok"]:
                        st.error(saved["msg"])
                    else:
                        try:
                            result = review.approve_item(r["id"])
                        except SystemExit as exc:
                            # publisher raises this with a plain-English message
                            # (e.g. no token while live). Show it, do not crash.
                            result = {"ok": False, "msg": str(exc)}
                        except Exception as exc:  # noqa: BLE001
                            result = {"ok": False, "msg": "Post failed: %s" % exc}
                        (st.success if result["ok"] else st.error)(result["msg"])
                        if result["ok"]:
                            st.rerun()
            with rj:
                if st.button("Reject", key="rj-%s" % r["id"], width="stretch"):
                    review.reject_item(r["id"])
                    st.rerun()

with tab_drafts:
    st.caption(
        "After you post a draft to the real platform, mark it published here. "
        "That writes it to content history, so next week's plan balances "
        "pillars against what actually went out instead of starting from zero."
    )
    left, right = st.columns(2)
    with left:
        st.markdown("### LinkedIn Posts")
        render_draft_column(LINKEDIN_DOC, "linkedin")
    with right:
        st.markdown("### Substack Essays")
        render_draft_column(SUBSTACK_DOC, "substack")

with tab_perf:
    import posts_ledger
    import analytics
    import linkedin_metrics

    st.caption(
        "What actually landed. Sync pulls real reactions/comments from LinkedIn "
        "into the ledger; the multipliers then nudge which pillars the reaction "
        "cycle favors."
    )
    if st.button("Sync LinkedIn metrics", disabled=not has_api_key()):
        with st.spinner("Pulling engagement from LinkedIn..."):
            try:
                summary = linkedin_metrics.sync_ledger()
                st.success("Synced %d of %d posted item(s). %s"
                           % (summary.get("updated", 0), summary.get("candidates", 0),
                              summary.get("note", "")))
            except Exception as exc:  # noqa: BLE001
                st.error("Sync failed: %s" % exc)

    perf = analytics.summarize()
    mult = analytics.performance_multipliers()
    posted = posts_ledger.by_status("posted")
    st.write("**Posts on record:** %d" % len(posted))
    if not perf:
        st.info("No posted content yet. Approve some reactions, then sync metrics.")
    else:
        rows = []
        for pillar, s in perf.items():
            rows.append({
                "Pillar": pillar,
                "Posts": s["posts"],
                "With metrics": s["with_metrics"],
                "Avg engagement": s["avg_engagement"],
                "Ranking multiplier": mult.get(pillar, 1.0),
            })
        st.dataframe(rows, width="stretch", hide_index=True)

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
                "Engagement": scores.get("engagement_score", ""),
                "Tone": scores.get("tone", ""),
                "Intent": decision.get("intent", ""),
            })
        st.dataframe(rows, width="stretch", hide_index=True)
