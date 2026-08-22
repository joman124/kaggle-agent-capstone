# -*- coding: utf-8 -*-
"""
Diagnostic. Confirms your API key works and shows which models it can use.
Run:  python check_setup.py
This makes ZERO content requests, so it will not cost anything.
"""

import os
from dotenv import load_dotenv
import anthropic

load_dotenv(override=True)  # .env always wins over a stray system/user env var
API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not API_KEY:
    raise SystemExit("No ANTHROPIC_API_KEY found in .env")

print("Key loaded. Last 4 chars:", API_KEY[-4:])
print("Asking the API which models this key can use...\n")

client = anthropic.Anthropic(api_key=API_KEY)

usable = []
try:
    for m in client.models.list():
        print(f"  - {m.id}  ({m.display_name})")
        usable.append(m.id)
except anthropic.AuthenticationError:
    raise SystemExit(
        "\nThe key was rejected. Copy it again from\n"
        "https://console.anthropic.com/settings/keys into your .env\n"
    )
except Exception as e:
    print("Could not list models. Raw error:")
    print(" ", str(e)[:300])
    raise SystemExit(
        "\nIf this mentioned a connection problem, check your internet.\n"
        "Otherwise the key may lack permission for this workspace.\n"
    )

print("\nModels this key can call:", len(usable))
print("\nNext: put one of the ids above in .env as ANTHROPIC_MODEL")
print("(and ANTHROPIC_WRITER_MODEL). 'claude-opus-5' is the best for drafting;")
print("'claude-sonnet-5' is cheaper and faster if you want to trade quality for cost.")
