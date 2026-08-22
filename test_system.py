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
import review


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

    def test_cadence_holds_at_every_hour_of_the_day(self):
        """The cap must not depend on what time it is asked. It used to: with
        a UTC-calendar-date counter, posts made 5 hours ago fell on the
        previous date whenever 'now' was just past midnight UTC, so the count
        read zero and the limit silently stopped applying between 00:00 and
        05:00 UTC -- late afternoon and evening in the US."""
        for hour in range(24):
            now = datetime(2026, 7, 27, hour, 30, tzinfo=timezone.utc)
            ledger = [{"status": "posted",
                       "posted_at": (now - timedelta(hours=5)).isoformat()}
                      for _ in range(3)]
            gate = posting_policy.can_post_now(now=now, max_per_day=3, ledger=ledger)
            self.assertFalse(gate["allowed"],
                             "cap leaked at %02d:30 UTC" % hour)

    def test_cadence_cannot_be_reset_by_crossing_midnight_utc(self):
        """Three posts before the boundary must still block just after it."""
        midnight = datetime(2026, 7, 27, 0, 0, tzinfo=timezone.utc)
        ledger = [{"status": "posted",
                   "posted_at": (midnight - timedelta(minutes=m)).isoformat()}
                  for m in (30, 60, 90)]
        gate = posting_policy.can_post_now(now=midnight + timedelta(minutes=5),
                                           max_per_day=3, min_hours=0,
                                           ledger=ledger)
        self.assertFalse(gate["allowed"])

    def test_cadence_releases_once_posts_age_out_of_the_window(self):
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        ledger = [{"status": "posted",
                   "posted_at": (now - timedelta(hours=25)).isoformat()}
                  for _ in range(3)]
        gate = posting_policy.can_post_now(now=now, max_per_day=3, min_hours=0,
                                           ledger=ledger)
        self.assertTrue(gate["allowed"])

    def test_cadence_survives_a_naive_timestamp(self):
        """A naive timestamp used to crash the guard on comparison, which would
        have taken out cadence control altogether rather than failing closed."""
        now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)
        ledger = [{"status": "posted",
                   "posted_at": (now - timedelta(hours=1)).replace(tzinfo=None).isoformat()}
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


class TestScheduling(unittest.TestCase):
    """Scheduling is the part that can post without a human in the room, so
    the failure modes matter more than the happy path."""

    def _scheduled(self, path, offset_hours):
        posts_ledger.add("topic", "body", "linkedin", path=path)
        when = datetime.now(timezone.utc) + timedelta(hours=offset_hours)
        posts_ledger.schedule("p0001", when.isoformat(), path=path)
        return "p0001"

    def test_future_post_is_not_due(self):
        with TempLedger() as path:
            self._scheduled(path, +2)
            self.assertEqual(posts_ledger.due_scheduled(path=path), [])

    def test_past_post_is_due(self):
        with TempLedger() as path:
            self._scheduled(path, -1)
            due = posts_ledger.due_scheduled(path=path)
            self.assertEqual([r["id"] for r in due], ["p0001"])

    def test_substack_is_never_due_for_auto_posting(self):
        with TempLedger() as path:
            posts_ledger.add("topic", "body", "substack", path=path)
            past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            posts_ledger.schedule("p0001", past, path=path)
            self.assertEqual(posts_ledger.due_scheduled(path=path), [])

    def test_naive_timestamp_is_treated_as_utc_not_mis_compared(self):
        with TempLedger() as path:
            posts_ledger.add("topic", "body", "linkedin", path=path)
            naive_future = (datetime.now(timezone.utc)
                            + timedelta(hours=3)).replace(tzinfo=None).isoformat()
            posts_ledger.schedule("p0001", naive_future, path=path)
            self.assertEqual(posts_ledger.due_scheduled(path=path), [])

    def test_unschedule_returns_it_to_the_queue(self):
        with TempLedger() as path:
            self._scheduled(path, +2)
            posts_ledger.unschedule("p0001", path=path)
            self.assertEqual(len(posts_ledger.by_status("queued", path=path)), 1)
            self.assertEqual(posts_ledger.scheduled(path=path), [])


class TestPublishDue(unittest.TestCase):
    def setUp(self):
        import publish_due
        self.publish_due = publish_due

    def _queue_due(self, path, hours_late=1):
        posts_ledger.add("topic", "body", "linkedin", path=path)
        when = datetime.now(timezone.utc) - timedelta(hours=hours_late)
        posts_ledger.schedule("p0001", when.isoformat(), path=path)

    def test_dry_run_does_not_consume_scheduled_posts(self):
        """A dry run must leave plans intact -- otherwise going live later
        would silently have eaten everything John scheduled."""
        with TempLedger() as path:
            self._queue_due(path)
            summary = self.publish_due.publish_due(force_dry_run=True, path=path)
            self.assertEqual(summary["previewed"], ["p0001"])
            self.assertEqual(summary["posted"], [])
            still = posts_ledger.by_status("scheduled", path=path)
            self.assertEqual(len(still), 1)

    def test_dry_run_does_not_consume_very_late_posts_either(self):
        """The lateness check must not fire before the dry-run check. It used
        to, so a stale item was marked 'missed' and written to disk during what
        was supposed to be a side-effect-free preview."""
        with TempLedger() as path:
            self._queue_due(path, hours_late=self.publish_due.MAX_LATE_HOURS + 5)
            summary = self.publish_due.publish_due(force_dry_run=True, path=path)
            self.assertEqual(summary["previewed"], ["p0001"])
            self.assertEqual(summary["missed"], [])
            self.assertEqual(len(posts_ledger.by_status("scheduled", path=path)), 1)
            self.assertEqual(posts_ledger.by_status("missed", path=path), [])

    def test_publisher_resolving_to_dry_run_leaves_it_scheduled(self):
        """If the two independent safety gates disagree, publish nothing."""
        import linkedin_publisher
        original = linkedin_publisher.post_text

        def simulated(text, dry_run=None, first_comment=None):
            return {"posted": False, "dry_run": True,
                    "post_id": "dry-run-simulated", "actor": "urn:li:person:x"}

        linkedin_publisher.post_text = simulated
        try:
            with TempLedger() as path:
                self._queue_due(path)
                summary = self.publish_due.publish_due(force_dry_run=False, path=path)
                self.assertEqual(summary["posted"], [])
                self.assertEqual(
                    len(posts_ledger.by_status("scheduled", path=path)), 1)
        finally:
            linkedin_publisher.post_text = original

    def test_very_late_post_is_missed_not_blasted_out(self):
        with TempLedger() as path:
            self._queue_due(path, hours_late=self.publish_due.MAX_LATE_HOURS + 5)
            summary = self.publish_due.publish_due(force_dry_run=False, path=path)
            self.assertEqual(summary["missed"], ["p0001"])
            self.assertEqual(summary["posted"], [])
            self.assertEqual(
                posts_ledger.by_status("missed", path=path)[0]["id"], "p0001")

    def test_api_failure_is_recorded_and_does_not_crash_the_batch(self):
        import linkedin_publisher
        original = linkedin_publisher.post_text

        def boom(text, dry_run=None, first_comment=None):
            raise SystemExit("token expired")

        linkedin_publisher.post_text = boom
        try:
            with TempLedger() as path:
                self._queue_due(path)
                summary = self.publish_due.publish_due(force_dry_run=False, path=path)
                self.assertEqual(summary["failed"], ["p0001"])
                failed = posts_ledger.by_status("failed", path=path)[0]
                self.assertIn("token expired", failed["error"])
        finally:
            linkedin_publisher.post_text = original

    def test_live_run_posts_and_marks_the_ledger(self):
        import linkedin_publisher
        original = linkedin_publisher.post_text

        def fake(text, dry_run=None, first_comment=None):
            return {"posted": True, "dry_run": False,
                    "post_id": "urn:li:share:999", "actor": "urn:li:person:x"}

        linkedin_publisher.post_text = fake
        try:
            with TempLedger() as path:
                self._queue_due(path)
                summary = self.publish_due.publish_due(force_dry_run=False, path=path)
                self.assertEqual(summary["posted"], ["p0001"])
                posted = posts_ledger.by_status("posted", path=path)[0]
                self.assertEqual(posted["urn"], "urn:li:share:999")
        finally:
            linkedin_publisher.post_text = original


class TestReviewScheduling(unittest.TestCase):
    """review.* resolves records through posts_ledger's module-level default
    path, which is bound at import time -- reassigning LEDGER_PATH does NOT
    redirect it. So these stub the lookup and the writer outright, which also
    guarantees a test run can never touch the real memory/posts.json."""

    def _patch(self, record):
        import review
        self.review = review
        self.calls = []
        self._orig_find = review._find
        self._orig_schedule = posts_ledger.schedule
        review._find = lambda rid: record
        posts_ledger.schedule = lambda rid, when, path=None: self.calls.append((rid, when))
        self.addCleanup(setattr, review, "_find", self._orig_find)
        self.addCleanup(setattr, posts_ledger, "schedule", self._orig_schedule)

    def test_substack_cannot_be_scheduled(self):
        self._patch({"id": "p1", "platform": "substack", "status": "queued"})
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        result = self.review.schedule_item("p1", future)
        self.assertFalse(result["ok"])
        self.assertIn("Substack", result["msg"])
        self.assertEqual(self.calls, [])

    def test_already_posted_item_cannot_be_rescheduled(self):
        self._patch({"id": "p1", "platform": "linkedin", "status": "posted"})
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        result = self.review.schedule_item("p1", future)
        self.assertFalse(result["ok"])
        self.assertEqual(self.calls, [])

    def test_queued_linkedin_item_schedules(self):
        self._patch({"id": "p1", "platform": "linkedin", "status": "queued"})
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        result = self.review.schedule_item("p1", future)
        self.assertTrue(result["ok"])
        self.assertEqual(len(self.calls), 1)


class TestPublishSettings(unittest.TestCase):
    """This flag is the master safety switch, so its edge cases are the ones
    that decide whether something posts publicly by accident."""

    def setUp(self):
        import publish_settings
        self.ps = publish_settings
        self.dir = tempfile.mkdtemp()
        self.env = os.path.join(self.dir, ".env")
        self._orig_env_path = self.ps.ENV_PATH
        self._orig_repo = self.ps.REPO_DIR
        self.ps.ENV_PATH = self.env
        self.ps.REPO_DIR = self.dir
        self._had = os.environ.pop(self.ps.KEY, None)
        self.addCleanup(self._restore)

    def _restore(self):
        self.ps.ENV_PATH = self._orig_env_path
        self.ps.REPO_DIR = self._orig_repo
        os.environ.pop(self.ps.KEY, None)
        if self._had is not None:
            os.environ[self.ps.KEY] = self._had

    def _write(self, text):
        with open(self.env, "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_missing_env_file_is_never_live(self):
        self.assertFalse(os.path.exists(self.env))
        self.assertFalse(self.ps.is_live())

    def test_stray_process_env_cannot_force_live_without_the_file(self):
        os.environ[self.ps.KEY] = "false"
        self.assertFalse(self.ps.is_live())

    def test_absent_key_defaults_to_dry_run(self):
        self._write("ANTHROPIC_API_KEY=x\n")
        self.assertFalse(self.ps.is_live())

    def test_only_explicit_false_is_live(self):
        for value, expected in [("false", True), ("FALSE", True), (" false ", True),
                                ("true", False), ("0", False), ("no", False),
                                ("", False), ("maybe", False)]:
            self._write("LINKEDIN_DRY_RUN=%s\n" % value)
            self.assertEqual(self.ps.is_live(), expected,
                             "value %r should give live=%s" % (value, expected))

    def test_duplicate_keys_are_collapsed_so_ui_and_publisher_agree(self):
        """python-dotenv honours the LAST definition. Rewriting only the first
        would leave the UI saying DRY RUN while the background task posts."""
        self._write("LINKEDIN_DRY_RUN=true\nOTHER=1\nLINKEDIN_DRY_RUN=false\n")
        self.assertTrue(self.ps.is_live())          # last one wins on read
        self.ps.set_live(False)
        with open(self.env, encoding="utf-8") as fh:
            body = fh.read()
        self.assertEqual(body.count("LINKEDIN_DRY_RUN="), 1)
        self.assertFalse(self.ps.is_live())
        self.assertIn("OTHER=1", body)

    def test_toggling_preserves_other_secrets(self):
        self._write("LINKEDIN_ACCESS_TOKEN=abc123\n"
                    "LINKEDIN_CLIENT_SECRET=shh\n"
                    "LINKEDIN_DRY_RUN=true\n")
        self.ps.set_live(True)
        with open(self.env, encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn("LINKEDIN_ACCESS_TOKEN=abc123", body)
        self.assertIn("LINKEDIN_CLIENT_SECRET=shh", body)
        self.assertTrue(self.ps.is_live())


class TestLedgerIds(unittest.TestCase):
    def test_new_id_does_not_reuse_a_live_id_after_a_removal(self):
        """len(records)+1 would reissue p0002 here, and update() patches only
        the first match -- which could leave a posted record marked scheduled
        and publish it twice."""
        with TempLedger() as path:
            for _ in range(3):
                posts_ledger.add("t", "x", "linkedin", path=path)
            records = posts_ledger.load(path)
            del records[0]                      # p0001 removed, p0003 still live
            posts_ledger.save(records, path)
            fresh = posts_ledger.add("t", "x", "linkedin", path=path)
            self.assertEqual(fresh["id"], "p0004")
            ids = [r["id"] for r in posts_ledger.load(path)]
            self.assertEqual(len(ids), len(set(ids)))


class TestReviewEdit(unittest.TestCase):
    """review.edit_item lets a human revise a queued draft before it posts.
    review._find/posts_ledger.update/load all resolve their path dynamically
    (path=None, defaulting to the current posts_ledger.LEDGER_PATH at call
    time), so reassigning LEDGER_PATH in setUp does redirect them -- but
    posts_ledger.add/save now default path to LEDGER_PATH's value at import
    time (a real early-binding gotcha, see TestReviewScheduling above), so
    a bare add() call here would silently write to the real
    memory/posts.json instead of the temp file. Passing path= explicitly on
    every add()/mark_posted() call below sidesteps that; review.edit_item()
    itself is still called with no path, exercising the real code path."""
    def setUp(self):
        self._saved = posts_ledger.LEDGER_PATH
        self.dir = tempfile.mkdtemp()
        posts_ledger.LEDGER_PATH = os.path.join(self.dir, "posts.json")

    def tearDown(self):
        posts_ledger.LEDGER_PATH = self._saved

    def test_edit_updates_queued_text(self):
        posts_ledger.add("AI writes code", "old body", "linkedin",
                         path=posts_ledger.LEDGER_PATH)
        res = review.edit_item("p0001", "new body from the dashboard")
        self.assertTrue(res["ok"])
        self.assertEqual(posts_ledger.load()[0]["text"], "new body from the dashboard")

    def test_edit_rejects_empty_text(self):
        posts_ledger.add("topic", "old body", "linkedin",
                         path=posts_ledger.LEDGER_PATH)
        res = review.edit_item("p0001", "   ")
        self.assertFalse(res["ok"])
        self.assertEqual(posts_ledger.load()[0]["text"], "old body")

    def test_cannot_edit_after_posted(self):
        posts_ledger.add("topic", "live text", "linkedin",
                         path=posts_ledger.LEDGER_PATH)
        posts_ledger.mark_posted("p0001", "urn:li:share:9", path=posts_ledger.LEDGER_PATH)
        res = review.edit_item("p0001", "sneaky change")
        self.assertFalse(res["ok"])
        self.assertEqual(posts_ledger.load()[0]["text"], "live text")

    def test_edit_missing_id(self):
        self.assertFalse(review.edit_item("p9999", "x")["ok"])


if __name__ == "__main__":
    unittest.main()
