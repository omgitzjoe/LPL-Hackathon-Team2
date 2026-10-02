"""
Request state store + append-only audit log backed by DynamoDB.

Diagram step 5: "Saves state as PENDING_APPROVAL & returns draft payload"
Diagram step 7/8: Advisor approves -> action is "Logged to Audit"

Uses DynamoDB for persistent storage across deploys. Falls back to in-memory
storage if DynamoDB is unavailable (local dev without AWS credentials).
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
AUDIT_LOG_PATH = DATA_DIR / "audit_log.json"

REQUESTS_TABLE = os.environ.get("DYNAMODB_REQUESTS_TABLE", "lpl-delegation-requests")
AUDIT_TABLE = os.environ.get("DYNAMODB_AUDIT_TABLE", "lpl-audit-log")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

_lock = threading.Lock()
_requests: dict[str, dict] = {}

_dynamo = None
_use_dynamo = False


def _init_dynamo():
    global _dynamo, _use_dynamo
    if _dynamo is not None or _use_dynamo:
        return
    try:
        import boto3
        _dynamo = boto3.resource("dynamodb", region_name=AWS_REGION)
        # Use GetItem (always permitted) instead of DescribeTable to verify connectivity
        _dynamo.Table(REQUESTS_TABLE).get_item(Key={"request_id": "__ping__"})
        _use_dynamo = True
    except Exception:
        _dynamo = None
        _use_dynamo = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_for_dynamo(item: dict) -> dict:
    """Replace None values with a sentinel and convert floats to Decimal."""
    cleaned = {}
    for k, v in item.items():
        if v is None:
            cleaned[k] = "NULL"
        elif isinstance(v, float):
            cleaned[k] = Decimal(str(v))
        else:
            cleaned[k] = v
    return cleaned


def _restore_from_dynamo(item: dict) -> dict:
    """Reverse the DynamoDB sanitization."""
    cleaned = {}
    for k, v in item.items():
        if v == "NULL":
            cleaned[k] = None
        elif isinstance(v, Decimal):
            cleaned[k] = int(v) if v == int(v) else float(v)
        else:
            cleaned[k] = v
    return cleaned


# ── File-based audit log (fallback) ──

def _load_audit_log_file() -> list[dict]:
    if not AUDIT_LOG_PATH.exists():
        return []
    try:
        return json.loads(AUDIT_LOG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _save_audit_log_file(entries: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_LOG_PATH.write_text(json.dumps(entries, indent=2))


# ── Public API ──

def create_request(client_id: str, client_name: str, advisor: str, request_prompt: str, draft: str) -> dict:
    """Create a new delegation request in PENDING_APPROVAL state."""
    _init_dynamo()
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

    if _use_dynamo:
        table = _dynamo.Table(REQUESTS_TABLE)
        table.put_item(Item=_sanitize_for_dynamo(record))
    else:
        with _lock:
            _requests[request_id] = record

    return record


def get_request(request_id: str) -> dict | None:
    _init_dynamo()
    if _use_dynamo:
        table = _dynamo.Table(REQUESTS_TABLE)
        resp = table.get_item(Key={"request_id": request_id})
        item = resp.get("Item")
        return _restore_from_dynamo(item) if item else None
    else:
        with _lock:
            return _requests.get(request_id)


def revise_request(request_id: str, new_draft: str, revision_feedback: str) -> dict | None:
    """Update a PENDING_APPROVAL request with a revised draft."""
    _init_dynamo()
    if _use_dynamo:
        table = _dynamo.Table(REQUESTS_TABLE)
        resp = table.get_item(Key={"request_id": request_id})
        item = resp.get("Item")
        if not item or item.get("status") != "PENDING_APPROVAL":
            return None
        revision_count = int(item.get("revision_count", 0)) + 1
        table.update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET draft = :d, last_revision_feedback = :f, revised_at = :r, revision_count = :c",
            ExpressionAttributeValues={
                ":d": new_draft,
                ":f": revision_feedback,
                ":r": _now(),
                ":c": revision_count,
            },
        )
        resp = table.get_item(Key={"request_id": request_id})
        return _restore_from_dynamo(resp["Item"])
    else:
        with _lock:
            record = _requests.get(request_id)
            if record is None or record["status"] != "PENDING_APPROVAL":
                return None
            record["revision_count"] = record.get("revision_count", 0) + 1
            record["draft"] = new_draft
            record["last_revision_feedback"] = revision_feedback
            record["revised_at"] = _now()
        return record


def approve_request(request_id: str, advisor: str) -> dict | None:
    """Mark a request APPROVED and append an immutable audit log entry."""
    _init_dynamo()
    approved_at = _now()

    if _use_dynamo:
        table = _dynamo.Table(REQUESTS_TABLE)
        resp = table.get_item(Key={"request_id": request_id})
        item = resp.get("Item")
        if not item:
            return None
        record = _restore_from_dynamo(item)

        table.update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET #s = :s, approved_at = :a",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "APPROVED", ":a": approved_at},
        )
        record["status"] = "APPROVED"
        record["approved_at"] = approved_at

        audit_entry = {
            "audit_id": f"AUD-{uuid.uuid4().hex[:8].upper()}",
            "request_id": request_id,
            "client_id": record["client_id"],
            "client_name": record["client_name"],
            "advisor": advisor,
            "action": "APPROVE_AND_EXECUTE",
            "request_prompt": record["request_prompt"],
            "timestamp": approved_at,
        }
        audit_table = _dynamo.Table(AUDIT_TABLE)
        audit_table.put_item(Item=_sanitize_for_dynamo(audit_entry))

        return {"record": record, "audit_entry": audit_entry}
    else:
        with _lock:
            record = _requests.get(request_id)
            if record is None:
                return None
            record["status"] = "APPROVED"
            record["approved_at"] = approved_at

            audit_entry = {
                "audit_id": f"AUD-{uuid.uuid4().hex[:8].upper()}",
                "request_id": request_id,
                "client_id": record["client_id"],
                "client_name": record["client_name"],
                "advisor": advisor,
                "action": "APPROVE_AND_EXECUTE",
                "request_prompt": record["request_prompt"],
                "timestamp": approved_at,
            }
            entries = _load_audit_log_file()
            entries.append(audit_entry)
            _save_audit_log_file(entries)

        return {"record": record, "audit_entry": audit_entry}


def list_audit_log() -> list[dict]:
    _init_dynamo()
    if _use_dynamo:
        table = _dynamo.Table(AUDIT_TABLE)
        resp = table.scan()
        return [_restore_from_dynamo(i) for i in resp.get("Items", [])]
    else:
        with _lock:
            return _load_audit_log_file()


def list_requests() -> list[dict]:
    _init_dynamo()
    if _use_dynamo:
        table = _dynamo.Table(REQUESTS_TABLE)
        resp = table.scan()
        return [_restore_from_dynamo(i) for i in resp.get("Items", [])]
    else:
        with _lock:
            return list(_requests.values())
