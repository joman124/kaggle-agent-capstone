# -*- coding: utf-8 -*-
"""
The live/dry-run switch for LinkedIn publishing.

The flag lives in .env as LINKEDIN_DRY_RUN, which is also what
linkedin_publisher reads. Keeping one source of truth matters here because two
separate processes act on it: the Streamlit app (when John clicks Publish) and
publish_due.py (run unattended by Task Scheduler). A toggle held only in
Streamlit session state would let the background publisher post while the UI
still showed "dry run".

Fail safe: anything other than an explicit "false" means dry run.

Run:  python publish_settings.py          # show current mode
      python publish_settings.py live     # turn live posting ON
      python publish_settings.py dry      # turn live posting OFF
"""

import os
import sys
import tempfile

from dotenv import dotenv_values, load_dotenv

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(REPO_DIR, ".env")
KEY = "LINKEDIN_DRY_RUN"


def _matches_key(line: str) -> bool:
    """python-dotenv honours 'export KEY=...' too, so both forms count."""
    stripped = line.strip()
    return stripped.startswith(KEY + "=") or stripped.startswith("export " + KEY + "=")


def is_live() -> bool:
    """True only if the .env FILE explicitly says LINKEDIN_DRY_RUN=false.

    Read from the file rather than os.getenv on purpose. load_dotenv does
    nothing (without raising) if .env is missing or unreadable, and os.getenv
    would then fall through to the inherited process environment -- so a stray
    LINKEDIN_DRY_RUN=false left in the Windows environment could make the
    unattended task post live with no .env present at all. No file means no
    posting."""
    if not os.path.exists(ENV_PATH):
        return False
    try:
        values = dotenv_values(ENV_PATH)
    except OSError:
        return False
    # Still refresh the process env so callers see the token/actor.
    load_dotenv(ENV_PATH, override=True)
    return (values.get(KEY) or "true").strip().lower() == "false"


def status() -> dict:
    """Everything the UI needs to describe the current posting mode."""
    live = is_live()
    token = os.getenv("LINKEDIN_ACCESS_TOKEN", "").strip()
    actor = os.getenv("LINKEDIN_ACTOR_URN", "").strip()
    return {
        "live": live,
        "has_token": bool(token),
        "actor": actor,
        "ready": bool(token and actor),
        "label": "LIVE - posts go to LinkedIn" if live else "DRY RUN - nothing posts",
    }


def set_live(live: bool) -> bool:
    """Write the flag back to .env and refresh this process's environment.
    Only this one key is touched, so comments and other keys survive.

    Two details that matter more than they look:

    1. EVERY occurrence is rewritten, not just the first. python-dotenv
       resolves the LAST definition of a key, so rewriting only the first of
       two would leave the UI reporting DRY RUN while the background publisher
       read 'false' and posted live -- the exact failure this switch exists to
       prevent. Duplicates are collapsed to one line.
    2. The write is atomic. This file holds the LinkedIn access token and
       client secret, it is gitignored, and there is no backup anywhere: a
       crash midway through a plain truncating write would destroy both and
       force a full OAuth re-run."""
    value = "false" if live else "true"
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()

    rewritten, seen = [], False
    for line in lines:
        if _matches_key(line):
            if seen:
                continue  # drop duplicate definitions of this key
            rewritten.append(KEY + "=" + value)
            seen = True
        else:
            rewritten.append(line)
    if not seen:
        rewritten.append(KEY + "=" + value)

    handle, temp_path = tempfile.mkstemp(dir=REPO_DIR, prefix=".env.", suffix=".tmp")
    try:
        # newline="\n" keeps the file LF-only instead of rewriting it to CRLF
        # on every toggle.
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as out:
            out.write("\n".join(rewritten) + "\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp_path, ENV_PATH)
    except BaseException:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

    # load_dotenv will not overwrite an existing os.environ entry unless told
    # to, and this process may already hold the old value, so set both.
    os.environ[KEY] = value
    load_dotenv(ENV_PATH, override=True)
    return is_live()


def main(argv) -> None:
    if argv and argv[0].lower() in ("live", "on", "true"):
        print("[SETTINGS] Live posting is now %s." % ("ON" if set_live(True) else "OFF"))
        return
    if argv and argv[0].lower() in ("dry", "off", "false"):
        set_live(False)
        print("[SETTINGS] Live posting is now OFF (dry run).")
        return
    current = status()
    print("[SETTINGS] %s" % current["label"])
    print("           token set: %s   actor: %s"
          % (current["has_token"], current["actor"] or "(none)"))


if __name__ == "__main__":
    main(sys.argv[1:])
