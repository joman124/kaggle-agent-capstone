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
    overload). Raises SystemExit with a plain-English message on quota
    (429), bad model name (404), or auth errors instead of a raw traceback."""
    config_kwargs = {}
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction
    if tools:
        config_kwargs["tools"] = tools

    last_server_error = None
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
                raise SystemExit(
                    "\n[QUOTA] Your API key has no available quota (limit: 0).\n"
                    "Fix: create a NEW key via 'Create API key in new project' at\n"
                    "aistudio.google.com, put it in .env, and rerun. If a fresh key\n"
                    "still shows limit: 0, enable billing on the Cloud project.\n"
                )
            if "NOT_FOUND" in msg or "404" in msg:
                raise SystemExit(
                    f"\n[MODEL] '{model}' is not available to your key.\n"
                    "Run 'python check_setup.py' to list valid model names, then fix\n"
                    "the model name in your .env.\n"
                )
            if "PERMISSION_DENIED" in msg or "API_KEY_INVALID" in msg:
                raise SystemExit("\n[AUTH] Your API key is invalid or lacks permission. Check .env.\n")
            raise
    # Exhausted all retries on server errors
    raise SystemExit(
        f"\n[SERVER] Gemini was overloaded after {max_retries} attempts.\n"
        "This is on Google's end, not yours. Wait a minute and run again.\n"
        f"Last error: {str(last_server_error)[:120]}\n"
    )
