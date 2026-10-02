"""
Core "Lambda" business logic.

These pure handler functions implement the Mock Gate behavior from the
architecture diagram (steps 3-5 and 7-8). They are deliberately decoupled
from any specific web framework so they can be:

1. Called directly by backend/server.py (FastAPI) for local development, or
2. Wrapped by infra/lambda_function.py as a real AWS Lambda Function URL
   handler for deployment.
"""
from backend import mock_clients, state_store
from backend.bedrock_client import BedrockDraftGenerator

_draft_generator = BedrockDraftGenerator()


class HandlerError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def generate_draft_handler(payload: dict) -> dict:
    """
    Step 3: Fetch mock LPL client profile data from hardcoded dictionary.
    Step 4: Generate the draft document & apply LPL compliance guardrails via Bedrock.
    Step 5: Save state as PENDING_APPROVAL & return draft payload.
    """
    client_id = payload.get("client_id")
    request_prompt = payload.get("request_prompt")
    advisor = payload.get("advisor", "Unknown Advisor")

    if not client_id or not request_prompt:
        raise HandlerError(400, "client_id and request_prompt are required")

    client_profile = mock_clients.get_client(client_id)
    if client_profile is None:
        raise HandlerError(404, f"No mock client profile found for client_id={client_id}")

    draft = _draft_generator.generate_draft(client_profile, request_prompt)

    record = state_store.create_request(
        client_id=client_id,
        client_name=client_profile["name"],
        advisor=advisor,
        request_prompt=request_prompt,
        draft=draft,
    )

    return {
        "request_id": record["request_id"],
        "status": record["status"],
        "client_name": record["client_name"],
        "draft": record["draft"],
        "created_at": record["created_at"],
    }


def revise_draft_handler(payload: dict) -> dict:
    """
    Advisor requests a revision: re-invoke Bedrock with the original prompt
    plus the advisor's feedback, then update the stored draft.
    """
    request_id = payload.get("request_id")
    feedback = payload.get("feedback", "")

    if not request_id or not feedback:
        raise HandlerError(400, "request_id and feedback are required")

    record = state_store.get_request(request_id)
    if record is None:
        raise HandlerError(404, f"No request found for request_id={request_id}")
    if record["status"] != "PENDING_APPROVAL":
        raise HandlerError(400, f"Request {request_id} is not in PENDING_APPROVAL state")

    client_profile = mock_clients.get_client(record["client_id"])
    revision_prompt = (
        f"{record['request_prompt']}\n\n"
        f"--- Previous draft ---\n{record['draft']}\n\n"
        f"--- Advisor feedback ---\n{feedback}\n\n"
        f"Please revise the draft to address the advisor's feedback."
    )
    new_draft = _draft_generator.generate_draft(client_profile, revision_prompt)

    updated = state_store.revise_request(request_id, new_draft, feedback)

    return {
        "request_id": request_id,
        "status": updated["status"],
        "client_name": updated["client_name"],
        "draft": updated["draft"],
        "revision_count": updated.get("revision_count", 1),
    }


def approve_handler(payload: dict) -> dict:
    """
    Step 7: Advisor reviews draft and clicks [APPROVE & EXECUTE].
    Step 8: Log the approval to the audit trail.
    """
    request_id = payload.get("request_id")
    advisor = payload.get("advisor", "Unknown Advisor")

    if not request_id:
        raise HandlerError(400, "request_id is required")

    result = state_store.approve_request(request_id, advisor)
    if result is None:
        raise HandlerError(404, f"No request found for request_id={request_id}")

    return {
        "status": "APPROVED",
        "request_id": request_id,
        "logged_to_audit": True,
        "audit_entry": result["audit_entry"],
    }


def list_clients_handler() -> dict:
    return {"clients": mock_clients.list_clients()}


def get_client_handler(client_id: str) -> dict:
    client = mock_clients.get_client(client_id)
    if client is None:
        raise HandlerError(404, f"No client found for client_id={client_id}")
    return {"client": client}


def list_audit_log_handler() -> dict:
    return {"audit_log": state_store.list_audit_log()}
