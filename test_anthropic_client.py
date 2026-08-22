# -*- coding: utf-8 -*-
"""
Unit tests for the Anthropic call wrapper. Covers the two bits with real
logic: pulling the answer out of a mixed content list, and resuming a turn
the web-search tool paused. Makes ZERO real API calls.

Run:  python test_anthropic_client.py
"""

import os
import unittest

# anthropic_client raises SystemExit at import without a key, so set a fake
# one before importing. No request is ever sent with it.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")

import anthropic_client  # noqa: E402


class Block:
    """Stand-in for an SDK content block."""

    def __init__(self, type_, text=None):
        self.type = type_
        self.text = text


class Usage:
    """Stand-in for an SDK usage object. Cache fields are omitted on purpose
    for some tests -- the SDK leaves them off when caching is not in play."""

    def __init__(self, input_tokens=0, output_tokens=0, **extra):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        for k, v in extra.items():
            setattr(self, k, v)


class Message:
    """Stand-in for an SDK Message response."""

    def __init__(self, content, stop_reason="end_turn", stop_details=None,
                 usage=None):
        self.content = content
        self.stop_reason = stop_reason
        self.stop_details = stop_details
        self.usage = usage if usage is not None else Usage(100, 50)


class FakeMessages:
    """Returns queued responses and records the requests it was given."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class ClientPatch:
    """Swap anthropic_client's module-level SDK client for a fake."""

    def __init__(self, responses):
        self.fake = FakeMessages(responses)

    def __enter__(self):
        self._real = anthropic_client.client
        anthropic_client.client = type("C", (), {"messages": self.fake})()
        return self.fake

    def __exit__(self, *exc):
        anthropic_client.client = self._real


class TestExtractText(unittest.TestCase):

    def test_skips_non_text_blocks(self):
        # Arrange: the answer is buried behind thinking and search results,
        # so content[0].text would return the wrong thing (or crash).
        msg = Message([
            Block("thinking"),
            Block("server_tool_use"),
            Block("web_search_tool_result"),
            Block("text", "The actual answer."),
        ])

        # Act
        text = anthropic_client._extract_text(msg)

        # Assert
        self.assertEqual(text, "The actual answer.")

    def test_joins_multiple_text_blocks(self):
        msg = Message([Block("text", "First."), Block("text", "Second.")])
        self.assertEqual(anthropic_client._extract_text(msg), "First.\nSecond.")

    def test_empty_when_no_text_blocks(self):
        msg = Message([Block("thinking"), Block("text", None)])
        self.assertEqual(anthropic_client._extract_text(msg), "")


class TestGenerate(unittest.TestCase):

    def test_returns_text_on_normal_turn(self):
        with ClientPatch([Message([Block("text", "done")])]):
            self.assertEqual(anthropic_client.generate("m", "hi"), "done")

    def test_resumes_a_paused_turn(self):
        # Arrange: first response pauses (web search hit its per-turn cap).
        paused = Message([Block("text", "searching")], stop_reason="pause_turn")
        finished = Message([Block("text", "final answer")])

        # Act
        with ClientPatch([paused, finished]) as fake:
            result = anthropic_client.generate("m", "hi")

        # Assert: it re-sent with the paused turn appended, and returned the
        # resumed answer rather than the truncated one.
        self.assertEqual(result, "final answer")
        self.assertEqual(len(fake.calls), 2)
        resumed = fake.calls[1]["messages"]
        self.assertEqual(resumed[0]["role"], "user")
        self.assertEqual(resumed[1]["role"], "assistant")
        self.assertEqual(resumed[1]["content"], paused.content)

    def test_pause_loop_is_bounded(self):
        # A turn that never stops pausing must give up, not spin forever.
        pauses = [Message([Block("text", "x")], stop_reason="pause_turn")
                  for _ in range(anthropic_client._MAX_RESUMES + 1)]
        with ClientPatch(pauses) as fake:
            anthropic_client.generate("m", "hi")
        self.assertEqual(len(fake.calls), anthropic_client._MAX_RESUMES + 1)

    def test_refusal_exits_with_plain_english(self):
        refused = Message([], stop_reason="refusal")
        with ClientPatch([refused]):
            with self.assertRaises(SystemExit) as ctx:
                anthropic_client.generate("m", "hi")
        self.assertIn("declined", str(ctx.exception).lower())

    def test_empty_response_exits_with_plain_english(self):
        with ClientPatch([Message([], stop_reason="max_tokens")]):
            with self.assertRaises(SystemExit) as ctx:
                anthropic_client.generate("m", "hi")
        self.assertIn("EMPTY", str(ctx.exception))

    def test_temperature_is_not_sent(self):
        # Claude Opus 5 rejects temperature with a 400, so the wrapper must
        # swallow it even though callers still pass one.
        with ClientPatch([Message([Block("text", "ok")])]) as fake:
            anthropic_client.generate("m", "hi", temperature=0.0)
        self.assertNotIn("temperature", fake.calls[0])

    def test_system_and_tools_are_passed_through(self):
        with ClientPatch([Message([Block("text", "ok")])]) as fake:
            anthropic_client.generate(
                "m", "hi",
                system_instruction="be brief",
                tools=[anthropic_client.WEB_SEARCH_TOOL],
            )
        call = fake.calls[0]
        self.assertEqual(call["system"], "be brief")
        self.assertEqual(call["tools"][0]["name"], "web_search")


