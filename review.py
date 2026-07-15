# -*- coding: utf-8 -*-
"""
The approval queue. The scheduled cycle (run_cycle.py) drafts content and puts
it here with status "queued" instead of posting straight to LinkedIn. John then
reviews and approves what goes live -- fast reaction, but a human still says yes
before the brand speaks.

Commands:
  python review.py list                 # show what is waiting
  python review.py show <id>            # print one item in full
  python review.py approve <id>         # post it live (LinkedIn) / mark done
  python review.py reject <id>          # drop it

Approving a LinkedIn item posts it through linkedin_publisher (which honors
LINKEDIN_DRY_RUN). Substack items cannot be auto-posted, so approving one just
records it as done and reminds you to paste it into Substack.
"""

import sys

import posts_ledger


def _find(record_id: str):
    for r in posts_ledger.load():
        if r["id"] == record_id:
            return r
    return None


def approve_item(record_id: str) -> dict:
    """Approve one queued item. Posts LinkedIn items via the publisher (honors
    dry run); marks Substack items done for manual posting. Returns a structured
    result dict so both the CLI and the UI can report cleanly:
      {"ok": bool, "msg": str, "posted": bool, "dry_run": bool, "post_id": str}"""
    record = _find(record_id)
    if not record:
        return {"ok": False, "msg": f"No item with id {record_id}."}
    if record["status"] != "queued":
        return {"ok": False, "msg": f"{record_id} is '{record['status']}', not queued."}

    if record["platform"] == "linkedin":
        from linkedin_publisher import post_text
        result = post_text(record["text"])
        if result["dry_run"]:
            posts_ledger.update(record_id, status="posted", urn="dry-run-simulated")
            return {"ok": True, "posted": False, "dry_run": True,
                    "msg": f"{record_id} approved (DRY RUN -- not actually posted)."}
        posts_ledger.mark_posted(record_id, result["post_id"])
        return {"ok": True, "posted": True, "dry_run": False,
                "post_id": result["post_id"],
                "msg": f"{record_id} posted to LinkedIn (id {result['post_id']})."}
    posts_ledger.update(record_id, status="posted")
    return {"ok": True, "posted": False, "manual": True,
            "msg": f"{record_id} marked done. Paste it into Substack yourself."}


def reject_item(record_id: str) -> dict:
    updated = posts_ledger.update(record_id, status="rejected")
    if updated:
        return {"ok": True, "msg": f"{record_id} rejected."}
    return {"ok": False, "msg": f"No item with id {record_id}."}


def cmd_list() -> None:
    pending = posts_ledger.by_status("queued")
    if not pending:
        print("[REVIEW] Nothing queued.")
        return
    print(f"[REVIEW] {len(pending)} item(s) queued:\n")
    for r in pending:
        first_line = (r.get("text") or "").strip().splitlines()[0:1]
        preview = first_line[0] if first_line else ""
        print(f"  {r['id']}  [{r['platform']}] {r.get('pillar') or '-'}  {r['topic']}")
        print(f"        {preview[:80]}")
    print("\nApprove with:  python review.py approve <id>")


def cmd_show(record_id: str) -> None:
    for r in posts_ledger.load():
        if r["id"] == record_id:
            print(f"[REVIEW] {r['id']} [{r['platform']}] status={r['status']}")
            print(f"Topic: {r['topic']}\n")
            print(r.get("text") or "")
            return
    print(f"[REVIEW] No item with id {record_id}.")


def cmd_approve(record_id: str) -> None:
    record = _find(record_id)
    result = approve_item(record_id)
    print("[REVIEW] " + result["msg"])
    if result.get("manual") and record:
        print("\n" + (record.get("text") or ""))


def cmd_reject(record_id: str) -> None:
    print("[REVIEW] " + reject_item(record_id)["msg"])


def main(argv) -> None:
    if not argv:
        cmd_list()
        return
    cmd = argv[0].lower()
    arg = argv[1] if len(argv) > 1 else None
    if cmd == "list":
        cmd_list()
    elif cmd == "show" and arg:
        cmd_show(arg)
    elif cmd == "approve" and arg:
        cmd_approve(arg)
    elif cmd == "reject" and arg:
        cmd_reject(arg)
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
