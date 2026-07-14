# -*- coding: utf-8 -*-
"""
LinkedIn publisher: posts text content to LinkedIn via the official Posts API.

For After Work this posts as John (a member), using an access token with the
w_member_social scope. The actor is set in .env as LINKEDIN_ACTOR_URN, e.g.
urn:li:person:xxxx.

SAFETY: this posts publicly, which cannot be undone from code. It therefore
defaults to DRY RUN (LINKEDIN_DRY_RUN=true): it builds and logs the exact
payload but sends nothing. Set LINKEDIN_DRY_RUN=false in .env only once you
have a real token and actor URN and want posts to go live.

Getting a token is a one-time manual step (create a LinkedIn developer app,
request the "Share on LinkedIn" product, run the OAuth flow). See README.

Run:  python -m linkedin_publisher "some text to post"   # honors DRY RUN
"""

import os
import sys

from dotenv import load_dotenv

from observability import log_decision

load_dotenv(override=True)

POSTS_URL = "https://api.linkedin.com/rest/posts"


def _dry_run_default() -> bool:
    """Dry run is ON unless .env explicitly says false. Fail safe: an unset
    or malformed value means we do NOT post."""
    return os.getenv("LINKEDIN_DRY_RUN", "true").strip().lower() != "false"


def _build_payload(commentary: str, actor_urn: str) -> dict:
    """The Posts API body for a plain text share. Same shape for a person or
    an organization actor -- only the URN differs."""
    return {
        "author": actor_urn,
        "commentary": commentary,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }


def _api_headers(token: str) -> dict:
    api_version = os.getenv("LINKEDIN_API_VERSION", "202405").strip()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "LinkedIn-Version": api_version,
        "X-Restli-Protocol-Version": "2.0.0",
    }


def _post_comment(post_urn: str, text: str, actor_urn: str, token: str) -> None:
    """Add a comment to a post. Used for the first-comment link strategy:
    LinkedIn suppresses reach on posts with external links in the body, so the
    link goes in the first comment instead. Best-effort -- a failed comment does
    not undo the post, so we do not raise."""
    import requests
    import urllib.parse
    url = ("https://api.linkedin.com/rest/socialActions/"
           + urllib.parse.quote(post_urn, safe="") + "/comments")
    body = {"actor": actor_urn, "message": {"text": text}}
    try:
        requests.post(url, headers=_api_headers(token), json=body, timeout=30)
    except requests.RequestException:
        pass


def post_text(commentary: str, dry_run: bool = None, first_comment: str = None) -> dict:
    """Post plain text to LinkedIn. Returns {"posted": bool, "dry_run": bool,
    "post_id": str|None, "actor": str}. If first_comment is given, it is added
    as the first comment after the post goes live (the link-in-first-comment
    reach strategy). In dry run it logs the payload and returns a simulated id
    so the whole pipeline is testable with no token."""
    if dry_run is None:
        dry_run = _dry_run_default()

    actor_urn = os.getenv("LINKEDIN_ACTOR_URN", "").strip()
    if not actor_urn:
        actor_urn = "urn:li:person:DRY_RUN_PLACEHOLDER"
        if not dry_run:
            raise SystemExit(
                "\n[LINKEDIN] LINKEDIN_ACTOR_URN is not set. Add it to .env "
                "(e.g. urn:li:person:xxxx) before posting for real, or keep "
                "LINKEDIN_DRY_RUN=true."
            )

    payload = _build_payload(commentary, actor_urn)

    if dry_run:
        log_decision(agent="linkedin_publisher", action="post_text",
                     inputs={"actor": actor_urn, "chars": len(commentary)},
                     decision={"dry_run": True, "payload_preview": commentary[:200],
                               "first_comment": bool(first_comment)})
        print("[LINKEDIN] DRY RUN -- nothing was posted. Payload:")
        print(f"  author: {actor_urn}")
        print(f"  commentary ({len(commentary)} chars):\n{commentary}\n")
        if first_comment:
            print(f"  first comment (link): {first_comment}\n")
        return {"posted": False, "dry_run": True,
                "post_id": "dry-run-simulated", "actor": actor_urn}

    token = os.getenv("LINKEDIN_ACCESS_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "\n[LINKEDIN] LINKEDIN_ACCESS_TOKEN is not set but "
            "LINKEDIN_DRY_RUN=false. Add a real token to .env or set "
            "LINKEDIN_DRY_RUN=true."
        )

    # Imported here so dry-run / import stays possible without requests.
    import requests

    headers = _api_headers(token)
    try:
        resp = requests.post(POSTS_URL, headers=headers, json=payload, timeout=30)
    except requests.RequestException as exc:
        raise SystemExit(f"\n[LINKEDIN] Network error posting to LinkedIn: {exc}")

    if resp.status_code in (401, 403):
        raise SystemExit(
            "\n[LINKEDIN] LinkedIn rejected the request (auth/scope). Check that "
            "your token is valid and has w_member_social (member) or "
            "w_organization_social (organization), and that the actor URN "
            f"matches the token. HTTP {resp.status_code}: {resp.text[:300]}"
        )
    if resp.status_code not in (200, 201):
        raise SystemExit(
            f"\n[LINKEDIN] Unexpected response HTTP {resp.status_code}: "
            f"{resp.text[:300]}"
        )

    post_id = resp.headers.get("x-restli-id") or resp.headers.get("x-linkedin-id")
    if first_comment and post_id:
        _post_comment(post_id, first_comment, actor_urn, token)
    log_decision(agent="linkedin_publisher", action="post_text",
                 inputs={"actor": actor_urn, "chars": len(commentary)},
                 decision={"dry_run": False, "post_id": post_id,
                           "first_comment": bool(first_comment)})
    return {"posted": True, "dry_run": False, "post_id": post_id, "actor": actor_urn}


if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) or "Test post from the After Work viral agent."
    result = post_text(text)
    print(f"\n[LINKEDIN] {result}")
