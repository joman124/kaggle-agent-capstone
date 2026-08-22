# -*- coding: utf-8 -*-
"""
Shared Anthropic (Claude) call wrapper. Every agent calls generate() instead
of touching the SDK directly, so retry-with-backoff and plain-English error
handling stay in one place as more agents are added.

Replaces the old gemini_client.py. Same generate() signature, so agents did
not change beyond their import line.
"""

import os
from dotenv import load_dotenv
import anthropic

load_dotenv(override=True)  # .env always wins over a stray system/user env var
API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not API_KEY:
    raise SystemExit(
        "No ANTHROPIC_API_KEY found. Create a file named .env in this folder with:\n"
        "ANTHROPIC_API_KEY=your_key_here\n"
        "Get a key at https://console.anthropic.com"
    )

# The SDK retries 429s and 5xx itself with exponential backoff, so there is no
# hand-rolled retry loop below -- max_retries here is that budget.
client = anthropic.Anthropic(api_key=API_KEY, max_retries=5)

# Server-side web search, run on Anthropic's infrastructure. Scout passes this
# in tools= as the replacement for Gemini's old Google Search grounding.
WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search"}

# Generous enough for a Substack essay. Caps thinking + answer together, so
# leave headroom; well under the ~16k where non-streaming risks a timeout.
MAX_TOKENS = 16000

# A turn using the web-search tool can stop with stop_reason="pause_turn" when
# the server-side tool loop hits its iteration cap. Re-sending resumes it; this
# bounds how many times, so a pathological search cannot spin forever.
_MAX_RESUMES = 5

# USD per million tokens (input, output). Cached reads bill at ~0.1x input.
# Update if Anthropic changes pricing; an unknown model logs tokens with a
# null cost rather than guessing.
PRICING = {
    "claude-opus-5":    (5.00, 25.00),
    "claude-opus-4-8":  (5.00, 25.00),
    "claude-sonnet-5":  (3.00, 15.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00,  5.00),
}


def estimate_cost(model: str, usage: dict):
    """USD for one call, or None if we have no price for this model. Cached
    input reads bill at ~10% of the input rate; cache writes at ~125%."""
    price = PRICING.get(model)
    if price is None:
        return None
    in_rate, out_rate = price
    return (
        usage["input_tokens"] * in_rate
        + usage["cache_read_input_tokens"] * in_rate * 0.10
        + usage["cache_creation_input_tokens"] * in_rate * 1.25
        + usage["output_tokens"] * out_rate
    ) / 1e6


