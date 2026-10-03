"""
Tamper-evident audit records.

Every audit entry carries the SHA-256 hash of the entry before it, forming a chain.
Changing, deleting or re-ordering any earlier entry breaks every hash after it, which
`verify_chain` detects. This makes the log tamper-evident, not tamper-proof: pair it
with write-once storage (for example S3 Object Lock) for regulatory retention.
"""
from __future__ import annotations

import difflib
import hashlib
import json
from typing import Optional

GENESIS = "GENESIS"
HASH_VERSION = 1


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def canonical_json(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "entry_hash"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_entry_hash(entry: dict) -> str:
    return sha256_text(canonical_json(entry))


def seal(entry: dict, prev_hash: str, seq: int) -> dict:
    """Return a copy of `entry` with sequence, previous hash and its own hash set."""
    sealed = dict(entry)
    sealed["seq"] = seq
    sealed["prev_hash"] = prev_hash
    sealed["hash_version"] = HASH_VERSION
    sealed["entry_hash"] = compute_entry_hash(sealed)
    return sealed


def unified_diff(before: str, after: str) -> str:
    """Line diff from the AI draft to the final approved text."""
    lines = difflib.unified_diff(
        (before or "").splitlines(),
        (after or "").splitlines(),
        fromfile="ai_draft",
        tofile="final_text",
        lineterm="",
        n=1,
    )
    return "\n".join(lines)


def verify_chain(entries: list[dict], head: Optional[dict] = None) -> dict:
    """
    Check hash links, sequence continuity and (optionally) the stored head pointer.

    Entries written before hashing was introduced have no `entry_hash`; they are
    counted as `legacy_unchained` and are not covered by the guarantee.
    """
    chained = [e for e in entries if e.get("entry_hash")]
    legacy = len(entries) - len(chained)
    chained.sort(key=lambda e: int(e.get("seq", 0)))
    errors: list[dict] = []
    prev = GENESIS
    expected_seq = 1
    for e in chained:
        seq = int(e.get("seq", 0))
        ref = {"seq": seq, "audit_id": e.get("audit_id", "")}
        if seq != expected_seq:
            errors.append({**ref, "problem": f"sequence gap: expected {expected_seq}"})
            expected_seq = seq
        if e.get("prev_hash") != prev:
            errors.append({**ref, "problem": "previous-hash link does not match the prior entry"})
        if compute_entry_hash(e) != e["entry_hash"]:
            errors.append({**ref, "problem": "entry contents do not match their hash (modified)"})
        prev = e["entry_hash"]
        expected_seq += 1

    if head:
        head_seq = int(head.get("seq", 0))
        last_seq = int(chained[-1].get("seq", 0)) if chained else 0
        if last_seq < head_seq:
            errors.append({"seq": head_seq, "audit_id": "", "problem": "entries missing at the end of the log"})
        elif chained and head.get("entry_hash") != chained[-1]["entry_hash"]:
            errors.append({"seq": last_seq, "audit_id": "", "problem": "latest entry does not match the stored head"})

    return {
        "ok": not errors,
        "checked": len(chained),
        "legacy_unchained": legacy,
        "head_hash": chained[-1]["entry_hash"] if chained else "",
        "errors": errors,
    }
