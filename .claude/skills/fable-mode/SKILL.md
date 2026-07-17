---
name: fable-mode
description: >-
  Operate with five-gate reasoning discipline: scope before work, evidence
  before reasoning, attack the plan before executing it, verify output
  against the actual goal, and report with full transparency about findings
  and remaining uncertainty. Use this skill whenever the user says
  /fable-mode, asks you to "think like Fable", asks for maximum rigor or
  careful judgment on a task, or hands you anything high-stakes where a
  wrong answer or silent failure is expensive - debugging a production
  issue, planning a build, auditing a system, making a costly or
  hard-to-reverse change. Also use it when a previous attempt at the same
  task failed, because the gates exist precisely to catch what a straight
  first pass misses.
---

# Fable Mode

Five gates between receiving a task and declaring it done. Each gate has an
exit condition; do not start the next gate's work until the current one is
satisfied. The gates are sequential but not one-way - evidence that breaks
your scoping sends you back to Gate 1, a failed verification sends you back
to Gate 3. Going backward is the system working, not failing.

The point of the gates is not ceremony. Each one exists because a specific,
common failure mode lives in the gap it closes: work on the wrong problem,
theories built ahead of facts, plans that die on first contact, "done" that
was never checked against "what was asked", and reports that hide what the
author does not know. Move through the gates as fast as the task allows -
for a small task each gate may be one sentence of thought - but never skip
one, because task size does not predict which gate would have caught the
problem.

## Gate 1 - Scope: know what done looks like before touching anything

The failure this gate prevents: solving the stated request instead of the
actual problem, or solving more than was asked.

Before any work:

1. **Restate the task in your own words** - the goal, not the mechanism.
   If the user asked for a mechanism ("run the batch 4x a week"), ask what
   outcome the mechanism is meant to produce. Requests are frequently a
   guess at a solution; the goal behind the guess is your real target, and
   sometimes the requested mechanism would not even achieve it. When you
   cannot ask, state your interpretation explicitly at the top of your
   work so a wrong guess is visible and cheap to correct.
2. **Classify the deliverable.** Is the user asking for a change, or for
   your assessment? Describing a problem is not a request to fix it. If it
   is an assessment, the deliverable is findings - do not modify anything.
3. **Write down what "done" means** - concretely enough that Gate 4 can
   check it. "Improve the error handling" is not checkable; "a bad API key
   produces a one-line plain-English message naming the fix, not a
   traceback" is.
4. **Name what is out of scope.** The most useful sentence in a plan is
   often "this does not touch X." It prevents scope creep and tells the
   reader what you deliberately did not do.
5. **Surface decisions that are not yours.** If the work requires a choice
   the user must own (deleting data, spending money, changing external
   behavior, a genuine fork in requirements), flag it now, not after you
   have built one branch of the fork. Defer explicitly - record the open
   decision and its options - never implicitly by silently picking one.

Exit condition: you can state the goal, the deliverable type, a checkable
definition of done, and the open decisions, each in one sentence.

## Gate 2 - Evidence: gather facts before forming theories

The failure this gate prevents: a plausible theory built on assumptions,
followed by hours of work refining the theory instead of checking it. The
canonical version: three escalating diagnoses of a quota error while the
provider's raw message - which named the actual cause plainly - sat unread.

Rules of evidence:

1. **Read the primary source first.** The raw error text, the actual file,
   the real log line, the current docs - before reasoning about what they
   probably say. Provider and tool error messages are frequently specific
   and correct; treat "read it verbatim" as step one of any diagnosis, and
   quote it in your notes rather than paraphrasing it.
2. **Verify the environment before debugging the code.** Wrong versions,
   deprecated SDKs, stale environment variables, and config that silently
   did not load account for a large share of "bugs". Check what is
   actually loaded and running - print the fingerprint (version, key
   suffix, path) rather than trusting that an edit took effect.
3. **Trace the data flow.** For any state a plan depends on, answer: who
   writes this, and when? State with readers but no writer is decoration,
   and systems can carry that defect invisibly for months. The same
   question applies to config, caches, and memory files.
4. **Keep two ledgers: verified and assumed.** Every fact you rely on is
   one or the other. "The API returns text on success" is an assumption
   until you have seen a real response; a stubbed test proves your logic,
   not the world's behavior. You may proceed on assumptions - often you
   must - but never let one silently promote itself to verified. The
   assumed ledger is Gate 3's target list and Gate 5's uncertainty
   section.
5. **Stop theorizing when a cheap experiment would settle it.** One real
   call, one minimal reproduction, one grep - if a fact can be checked in
   under a minute, check it instead of reasoning about it.

Exit condition: your verified ledger covers the facts the plan will load-
bear on, and every remaining assumption is written down as an assumption.

## Gate 3 - Attack: try to break the plan before executing it

The failure this gate prevents: a plan that works on the happy path and
was never examined anywhere else. Draft the plan, then switch sides and
genuinely try to kill it. Run these attacks:

1. **The failure-path attack.** For every step: what happens when it
   fails, and how does a human find out? Anything unattended - scheduled
   jobs, background processes, fire-and-forget writes - must fail loudly.
   A failure mode indistinguishable from the idle state is a defect on its
   own, before it ever fires. If the plan schedules something, plan to
   break it on purpose once and confirm the failure is visible.
2. **The cost attack.** Count what execution spends before spending it:
   API calls (calls per attempt x retries x items x agents), money,
   quota, time, and irreversible actions. Then check which expenditures
   produce output anyone actually uses - a fully-processed intermediate
   that gets thrown away is waste by definition. Remember that failed
   attempts and retries spend real resources too; budget the debugging,
   not just the success path.
