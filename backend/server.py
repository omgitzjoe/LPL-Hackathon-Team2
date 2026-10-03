"""
Local stand-in for the "AWS Lambda (Function URL / Mock Gate)" box in the
architecture diagram.

Run with:
    uvicorn backend.server:app --reload --port 8000

This exposes the same request/response shape that a real Lambda Function URL
would (see infra/lambda_function.py for the AWS deployment version), so the
frontend talks to an identical contract whether running locally or against
a deployed Lambda.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.lambda_handler import (
    HandlerError,
    approve_handler,
    generate_draft_handler,
    list_audit_log_handler,
    list_clients_handler,
)

app = FastAPI(title="LPL Delegation Mock Gate")

# Allow the Streamlit frontend (different port) to call this API locally.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateDraftRequest(BaseModel):
    client_id: str
    request_prompt: str
    advisor: str = "Unknown Advisor"


class ApproveRequest(BaseModel):
    request_id: str
    advisor: str = "Unknown Advisor"
    edited_draft: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/clients")
def clients():
    return list_clients_handler()


@app.post("/generate-draft")
def generate_draft(req: GenerateDraftRequest):
    try:
        return generate_draft_handler(req.model_dump())
    except HandlerError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@app.post("/approve")
def approve(req: ApproveRequest):
    try:
        return approve_handler(req.model_dump())
    except HandlerError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@app.get("/audit-log")
def audit_log():
    return list_audit_log_handler()
