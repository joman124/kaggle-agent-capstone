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

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise SystemExit(
        "No GEMINI_API_KEY found. Create a file named .env in this folder with:\n"
        "GEMINI_API_KEY=your_key_here"
    )

client = genai.Client(api_key=API_KEY)


def generate(model: str, prompt: str, system_instruction: str = None,
             tools: list = None, max_retries: int = 5) -> str:
    """Call Gemini with automatic retry on transient server errors (503/
    overload) and on 429 rate-limit errors (a backoff-and-retry is worth it
    in case this is a short per-minute throttle rather than a real quota
    cap). Raises SystemExit with a plain-English message on bad model name
    (404) or auth errors instead of a raw traceback."""
    config_kwargs = {}
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction
    if tools:
        config_kwargs["tools"] = tools

    last_server_error = None
    last_quota_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )
            return response.text.strip()
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
                # ~60s) or a real per-model/per-day quota cap (will not
                # clear no matter how long we wait). Back off first;
                # if it never clears across the full retry budget, the
                # message below points at the second case instead.
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
        total_wait = sum(15 * a for a in range(1, max_retries + 1))
        raise SystemExit(
            f"\n[QUOTA] Still rate-limited on model '{model}' after {max_retries}\n"
            f"retries totaling {total_wait}s of backoff.\n"
            "A real per-minute throttle clears in under 60 seconds, so failing\n"
            "every attempt across this much wait time means this is NOT a\n"
            "per-minute limit - it is a real quota cap on this specific model.\n"
            "This usually means: the free tier gives pro-tier models (like\n"
            "gemini-pro-latest) a very low or zero daily quota unless billing is\n"
            "actively linked to the SAME Cloud project this key belongs to. An\n"
            "AI Studio prepaid balance is not automatically the same thing as\n"
            "linked Cloud billing for that project.\n"
            "Next steps:\n"
            "  1. Check this model's actual quota at https://aistudio.google.com/app/apikey\n"
            "     (look up the limit for the exact model named above, not the key in general).\n"
            "  2. If it is a pro-tier model and shows 0 or very low free quota, either\n"
            "     link billing to that key's Cloud project, or temporarily set the\n"
            "     relevant .env model variable (e.g. GEMINI_WRITER_MODEL) to a Flash\n"
            "     model, which has a much more generous free tier.\n"
            "  3. Run 'python check_setup.py' to confirm the model name is exactly\n"
            "     right and see what else your key can call.\n"
            f"Raw error from Google: {str(last_quota_error)[:300]}\n"
        )
    # Exhausted all retries on server errors
    raise SystemExit(
        f"\n[SERVER] Gemini was overloaded after {max_retries} attempts.\n"
        "This is on Google's end, not yours. Wait a minute and run again.\n"
        f"Last error: {str(last_server_error)[:120]}\n"
    )
