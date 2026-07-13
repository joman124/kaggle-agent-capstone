# -*- coding: utf-8 -*-
"""
Unit tests for the parts of the agent system that run without an API key:
the Orchestrator's keyword routing, the pure-logic engagement critic, and the
rule-based guardrail checks. These never call Gemini, so they are fast and
run in CI or offline.

Run:  python -m unittest test_agents
  or: python test_agents.py
"""

import unittest

from agents.orchestrator import route
import engagement
import guardrails
from voice_profile import PLATFORM_RULES

VIRAL = PLATFORM_RULES["linkedin_viral"]
NOTE = PLATFORM_RULES["substack_note"]

EM_DASH = chr(0x2014)
CURLY_APOS = chr(0x2019)
EMOJI = chr(0x1F600)

GOOD_POST = (
    "Another firm handed first-draft code to a model.\n"
    "A developer I know says he feels like a proofreader now.\n"
    "The paycheck holds. The pride does not.\n"
    "What replaces the pride is the question leaders keep skipping.\n"
    "#AI #Work #Leadership"
)


class TestRouting(unittest.TestCase):
    def test_intents(self):
        cases = {
            "go viral about the new AI coding study": ("viral", "the new AI coding study"),
            "react to Sam Altman's interview": ("viral", "Sam Altman's interview"),
            "hot take on AI layoffs": ("viral", "AI layoffs"),
            "what's trending?": ("trending", None),
            "write me a linkedin post about burnout": ("linkedin_post", "burnout"),
            "draft an essay about meaning": ("essay", "meaning"),
            "what should i publish this week?": ("weekly_plan", None),
            "here are last week's numbers": ("engagement", None),
        }
        for request, expected in cases.items():
            self.assertEqual(route(request), expected, msg=request)

    def test_viral_beats_trending(self):
        # "go viral about the trending X" is a viral request, not a lookup.
        intent, _ = route("go viral about the trending AI news")
        self.assertEqual(intent, "viral")


class TestEngagement(unittest.TestCase):
    def test_good_post_passes(self):
        result = engagement.check(GOOD_POST, VIRAL)
        self.assertTrue(result["passed"], msg=result["feedback"])
        self.assertGreaterEqual(result["score"], 90)

    def test_question_opener_fails(self):
        text = "Have you ever lost a job to a model?\nIt happens quietly.\n#AI #Work #Jobs"
        result = engagement.check(text, VIRAL)
        self.assertFalse(result["passed"])
        self.assertIn("question", result["feedback"])

    def test_too_many_hashtags_fails(self):
        text = GOOD_POST + " #Extra #More #Toomany #Again"
        result = engagement.check(text, VIRAL)
        self.assertFalse(result["passed"])
        self.assertIn("hashtags", result["feedback"])

    def test_emoji_fails_when_disallowed(self):
        text = GOOD_POST.replace("model.", "model." + EMOJI)
        result = engagement.check(text, VIRAL)
        self.assertFalse(result["passed"])
        self.assertIn("emoji", result["feedback"])

    def test_note_rejects_hashtags(self):
        # Notes allow zero hashtags, so any hashtag is too many.
        result = engagement.check("The model writes his code now. #AI", NOTE)
        self.assertFalse(result["passed"])

    def test_long_hook_is_soft_flagged_not_failed(self):
        # First line is over the ~120 soft limit but under the 160 hard limit,
        # and the post is otherwise fine (enough words, 3 hashtags, no emoji).
        long_hook = ("A developer I have known for twenty years told me last week "
                     "that a model now writes the first draft of nearly all of his code")
        self.assertGreater(len(long_hook), 120)
        self.assertLess(len(long_hook), 160)
        text = (long_hook + "\n"
                "He still shows up. He is just not sure who he shows up for.\n"
                "The paycheck holds. The point of the work does not.\n"
                "#AI #Work #Leadership")
        result = engagement.check(text, VIRAL)
        self.assertTrue(result["passed"], msg=result["feedback"])  # soft, not hard
        self.assertNotEqual(result["feedback"], "none")


class TestGuardrailRules(unittest.TestCase):
    def test_clean_passes(self):
        text = "A developer told me the model writes his code now. He shows up anyway."
        self.assertTrue(guardrails.run_guardrails(text)["clean"])

    def test_banned_phrase_fails(self):
        result = guardrails.run_guardrails("Let me be clear, this is a game changer.")
        self.assertFalse(result["clean"])
        self.assertTrue(result["banned_phrases"])

    def test_antithesis_detected(self):
        hits = guardrails.find_antithesis("It's not about the money, it's about meaning.")
        self.assertTrue(hits)

    def test_em_dash_overuse_fails(self):
        text = f"He paused {EM_DASH} then spoke {EM_DASH} and left."
        self.assertFalse(guardrails.run_guardrails(text, max_em_dashes=1)["clean"])

    def test_curly_quotes_fail(self):
        text = f"He said it{CURLY_APOS}s fine."
        self.assertFalse(guardrails.run_guardrails(text)["clean"])


if __name__ == "__main__":
    unittest.main()
