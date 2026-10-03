"""
Request state and the tamper-evident audit log.

Request lifecycle (two-level supervision):

    PENDING_APPROVAL --advisor approves--> PENDING_SUPERVISION --principal approves--> APPROVED
           ^                                       |
           |                                       +--principal rejects--> REJECTED
           +------ revise / save edits ------------+----------------------------+

Every state change appends an entry to the audit log. Entries are hash-chained (see
backend/audit_chain.py) and record the real user ID, role, the compliance result and
a fingerprint of the text at that moment.

Storage: Amazon DynamoDB when reachable (shared by every user), otherwise in-memory
requests plus a local JSON audit file (this machine only).
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

from backend import audit_chain

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
AUDIT_LOG_PATH = DATA_DIR / "audit_log.json"

REQUESTS_TABLE = os.environ.get("DYNAMODB_REQUESTS_TABLE", "lpl-delegation-requests")
AUDIT_TABLE = os.environ.get("DYNAMODB_AUDIT_TABLE", "lpl-audit-log")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
# "true" fails fast instead of silently using per-machine local storage.
REQUIRE_SHARED_STORE = os.environ.get("REQUIRE_SHARED_STORE", "false").lower() == "true"

HEAD_ID = "__HEAD__"  # DynamoDB item that stores the newest audit sequence and hash

STATUS_PENDING_APPROVAL = "PENDING_APPROVAL"
STATUS_PENDING_SUPERVISION = "PENDING_SUPERVISION"
STATUS_APPROVED = "APPROVED"
STATUS_REJECTED = "REJECTED"

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
        # GetItem/Scan are always permitted, unlike DescribeTable.
        _dynamo.Table(REQUESTS_TABLE).get_item(Key={"request_id": "__ping__"})
        _dynamo.Table(AUDIT_TABLE).scan(Limit=1)
        _use_dynamo = True
    except Exception as e:
        _dynamo = None
        _use_dynamo = False
        if REQUIRE_SHARED_STORE:
            raise RuntimeError(f"DynamoDB is required but unavailable: {e}") from e


def storage_mode() -> str:
    """'dynamodb' = shared across all users; 'local' = this machine only."""
    _init_dynamo()
    return "dynamodb" if _use_dynamo else "local"


def _scan_all(table) -> list[dict]:
    items: list[dict] = []
    kwargs: dict = {}
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            return items
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


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


# ── Local audit file (fallback) ──

def _load_audit_log_file() -> list[dict]:
    if not AUDIT_LOG_PATH.exists():
        return []
    try:
        return json.loads(AUDIT_LOG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _save_audit_log_file(entries: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = AUDIT_LOG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(entries, indent=2))
    tmp.replace(AUDIT_LOG_PATH)


# ── Requests ──

def create_request(client_id: str, client_name: str, actor: dict, request_prompt: str, draft: str) -> dict:
    """Create a new delegation request awaiting advisor approval."""
    _init_dynamo()
    request_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"
    record = {
        "request_id": request_id,
        "client_id": client_id,
        "client_name": client_name,
        "created_by": actor["user_id"],
        "created_by_name": actor["name"],
        "created_by_role": actor["role"],
        "request_prompt": request_prompt,
        "draft": draft,
        "ai_draft": draft,
        "status": STATUS_PENDING_APPROVAL,
        "created_at": _now(),
        "revision_count": 0,
    }
    if _use_dynamo:
        _dynamo.Table(REQUESTS_TABLE).put_item(Item=_sanitize_for_dynamo(record))
    else:
        with _lock:
            _requests[request_id] = record
    return dict(record)


def get_request(request_id: str) -> Optional[dict]:
    _init_dynamo()
    if _use_dynamo:
        item = _dynamo.Table(REQUESTS_TABLE).get_item(Key={"request_id": request_id}).get("Item")
        return _restore_from_dynamo(item) if item else None
    with _lock:
        record = _requests.get(request_id)
        return dict(record) if record else None


def list_requests() -> list[dict]:
    _init_dynamo()
    if _use_dynamo:
        records = [_restore_from_dynamo(i) for i in _scan_all(_dynamo.Table(REQUESTS_TABLE))]
    else:
        with _lock:
            records = [dict(r) for r in _requests.values()]
    return sorted(records, key=lambda r: r.get("created_at") or "", reverse=True)


def transition(request_id: str, expected: tuple, updates: dict) -> Optional[dict]:
    """
    Atomically apply `updates` if the request is currently in one of the `expected`
    statuses. Returns the updated record, or None if the request is missing or in
    another state (for example because someone else acted first).
    """
    _init_dynamo()
    if _use_dynamo:
        from botocore.exceptions import ClientError

        names = {"#s": "status"}
        values = {}
        sets = []
        for i, (key, value) in enumerate(updates.items()):
            names[f"#f{i}"] = key
            values[f":v{i}"] = _sanitize_for_dynamo({"x": value})["x"]
            sets.append(f"#f{i} = :v{i}")
        exp_placeholders = []
        for i, status in enumerate(expected):
            values[f":e{i}"] = status
            exp_placeholders.append(f":e{i}")
        try:
            resp = _dynamo.Table(REQUESTS_TABLE).update_item(
                Key={"request_id": request_id},
                UpdateExpression="SET " + ", ".join(sets),
                ConditionExpression=f"#s IN ({', '.join(exp_placeholders)})",
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
                ReturnValues="ALL_NEW",
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return None
            raise
        return _restore_from_dynamo(resp["Attributes"])

    with _lock:
        record = _requests.get(request_id)
        if record is None or record["status"] not in expected:
            return None
        record.update(updates)
        return dict(record)


# ── Audit log ──

def _get_head() -> Optional[dict]:
    item = _dynamo.Table(AUDIT_TABLE).get_item(Key={"audit_id": HEAD_ID}, ConsistentRead=True).get("Item")
    return _restore_from_dynamo(item) if item else None


def append_audit(fields: dict) -> dict:
    """
    Seal and append one audit entry. `fields` holds the event details (action,
    actor, request, hashes...); this adds the ID, timestamp, sequence and hash links.
    Concurrent writers are serialized: in DynamoDB the entry and the head pointer are
    written in one transaction conditioned on the previous sequence number.
    """
    _init_dynamo()
    if _use_dynamo:
        from botocore.exceptions import ClientError

        # The resource's client converts plain Python values to DynamoDB types itself.
        client = _dynamo.meta.client
        for _ in range(8):
            head = _get_head()
            prev_seq = int(head["seq"]) if head else 0
            prev_hash = head["entry_hash"] if head else audit_chain.GENESIS
            entry = audit_chain.seal(
                {"audit_id": f"AUD-{uuid.uuid4().hex[:8].upper()}", "timestamp": _now(), **fields},
                prev_hash,
                prev_seq + 1,
            )
            entry_item = _sanitize_for_dynamo(entry)
            head_item = {
                "audit_id": HEAD_ID,
                "seq": entry["seq"],
                "entry_hash": entry["entry_hash"],
                "updated_at": entry["timestamp"],
            }
            head_put = {"TableName": AUDIT_TABLE, "Item": head_item}
            if head:
                head_put["ConditionExpression"] = "seq = :prev"
                head_put["ExpressionAttributeValues"] = {":prev": prev_seq}
            else:
                head_put["ConditionExpression"] = "attribute_not_exists(audit_id)"
            try:
                client.transact_write_items(TransactItems=[
                    {"Put": {"TableName": AUDIT_TABLE, "Item": entry_item,
                             "ConditionExpression": "attribute_not_exists(audit_id)"}},
                    {"Put": head_put},
                ])
                return entry
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code")
                reasons = [r.get("Code") for r in e.response.get("CancellationReasons", [])]
                # Only a lost race (conditional check failure) is retried.
                if code != "TransactionCanceledException" or "ValidationError" in reasons:
                    raise
        raise RuntimeError("Could not append to the audit log after repeated conflicts")

    with _lock:
        entries = _load_audit_log_file()
        chained = [e for e in entries if e.get("entry_hash")]
        last = max(chained, key=lambda e: int(e.get("seq", 0))) if chained else None
        entry = audit_chain.seal(
            {"audit_id": f"AUD-{uuid.uuid4().hex[:8].upper()}", "timestamp": _now(), **fields},
            last["entry_hash"] if last else audit_chain.GENESIS,
            int(last["seq"]) + 1 if last else 1,
        )
        entries.append(entry)
        _save_audit_log_file(entries)
        return entry


def list_audit_log() -> list[dict]:
    _init_dynamo()
    if _use_dynamo:
        items = [_restore_from_dynamo(i) for i in _scan_all(_dynamo.Table(AUDIT_TABLE))]
        entries = [e for e in items if e.get("audit_id") != HEAD_ID]
    else:
        with _lock:
            entries = _load_audit_log_file()
    return sorted(entries, key=lambda e: (e.get("timestamp") or "", int(e.get("seq") or 0)))


def verify_audit_log() -> dict:
    """Recompute the hash chain and compare it with the stored head pointer."""
    _init_dynamo()
    head = _get_head() if _use_dynamo else None
    result = audit_chain.verify_chain(list_audit_log(), head)
    result["storage"] = storage_mode()
    return result
