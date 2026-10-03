"""
FastAPI app: local stand-in for the "AWS Lambda (Function URL / Mock Gate)" box in the
architecture diagram.

Run with:
    uvicorn backend.server:app --reload --port 8000

Every endpoint except /health, /auth/info and /auth/login requires a bearer token
obtained from /auth/login. The signed-in user is passed to the handlers, so audit
records carry the real user ID and role.
"""
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend import auth
from backend.lambda_handler import (
    HandlerError,
    advisor_approve_handler,
    check_handler,
    generate_draft_handler,
    get_client_handler,
    get_request_handler,
    list_audit_log_handler,
    list_clients_handler,
    list_requests_handler,
    revise_draft_handler,
    save_draft_handler,
    supervise_handler,
    verify_audit_handler,
)
from backend import state_store

app = FastAPI(title="LPL Delegation Mock Gate")

# Allow the Streamlit frontend (different port) to call this API locally.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    user_id: str
    password: str


class GenerateDraftRequest(BaseModel):
    client_id: str
    request_prompt: str


class ReviseDraftRequest(BaseModel):
    request_id: str
    feedback: str


class SaveDraftRequest(BaseModel):
    request_id: str
    draft: str


class AdvisorApproveRequest(BaseModel):
    request_id: str
    final_draft: Optional[str] = None


class SuperviseRequest(BaseModel):
    request_id: str
    decision: str
    comment: Optional[str] = ""


class CheckRequest(BaseModel):
    text: str
    client_id: Optional[str] = None


def current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    try:
        return auth.verify_token(token)
    except auth.AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except HandlerError as e:
        detail = {"message": e.message, **e.extra} if e.extra else e.message
        raise HTTPException(status_code=e.status_code, detail=detail)


@app.get("/health")
def health():
    mode = state_store.storage_mode()
    return {"status": "ok", "storage": mode, "dynamo": mode == "dynamodb"}


@app.get("/auth/info")
def auth_info():
    return {"demo_mode": auth.is_demo_mode()}


@app.post("/auth/login")
def login(req: LoginRequest):
    try:
        user = auth.authenticate(req.user_id.strip(), req.password)
    except auth.AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return {"token": auth.issue_token(user), "user": user}


@app.get("/auth/me")
def me(user: dict = Depends(current_user)):
    return {"user": user}


@app.get("/clients")
def clients(user: dict = Depends(current_user)):
    return _run(list_clients_handler, user)


@app.get("/clients/{client_id}")
def client_detail(client_id: str, user: dict = Depends(current_user)):
    return _run(get_client_handler, client_id, user)


@app.post("/compliance/check")
def compliance_check(req: CheckRequest, user: dict = Depends(current_user)):
    return _run(check_handler, req.model_dump(), user)


@app.post("/generate-draft")
def generate_draft(req: GenerateDraftRequest, user: dict = Depends(current_user)):
    return _run(generate_draft_handler, req.model_dump(), user)


@app.post("/revise-draft")
def revise_draft(req: ReviseDraftRequest, user: dict = Depends(current_user)):
    return _run(revise_draft_handler, req.model_dump(), user)


@app.post("/save-draft")
def save_draft(req: SaveDraftRequest, user: dict = Depends(current_user)):
    return _run(save_draft_handler, req.model_dump(), user)


@app.post("/advisor-approve")
def advisor_approve(req: AdvisorApproveRequest, user: dict = Depends(current_user)):
    return _run(advisor_approve_handler, req.model_dump(), user)


@app.post("/supervise")
def supervise(req: SuperviseRequest, user: dict = Depends(current_user)):
    return _run(supervise_handler, req.model_dump(), user)


@app.get("/requests")
def requests_list(
    statuses: Optional[str] = Query(default=None, description="Comma-separated statuses"),
    mine: bool = False,
    user: dict = Depends(current_user),
):
    wanted = [s.strip() for s in statuses.split(",") if s.strip()] if statuses else None
    return _run(list_requests_handler, wanted, mine, user)


@app.get("/requests/{request_id}")
def request_detail(request_id: str, user: dict = Depends(current_user)):
    return _run(get_request_handler, request_id, user)


@app.get("/audit-log")
def audit_log(user: dict = Depends(current_user)):
    return _run(list_audit_log_handler, user)


@app.get("/audit-log/verify")
def audit_verify(user: dict = Depends(current_user)):
    return _run(verify_audit_handler, user)
