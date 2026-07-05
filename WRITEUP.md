# After Work: An AI Agent That Builds an Author's Platform

**Kaggle AI Agents -- Intensive Vibe Coding Capstone**
Track: Agents for Business
Author: John Mansoor, PsyD

---

## 1. The Problem

I am a clinical psychologist writing a book called *After Work: Finding Meaning,
Identity, and Purpose When the World No Longer Needs Your Labor*. The book's
thesis is that work has been humanity's psychological infrastructure for
millennia -- structure, competence, belonging, identity, meaning -- and that AI
is dismantling that infrastructure faster than anyone is prepared for.

To sell a book like this, you need an author platform. Literary agents look for
one before they will take a first-time author seriously; readers find you
through it. I had none. No public presence, no marketing background, no time to
become a content marketer, and a credibility that is clinical rather than
promotional. Writing a good LinkedIn post is a different skill than running a
therapy session, and the thesis is time-sensitive -- the AI-and-work
conversation is happening now.

There is an irony that sits at the center of this project, and it is the same
tension the book is about: a psychologist writing about AI displacing human
labor built an AI to displace his own marketing labor. I built a tool I actually 
use, and I felt the exact thing my patients describe
while building it.

## 2. The Solution

A multi-agent system that researches, plans, drafts in my voice, and learns
from what performs. I ask it one question in plain English -- *"What should I
publish this week?"* -- and it returns a full, review-ready content package:
a week of LinkedIn posts and Substack essays, drafted in my voice, saved to
Word documents I read and post from. **I review and post. The system does
everything else.**

The human stays in the loop by design. The whole point of the voice-guardrail
system is that nothing goes out that does not sound like me, so a human
approval gate is a feature rather than a limitation.

### Architecture

Five specialized agents coordinated by an Orchestrator. Each agent does one job.

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

- **Scout** finds what is trending in the psychology + AI + work space using
  Gemini with Google Search grounding, and returns a structured briefing.
- **Strategist** plans the week -- which content pillar, which platform, which
  day -- balancing coverage over a rolling 30-day window. Pure logic, no LLM.
- **Writer** drafts each post in my voice, through a generate-evaluate-revise
  guardrail loop.
- **Substack Specialist** expands a LinkedIn post into a long-form essay
  through the same guardrail loop with looser platform rules.
- **Analyst** reads engagement data, scores each pillar against a target, and
  feeds adjustments back to the Strategist so the system learns. Pure logic.

The user experience: one natural-language request runs the whole pipeline
(Scout -> Analyst -> Strategist -> Writer -> Substack Specialist) and produces
a week of drafts waiting for review.

## 3. Key Course Concepts Applied

The rubric asks for at least three course concepts. This project implements
five, one per day of the course.

| Concept | Where it lives | What it does |
|--------|----------------|--------------|
| **Agentic architecture (multi-agent)** | `agents/orchestrator.py` + 5 agents | An Orchestrator routes a natural-language request to a pipeline of single-responsibility agents. Routing is deterministic keyword-matching, so it is fully unit-tested without an API key. |
| **Tool use / interoperability** | `agents/scout.py` | Scout calls Gemini with the built-in Google Search grounding tool (`types.Tool(google_search=...)`) to pull real, current headlines rather than hallucinated ones. |
| **Context engineering: memory & state** | `agents/strategist.py`, `memory/*.json` | State lives in JSON: content history, a rolling pillar tracker, the calendar, engagement data. The Strategist reads and writes this state to keep pillar coverage balanced over time. |
| **Quality: guardrails & evaluation** | `guardrails.py`, `voice_profile.py` | A two-layer voice system plus a generate-evaluate-revise loop: rule-based first-pass checks (47 banned phrases, em-dash and curly-quote limits, antithesis-pattern detection) AND an LLM-as-a-judge that scores voice 0-10 and tone against reference passages from the book. Rejects below 7 trigger up to 3 redrafts with the judge's feedback fed forward. |
| **Prototype to production** | `observability.py`, `run_weekly.bat`, Streamlit/Cloud Run | Every routing and draft decision is logged as JSONL to `logs/agent_trace.jsonl`. A scheduled Windows task runs the weekly batch unattended and writes a plain-English success/failure status file. |

### What I learned building the guardrails

The hard part was getting it to *not* sound like AI. Generic model output leans 
on a recognizable set of tells: em-dash pile-ups, rule-of-three padding, the word "quietly," and the
"it's not X, it's Y" antithesis frame. My first guardrail only *flagged* those
for review, and the antithesis structure kept leaking through. So I made it a
hard failure: seven regexes detect the reversal frame, and any match forces a
rewrite with an explicit instruction, while still allowing my own trailing
negations that are part of my real voice. Getting the machine to strip its own
fingerprints turned out to be a more interesting problem than getting it to
generate.

## 4. Technical Architecture

