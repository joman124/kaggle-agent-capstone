# -*- coding: utf-8 -*-
"""
STEP 1: The Writer Agent (single-agent prototype).
Reads the model name from .env (GEMINI_MODEL) so you can change it without
editing code. Fails with a plain-English message on quota/auth errors.
Run:  python step1_writer.py
"""

import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from voice_profile import (
    VOICE_SYSTEM_PROMPT,
    ANTI_AI_TELL_PROMPT,
    BANNED_PHRASES,
    NEGATIVE_PARALLELISM_FLAGS,
)

EM_DASH = chr(0x2014)
CURLY_CHARS = [chr(0x2018), chr(0x2019), chr(0x201C), chr(0x201D)]

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
# Default to a current Flash model; override anytime by setting GEMINI_MODEL in .env
MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

if not API_KEY:
    raise SystemExit(
        "No GEMINI_API_KEY found. Create a file named .env in this folder with:\n"
        "GEMINI_API_KEY=your_key_here"
    )

client = genai.Client(api_key=API_KEY)
SYSTEM_INSTRUCTION = VOICE_SYSTEM_PROMPT + "\n\n" + ANTI_AI_TELL_PROMPT


def _generate(prompt: str, max_retries: int = 5) -> str:
    """Call Gemini with automatic retry on transient server errors (503/overload)."""
    last_server_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                ),
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
                    f"\n[MODEL] '{MODEL}' is not available to your key.\n"
                    "Run 'python check_setup.py' to list valid model names, then set\n"
                    "GEMINI_MODEL in your .env to one of them.\n"
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


def write_linkedin_post(topic: str) -> str:
    prompt = f"""Write a LinkedIn text post about this topic:

TOPIC: {topic}

Find a fresh angle. Do not default to the most obvious patient or scenario;
vary the person, the setting, and the specific detail each time.

Requirements:
- 100 to 300 words
- Open with a specific moment or clinical detail, not an abstraction
- First person
- End on something unresolved or a quiet observation
- Add 3 to 5 relevant hashtags on the last line
- No external links in the body
- No emoji

Write only the post. No preamble, no explanation."""
    return _generate(prompt)


def run_guardrails(text: str) -> dict:
    lowered = text.lower()
    banned_hits = [p for p in BANNED_PHRASES if p in lowered]
    parallelism_hits = [p for p in NEGATIVE_PARALLELISM_FLAGS if p in lowered]
    em_dash_count = text.count(EM_DASH)
    curly = any(ch in text for ch in CURLY_CHARS)
    return {
        "banned_phrases": banned_hits,
        "negative_parallelisms": parallelism_hits,
        "em_dash_count": em_dash_count,
        "has_curly_quotes": curly,
        "clean": not banned_hits and em_dash_count <= 1 and not curly,
    }


if __name__ == "__main__":
    print(f"Using model: {MODEL}\n")
    test_topics = [
        "A patient who felt embarrassed to grieve a job he lost to an AI pipeline",
        "Why the financial loss of a job is survivable but the identity loss breaks people",
        "My brother started talking to ChatGPT more than to me, and I'm a psychologist",
    ]

    for i, topic in enumerate(test_topics, 1):
        print("=" * 70)
        print(f"TEST {i}: {topic}")
        print("=" * 70)
        # Free-tier allows only a few requests per minute; pause between calls.
        if i > 1:
            time.sleep(20)
        post = write_linkedin_post(topic)
        print(post)
        print()
        g = run_guardrails(post)
        if g["clean"]:
            print("[GUARDRAILS] Clean. No AI tells or banned phrases detected.")
        else:
            print("[GUARDRAILS] Flags:")
            if g["banned_phrases"]:
                print(f"   banned phrases: {g['banned_phrases']}")
            if g["em_dash_count"] > 1:
                print(f"   em dashes: {g['em_dash_count']} (limit 1)")
            if g["has_curly_quotes"]:
                print("   curly quotes present (should be straight)")
            if g["negative_parallelisms"]:
                print(f"   review - possible negative parallelism: {g['negative_parallelisms']}")
        print()
