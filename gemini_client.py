# -*- coding: utf-8 -*-
"""
Shared Gemini call wrapper. Every agent calls generate() instead of touching
the SDK directly, so retry-with-backoff and plain-English error handling stay
in one place as more agents are added.
"""

import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

load_dotenv(override=True)  # .env always wins over a stray system/user env var
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise SystemExit(
        "No GEMINI_API_KEY found. Create a file named .env in this folder with:\n"
        "GEMINI_API_KEY=your_key_here"
    )

client = genai.Client(api_key=API_KEY)

# finish_reason values that mean the model deliberately declined to answer;
# retrying with the same input will not help, so we fail with a clear message.
_BLOCK_FINISH_REASONS = {
    "SAFETY", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII",
    "IMAGE_SAFETY",
}


def _thinking_off():
    """Return a ThinkingConfig that disables the model's internal 'thinking'
    step, or None if this google-genai version predates thinking configs.
    gemini-2.5-flash is a thinking model; with Google Search grounding it can
    return finish_reason=STOP but an empty answer, because the whole turn went
    into thought parts with no final text part. Turning thinking off makes it
    emit the answer again. Only applied to calls that pass disable_thinking
    (currently Scout's grounded call); the pro-tier Writer/Substack drafts
    keep thinking, since reasoning helps draft quality there."""
    tc = getattr(types, "ThinkingConfig", None)
    if tc is None:
        return None
    try:
        return tc(thinking_budget=0)
    except Exception:
        return None


def _debug_candidates(response) -> str:
    """One-line structural summary of a response's candidates/parts, so an
    empty completion stays diagnosable from the log without a live debugger."""
    try:
        cands = response.candidates or []
    except Exception:
        return "candidates=<unavailable>"
    if not cands:
        return "candidates=0"
    bits = [f"candidates={len(cands)}"]
    content = getattr(cands[0], "content", None)
    if content is None:
        bits.append("candidate0.content=None")
        return " ".join(bits)
    parts = getattr(content, "parts", None) or []
    bits.append(f"candidate0.parts={len(parts)}")
    for i, part in enumerate(parts[:4]):
        flags = []
        if getattr(part, "text", None):
            flags.append("text")
        if getattr(part, "thought", None):
            flags.append("thought")
        if getattr(part, "function_call", None):
            flags.append("function_call")
        if getattr(part, "inline_data", None):
            flags.append("inline_data")
        bits.append(f"part{i}=[{','.join(flags) or 'empty'}]")
    return " ".join(bits)


def _extract_text(response) -> str:
    """Return the response's text, or '' if it carried none. response.text is
    a convenience property that is None when no candidate produced a text part
    -- blocked content, or a 'thinking' model (e.g. gemini-2.5-flash) that
    spent its whole output-token budget on internal reasoning before writing
    an answer. Calling .strip() on that None was the old AttributeError crash.
    Falls back to walking candidate parts directly."""
    try:
        primary = response.text
    except Exception:
        primary = None
    if primary:
        return primary.strip()
    try:
        for cand in (response.candidates or []):
            content = getattr(cand, "content", None)
            for part in (getattr(content, "parts", None) or []):
                # Skip 'thought' parts: those are the model's internal
                # reasoning, not the answer (response.text excludes them too).
                if getattr(part, "thought", None):
                    continue
                piece = getattr(part, "text", None)
                if piece:
                    return piece.strip()
    except Exception:
        pass
    return ""


def _empty_response_message(model: str, response) -> str:
    """Plain-English explanation for a response that came back with no text,
    using the prompt block_reason / candidate finish_reason when the SDK
    exposes them, so John sees the real cause instead of a raw traceback."""
    block = None
    try:
        block = getattr(getattr(response, "prompt_feedback", None), "block_reason", None)
    except Exception:
        block = None

    finish = None
    try:
        cands = response.candidates or []
        if cands:
            finish = getattr(cands[0], "finish_reason", None)
    except Exception:
        finish = None
    finish_name = getattr(finish, "name", None) or (str(finish) if finish is not None else None)

    lines = [f"\n[EMPTY] Model '{model}' returned a response with no usable text."]
    if block:
        block_name = getattr(block, "name", None) or str(block)
        lines += [
            f"The prompt was blocked before generation (block_reason={block_name}).",
            "Reword the topic so it does not trip Google's safety filters, then rerun.",
        ]
    elif finish_name and finish_name.upper() in _BLOCK_FINISH_REASONS:
        lines += [
            f"The model stopped for finish_reason={finish_name} (a content filter).",
            "Reword the topic so it does not trip Google's safety filters, then rerun.",
        ]
    elif finish_name and finish_name.upper() == "MAX_TOKENS":
        lines += [
            "The model hit its output-token limit before writing any answer.",
            f"'{model}' is a 'thinking' model, so its internal reasoning can consume",
            "the whole budget and leave no text. Fix by raising max_output_tokens, or",
            "capping the thinking budget, or pointing this agent's model in .env at a",
            "non-thinking model. Tell me the finish_reason and I will wire the fix.",
        ]
    else:
        lines += [
            f"finish_reason={finish_name or 'unknown'}. Usually a transient hiccup or a",
            "grounded/tool response with no plain-text part. Run it once more; if it",
            "repeats, send me the finish_reason above and I will handle that case.",
        ]
    lines += ["", "Response structure: " + _debug_candidates(response)]
    return "\n".join(lines) + "\n"


