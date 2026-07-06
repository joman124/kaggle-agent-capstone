# Video Script -- After Work Social Presence Agent (3-5 min)

Screen-record and talk over it. Each beat pairs DO (what is on screen) with
SAY (the words). Total spoken length is about 600 words = roughly 4 minutes
at a natural pace. Do not rush; the pauses while things load are fine.

---

## Before you hit record (5-minute pre-flight)

1. Close Microsoft Word completely (an open docx makes the save fail).
2. Open a terminal in the project folder and run: `streamlit run app.py`
   -- leave the app open in your browser.
3. In a second browser tab, open your Substack post (the real, live one).
4. In the app, go to the **Drafts** tab, find the essay you posted to
   Substack, pick its pillar, and click **Mark as published** NOW, before
   recording -- so the green "Published" badge is already there on camera.
5. Sanity-check the live run works today: in the app, run
   "What's trending?" once. If it returns topics, you are good. (This
   costs one small API call.)
6. Recording tip: capture the browser window only, hide bookmarks bar.

Fallback: if the live run fails on camera (quota, network), do not restart.
Say "the pipeline runs in about a minute -- here is one it generated
earlier," and click into the Drafts tab. Every draft there is real output.

---

## BEAT 1 -- The problem (0:00-0:30)

**DO:** Start on your live Substack post. Scroll it slowly while you talk.

**SAY:**
"I'm a clinical psychologist, and I'm writing a book called After Work --
about what happens to people psychologically when AI takes over the work
that gave them structure, identity, and meaning. To sell a book, you need
an author platform. Literary agents check. I had no public presence, no
marketing background, and no time to become a content marketer. So I built
an AI agent system to do it for me."

## BEAT 2 -- The irony (0:30-1:00)

**DO:** Stay on the Substack post. Hover the byline / title.

**SAY:**
"There's an irony here, and it's the same tension the book is about: a
psychologist writing about AI displacing human labor built an AI to
displace his own marketing labor. This essay you're looking at is live on
my Substack right now -- and it was drafted by the system I'm about to
show you. I reviewed it and posted it. The system did everything else."

## BEAT 3 -- Architecture (1:00-1:50)

**DO:** Switch to the Streamlit app tab. Point the cursor at the sidebar
list of the five agents, reading down it as you name each one.

**SAY:**
"Here's the system. Five specialized agents behind one orchestrator, and I
talk to it in plain English. Scout finds what's trending in the
psychology-and-AI space using Gemini with Google Search grounding -- real
headlines, not hallucinated ones. Strategist plans the week: which content
pillar, which platform, which day -- balancing coverage over a rolling
thirty-day window, with no LLM at all, just logic over memory files.
Writer drafts every post in my voice through a guardrail loop. The
Substack Specialist expands a short post into a long-form essay. And the
Analyst reads engagement data and feeds adjustments back to the
Strategist, so the system learns."

## BEAT 4 -- Live demo (1:50-2:50)

**DO:** Click into the request box. Clear it and type:
`Write me a LinkedIn post about parents watching AI raise their kids' expectations`
(or any topic you like). Click **Run**. The routing line appears
immediately -- point at it. The draft takes about 45 seconds; keep
talking over the spinner, then scroll the finished draft.

**SAY:**
"Let me run it live. I ask for a post the way I'd ask a person. First
thing it shows me: the orchestrator routed this to the right intent and
pulled out the topic -- that's deterministic code, not a model guessing.
Now the Writer is drafting. Under the hood there's a
generate-evaluate-revise loop: every draft gets checked against
forty-seven banned phrases, em-dash limits, and a second model acting as
a judge, scoring the voice against real passages from my book, zero to
ten. Score under seven? It gets rejected, and the judge's feedback goes
into the next attempt. ... And there it is. It opens on a specific person
in a room, short sentences when the point lands, ends unresolved. That's
not generic AI writing -- that's my voice. And it's already saved into a
Word document, because that's where I review."

## BEAT 5 -- The week + the guardrail evidence (2:50-3:40)

**DO:** Click the **This Week's Plan** tab; sweep the cursor down the
7-day table. Then click the **Agent Trace** tab; point at the
voice_score and tone columns. Then click the **Drafts** tab and point at
the green "Published" badge on your Substack essay.

**SAY:**
"One request -- 'what should I publish this week?' -- produces this: a
seven-day plan, five LinkedIn posts, two Substack essays, each pillar
matched to a real trending headline Scout found. Every decision the
system makes is logged. This trace shows each draft's voice score --
eights and nines -- and the tone check. The hard part of this project was
never getting the model to write. It was getting it to stop sounding
like AI -- so 'it's not X, it's Y' constructions, rule-of-three padding,
the word 'quietly' -- those are hard failures that force a rewrite. And
here's the loop closing: when I actually publish a draft, I mark it here,
it's written to content history, and next week's plan balances around
what really went out."

## BEAT 6 -- Course concepts (3:40-4:05)

**DO:** Stay in the app, or briefly show README.md's concepts table if
you have it open. No clicking needed.

**SAY:**
"For the rubric: this demonstrates five course concepts. Multi-agent
architecture with an orchestrator. Tool use -- Google Search grounding.
Context engineering -- memory and state in JSON driving the planner.
Guardrails and evaluation -- rules plus an LLM-as-a-judge with a revise
loop. And prototype-to-production -- full observability traces, a
scheduled weekly batch job, and this UI."

## BEAT 7 -- Close (4:05-4:25)

**DO:** Switch back to the live Substack post tab. Hold on it.

**SAY:**
"This isn't a demo I built for a competition. I'm using it. The first
essay on my Substack was drafted by this system, and the first LinkedIn
post goes up tomorrow. The book is After Work. The agent is building the
platform to sell it."

---

## Timing summary

| Beat | Screen | Time |
|------|--------|------|
| 1. Problem | Substack post | 0:00-0:30 |
| 2. Irony | Substack post | 0:30-1:00 |
| 3. Architecture | App sidebar | 1:00-1:50 |
| 4. Live demo | Request box -> Run -> draft | 1:50-2:50 |
| 5. Week + guardrails | Plan / Trace / Drafts tabs | 2:50-3:40 |
| 6. Course concepts | App or README table | 3:40-4:05 |
| 7. Close | Substack post | 4:05-4:25 |

If you run long, trim Beat 6 to one sentence ("Five course concepts:
multi-agent, tool use, memory, guardrails, production") -- the writeup
covers the detail.
