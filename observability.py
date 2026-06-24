# -*- coding: utf-8 -*-
"""
Structured logging of every agent decision: which agent acted, what inputs
it took, what it decided, and any scores attached. Appends one JSON object
per line to logs/agent_trace.jsonl so a full run produces a readable,
greppable trace (the Day 4/5 observability talking point for the capstone).
"""

import json
import os
from datetime import datetime, timezone

LOG_DIR = "logs"
LOG_PATH = os.path.join(LOG_DIR, "agent_trace.jsonl")


def log_decision(agent: str, action: str, **fields) -> dict:
    """Record one agent decision and append it to the trace file.
    agent: which agent acted (e.g. 'writer', 'strategist').
    action: what kind of decision (e.g. 'draft_attempt', 'plan_week').
    fields: anything relevant - inputs, decision, scores. Returns the
    record that was written so callers/tests can inspect it directly."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent,
        "action": action,
        **fields,
    }
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record