def generate(model: str, prompt: str, system_instruction: str = None,
             tools: list = None, max_retries: int = 5,
             temperature: float = None, disable_thinking: bool = False) -> str:
    """Call Gemini with automatic retry on transient server errors (503/
    overload) and on 429 rate-limit errors (a backoff-and-retry is worth it
    in case this is a short per-minute throttle rather than a real quota
    cap). temperature, when given, sets the sampling temperature (callers
    pass a per-content-type value from PLATFORM_RULES; the voice judge
    passes 0.0). Raises SystemExit with a plain-English message on bad model
    name (404) or auth errors instead of a raw traceback."""
    config_kwargs = {}
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction
    if tools:
        config_kwargs["tools"] = tools
    if temperature is not None:
        config_kwargs["temperature"] = temperature
    if disable_thinking:
        thinking_cfg = _thinking_off()
        if thinking_cfg is not None:
            config_kwargs["thinking_config"] = thinking_cfg

    last_server_error = None
    last_quota_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )
            text = _extract_text(response)
            if text:
                return text
            # The HTTP call succeeded but the model returned no text. Do not
            # crash on None (the old bug); explain the real cause and stop.
            raise SystemExit(_empty_response_message(model, response))
        except genai_errors.ServerError as e:
            # 503 / 500 / overload: temporary. Wait and retry with backoff.
            last_server_error = e
            wait = 4 * attempt  # 4s, 8s, 12s, ...
            print(f"   [retry] server busy ({str(e)[:40]}...), waiting {wait}s "
                  f"(attempt {attempt}/{max_retries})")
            time.sleep(wait)
            continue
        except genai_errors.ClientError as e:
            msg = str(e)
            if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                # Could be a short per-minute throttle (clears within
                # ~60s) or a real account/project-level daily quota cap
                # (will not clear no matter how long we wait). Back off
                # first; if it never clears across the full retry budget,
                # the message below points at the second case instead.
                last_quota_error = e
                wait = 15 * attempt  # 15s, 30s, 45s, ...
                print(f"   [retry] rate-limited on '{model}', waiting {wait}s "
                      f"(attempt {attempt}/{max_retries})")
                time.sleep(wait)
                continue
            if "NOT_FOUND" in msg or "404" in msg:
                raise SystemExit(
                    f"\n[MODEL] '{model}' is not available to your key.\n"
                    "Run 'python check_setup.py' to list valid model names, then fix\n"
                    "the model name in your .env.\n"
                )
            if "PERMISSION_DENIED" in msg or "API_KEY_INVALID" in msg:
                raise SystemExit("\n[AUTH] Your API key is invalid or lacks permission. Check .env.\n")
            raise
    if last_quota_error is not None:
        raw = str(last_quota_error)
        total_wait = sum(15 * a for a in range(1, max_retries + 1))
        # Surface the structured facts Google buries in the 429 body: which
        # quota tripped (quotaId / quotaMetric), its limit value, and the
        # suggested retry delay. These name the REAL limit, so do NOT truncate
        # them away (the old raw[:300] cut off exactly this).
        import re as _re

        def _grab(key):
            return (_re.findall(r'"%s"\s*:\s*"([^"]+)"' % key, raw)
                    or _re.findall(r"'%s'\s*:\s*'([^']+)'" % key, raw))

        quota_ids = _grab("quotaId")
        quota_metrics = _grab("quotaMetric")
        quota_values = _grab("quotaValue")
        retry_delay = (_grab("retryDelay") or [None])[0]
        joined = " ".join(quota_ids + quota_metrics).lower()

        lines = [
            f"\n[QUOTA] Still rate-limited on model '{model}' after {max_retries} retries",
            f"totaling {total_wait}s of backoff. {total_wait}s is longer than a one-",
            "minute window, so this is NOT a per-minute throttle -- it is a per-day",
            "or per-model cap that will not clear just by waiting.",
            "",
            "The exact limit Google reported:",
        ]
        if quota_ids or quota_metrics:
            names = quota_ids or quota_metrics
            for i, q in enumerate(names):
                val = quota_values[i] if i < len(quota_values) else "?"
                lines.append(f"  - {q}  (limit: {val})")
        else:
            lines.append("  (no structured quotaId returned; see the raw error below)")
        if retry_delay:
            lines.append(f"  Google suggests retrying after: {retry_delay}")
        lines += ["", "Raw Google error:", f"  {raw[:1500]}", ""]

        if "freetier" in joined or "free_tier" in joined:
            lines += [
                "This is a FREE-TIER quota, which means this model is metered on the",
                "free tier even if your account is Tier 1. That happens with preview /",
                "'-latest' aliased models: paid tier does not raise their caps. To get",
                "your paid limits, point this agent's model in .env at a generally-",
                "available id (e.g. gemini-2.5-flash); or keep -latest and accept the",
                "preview cap.",
            ]
        elif "perday" in joined or "per_day" in joined or "requests_per_day" in joined:
            lines += [
                "This is a PER-DAY cap, so it will not reset until the daily rollover",
                "(around midnight Pacific). If your usage was light, the model behind",
                "this name simply has a low daily allowance on your tier.",
            ]
        elif "prepay" in raw.lower() or "depleted" in raw.lower():
            lines += [
                "Your prepaid credits are depleted for this project's billing. Add",
                "credit (or switch the project off prepay billing), then run again.",
            ]
        else:
            lines += [
                "Next: open https://ai.dev/rate-limit and compare this key's limit for",
                f"'{model}' against your usage. A small limit here means this model",
                "name carries a low cap on your tier; a GA model id in .env lifts it.",
            ]
        raise SystemExit("\n".join(lines) + "\n")
    # Exhausted all retries on server errors
    raise SystemExit(
        f"\n[SERVER] Gemini was overloaded after {max_retries} attempts.\n"
        "This is on Google's end, not yours. Wait a minute and run again.\n"
        f"Last error: {str(last_server_error)[:120]}\n"
    )
