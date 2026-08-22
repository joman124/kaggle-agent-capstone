# Capstone Requirements — Kaggle AI Agents Vibe Coding

## Competition

- **Name:** AI Agents: Intensive Vibe Coding Capstone Project
- **Deadline:** July 6, 2026, 11:59 PM PT
- **Recommended track:** Agents for Business (automates a real content-marketing
  workflow for an author-entrepreneur). Concierge Agents is a secondary fit.

## Four required deliverables

1. **Kaggle Writeup** — the project report; judges read this first.
2. **Public codebase** — GitHub repo and/or public Kaggle Notebook.
3. **Video demonstration** — 3-5 minutes.
4. **Project link** — the deployed/working app.

## Scoring rubric

### Category 1: The Pitch — problem, solution, value (30 pts)
- **Problem:** expert-author with no platform; agents won't take the book
  seriously without one; no time/skill to run content marketing; thesis is
  time-sensitive.
- **Solution:** four-agent system that researches, plans, drafts in-voice, and
  optimizes content. John reviews and posts.
- **Value:** a real production tool used by a real person. The irony sells it: a
  psychologist writing about AI displacing human work builds an AI to handle his
  own marketing.

### Category 2: The Implementation — architecture, code (70 pts)
Must demonstrate at least 3 course concepts; this project hits 5:

| Concept | Day | Where |
|--------|-----|-------|
| Agentic architecture (multi-agent) | 1 | Orchestrator + 4 agents |
| Tool use / interoperability | 2 | Scout: Claude server-side web search |
| Context engineering: memory & state | 3 | Strategist: history + pillar state |
| Quality: guardrails & evaluation | 4 | Writer: voice scoring, banned phrases, tone |
| Prototype to production | 5 | Streamlit + Cloud Run + observability |

## Writeup outline (mirror the rubric)

1. **The Problem** (Pitch) — who it's for; the platform trap; the irony.
2. **The Solution** — architecture overview + diagram; per-agent rationale; the
   user experience ("what should I publish this week?" -> full package).
3. **Key Course Concepts Applied** — each concept, how it was implemented, what
   was learned.
4. **Technical Architecture** — framework, tools, memory design, guardrail
   pipeline, observability.
5. **Results & Demo** — UI screenshots; generated content vs. John's real
   writing; guardrail catches; early engagement data if available.
6. **What I Learned** — honest reflection; how vibe coding shaped the build;
   future directions (direct-publish APIs, A/B testing, cross-platform analytics).

## Video script (3-5 min, timed)

1. (30s) The problem. "I'm a clinical psychologist writing a book about AI
   displacing human work. Agents told me I need a platform. I don't have one,
   and I don't have time to become a content marketer. So I built an AI system
   to do it."
2. (30s) The irony. A psychologist writing about AI taking over human functions
   built an AI to take over his marketing function. That tension is in the book.
3. (60s) Architecture. Walk the diagram. Four agents + orchestrator: Scout finds
   what's trending, Strategist plans the calendar, Writer drafts in my voice,
   Analyst learns from what works.
4. (60s) Live demo. Type "what should I publish this week?" Show the pipeline
   run and the content package returned.
5. (45s) The guardrails. "The hard part wasn't making it write. It was making it
   write like me." Show a generic draft vs. the guardrail-enforced version and
   the voice-consistency score.
6. (30s) Course concepts. Quick list of the five.
7. (15s) Close. "This isn't a demo. I'm using it. The first posts on my Substack
   were drafted by this system. The book is After Work. The agent is building
   the platform to sell it."

## Notes

- The closing line must be TRUE at submission. By Step 11, publish a few real
  posts so the demo is genuine, not staged.
- Keep the codebase clean and commented; judges read it.
