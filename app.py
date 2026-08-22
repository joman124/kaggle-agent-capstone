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


def _bridge_secrets_to_env():
    """Make Streamlit Cloud secrets visible to the whole app.

    Locally, config lives in .env (loaded above). On Streamlit Community Cloud
    there is no .env -- it is gitignored and never deploys -- so config must be
    set in the app's Secrets (Settings -> Secrets, TOML format). Every module
    here reads os.getenv(...), so copy any string secret into os.environ before
    those reads happen. .env still wins for keys it already set (we only fill
    blanks), which keeps local behavior unchanged. Guarded because st.secrets
    raises when no secrets file exists (the normal local case)."""
    try:
        secrets = st.secrets
    except Exception:
        return
    try:
        for key, value in secrets.items():
            if isinstance(value, str) and not os.environ.get(key):
                os.environ[key] = value
    except Exception:
        pass


_bridge_secrets_to_env()

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
# Data helpers (read-only; no model calls, safe to run anytime)
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
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def render_draft_column(doc_path, platform):
    """One Drafts-tab column: every draft in an editable box, each with an
    'Add to queue' control that sends the edited text to the Approval Queue
    (where it can be published now or scheduled), plus a 'Mark as published'
    control that appends the publish event to memory/content_history.json --
    the write-back that lets the Strategist's rolling pillar balance see what
    actually went out."""
    from publish_log import is_published, mark_published
    import posts_ledger

    drafts = load_drafts(doc_path)
    if not drafts:
        st.info("No drafts yet in %s." % doc_path)
        return

    st.caption("%d draft(s) in %s" % (len(drafts), doc_path))

    # Headings are not unique: two drafts share one when neither day had a
    # Scout topic, so both fall back to "<pillar> -- <date>". Number the
    # repeats to get a per-draft id that is unique (Streamlit widget keys
    # must be) and stable (counted in document order, so appending a new
    # draft never renumbers the existing ones -- a positional index over the
    # reversed list would shift every key and scatter in-progress edits).
    seen = {}
    for e in drafts:
        n = seen.get(e["heading"], 0) + 1
        seen[e["heading"]] = n
        e["uid"] = "%s #%d" % (e["heading"], n)

    # Guess each draft's pillar from the calendar: the Orchestrator uses the
    # day's topic (or bare pillar name) as the docx heading, so a match here
    # recovers the pillar the Strategist assigned. Ad-hoc drafts won't match
    # and fall back to a manual pick.
    topic_to_pillar = {}
    for d in load_calendar():
        key = d.get("topic") or d.get("pillar")
        if key:
            topic_to_pillar[key] = d.get("pillar")

    # Which drafts are already in the queue, so one cannot be added twice.
    # Read off the ledger itself rather than kept in a second state file, so
    # there is nothing to fall out of sync. A rejected item can be requeued.
    # Matched on the uid above, not the topic: days with no Scout topic use
    # the bare pillar name, so two weeks' "Clinical Window" drafts share a
    # topic and queueing one would wrongly lock the other.
    in_ledger = {}
    for r in posts_ledger.load():
        if r.get("source") and r.get("status") != "rejected":
            in_ledger[r["source"]] = r.get("status")

    for e in reversed(drafts):
        label = e["heading"][:90] + ("..." if len(e["heading"]) > 90 else "")
        topic = e["heading"].rsplit(" -- ", 1)[0]
        with st.expander(label):
            # Editable, so John can rewrite before queueing -- what the button
            # below queues is whatever is in this box.
            edited = st.text_area(
                "Draft", value=e["body"], height=320,
                key="draft-%s-%s" % (platform, e["uid"]),
                label_visibility="collapsed",
            )

            queued_status = in_ledger.get(e["uid"])
            if queued_status:
                st.info("Already in the Approval Queue (status: %s). Publish "
                        "or schedule it from that tab." % queued_status)
            elif st.button("Add to queue", type="primary", width="stretch",
                           key="queue-%s-%s" % (platform, e["uid"])):
                posts_ledger.add(topic, edited, platform,
                                 pillar=topic_to_pillar.get(topic),
                                 source=e["uid"])
                st.rerun()

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
                        key="pillar-%s-%s" % (doc_path, e["uid"]),
                        label_visibility="collapsed",
                    )
                with col_b:
                    if st.button(
                        "Mark as published",
                        key="publish-%s-%s" % (doc_path, e["uid"]),
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
        st.success("ANTHROPIC_API_KEY loaded")
    else:
        st.error("No ANTHROPIC_API_KEY found. Live runs are disabled.")
        st.caption(
            "Local: put it in .env, then restart. Deployed (Streamlit Cloud): "
            "add it under Settings -> Secrets as  ANTHROPIC_API_KEY = \"...\"  "
            "(the app reboots automatically). Read-only views still work.")

    st.write("**Models**")
    st.write("- Agents / judge: `%s`" % (os.getenv("ANTHROPIC_MODEL") or "claude-opus-5"))
    st.write("- Writer: `%s`" % (os.getenv("ANTHROPIC_WRITER_MODEL") or "claude-opus-5"))

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
    st.divider()
    st.header("LinkedIn posting")

    import publish_settings

    mode = publish_settings.status()
    if not mode["ready"]:
        st.error("No LinkedIn token yet. Run: python linkedin_auth.py")
        st.caption("Publishing stays disabled until a token and actor URN exist.")
    elif mode["live"]:
        st.warning("LIVE - approved posts really publish")
    else:
        st.info("DRY RUN - nothing publishes")

    if mode["ready"]:
        want_live = st.toggle(
            "Enable live posting", value=mode["live"], key="live-toggle",
            help=("Off means every publish is simulated. On means Publish now "
                  "and scheduled posts really go to your LinkedIn profile."),
        )
        if want_live != mode["live"]:
            # Only trust an explicit confirmation for the dangerous direction.
            if want_live:
                st.warning("This lets posts publish publicly as you.")
                if st.button("Yes, turn live posting on", type="primary",
                             width="stretch", key="confirm-live"):
                    publish_settings.set_live(True)
                    st.rerun()
            else:
                publish_settings.set_live(False)
                st.rerun()
        st.caption("Posting as `%s`" % mode["actor"])

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
        "A full weekly plan makes many live model calls (Scout, then the "
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
            # anthropic_client raises SystemExit with a plain-English message on
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
tab_plan, tab_queue, tab_drafts, tab_perf, tab_voice, tab_trace = st.tabs(
    ["This Week's Plan", "Approval Queue", "Drafts", "Performance", "Voice Rules", "Agent Trace"]
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
    from datetime import datetime, time as dtime, timedelta, timezone

    import posts_ledger
    import publish_settings
    import review

    live_mode = publish_settings.status()

    def _to_utc_iso(day, clock):
        """Combine a local date + time from the pickers into a UTC timestamp.
        A naive datetime's .astimezone() assumes local time, which is exactly
        what John typed, so this converts rather than mislabels."""
        naive = datetime.combine(day, clock)
        return naive.astimezone().astimezone(timezone.utc).isoformat()

    def _local_label(timestamp):
        parsed = posts_ledger._parse(timestamp)
        return parsed.astimezone().strftime("%a %d %b, %H:%M") if parsed else "?"

    queued = posts_ledger.by_status("queued")
    st.caption(
        "Reactions waiting for you. LinkedIn items can be published now or "
        "scheduled; Substack has no API, so approving one just marks it done "
        "for you to paste in. %d item(s) queued." % len(queued)
    )
    if not live_mode["live"]:
        st.info(
            "DRY RUN is on, so Publish now is simulated and scheduled posts "
            "stay put until you go live (they are not consumed). Turn on live "
            "posting in the sidebar when you are ready."
        )

    if not queued:
        st.info("Nothing queued. Use 'Fast reaction' above, or run the cycle.")

    for r in reversed(queued):
        rid = r["id"]
        head = "[%s] %s" % (r["platform"], r["topic"])
        with st.expander(head[:100]):
            # Editable: every button below saves whatever is in this box
            # first (matching what you see is what publishes), and each
            # save is logged to memory/edit_history.json for the Voice
            # Rules tab -- so a pattern in what you change by hand can be
            # turned into a permanent rule later.
            edited = st.text_area(
                "Edit before publishing",
                value=r.get("text") or "",
                height=220,
                key="edit-%s" % rid,
                label_visibility="collapsed",
            )
            if st.button("Save edits", key="sv-%s" % rid, width="stretch"):
                res = review.edit_item(rid, edited)
                (st.success if res["ok"] else st.error)(res["msg"])
                st.rerun()
            st.divider()

            if r["platform"] != "linkedin":
                # Substack: mark done, paste it yourself.
                done, rej = st.columns(2)
                with done:
                    if st.button("Mark as done", key="ap-%s" % rid, width="stretch"):
                        saved = review.edit_item(rid, edited)
                        if not saved["ok"]:
                            st.error(saved["msg"])
                        else:
                            result = review.approve_item(rid)
                            (st.success if result["ok"] else st.error)(result["msg"])
                            st.rerun()
                with rej:
                    if st.button("Reject", key="rj-%s" % rid, width="stretch"):
                        review.reject_item(rid)
                        st.rerun()
                continue

            st.markdown("**Publish now**")
            confirm = True
            if live_mode["live"]:
                confirm = st.checkbox(
                    "Yes - post this to my LinkedIn profile now",
                    key="cf-%s" % rid,
                )
            now_col, rej_col = st.columns(2)
            with now_col:
                label = "Publish now" if live_mode["live"] else "Publish now (simulated)"
                # Credentials are only required to post for real. A dry run
                # needs none, so simulating stays available before OAuth setup.
                blocked = live_mode["live"] and not live_mode["ready"]
                if st.button(label, key="ap-%s" % rid, type="primary",
                             width="stretch",
                             disabled=not confirm or blocked):
                    saved = review.edit_item(rid, edited)
                    if not saved["ok"]:
                        st.error(saved["msg"])
                    else:
                        result = review.approve_item(rid)
                        (st.success if result["ok"] else st.error)(result["msg"])
                        st.rerun()
            with rej_col:
                if st.button("Reject", key="rj-%s" % rid, width="stretch"):
                    review.reject_item(rid)
                    st.rerun()

            st.markdown("**Or schedule it**")
            default_at = (datetime.now().astimezone() + timedelta(hours=1)).replace(
                minute=0, second=0, microsecond=0)
            d_col, t_col, s_col = st.columns([2, 2, 2])
            with d_col:
                day = st.date_input("Date", value=default_at.date(),
                                    key="sd-%s" % rid)
            with t_col:
                clock = st.time_input("Time", value=dtime(default_at.hour, 0),
                                      key="st-%s" % rid)
            with s_col:
                st.write("")
                if st.button("Schedule", key="sc-%s" % rid, width="stretch",
                             disabled=live_mode["live"] and not live_mode["ready"]):
                    when_utc = _to_utc_iso(day, clock)
                    if posts_ledger._parse(when_utc) <= datetime.now(timezone.utc):
                        st.error("That time is in the past. Pick a future time.")
                    else:
                        saved = review.edit_item(rid, edited)
                        if not saved["ok"]:
                            st.error(saved["msg"])
                        else:
                            result = review.schedule_item(rid, when_utc)
                            (st.success if result["ok"] else st.error)(result["msg"])
                            if result["ok"]:
                                st.rerun()
            st.caption("Your local time. Scheduled posts fire from this PC, so "
                       "it needs to be on and online at that moment.")

    # ---- Scheduled / failed / missed ---------------------------------------
    st.divider()
    st.subheader("Scheduled")
    upcoming = posts_ledger.scheduled()
    if not upcoming:
        st.caption("Nothing scheduled.")
    for r in upcoming:
        with st.expander("%s  -  %s" % (_local_label(r.get("scheduled_for")),
                                        r["topic"][:70])):
            st.write(r.get("text") or "")
            if st.button("Cancel schedule", key="cx-%s" % r["id"]):
                result = review.cancel_schedule(r["id"])
                (st.success if result["ok"] else st.error)(result["msg"])
                st.rerun()

    # "publishing" means a run claimed the item and then died before it could
    # record the outcome. It is listed here so it cannot silently disappear.
    problems = (posts_ledger.by_status("failed") + posts_ledger.by_status("missed")
                + posts_ledger.by_status("publishing"))
    if problems:
        st.subheader("Needs attention")
        for r in problems:
            st.warning("**%s** (%s): %s" % (r["id"], r["status"],
                                            r.get("error") or "no detail"))
            if r["status"] in ("failed", "publishing"):
                st.caption(
                    "Check your LinkedIn profile before requeuing this one. If "
                    "the connection dropped after LinkedIn accepted the post, it "
                    "may already be live, and requeuing would post it twice."
                )
            if st.button("Put back in queue", key="rq-%s" % r["id"]):
                result = review.requeue_item(r["id"])
                (st.success if result["ok"] else st.error)(result["msg"])
                if result["ok"]:
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

with tab_voice:
    import voice_learnings

    st.caption(
        "Permanent feedback on how the agents should write. Every rule here is "
        "injected into the system prompt for every future LinkedIn post, essay, "
        "and reaction -- add a rule once and it applies to every draft from now "
        "on, not just the one you are looking at. No API call needed to save one."
    )

    learnings = voice_learnings.load_learnings()
    if not learnings:
        st.info("No permanent voice rules yet. Add the first one below.")
    else:
        st.caption("%d rule(s) in effect." % len(learnings))
        for entry in reversed(learnings):
            enforced = entry.get("banned_snippets") or entry.get("regex_patterns")
            tag = "hard-blocked, forces a redraft" if enforced else "prompt guidance"
            with st.expander("%s -- %s (%s)" % (entry["id"], entry["date"], tag)):
                st.write(entry["rule"])
                if entry.get("banned_snippets"):
                    st.caption("Exact phrases blocked: " + ", ".join(entry["banned_snippets"]))
                if entry.get("regex_patterns"):
                    st.caption("%d pattern(s) also force a redraft on a match."
                               % len(entry["regex_patterns"]))

    st.divider()
    st.markdown("### Add a permanent rule")
    with st.form("add_voice_rule", clear_on_submit=True):
        rule_text = st.text_area(
            "Rule (plain English)",
            placeholder="e.g. Do not open a post by naming the pillar out loud.",
        )
        snippets = st.text_input(
            "Also hard-block these exact phrases (comma-separated, optional)",
            placeholder="e.g. at the end of the day, circle back",
        )
        submitted = st.form_submit_button("Save rule")
    if submitted:
        if not rule_text.strip():
            st.error("Rule text cannot be empty.")
        else:
            snippet_list = [s.strip() for s in snippets.split(",") if s.strip()]
            entry = voice_learnings.add_learning(rule_text.strip(), banned_snippets=snippet_list)
            st.success("Saved as %s. It applies to every draft from now on." % entry["id"])
            st.rerun()

    st.divider()
    st.markdown("### Recent manual edits")
    st.caption(
        "What you actually changed before approving a reaction in the Approval "
        "Queue tab. Look for a pattern here, then write it up as a rule above."
    )
    edit_path = os.path.join("memory", "edit_history.json")
    edits = []
    if os.path.exists(edit_path):
        try:
            with open(edit_path, "r", encoding="utf-8") as fh:
                edits = json.load(fh)
        except (json.JSONDecodeError, OSError):
            edits = []
    if not edits:
        st.info("No edits logged yet. Editing a queued item in Approval Queue logs it here.")
    else:
        for e in reversed(edits[-10:]):
            with st.expander("%s -- %s" % (e.get("record_id", ""), e.get("date", ""))):
                st.write("**Before**")
                st.text(e.get("before", ""))
                st.write("**After**")
                st.text(e.get("after", ""))

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