class TestUsageAndCost(unittest.TestCase):

    def test_usage_of_tolerates_missing_cache_fields(self):
        # The SDK omits cache_* entirely when caching is not in play; reading
        # them must not raise.
        got = anthropic_client._usage_of(Message([], usage=Usage(10, 20)))
        self.assertEqual(got["input_tokens"], 10)
        self.assertEqual(got["output_tokens"], 20)
        self.assertEqual(got["cache_read_input_tokens"], 0)

    def test_usage_of_tolerates_no_usage_at_all(self):
        msg = Message([])
        msg.usage = None
        self.assertEqual(anthropic_client._usage_of(msg)["input_tokens"], 0)

    def test_cost_matches_published_rates(self):
        # 1M in + 1M out on Opus 5 = $5 + $25.
        usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000,
                 "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
        self.assertAlmostEqual(
            anthropic_client.estimate_cost("claude-opus-5", usage), 30.00, places=6)

    def test_cached_reads_bill_at_one_tenth(self):
        usage = {"input_tokens": 0, "output_tokens": 0,
                 "cache_read_input_tokens": 1_000_000,
                 "cache_creation_input_tokens": 0}
        self.assertAlmostEqual(
            anthropic_client.estimate_cost("claude-opus-5", usage), 0.50, places=6)

    def test_unknown_model_returns_none_rather_than_guessing(self):
        usage = {"input_tokens": 1000, "output_tokens": 1000,
                 "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
        self.assertIsNone(anthropic_client.estimate_cost("some-future-model", usage))

    def test_paused_turn_sums_usage_across_both_calls(self):
        paused = Message([Block("text", "a")], stop_reason="pause_turn",
                         usage=Usage(100, 10))
        done = Message([Block("text", "b")], usage=Usage(200, 20))
        logged = {}
        real = anthropic_client._log_usage
        anthropic_client._log_usage = lambda m, t, c, u, s: logged.update(
            totals=t, calls=c)
        try:
            with ClientPatch([paused, done]):
                anthropic_client.generate("claude-opus-5", "hi")
        finally:
            anthropic_client._log_usage = real
        self.assertEqual(logged["calls"], 2)
        self.assertEqual(logged["totals"]["input_tokens"], 300)
        self.assertEqual(logged["totals"]["output_tokens"], 30)

    def test_logging_failure_never_breaks_a_draft(self):
        # A broken trace file must cost a log line, not the draft.
        real = anthropic_client.estimate_cost
        anthropic_client.estimate_cost = lambda *a: 1 / 0
        try:
            with ClientPatch([Message([Block("text", "survived")])]):
                self.assertEqual(
                    anthropic_client.generate("claude-opus-5", "hi"), "survived")
        finally:
            anthropic_client.estimate_cost = real


class TestCostReport(unittest.TestCase):

    def _write(self, tmp, records):
        import json
        with open(tmp, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    def test_reports_missing_file_plainly(self):
        out = anthropic_client.cost_report("no-such-file.jsonl")
        self.assertIn("No trace file", out)

    def test_totals_across_models_and_skips_other_records(self):
        import tempfile
        tmp = os.path.join(tempfile.gettempdir(), "trace_test.jsonl")
        self._write(tmp, [
            {"action": "draft_attempt", "agent": "writer"},  # must be ignored
            {"action": "api_call", "inputs": {"model": "claude-opus-5"},
             "usage": {"input_tokens": 1000, "output_tokens": 500,
                       "cache_read_input_tokens": 0}, "cost_usd": 0.0175},
            {"action": "api_call", "inputs": {"model": "claude-sonnet-5"},
             "usage": {"input_tokens": 2000, "output_tokens": 100,
                       "cache_read_input_tokens": 0}, "cost_usd": 0.0075},
        ])
        out = anthropic_client.cost_report(tmp)
        os.remove(tmp)
        self.assertIn("claude-opus-5", out)
        self.assertIn("claude-sonnet-5", out)
        self.assertIn("0.0250", out)  # 0.0175 + 0.0075

    def test_survives_a_truncated_final_line(self):
        import tempfile
        tmp = os.path.join(tempfile.gettempdir(), "trace_trunc.jsonl")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write('{"action":"api_call","inputs":{"model":"claude-opus-5"},'
                    '"usage":{"input_tokens":10,"output_tokens":5},"cost_usd":0.001}\n')
            f.write('{"action":"api_call","inputs":{"model":')  # killed mid-write
        out = anthropic_client.cost_report(tmp)
        os.remove(tmp)
        self.assertIn("claude-opus-5", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
