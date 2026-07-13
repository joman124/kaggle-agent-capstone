# Architecture — After Work Social Presence Agent

## Overview

Five specialized agents coordinated by an Orchestrator. Each agent has one job.
The user interacts in natural language; the Orchestrator routes the request.

```
                    USER (John) - reviews & posts
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
            state                  (substack_essay
                                    platform rules)
```

## Agents

### Scout (Day 2 — tool use) [BUILT]
Finds trending topics in the psychology + AI + work space using Gemini with
Google Search grounding (`agents/scout.py`). Returns a JSON array of 3-5
topics with headline, source, relevance score, suggested angle, pillar, and
platform. Takes an optional topic to focus the search instead of scanning
broadly for what's trending. Uses `GEMINI_MODEL` (Flash), shared with future
agents, not the Writer's pro model.

### Strategist (Day 3 — context engineering / memory) [BUILT]
Plans what to publish, when, and where (`agents/strategist.py`). Pure logic,
no Gemini calls. Reads `memory/content_history.json`, computes a rolling
30-day pillar distribution, and writes it to `memory/pillar_tracker.json`.
Ranks pillars least-used-first so coverage stays balanced over time, applies
a fixed platform cadence (3 LinkedIn : 2 Substack per 5-day plan) so platform
balance does not depend on what Scout suggests, and optionally matches each
day's pillar to a topic from a Scout briefing. `plan_week()` now also takes
an optional `pillar_adjustments` map from the Analyst (`{pillar: +1/-1/0}`)
and shifts the ranking accordingly -- an overperforming pillar (+1) moves
earlier without overriding the rolling-window balance outright. Writes the
plan to `memory/calendar.json`.

### Writer (Day 4 — quality / guardrails) [BUILT]
Drafts publication-ready content in John's voice (`agents/writer.py`). Loads
`voice_profile.py` and drafts through `guardrails.draft_with_guardrails()`:
first-pass checks (banned-phrase scan, em-dash and curly-quote checks,
negative-parallelism flags) plus an LLM-as-a-judge voice/tone score against
`REFERENCE_PASSAGES` (0-10; reject below 7, or a non-"authentic" tone). On a
reject, the judge's feedback is fed back into the next prompt and the Writer
redrafts, up to 3 attempts, before giving up and returning its best attempt.
Uses its own model (`GEMINI_WRITER_MODEL`, pro-tier by default) for drafting;
the judge itself uses `GEMINI_MODEL` (Flash), since evaluation does not need
the pro-tier model. Saves generated posts to `LinkedIn Posts.docx` (via
`doc_output.py`) instead of printing markdown to the console, since John
reviews from the docx.

### Substack Specialist (added alongside Step 5) [BUILT]
Expands a LinkedIn post into a long-form Substack essay
(`agents/substack_specialist.py`). Takes the Writer's draft as a seed and
goes deeper into the specific moments, patients, and arguments the short
post only had room to gesture at -- not a padded restatement of the same
paragraph. Drafts through the same `guardrails.draft_with_guardrails()`
generate-evaluate-revise loop as the Writer, using the `substack_essay`
entry from `PLATFORM_RULES` (800-1500 words, no hashtags, up to 4 em
dashes) for its first-pass checks. Shares the Writer's pro-tier model
(`GEMINI_WRITER_MODEL`) since draft quality matters here too. Saves
essays to `Substack Essays.docx` via `doc_output.py`.

### Analyst (Day 5 — observability / iteration) [BUILT]
Ingests engagement data from `memory/engagement_data.json`
(`agents/analyst.py`). Pure logic, no Gemini calls. Computes an
impressions-weighted engagement rate per pillar (`compute_performance()`),
compares each against `DEFAULT_TARGET_RATE` (a 3% placeholder benchmark
until John has real targets) to classify it "above"/"at"/"below"
(`compare_to_target()`), and turns that into a `{pillar: +1/-1/0}`
adjustment map (`pillar_adjustments()` / `get_pillar_adjustments()`) that
the Strategist consumes to favor overperforming pillars. Also produces a
human-readable `weekly_summary()`, which the Orchestrator now returns for
"engagement"-intent requests instead of the old "not built yet" message.