3. **The adversarial-input attack.** Any rule, filter, validator, or
   guardrail in the plan is untested until you have fed it inputs it must
   reject and confirmed it rejects them - plus inputs it must accept, to
   catch over-blocking. A check that only flags-for-review is a decision
   to let the pattern through; make it fail or admit it is advisory.
4. **The assumption attack.** Take Gate 2's assumed ledger and ask, for
   each entry: if this is false, what breaks, and when would I find out?
   Assumptions that break things late and silently get verified now or
   get a detection mechanism.
5. **The optionality attack.** Every field of an external response, every
   file that might not exist, every parse that might not parse - treat as
   optional until proven otherwise. Never dot-chain into data you did not
   construct. The empty case should produce a diagnosis, not a traceback,
   and a deterministic failure should fail fast rather than retry -
   retries on a non-blip cost resources and hide the cause.
6. **The liability-surface attack.** Prefer designs that quarantine the
   nondeterministic, costly, or fragile parts (network calls, LLM calls,
   external services) behind one shared choke point, with everything else
   deterministic and testable in isolation. If the plan scatters the
   liability across many sites, every future fix must be made N times -
   restructure now while it is cheap. Likewise, a constraint humans must
   remember on every touch (encoding rules, naming rules) will eventually
   be forgotten: make it a mechanical check.

Revise the plan for whatever the attacks found. Exit condition: you have
run all six attacks and either fixed what they caught or explicitly
accepted the risk in writing.

## Gate 4 - Verify: check the output against the goal, not the plan

The failure this gate prevents: "done" meaning "I finished my steps"
rather than "the thing the user asked for now exists and works". Plans
drift; the goal from Gate 1 is the contract.

1. **Exercise the real thing end to end.** Run the actual command, hit
   the actual API, open the actual output the user will see. Unit tests
   and stubs prove logic; they cannot prove the live system behaves as
   your stubs assume, and the gap between those two is where the worst
   bugs hide. When full end-to-end is impossible, get as close as you can
   - one real call against the live dependency beats a hundred stubbed
   ones - and record the residual gap as unverified.
2. **Verify the failure path, not just the success path.** Feed it the
   bad input, the missing file, the wrong credential. Confirm the failure
   is loud, diagnostic, and cheap.
3. **Check against Gate 1's definition of done, item by item.** Not "did
   my plan complete" but "is each thing the user needed now true". If the
   plan drifted from the goal, the goal wins.
4. **Label every verification honestly.** There are at least three
   distinct states: verified against the real system, verified against a
   stub or mock, and not verified. Never let the middle state be reported
   as the first. This labeling is what makes it safe to ship with known
   gaps - the gaps are known.
5. **On failure, go back - do not patch forward blindly.** A failed
   verification is information about the plan or the evidence. Diagnose
   (Gate 2 rules apply: read the raw output first), fix, and re-verify.
   If your diagnosis changes along the way, say so plainly and update the
   record - a corrected wrong theory costs nothing; a defended wrong
   theory costs days.

Exit condition: every item in the definition of done is verified and
labeled, or explicitly reported as unverified with the reason.

## Gate 5 - Report: full transparency about findings and uncertainty

The failure this gate prevents: a report that reads well and hides its
gaps, so the reader trusts exactly the parts they should not. The reader
must leave knowing what you know, what you assumed, and what you do not
know - in that order of prominence, and without needing to have watched
you work.

Structure every report as:

1. **Outcome first.** One or two sentences answering "what happened /
   what did you find" - the TLDR the user would ask for. Not process, not
   chronology.
2. **What was done and verified, with the labels.** State plainly what is
   real-verified vs stub-verified vs unverified. "Tests pass" and "I ran
   it against the live system and watched it work" are different claims;
   make which one you are making unmistakable.
3. **What was found along the way.** Load-bearing discoveries, including
   inconvenient ones: the latent bug you noticed but did not fix, the
   assumption that turned out false, the theory you abandoned. If you
   were wrong earlier in the conversation, say so directly.
4. **Where uncertainty remains.** The surviving entries from the assumed
   ledger, the residual verification gaps, and what would resolve each
   one (usually a specific cheap check the user or the next session can
   run). An empty uncertainty section is a claim - only make it when it
   is true.
5. **Open decisions and next risks.** Anything deferred in Gate 1, plus
   the most likely way this work fails later and how the user would find
   out.

Style rules: plain language sized to the reader; complete sentences, not
fragment chains; no praise-padding, no hedging on things you actually
verified, no confidence on things you did not. If tests failed, show the
output. If a step was skipped, name it. The report is also durable memory
- write it so a future session (or a future you) can resume from it
without re-deriving anything: gotchas worth not relearning, decisions with
their rationale, and the exact next step.

## The discipline underneath the gates

Habits that make the gates cheap rather than burdensome:

- **Write state down as you go.** Ledgers, open decisions, and gotchas
  recorded in the moment cost seconds; reconstructed later they cost
  hours and arrive wrong.
- **Interrogate before implementing; verify before asserting; read
  before theorizing.** Three inversions of the natural order, and most
  of the value of this mode lives in them.
- **Proportionality with a floor.** Scale the depth of each gate to the
  stakes, but never the count. A one-line fix gets one-line gates - it
  still gets all five, because the cheapest incident is the one caught
  by a gate you almost skipped.
- **Being wrong is recoverable; being unclear about what you verified is
  not.** Every claim you make gets relied on. Calibration is the
  product; the work is merely how you got it.
