# -*- coding: utf-8 -*-
"""
Unit tests for the reaction-system modules that run without an API key: the
posts ledger, posting policy (dedup + cadence), the brand-safety gate, ranking
(best-of + topic ranking), and analytics (the learning loop). Each test uses a
temp ledger file so nothing touches real state.

Run:  python -m unittest test_system
"""

import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

import posts_ledger
import posting_policy
import safety
import ranking
import analytics


class TempLedger:
    """Context manager: a throwaway ledger file path."""
    def __enter__(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "posts.json")
        return self.path

    def __exit__(self, *a):
        pass


class TestLedger(unittest.TestCase):
    def test_add_update_status(self):
        with TempLedger() as path:
            rec = posts_ledger.add("AI writes code", "body", "linkedin",
                                   pillar="Current Events", path=path)
            self.assertEqual(rec["id"], "p0001")
            self.assertEqual(rec["status"], "queued")
            posts_ledger.mark_posted("p0001", "urn:li:share:1", path=path)
            posted = posts_ledger.by_status("posted", path=path)
            self.assertEqual(len(posted), 1)
            self.assertEqual(posted[0]["urn"], "urn:li:share:1")


class TestPostingPolicy(unittest.TestCase):
    def test_duplicate_detection(self):
        ledger = [{"status": "posted", "created": datetime.now(timezone.utc).isoformat(),
                   "topic": "AI now writes most first-draft code at big firms"}]
        dup = posting_policy.is_duplicate("most first-draft code is written by AI now",
                                          ledger=ledger)
        self.assertTrue(dup["duplicate"])
        fresh = posting_policy.is_duplicate("burnout among nurses", ledger=ledger)
        self.assertFalse(fresh["duplicate"])

    def test_cadence_max_per_day(self):
        now = datetime.now(timezone.utc)
        ledger = [{"status": "posted", "posted_at": (now - timedelta(hours=5)).isoformat()}
                  for _ in range(3)]
        gate = posting_policy.can_post_now(now=now, max_per_day=3, ledger=ledger)
        self.assertFalse(gate["allowed"])

    def test_cadence_min_spacing(self):
        now = datetime.now(timezone.utc)
        ledger = [{"status": "posted", "posted_at": (now - timedelta(minutes=30)).isoformat()}]
        gate = posting_policy.can_post_now(now=now, min_hours=3, ledger=ledger)
        self.assertFalse(gate["allowed"])
        gate2 = posting_policy.can_post_now(now=now, min_hours=3, max_per_day=10,
                                            ledger=[])
        self.assertTrue(gate2["allowed"])


class TestSafety(unittest.TestCase):
    def test_blocks_tragedy(self):
        v = safety.assess("A factory shooting left several dead")
        self.assertFalse(v["safe"])

    def test_layoffs_allowed_but_flagged(self):
        v = safety.assess("Big Tech announces mass layoffs tied to AI")
        self.assertTrue(v["safe"])
        self.assertTrue(v["flags"])

    def test_ordinary_topic_safe(self):
        v = safety.assess("How AI changes the way teams write code")
        self.assertTrue(v["safe"])
        self.assertEqual(v["flags"], [])


class TestRanking(unittest.TestCase):
    def test_pick_best_prefers_passed_and_high_score(self):
        results = [
            {"text": "a", "evaluation": {"passed": False, "voice_score": 9,
                                         "extra": {"score": 100}}},
            {"text": "b", "evaluation": {"passed": True, "voice_score": 7,
                                         "extra": {"score": 80}}},
        ]
        self.assertEqual(ranking.pick_best(results)["text"], "b")

    def test_rank_topics_sinks_duplicate_and_unsafe(self):
        briefing = [
            {"headline": "Novel AI productivity study", "suggested_angle":
             "what AI does to team output", "relevance_score": 8,
             "suggested_pillar": "Current Events"},
            {"headline": "tragedy", "suggested_angle":
             "a fatal crash involving a robotaxi", "relevance_score": 9,
             "suggested_pillar": "Current Events"},
        ]
        ranked = ranking.rank_topics(briefing, ledger=[])
        # The safe, novel topic should outrank the sensitive one.
        self.assertIn("output", ranked[0].get("suggested_angle"))
        self.assertFalse(ranked[-1]["_rank"]["safe"])


class TestAnalytics(unittest.TestCase):
    def test_multipliers_favor_high_performers(self):
        with TempLedger() as path:
            posts_ledger.add("t1", "x", "linkedin", pillar="A", status="queued", path=path)
            posts_ledger.mark_posted("p0001", "u1", path=path)
            posts_ledger.update("p0001", path=path,
                                metrics={"reactions": 100, "comments": 20})
            posts_ledger.add("t2", "x", "linkedin", pillar="B", status="queued", path=path)
            posts_ledger.mark_posted("p0002", "u2", path=path)
            posts_ledger.update("p0002", path=path,
                                metrics={"reactions": 2, "comments": 0})
            mult = analytics.performance_multipliers(path=path)
            self.assertGreater(mult["A"], mult["B"])


if __name__ == "__main__":
    unittest.main()
