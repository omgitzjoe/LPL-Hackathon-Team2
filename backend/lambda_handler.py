"""
Core business logic: drafting, deterministic compliance checks and the two-level
supervision workflow.

Handlers are framework-agnostic. backend/server.py (FastAPI) authenticates the caller
and passes the verified `actor` ({"user_id", "name", "role"}). Identity is never taken
from the request body, so audit entries always record the real signed-in user.

Roles: assistant and advisor draft, advisors give first-level approval, compliance
principals give second-level approval or reject.
"""
from __future__ import annotations

from typing import Optional

from backend import audit_chain, auth, compliance, mock_clients, state_store
from backend.bedrock_client import BedrockDraftGenerator, Config as BedrockConfig

_draft_generator = BedrockDraftGenerator()

EDITABLE = (state_store.STATUS_PENDING_APPROVAL, state_store.STATUS_REJECTED)


class HandlerError(Exception):
    def __init__(self, status_code: int, message: str, extra: Optional[dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.extra = extra or {}


def _require(actor: Optional[dict], *roles: str) -> dict:
    if not actor:
        raise HandlerError(401, "Not signed in")
    if actor["role"] not in roles:
        allowed = ", ".join(auth.ROLE_LABELS[r] for r in roles)
        raise HandlerError(403, f"This action requires one of: {allowed}")
    return actor


def _load(request_id: Optional[str]) -> dict:
    if not request_id:
        raise HandlerError(400, "request_id is required")
    record = state_store.get_request(request_id)
    if record is None:
        raise HandlerError(404, f"No request found for request_id={request_id}")
    return record


def _client_for(record: dict) -> dict:
    client = mock_clients.get_client(record["client_id"])
    if client is None:
        raise HandlerError(404, f"No client found for client_id={record['client_id']}")
    return client


def _audit(action: str, record: dict, actor: dict, **extra) -> dict:
    """Append an audit entry describing `action` on `record`."""
    fields = {
        "action": action,
        "request_id": record["request_id"],
        "client_id": record["client_id"],
        "client_name": record["client_name"],
        "request_prompt": record["request_prompt"],
        "actor_id": actor["user_id"],
        "actor_name": actor["name"],
        "actor_role": actor["role"],
        "status_after": record["status"],
        "model_id": BedrockConfig.BEDROCK_MODEL_ID if not BedrockConfig.MOCK_MODE else "mock",
    }
    fields.update(extra)
    return state_store.append_audit(fields)


def _compliance_fields(result: dict) -> dict:
    return {
        "compliance_passed": result["passed"],
        "compliance_blocking": result["blocking"],
        "compliance_warnings": result["warnings"],
        "compliance_findings": compliance.summarize(result),
        "compliance_ruleset": result["ruleset_version"],
    }


def _view(record: dict) -> dict:
    """Request as returned to clients, including a fresh compliance check."""
    view = dict(record)
    client = mock_clients.get_client(record["client_id"])
    view["compliance"] = compliance.check_draft(record.get("draft", ""), client)
    return view


# ── Drafting ──

def generate_draft_handler(payload: dict, actor: Optional[dict] = None) -> dict:
    _require(actor, auth.ROLE_ASSISTANT, auth.ROLE_ADVISOR)
    client_id = payload.get("client_id")
    request_prompt = (payload.get("request_prompt") or "").strip()
    if not client_id or not request_prompt:
        raise HandlerError(400, "client_id and request_prompt are required")

    client_profile = mock_clients.get_client(client_id)
    if client_profile is None:
        raise HandlerError(404, f"No mock client profile found for client_id={client_id}")

    try:
        draft = _draft_generator.generate_draft(client_profile, request_prompt)
    except RuntimeError as e:
        raise HandlerError(502, str(e))

    record = state_store.create_request(
        client_id=client_id,
        client_name=client_profile["name"],
        actor=actor,
        request_prompt=request_prompt,
        draft=draft,
    )
    result = compliance.check_draft(draft, client_profile)
    _audit(
        "DRAFT_GENERATED", record, actor,
        ai_draft_sha256=audit_chain.sha256_text(draft),
        **_compliance_fields(result),
    )
    return _view(record)


def revise_draft_handler(payload: dict, actor: Optional[dict] = None) -> dict:
    """Re-invoke the model with the previous draft plus the user's feedback."""
    _require(actor, auth.ROLE_ASSISTANT, auth.ROLE_ADVISOR)
    feedback = (payload.get("feedback") or "").strip()
    record = _load(payload.get("request_id"))
    if not feedback:
        raise HandlerError(400, "feedback is required")
    if record["status"] not in EDITABLE:
        raise HandlerError(409, f"Request {record['request_id']} can no longer be revised ({record['status']})")

    client_profile = _client_for(record)
    try:
        new_draft = _draft_generator.revise_draft(
            client_profile, record["request_prompt"], record["draft"], feedback
        )
    except RuntimeError as e:
        raise HandlerError(502, str(e))

    updated = state_store.transition(
        record["request_id"], EDITABLE,
        {
            "draft": new_draft,
            "ai_draft": new_draft,
            "status": state_store.STATUS_PENDING_APPROVAL,
            "revision_count": int(record.get("revision_count", 0)) + 1,
            "last_revision_feedback": feedback,
            "revised_at": state_store._now(),
        },
    )
    if updated is None:
        raise HandlerError(409, "The request changed while it was being revised. Reload and try again.")

    result = compliance.check_draft(new_draft, client_profile)
    _audit(
        "DRAFT_REVISED", updated, actor,
        ai_draft_sha256=audit_chain.sha256_text(new_draft),
        comment=feedback,
        **_compliance_fields(result),
    )
    return _view(updated)


def save_draft_handler(payload: dict, actor: Optional[dict] = None) -> dict:
    """Persist human edits. A rejected draft returns to the advisor queue."""
    _require(actor, auth.ROLE_ASSISTANT, auth.ROLE_ADVISOR)
    record = _load(payload.get("request_id"))
    text = payload.get("draft")
    if text is None:
        raise HandlerError(400, "draft is required")
    if record["status"] not in EDITABLE:
        raise HandlerError(409, f"Request {record['request_id']} can no longer be edited ({record['status']})")
    updated = state_store.transition(
        record["request_id"], EDITABLE,
        {"draft": text, "status": state_store.STATUS_PENDING_APPROVAL, "edited_by": actor["user_id"]},
    )
    if updated is None:
        raise HandlerError(409, "The request changed while it was being saved. Reload and try again.")
    return _view(updated)


def check_handler(payload: dict, actor: Optional[dict] = None) -> dict:
    _require(actor, *auth.ROLES)
    client = mock_clients.get_client(payload.get("client_id") or "")
    return compliance.check_draft(payload.get("text", ""), client)


# ── Two-level approval ──

def advisor_approve_handler(payload: dict, actor: Optional[dict] = None) -> dict:
    """Level 1: the advisor signs off on the final text and sends it to supervision."""
    _require(actor, auth.ROLE_ADVISOR)
    record = _load(payload.get("request_id"))
    if record["status"] not in EDITABLE:
        raise HandlerError(409, f"Request {record['request_id']} is not awaiting advisor approval ({record['status']})")

    final_text = payload.get("final_draft")
    if final_text is None:
        final_text = record["draft"]
    client_profile = _client_for(record)
    result = compliance.check_draft(final_text, client_profile)
    if not result["passed"]:
        raise HandlerError(
            422, "The draft has blocking compliance findings and cannot be approved.", {"compliance": result}
        )

    updated = state_store.transition(
        record["request_id"], EDITABLE,
        {
            "draft": final_text,
            "status": state_store.STATUS_PENDING_SUPERVISION,
            "advisor_approved_by": actor["user_id"],
            "advisor_approved_by_name": actor["name"],
            "advisor_approved_at": state_store._now(),
        },
    )
    if updated is None:
        raise HandlerError(409, "The request changed before it could be approved. Reload and try again.")

    ai_draft = record.get("ai_draft", "")
    try:
        entry = _audit(
            "ADVISOR_APPROVED", updated, actor,
            ai_draft_sha256=audit_chain.sha256_text(ai_draft),
            final_draft_sha256=audit_chain.sha256_text(final_text),
            final_draft=final_text,
            edited_by_human=final_text != ai_draft,
            diff_from_ai=audit_chain.unified_diff(ai_draft, final_text),
            **_compliance_fields(result),
        )
    except Exception:
        # Never leave a state change without its audit record.
        state_store.transition(
            record["request_id"], (state_store.STATUS_PENDING_SUPERVISION,),
            {"status": record["status"], "draft": record["draft"]},
        )
        raise
    return {"request": _view(updated), "audit_entry": entry}


def supervise_handler(payload: dict, actor: Optional[dict] = None) -> dict:
    """Level 2: a compliance principal approves for release or rejects with a reason."""
    _require(actor, auth.ROLE_PRINCIPAL)
    record = _load(payload.get("request_id"))
    decision = (payload.get("decision") or "").lower()
    comment = (payload.get("comment") or "").strip()
    if decision not in ("approve", "reject"):
        raise HandlerError(400, "decision must be 'approve' or 'reject'")
    if decision == "reject" and not comment:
        raise HandlerError(400, "A comment is required when rejecting")
    if record["status"] != state_store.STATUS_PENDING_SUPERVISION:
        raise HandlerError(409, f"Request {record['request_id']} is not awaiting supervision ({record['status']})")
    if actor["user_id"] in (record.get("advisor_approved_by"), record.get("created_by")):
        raise HandlerError(403, "Separation of duties: you cannot supervise a request you created or approved")

    client_profile = _client_for(record)
    final_text = record["draft"]
    result = compliance.check_draft(final_text, client_profile)
    if decision == "approve" and not result["passed"]:
        raise HandlerError(
            422, "The draft has blocking compliance findings and cannot be released.", {"compliance": result}
        )

    new_status = state_store.STATUS_APPROVED if decision == "approve" else state_store.STATUS_REJECTED
    updates = {
        "status": new_status,
        "supervisor_id": actor["user_id"],
        "supervisor_name": actor["name"],
        "supervisor_comment": comment,
        "decided_at": state_store._now(),
    }
    updated = state_store.transition(record["request_id"], (state_store.STATUS_PENDING_SUPERVISION,), updates)
    if updated is None:
        raise HandlerError(409, "Another reviewer already acted on this request. Reload the queue.")

    try:
        entry = _audit(
            "SUPERVISOR_APPROVED" if decision == "approve" else "SUPERVISOR_REJECTED",
            updated, actor,
            final_draft_sha256=audit_chain.sha256_text(final_text),
            final_draft=final_text,
            comment=comment,
            advisor_id=record.get("advisor_approved_by", ""),
            **_compliance_fields(result),
        )
    except Exception:
        state_store.transition(
            record["request_id"], (new_status,), {"status": state_store.STATUS_PENDING_SUPERVISION}
        )
        raise
    return {"request": _view(updated), "audit_entry": entry}


# ── Reads ──

def get_request_handler(request_id: str, actor: Optional[dict] = None) -> dict:
    _require(actor, *auth.ROLES)
    return {"request": _view(_load(request_id))}


def list_requests_handler(statuses: Optional[list], mine: bool, actor: Optional[dict] = None) -> dict:
    _require(actor, *auth.ROLES)
    records = state_store.list_requests()
    if statuses:
        records = [r for r in records if r["status"] in statuses]
    if mine:
        records = [r for r in records if r.get("created_by") == actor["user_id"]]
    summaries = [
        {k: r.get(k, "") for k in (
            "request_id", "client_id", "client_name", "status", "created_by", "created_by_name",
            "created_at", "request_prompt", "advisor_approved_by_name", "supervisor_comment",
        )}
        for r in records
    ]
    return {"requests": summaries}


def list_clients_handler(actor: Optional[dict] = None) -> dict:
    _require(actor, *auth.ROLES)
    return {"clients": mock_clients.list_clients()}


def get_client_handler(client_id: str, actor: Optional[dict] = None) -> dict:
    _require(actor, *auth.ROLES)
    client = mock_clients.get_client(client_id)
    if client is None:
        raise HandlerError(404, f"No client found for client_id={client_id}")
    return {"client": client}


def list_audit_log_handler(actor: Optional[dict] = None) -> dict:
    _require(actor, *auth.ROLES)
    return {"audit_log": state_store.list_audit_log(), "storage": state_store.storage_mode()}


def verify_audit_handler(actor: Optional[dict] = None) -> dict:
    _require(actor, auth.ROLE_PRINCIPAL)
    return state_store.verify_audit_log()


def approve_handler(payload: dict, actor: Optional[dict] = None) -> dict:
    """Kept for the Lambda entrypoint; use /advisor-approve and /supervise instead."""
    raise HandlerError(410, "Use the advisor-approve and supervise endpoints (two-level approval).")
