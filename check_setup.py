# -*- coding: utf-8 -*-
"""
Diagnostic. Confirms your API key works and shows which models it can use.
Run:  python check_setup.py
This makes ZERO content requests, so it will not burn quota.
"""

import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise SystemExit("No GEMINI_API_KEY found in .env")

print("Key loaded. Last 4 chars:", API_KEY[-4:])
print("Asking the API which models this key can use...\n")

client = genai.Client(api_key=API_KEY)

usable = []
try:
    for m in client.models.list():
        # We only care about models that can generate text content
        actions = getattr(m, "supported_actions", None) or []
        if (not actions) or ("generateContent" in actions):
            print("  -", m.name)
            usable.append(m.name)
except Exception as e:
    print("Could not list models. Raw error:")
    print(" ", str(e)[:300])
    raise SystemExit(
        "\nIf this said PERMISSION_DENIED or API_KEY_INVALID, the key is wrong.\n"
        "If it listed nothing, the Generative Language API may be disabled on the project."
    )

print("\nModels this key can call:", len(usable))
print("\nNext: pick one of the names above (without the 'models/' prefix)")
print("for MODEL in step1_writer.py. A 'flash' one is cheapest/fastest.")