### Viral (added after Step 8 — fast hot-topic reactions) [BUILT]
Turns a hot topic into fast-reaction content (`agents/viral.py`). Reuses the
Writer's `draft_with_guardrails()` loop, so viral posts still pass the voice
judge; they are just shorter and hotter (`PLATFORM_RULES["linkedin_viral"]`,
50-150 words) plus a Substack Note (`PLATFORM_RULES["substack_note"]`). The
LinkedIn post is auto-posted through `linkedin_publisher.py` (official Posts
API, member actor), which DEFAULTS TO DRY RUN -- nothing goes live until
`LINKEDIN_DRY_RUN=false` and a real token + `LINKEDIN_ACTOR_URN` are set. The
Note is saved to `Substack Notes.docx` for John to post by hand (no Substack API).
Beyond the voice judge, viral drafts also pass a second, pure-logic gate --
`engagement.py` (hook length, no question opener, hashtag count, length, emoji
policy) -- wired in through `draft_with_guardrails`'s new `extra_checks` hook,
so a post has to be built for reach as well as on-voice. `linkedin_auth.py`
(with `LINKEDIN_SETUP.md`) is a guided OAuth helper for going live, and
`test_agents.py` unit-tests routing + engagement + guardrails without an API key.

### Orchestrator (Day 5 — multi-agent coordination) [BUILT]
Top-level router (`agents/orchestrator.py`). `route()` classifies a
natural-language request into an intent + topic via deterministic keyword
matching -- no Gemini call, so it is unit-tested without an API key.
`handle_request()` logs the routing decision via `observability.log_decision()`
right after calling `route()`, then runs the matched agent pipeline:
- "What should I publish this week?" -> Scout -> Analyst (pillar
  adjustments) -> Strategist -> Writer, then Substack Specialist for any
  day the calendar assigns to Substack
- "Go viral about X" / "react to X" -> Viral (auto-posts LinkedIn, drafts Note;
  Scout fills in a topic first if none was given)
- "Write me a LinkedIn post about X" -> Writer
- "What's trending?" -> Scout
- "Here are last week's numbers" -> Analyst
- "Draft an essay about/reacting to X" -> Writer -> Substack Specialist
  (Scout fills in a topic first if none was given)

## Memory / state files (JSON in /memory)

- `content_history.json` — every post: title, date, pillar, platform
  [BUILT; written by `publish_log.mark_published()` when John marks a
  draft published in the Streamlit Drafts tab (or via
  `python publish_log.py`), which is what makes the Strategist's
  rolling-window balance react to real publishing]
- `pillar_tracker.json` — rolling 30-day pillar distribution
  [BUILT, recomputed and overwritten by Strategist on every run]
- `calendar.json` — planned upcoming posts
  [BUILT, overwritten by Strategist's `plan_week()` on every run]
- `engagement_data.json` — post-level metrics over time
  [BUILT, seeded empty; John (or a later API integration) appends
  per-post {pillar, platform, likes, comments, shares, impressions}
  entries here for the Analyst to read]

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
  .env.example          [BUILT] documents required/optional vars
  .gitignore            [BUILT]
  requirements.txt
  voice_profile.py      [BUILT] voice + anti-AI-tell layers, guardrail data
  check_setup.py        [BUILT] lists available models, verifies key
  gemini_client.py      [BUILT] shared retry/error-handling call wrapper
  doc_output.py         [BUILT] appends generated content to a Word doc
  agents/
    __init__.py         [BUILT]
    writer.py           [BUILT] promoted from step1_writer.py; uses
                          GEMINI_WRITER_MODEL (pro-tier by default); saves
                          posts to LinkedIn Posts.docx
    scout.py            [BUILT] Google Search grounding, JSON topic briefing
    strategist.py       [BUILT] pillar/platform balancing, memory/calendar.json
    substack_specialist.py [BUILT] expands a LinkedIn post into a long-form
                          essay; saves to Substack Essays.docx
    analyst.py          [BUILT] pillar/platform performance vs. target
                          engagement rate; feeds pillar_adjustments back
                          to the Strategist; weekly_summary() report
    orchestrator.py     [BUILT] routes natural-language requests across
                          Scout / Strategist / Writer / Substack
                          Specialist / Analyst; logs every routing
                          decision via observability.log_decision()
  guardrails.py         [BUILT] first-pass checks (banned phrase, em-dash,
                          curly quotes, parallelism flags) + LLM-as-judge
                          voice/tone scoring (judge_voice, evaluate) +
                          the shared generate-evaluate-revise loop
                          (draft_with_guardrails) used by Writer and
                          Substack Specialist
  observability.py      [BUILT] log_decision() appends one JSON line per
                          agent decision to logs/agent_trace.jsonl
  publish_log.py        [BUILT] mark_published() write-back to
                          content_history.json; closes the loop between
                          drafting and the Strategist's pillar balance
  memory/
    content_history.json   [BUILT, seeded empty]
    pillar_tracker.json    [BUILT, generated by Strategist]
    calendar.json          [BUILT, generated by Strategist]
    engagement_data.json   [BUILT, seeded empty]
  app.py                [BUILT] Streamlit UI: NL request box -> Orchestrator,
                          plus read-only tabs (plan, drafts, agent trace)
  STYLE_GUIDE.md        [BUILT] full voice + anti-AI reference
```
