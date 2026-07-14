# -*- coding: utf-8 -*-
"""
Pull real engagement numbers back from LinkedIn so the system can learn what
actually landed (the performance loop). Given a post's URN, it reads the public
social counts (reactions + comments) via the socialActions endpoint. Impressions
need the analytics API (org-level) and are left None when unavailable, which is
fine -- reactions/comments are enough to rank relative performance.

Safe without credentials: sync_ledger() no-ops with a clear message if there is
no token, so nothing here breaks a dry-run environment.
"""

import os

from dotenv import load_dotenv

import posts_ledger

load_dotenv(override=True)

SOCIAL_URL = "https://api.linkedin.com/rest/socialActions/"


def _headers(token: str) -> dict:
    version = os.getenv("LINKEDIN_API_VERSION", "202405").strip()
    return {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": version,
        "X-Restli-Protocol-Version": "2.0.0",
    }


def fetch(urn: str, token: str = None) -> dict:
    """Return {"reactions", "comments", "impressions"} for a post URN, or None
    if we cannot read it. impressions is None unless a richer source fills it."""
    token = token or os.getenv("LINKEDIN_ACCESS_TOKEN", "").strip()
    if not token or not urn:
        return None

    import requests
    import urllib.parse
    encoded = urllib.parse.quote(urn, safe="")
    try:
        resp = requests.get(SOCIAL_URL + encoded, headers=_headers(token), timeout=30)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    data = resp.json()
    return {
        "reactions": (data.get("likesSummary") or {}).get("totalLikes", 0),
        "comments": (data.get("commentsSummary") or {}).get("totalComments", 0),
        "impressions": None,
    }


def sync_ledger(path: str = posts_ledger.LEDGER_PATH) -> dict:
    """Fill in metrics for every posted record that has a URN. Returns a small
    summary. No-ops safely (and says so) when there is no token."""
    token = os.getenv("LINKEDIN_ACCESS_TOKEN", "").strip()
    records = posts_ledger.load(path)
    posted = [r for r in records if r.get("status") == "posted" and r.get("urn")]
    if not token:
        return {"updated": 0, "note": "no LINKEDIN_ACCESS_TOKEN; nothing synced",
                "candidates": len(posted)}

    updated = 0
    for r in posted:
        metrics = fetch(r["urn"], token=token)
        if metrics is not None:
            posts_ledger.update(r["id"], path=path, metrics=metrics)
            updated += 1
    return {"updated": updated, "candidates": len(posted)}


if __name__ == "__main__":
    print(sync_ledger())