- **LLM:** Google Gemini via the `google-genai` SDK. Model names live in `.env`.
  The Writer and Substack Specialist use a pro-tier model
  (`GEMINI_WRITER_MODEL`) because draft quality matters most there; every other
  agent, including the voice judge, uses Flash (`GEMINI_MODEL`) because routing,
  scouting, and evaluation do not need the pro tier. The judge always runs at
  temperature 0 so a given draft scores consistently; generation temperature is
  tuned per content type (essays cooler at 0.6, LinkedIn 0.8, short notes 0.95).
- **Tool use:** Gemini Google Search grounding for Scout. Because grounding runs
  on a thinking model, Scout disables the thinking budget on that call -- an
  early bug where the model spent its entire token budget on internal reasoning
  and returned empty text taught me to guard `response.text` for `None` and fail
  with a clear, diagnosable message instead of a raw traceback.
- **Memory:** JSON files for the prototype (`memory/`), with a clear path to
  Firestore for deployment.
- **Guardrails:** a shared `draft_with_guardrails()` generate-evaluate-revise
  loop used by both drafting agents, combining rule-based checks and
  LLM-as-a-judge scoring.
- **Reliability:** shared retry-with-backoff on transient server errors, call
  pacing to respect free-tier rate limits, and plain-English error messages for
  quota, auth, and empty-response failures rather than tracebacks. This matters
  because the operator is a psychologist, not a developer.
- **Observability:** `observability.log_decision()` appends one JSON line per
  agent decision. A weekly run leaves a full trace and a one-line status file.

## 5. Results & Demo

The full pipeline has been run end to end against the live Gemini API. A single
`"What should I publish this week?"` request produced a seven-day plan
(`memory/calendar.json`), five LinkedIn posts, and two Substack essays. **Every
draft passed the guardrail and voice-judge loop on the first attempt, with
voice scores of 8-9 out of 10 and tone classified "authentic"** -- verifiable in
`logs/agent_trace.jsonl`.

The content is the proof. Here is an unedited excerpt the Writer produced, in
response to a Scout-surfaced trend about workers "outsourcing confidence" to AI:

> David sat on my couch with his phone face down on his knee. He is a senior
> crisis communications director. I listened as he explained how he spent four
> hours last Tuesday paralyzed over a three-sentence holding statement about a
> delayed shipment.
> [...]
> He hit send on the twenty-eighth draft at 1:00 AM. His boss replied
> immediately to say it was perfect. David stared at the ceiling and felt
> absolutely nothing.

That is my voice: it opens on a specific body in a room, names the feeling
before the theory, uses short sentences when the point lands, and ends
unresolved instead of tying a bow. It contains none of the banned constructions.
The Substack Specialist takes a seed like that and expands it into an
800-1500 word essay that goes *deeper* into the same patient rather than padding
the same paragraph.

The guardrails earn their place by contrast. A raw Gemini draft on this topic
reaches for the antithesis frame ("This isn't burnout -- it's something older")
and rule-of-three padding. The guardrail loop fails those drafts and feeds the
judge's specific objection back into the next attempt until the output reads
like a person wrote it.

## 6. What I Learned

- **Voice is a guardrail problem, not a prompt problem.** A good system prompt
  gets you 70% of the way. The last 30% -- the part that makes people believe a
  human wrote it -- comes from mechanical checks plus an evaluator model that
  can reject and explain.
- **Vibe coding shaped the build.** Working conversationally with an AI coding
  assistant, I built outward one agent at a time and let real failures (an
  empty-response crash, a quota saga that turned out to be a wrong-project API
  key, an antithesis pattern that kept leaking) drive the next fix, rather than
  designing everything up front.
- **The irony is real, and it is the pitch.** Building this made me feel the
  thing my patients feel -- watching a machine do, faster, the work I thought was
  mine. That is not a marketing angle. It is the entire premise of the book.
- **Future directions:** direct-publish integrations (LinkedIn's API; Substack
  has no official one, which is its own decision about ToS risk and the human
  review gate), A/B testing of hooks, and real cross-platform engagement
  analytics feeding the Analyst once live post data exists. These are documented
  in `PUBLISHING_HANDOFF.md` as deliberate future decisions, not shipped
  features.

This is not a demo. I am using it. The book is *After Work*. The agent is
building the platform to sell it.

---

### Repository map (for judges reading the code)

| File | Role |
|------|------|
| `agents/orchestrator.py` | Routes NL requests; logs every decision |
| `agents/scout.py` | Google Search grounding -> JSON trend briefing |
| `agents/strategist.py` | Pillar/platform planning over memory state (pure logic) |
| `agents/writer.py` | Drafts LinkedIn posts through the guardrail loop |
| `agents/substack_specialist.py` | Expands a post into a long-form essay |
| `agents/analyst.py` | Engagement scoring -> pillar adjustments (pure logic) |
| `guardrails.py` | First-pass checks + LLM-as-judge + revise loop |
| `voice_profile.py` | Voice prompt, anti-AI-tell prompt, banned phrases, patterns |
| `gemini_client.py` | Shared retry/error-handling call wrapper |
| `observability.py` | JSONL decision trace |
| `memory/*.json` | Content history, pillar tracker, calendar, engagement |
| `STYLE_GUIDE.md` | Full voice + anti-AI-tell reference |
