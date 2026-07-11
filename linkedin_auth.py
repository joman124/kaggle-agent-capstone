# -*- coding: utf-8 -*-
"""
Guided LinkedIn OAuth helper. It gets you an access token and your actor URN
so the Viral agent can post -- without you hand-crafting any HTTP requests.

Non-developer friendly: run it, click the link it prints, approve, and it hands
you the two lines to paste into .env.

Before running, do the one-time app setup in LINKEDIN_SETUP.md and put your
app's client id + secret in .env.

Run:  python linkedin_auth.py               # this repo posts as YOU (member)
      python linkedin_auth.py member
      python linkedin_auth.py organization  # if you ever want a company page
"""

import http.server
import os
import secrets
import sys
import urllib.parse

from dotenv import load_dotenv

load_dotenv(override=True)

# This repo (After Work) posts as John himself, a LinkedIn member.
DEFAULT_MODE = "member"

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
ORG_ACLS_URL = ("https://api.linkedin.com/rest/organizationAcls"
                "?q=roleAssignee&role=ADMINISTRATOR&state=APPROVED")

# Member posting needs w_member_social; openid+profile let us read your member
# id to build the person URN. Organization posting adds the org scopes and the
# admin scope so we can look up which pages you administer.
SCOPES = {
    "member": "openid profile w_member_social",
    "organization": ("openid profile w_member_social w_organization_social "
                     "rw_organization_admin"),
}


def _capture_code(redirect_uri: str) -> dict:
    """Open a one-shot local web server on the redirect URI and return the
    query params LinkedIn sends back (code / state / error)."""
    parsed = urllib.parse.urlparse(redirect_uri)
    host = parsed.hostname or "localhost"
    port = parsed.port or 80
    box = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            box["code"] = params.get("code", [None])[0]
            box["state"] = params.get("state", [None])[0]
            box["error"] = params.get("error", [None])[0]
            box["error_description"] = params.get("error_description", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<h2>LinkedIn authorization received.</h2>"
                b"<p>You can close this tab and return to the terminal.</p>"
            )

        def log_message(self, *args):
            pass  # keep the terminal clean

    server = http.server.HTTPServer((host, port), Handler)
    print("Waiting for LinkedIn to redirect back... (approve in your browser)")
    server.handle_request()  # blocks until exactly one request arrives
    server.server_close()
    return box


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(
            f"\n[AUTH] {name} is not set in .env. Do the one-time app setup in "
            "LINKEDIN_SETUP.md first, then put your app's values in .env."
        )
    return value


def _headers(token: str) -> dict:
    api_version = os.getenv("LINKEDIN_API_VERSION", "202405").strip()
    return {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": api_version,
        "X-Restli-Protocol-Version": "2.0.0",
    }


def _resolve_member_urn(token: str) -> str:
    import requests
    resp = requests.get(USERINFO_URL, headers={"Authorization": f"Bearer {token}"},
                        timeout=30)
    if resp.status_code != 200:
        raise SystemExit(
            f"\n[AUTH] Could not read your member id (HTTP {resp.status_code}: "
            f"{resp.text[:200]}). Make sure the app requested the 'openid' and "
            "'profile' scopes."
        )
    sub = resp.json().get("sub")
    if not sub:
        raise SystemExit("\n[AUTH] userinfo did not include a member id ('sub').")
    return f"urn:li:person:{sub}"


def _resolve_org_urns(token: str) -> list:
    import requests
    resp = requests.get(ORG_ACLS_URL, headers=_headers(token), timeout=30)
    if resp.status_code != 200:
        raise SystemExit(
            f"\n[AUTH] Could not list the pages you administer (HTTP "
            f"{resp.status_code}: {resp.text[:200]}). The app needs the "
            "Community Management API product and the 'rw_organization_admin' "
            "scope, and you must be an admin of the page."
        )
    elements = resp.json().get("elements", [])
    return [e.get("organizationalTarget") for e in elements if e.get("organizationalTarget")]


def main(mode: str) -> None:
    if mode not in SCOPES:
        raise SystemExit(f"\n[AUTH] Unknown mode '{mode}'. Use 'member' or 'organization'.")

    client_id = _require("LINKEDIN_CLIENT_ID")
    client_secret = _require("LINKEDIN_CLIENT_SECRET")
    redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8000/callback").strip()

    state = secrets.token_urlsafe(16)
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": SCOPES[mode],
        "state": state,
    }
    authorize_link = AUTH_URL + "?" + urllib.parse.urlencode(params)

    print(f"\nMode: {mode}")
    print("\n1) Open this link in your browser and approve access:\n")
    print(authorize_link)
    print(f"\n   (Your LinkedIn app must list this exact redirect URL: {redirect_uri})\n")
    try:
        import webbrowser
        webbrowser.open(authorize_link)
    except Exception:
        pass  # if it cannot auto-open, the printed link still works

    result = _capture_code(redirect_uri)
    if result.get("error"):
        raise SystemExit(
            f"\n[AUTH] LinkedIn returned an error: {result['error']} - "
            f"{result.get('error_description')}"
        )
    if result.get("state") != state:
        raise SystemExit("\n[AUTH] State mismatch. Please run the helper again.")
    code = result.get("code")
    if not code:
        raise SystemExit("\n[AUTH] No authorization code was returned. Try again.")

    import requests
    token_resp = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }, timeout=30)
    if token_resp.status_code != 200:
        raise SystemExit(
            f"\n[AUTH] Token exchange failed (HTTP {token_resp.status_code}: "
            f"{token_resp.text[:200]})."
        )
    token = token_resp.json().get("access_token")
    expires_in = token_resp.json().get("expires_in")
    if not token:
        raise SystemExit("\n[AUTH] No access token in the response.")

    print("\n2) Success. Access token obtained.")
    if expires_in:
        print(f"   (It expires in about {int(expires_in) // 86400} days; "
              "re-run this helper to refresh it.)")

    print("\n3) Paste these into your .env file:\n")
    print(f"LINKEDIN_ACCESS_TOKEN={token}")

    if mode == "member":
        urn = _resolve_member_urn(token)
        print(f"LINKEDIN_ACTOR_URN={urn}")
    else:
        urns = _resolve_org_urns(token)
        if not urns:
            print("# No admined pages found. Set LINKEDIN_ACTOR_URN to your page's")
            print("# urn:li:organization:xxxx once you have admin rights.")
        elif len(urns) == 1:
            print(f"LINKEDIN_ACTOR_URN={urns[0]}")
        else:
            print("# You administer several pages -- pick the Metis one:")
            for u in urns:
                print(f"#   LINKEDIN_ACTOR_URN={u}")

    print("\n4) Keep LINKEDIN_DRY_RUN=true for your first check, run the agent")
    print("   once to confirm the draft looks right, then set it to false.")


if __name__ == "__main__":
    chosen_mode = (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODE).lower()
    main(chosen_mode)