def _usage_of(message) -> dict:
    """Pull token counts off a response. Every field is read defensively:
    the SDK omits the cache fields entirely when caching is not in play."""
    u = getattr(message, "usage", None)
    return {
        "input_tokens": getattr(u, "input_tokens", 0) or 0,
        "output_tokens": getattr(u, "output_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
        "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
    }


def _extract_text(message) -> str:
    """Join the response's text blocks. Claude interleaves thinking, tool_use,
    and web-search-result blocks with the text ones, so filtering on .type is
    required -- content[0] is not reliably the answer."""
    parts = [b.text for b in message.content
             if getattr(b, "type", None) == "text" and getattr(b, "text", None)]
    return "\n".join(parts).strip()


def _refusal_message(message) -> str:
    """Plain-English explanation when Claude's safety classifiers declined the
    request. This is an HTTP 200 with stop_reason='refusal', not an error, so
    it has to be checked explicitly before reading the content."""
    details = getattr(message, "stop_details", None)
    category = getattr(details, "category", None)
    lines = ["\n[DECLINED] Claude declined to answer this prompt."]
    if category:
        lines.append(f"Reason category: {category}")
    lines += [
        "Reword the topic so it does not read as a restricted request, then rerun.",
        "If this keeps happening on an ordinary topic, send me the category above",
        "and I will handle that case.",
    ]
    return "\n".join(lines) + "\n"


def _empty_message(model: str, message) -> str:
    """Plain-English explanation for a response that came back with no text,
    so John sees the real cause instead of a raw traceback."""
    stop = getattr(message, "stop_reason", None)
    lines = [f"\n[EMPTY] Model '{model}' returned a response with no usable text.",
             f"stop_reason={stop or 'unknown'}."]
    if stop == "max_tokens":
        lines += [
            "The model hit its output limit before finishing an answer. Raise",
            f"MAX_TOKENS in {os.path.basename(__file__)} (currently {MAX_TOKENS}).",
        ]
    else:
        lines += [
            "Usually a transient hiccup. Run it once more; if it repeats, send me",
            "the stop_reason above and I will wire the fix.",
        ]
    return "\n".join(lines) + "\n"


def _log_usage(model: str, totals: dict, api_calls: int, used_tools: bool,
               stop_reason: str) -> None:
    """Append one token/cost record per generate() to logs/agent_trace.jsonl.
    Never let logging break a run: a failure here costs a trace line, not a
    draft John was waiting on."""
    try:
        from observability import log_decision
        log_decision(
            agent="anthropic_client",
            action="api_call",
            inputs={"model": model, "api_calls": api_calls,
                    "used_tools": used_tools},
            decision={"stop_reason": stop_reason},
            usage=totals,
            cost_usd=estimate_cost(model, totals),
        )
    except Exception:
        pass


def generate(model: str, prompt: str, system_instruction: str = None,
             tools: list = None, max_retries: int = 5,
             temperature: float = None, disable_thinking: bool = False) -> str:
    """Call Claude and return its text.

    temperature and disable_thinking are accepted but ignored: Claude Opus 5
    rejects a temperature parameter outright (400) and thinks adaptively by
    default. Callers still pass them from PLATFORM_RULES, so the parameters
    stay in the signature rather than forcing an edit at every call site.
    ponytail: the ceiling is that per-content-type temperature no longer
    varies output -- steer tone through the prompt instead. To restore a
    real knob, add output_config={"effort": ...} here and map the rules to it.

    Raises SystemExit with a plain-English message on auth, quota, bad model
    name, and refusal instead of a raw traceback.
    """
    kwargs = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system_instruction:
        kwargs["system"] = system_instruction
    if tools:
        kwargs["tools"] = tools

    # Accumulated across resumes, so one generate() logs one total even when
    # a paused web-search turn took several HTTP calls.
    totals = {"input_tokens": 0, "output_tokens": 0,
              "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    api_calls = 0

    for _ in range(_MAX_RESUMES + 1):
        try:
            message = client.messages.create(**kwargs)
        except anthropic.AuthenticationError:
            raise SystemExit(
                "\n[AUTH] Your ANTHROPIC_API_KEY is invalid or expired. Check .env.\n"
            )
        except anthropic.PermissionDeniedError:
            raise SystemExit(
                "\n[AUTH] Your API key lacks permission for this request.\n"
                "Check the key's workspace at https://console.anthropic.com\n"
            )
        except anthropic.NotFoundError:
            raise SystemExit(
                f"\n[MODEL] '{model}' is not available to your key.\n"
                "Run 'python check_setup.py' to list valid model names, then fix\n"
                "the model name in your .env.\n"
            )
        except anthropic.RateLimitError as e:
            raise SystemExit(
                f"\n[QUOTA] Still rate-limited on '{model}' after {max_retries} retries.\n"
                "Either you are sending too fast, or this key's spend limit is reached.\n"
                "Check https://console.anthropic.com/settings/limits, then run again.\n"
                f"Anthropic's message: {str(e)[:300]}\n"
            )
        except anthropic.APIConnectionError:
            raise SystemExit(
                "\n[NETWORK] Could not reach Anthropic. Check your internet connection\n"
                "and run again.\n"
            )
        except anthropic.APIStatusError as e:
            raise SystemExit(
                f"\n[SERVER] Anthropic returned an error ({e.status_code}) after\n"
                f"{max_retries} retries. Usually on their end. Wait a minute and rerun.\n"
                f"Last error: {str(e)[:200]}\n"
            )

        api_calls += 1
        for k, v in _usage_of(message).items():
            totals[k] += v

        if message.stop_reason != "pause_turn":
            break
        # A server-side tool (web search) hit its per-turn cap. Append the
        # paused turn and re-send; the API picks up where it left off.
        kwargs["messages"] = [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": message.content},
        ]

    _log_usage(model, totals, api_calls, bool(tools), message.stop_reason)

    if message.stop_reason == "refusal":
        raise SystemExit(_refusal_message(message))

    text = _extract_text(message)
    if not text:
        raise SystemExit(_empty_message(model, message))
    return text


def cost_report(path: str = None) -> str:
    """Summarize real spend from the trace file. Run:  python anthropic_client.py
    Reads what generate() logged, so the numbers are measured, not estimated."""
    import json
    from collections import defaultdict

    path = path or os.path.join("logs", "agent_trace.jsonl")
    if not os.path.exists(path):
        return (f"No trace file at {path} yet.\n"
                "Run a cycle first, then run this again.")

    by_model = defaultdict(lambda: {"calls": 0, "in": 0, "out": 0, "usd": 0.0})
    unpriced = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except ValueError:
                continue  # a partially written line; skip it
            if rec.get("action") != "api_call":
                continue
            m = rec.get("inputs", {}).get("model", "?")
            u = rec.get("usage", {})
            row = by_model[m]
            row["calls"] += 1
            row["in"] += u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
            row["out"] += u.get("output_tokens", 0)
            if rec.get("cost_usd") is None:
                unpriced.add(m)
            else:
                row["usd"] += rec["cost_usd"]

    if not by_model:
        return ("The trace file has no api_call records yet.\n"
                "Those are written from the first model call onward.")

    w = max(len(m) for m in by_model)
    lines = [f"Spend from {path}", "",
             f"{'model':<{w}}  {'calls':>6} {'in tok':>10} {'out tok':>10} {'USD':>9}"]
    total = 0.0
    for m, r in sorted(by_model.items(), key=lambda kv: -kv[1]["usd"]):
        total += r["usd"]
        lines.append(f"{m:<{w}}  {r['calls']:>6} {r['in']:>10,} {r['out']:>10,} "
                     f"{r['usd']:>9.4f}")
    lines += ["", f"{'TOTAL':<{w}}  {sum(r['calls'] for r in by_model.values()):>6} "
                  f"{sum(r['in'] for r in by_model.values()):>10,} "
                  f"{sum(r['out'] for r in by_model.values()):>10,} {total:>9.4f}"]
    if unpriced:
        lines += ["", "No price on file for: " + ", ".join(sorted(unpriced)),
                  "Add it to PRICING in this file to include it in the total."]
    return "\n".join(lines)


if __name__ == "__main__":
    print(cost_report())
