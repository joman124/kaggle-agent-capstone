# After Work: Social Presence Agent

A multi-agent AI system that researches, plans, drafts, and optimizes social
media content for John Mansoor, PsyD -- a clinical psychologist and author of
*After Work*, a book about the psychological cost of AI displacing human labor.

The system finds what is trending, plans a balanced week of content, drafts
every post in John's voice through a guardrail-and-judge loop, and learns from
engagement data. **John reviews and posts. The system does everything else.**

Built for the Kaggle **AI Agents: Intensive Vibe Coding Capstone** (Agents for
Business track). The full project report is in [`WRITEUP.md`](WRITEUP.md).

## How it works

```
                    USER (John) -- reviews & posts
                            |
                       ORCHESTRATOR
            routes requests to the right agent(s)
       /        |          |           |            \
   SCOUT   STRATEGIST    WRITER     SUBSTACK       ANALYST
   web      plan &      draft      SPECIALIST     learn &
   research calendar    posts      expands a       adjust
     |         |          |        LinkedIn post     |
  Google    content     voice      into an essay   engagement
  Search    history +   guard-         |            data store
  grounding pillar      rails      voice guardrails
            state
```

One natural-language request -- *"What should I publish this week?"* -- runs
the whole pipeline and leaves a week of in-voice drafts in Word documents,
ready for human review.

## Course concepts demonstrated

| Concept | Where |
|--------|-------|
| Agentic architecture (multi-agent) | `agents/orchestrator.py` + 5 agents |
| Tool use / interoperability | `agents/scout.py` (Google Search grounding) |
| Context engineering: memory & state | `agents/strategist.py` + `memory/*.json` |
| Quality: guardrails & evaluation | `guardrails.py` + `voice_profile.py` (rules + LLM-as-a-judge) |
| Prototype to production | `observability.py` (JSONL trace), `run_weekly.bat` (scheduled runs), `app.py` (Streamlit UI) |

## Quickstart

Requires Python 3.11+ and a Google Gemini API key
(free at https://aistudio.google.com).

```
python -m venv venv
venv\Scripts\activate          # Windows (source venv/bin/activate elsewhere)
pip install -r requirements.txt
copy .env.example .env         # then put your GEMINI_API_KEY in .env
python check_setup.py          # verifies the key and lists available models
```

Run the UI:

```
streamlit run app.py
```

Or drive it from the command line:

```
python -m agents.orchestrator "What should I publish this week?"
python -m agents.orchestrator "Write me a LinkedIn post about burnout"
python -m agents.orchestrator "What's trending?"
```

Drafts are saved to `LinkedIn Posts.docx` and `Substack Essays.docx`. Every
agent decision is logged to `logs/agent_trace.jsonl`.

## Repository map

| File | Role |
|------|------|
| `app.py` | Streamlit UI: request box + plan/drafts/trace views |
| `agents/orchestrator.py` | Routes natural-language requests; logs decisions |
| `agents/scout.py` | Google Search grounding -> JSON trend briefing |
| `agents/strategist.py` | Pillar/platform planning over memory state (pure logic) |
| `agents/writer.py` | Drafts LinkedIn posts through the guardrail loop |
| `agents/substack_specialist.py` | Expands a post into a long-form essay |
| `agents/analyst.py` | Engagement scoring -> pillar adjustments (pure logic) |
| `guardrails.py` | First-pass checks + LLM-as-judge + generate-evaluate-revise loop |
| `voice_profile.py` | Voice prompt, anti-AI-tell prompt, banned phrases, patterns |
| `gemini_client.py` | Shared retry/error-handling Gemini wrapper |
| `observability.py` | JSONL decision trace |
| `doc_output.py` | Saves drafts into Word documents for review |
| `memory/` | Content history, pillar tracker, calendar, engagement data |
| `STYLE_GUIDE.md` | Full voice + anti-AI-tell reference |
| `WRITEUP.md` | Kaggle project report |

## Project docs (development history)

`PROJECT_BRIEF.md`, `ARCHITECTURE.md`, `BUILD_PLAN.md`, `STATUS.md`,
`CAPSTONE_REQUIREMENTS.md`, and `PUBLISHING_HANDOFF.md` document how the
project was planned and built, including the honest dead ends. They are kept
in the repo deliberately -- this project was built by vibe coding, and the
paper trail is part of the story.
