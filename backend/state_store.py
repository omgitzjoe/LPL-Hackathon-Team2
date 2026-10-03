"""
In-memory request/state store + append-only audit log.

Diagram step 5: "Saves state as PENDING_APPROVAL & returns draft payload"
Diagram step 7/8: Advisor approves -> action is "Logged to Audit"

For the hackathon this is a thread-safe in-memory dict backing the request
lifecycle, plus a JSON file (data/audit_log.json) so the audit trail survives
a server restart. In production this would be DynamoDB (requests) + an
immutable audit log service.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
AUDIT_LOG_PATH = DATA_DIR / "audit_log.json"

_lock = threading.Lock()
_requests: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_audit_log() -> list[dict]:
    if not AUDIT_LOG_PATH.exists():
        return []
    try:
        return json.loads(AUDIT_LOG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _save_audit_log(entries: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_LOG_PATH.write_text(json.dumps(entries, indent=2))


def create_request(client_id: str, client_name: str, advisor: str, request_prompt: str, draft: str) -> dict:
    """Create a new delegation request in PENDING_APPROVAL state."""
    request_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"
    record = {
        "request_id": request_id,
        "client_id": client_id,
        "client_name": client_name,
        "advisor": advisor,
        "request_prompt": request_prompt,
        "draft": draft,
        "status": "PENDING_APPROVAL",
        "created_at": _now(),
        "approved_at": None,
    }
    with _lock:
        _requests[request_id] = record
    return record


def get_request(request_id: str) -> dict | None:
    with _lock:
        return _requests.get(request_id)


def approve_request(request_id: str, advisor: str, edited_draft: str | None = None) -> dict | None:
    """Mark a request APPROVED and append an immutable audit log entry."""
    with _lock:
        record = _requests.get(request_id)
        if record is None:
            return None
        record["status"] = "APPROVED"
        record["approved_at"] = _now()

        if edited_draft is not None:
            cleaned_draft = " ".join(edited_draft.replace("\r\n", "\n").split())
            record["draft"] = cleaned_draft

        audit_entry = {
            "audit_id": f"AUD-{uuid.uuid4().hex[:8].upper()}",
            "request_id": request_id,
            "client_id": record["client_id"],
            "client_name": record["client_name"],
            "advisor": advisor,
            "action": "APPROVE_AND_EXECUTE",
            "request_prompt": record["request_prompt"],
            "final_draft": record["draft"],  
            "timestamp": record["approved_at"],
        }
        entries = _load_audit_log()
        entries.append(audit_entry)
        _save_audit_log(entries)

    return {"record": record, "audit_entry": audit_entry}


def list_audit_log() -> list[dict]:
    with _lock:
        return _load_audit_log()


def list_requests() -> list[dict]:
    with _lock:
        return list(_requests.values())
