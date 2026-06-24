# Architecture — After Work Social Presence Agent

## Overview

Four specialized agents coordinated by an Orchestrator. Each agent has one job.
The user interacts in natural language; the Orchestrator routes the request.

```
                    USER (John) - reviews & posts
                            |
                       ORCHESTRATOR
            routes requests to the right agent(s)
            /          |           |            \
       SCOUT      STRATEGIST     WRITER       ANALYST
   web research   plan & calendar  draft     learn & adjust
        |              |            |            |
   Google Search   content history  voice    engagement
   grounding       + pillar state   guardrails  data store
```

## Agents

### Scout (Day 2 — tool use) [BUILT]
Finds trending topics in the psychology + AI + work space using Gemini with
Google Search grounding (`agents/scout.py`). Returns a JSON array of 3-5
topics with headline, source, relevance score, suggested angle, pillar, and
platform. Takes an optional topic to focus the search instead of scanning
broadly for what's trending. Uses `GEMINI_MODEL` (Flash), shared with future
agents, not the Writer's pro model.

### Strategist (Day 3 — context engineering / memory)
Plans what to publish, when, and where. Maintains persistent state: content
history, rolling 30-day pillar distribution, the upcoming calendar. Balances
pillars and platform cadence. Consumes Scout briefings and Analyst feedback.
Outputs a weekly content plan with per-day assignments.

### Writer (Day 4 — quality / guardrails) [PARTIALLY BUILT]
Drafts publication-ready content in John's voice (`agents/writer.py`). Loads
`voice_profile.py` and runs first-pass guardrails (`guardrails.py`): banned-
phrase scan, em-dash and curly-quote checks, negative-parallelism flags. Uses
its own model (`GEMINI_WRITER_MODEL`, pro-tier by default) since draft
quality matters most here. Still TODO: voice-consistency scoring
(LLM-as-a-judge against `REFERENCE_PASSAGES`), length enforcement per
platform, tone check, and the revise-and-recheck loop (up to 3 times).

### Analyst (Day 5 — observability / iteration)
Ingests engagement data (entered by John or via API later). Computes
performance per pillar/platform/format, compares against targets, and feeds
recommendations back to the Strategist. Produces a weekly summary report.

### Orchestrator
Top-level router. Maps natural-language requests to agents:
- "What should I publish this week?" -> Scout -> Strategist -> Writer
- "Write me a LinkedIn post about X" -> Writer
- "What's trending?" -> Scout
- "Here are last week's numbers" -> Analyst
- "Draft an essay reacting to [news]" -> Scout -> Writer

## Memory / state files (JSON in /memory)

- `content_history.json` — every post: title, date, pillar, platform, metrics
- `pillar_tracker.json` — rolling pillar distribution
- `calendar.json` — planned upcoming posts
- `engagement_data.json` — post-level metrics over time

## Tech stack

- **LLM:** Google Gemini via `google-genai` SDK. Model from `.env`
  (`gemini-2.5-flash` for speed; a `-pro` model optional for the Writer).
- **Web search:** Gemini Google Search grounding (built-in tool).
- **Memory:** JSON files for the prototype; Firestore optional for deploy.
- **Guardrails:** rule-based checks + Gemini as LLM-as-a-judge.
- **UI:** Streamlit.
- **Deploy:** Google Cloud Run (or run locally via Streamlit).

## File layout (target)

```
after-work-agent/
  .env                  (gitignored; key + model)
  .gitignore            [BUILT]
  requirements.txt
  voice_profile.py      [BUILT] voice + anti-AI-tell layers, guardrail data
  check_setup.py        [BUILT] lists available models, verifies key
  gemini_client.py      [BUILT] shared retry/error-handling call wrapper
  agents/
    __init__.py         [BUILT]
    writer.py           [BUILT] promoted from step1_writer.py; uses
                          GEMINI_WRITER_MODEL (pro-tier by default)
    scout.py            [BUILT] Google Search grounding, JSON topic briefing
    strategist.py       [TODO]
    analyst.py          [TODO]
    orchestrator.py     [TODO]
  guardrails.py         [BUILT] first-pass checks (banned phrase, em-dash,
                          curly quotes, parallelism flags); LLM-as-judge
                          voice/tone scoring still TODO (Step 6)
  memory/
    *.json              [TODO] state files
  app.py                [TODO] Streamlit UI
  STYLE_GUIDE.md        [BUILT] full voice + anti-AI reference
```
