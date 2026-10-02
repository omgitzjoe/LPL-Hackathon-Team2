# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LPL Delegation Assistant is a human-in-the-loop drafting workflow for LPL
Financial advisors, built for an AWS hackathon. An advisor delegates a
drafting task in plain language; the system looks up mock client data,
drafts a compliant document via Amazon Bedrock (Claude Opus 4.1), holds it
in a `PENDING_APPROVAL` state, and only logs/executes the action once the
advisor clicks **Approve & Execute**.

## Architecture

```
Assistant request ("Draft portfolio review for Jane Doe")
    ↓
Frontend (Streamlit) sends prompt + client_id
    ↓
Backend "Mock Gate" (Lambda Function URL locally run as FastAPI)
    ↓ fetch mock client profile (hardcoded dict)
    ↓ generate draft via Bedrock (Claude Opus 4.1) + compliance guardrails
    ↓ save state PENDING_APPROVAL
    ↓
Frontend displays draft to advisor
    ↓
Advisor clicks [Approve & Execute]
    ↓
Backend marks APPROVED, appends audit log entry
    ↓
Frontend shows "Logged to Audit" success screen
```

**Key Files:**
- `frontend/app.py` — Streamlit advisor dashboard (diagram steps 1-2, 6-8)
- `backend/server.py` — FastAPI app, local stand-in for the Lambda Function URL (Mock Gate)
- `backend/lambda_handler.py` — Framework-agnostic handler logic (steps 3-5, 7-8)
- `backend/bedrock_client.py` — Bedrock wrapper + compliance guardrail system prompt (step 4)
- `backend/mock_clients.py` — Hardcoded LPL client profile dictionary (step 3)
- `backend/state_store.py` — In-memory request state + JSON audit log (steps 5, 8)
- `infra/lambda_function.py` — Real AWS Lambda entrypoint (same handler logic, for deployment)
- `infra/template.yaml` — AWS SAM template for the Lambda Function URL

## Development Commands

```bash
# Setup
pip install -r requirements.txt
cp .env.example .env

# Run backend (Mock Gate) — terminal 1
uvicorn backend.server:app --reload --port 8000

# Run frontend — terminal 2
streamlit run frontend/app.py

# Run with real Bedrock instead of mock drafts
BEDROCK_MOCK_MODE=false uvicorn backend.server:app --reload --port 8000

# Deploy the Mock Gate as a real Lambda Function URL
cd infra && ./setup.sh
```

## Configuration

Config lives in `backend/bedrock_client.py:Config`:
- `BEDROCK_MOCK_MODE` — `true` (default) uses a deterministic offline draft generator, no AWS needed
- `BEDROCK_MODEL_ID` — Claude model ID (default `anthropic.claude-opus-4-1-20250805-v1:0`)
- `AWS_REGION` — Bedrock region (default `us-east-1`)

Frontend reads `BACKEND_URL` (default `http://localhost:8000`) to reach the backend.

## AWS Services

**Bedrock:**
- Model: `anthropic.claude-opus-4-1-20250805-v1:0`
- Requires: Model access enabled in Bedrock console (see AWS_SETUP.md)
- IAM permission needed: `bedrock:InvokeModel`

**Lambda (optional, for real deployment):**
- Function URL with `AuthType: NONE` (hackathon simplicity — add auth before production)
- Deployed via AWS SAM (`infra/template.yaml`)

## Code Structure

- `backend/mock_clients.py` — `MOCK_CLIENTS` dict + `get_client()` / `list_clients()`
- `backend/bedrock_client.py` — `BedrockDraftGenerator.generate_draft(client_profile, request_prompt)`,
  falls back to `_mock_draft()` when `MOCK_MODE` is true or boto3/credentials are unavailable
- `backend/state_store.py` — `create_request()`, `approve_request()`, `list_audit_log()`;
  thread-safe in-memory dict + `data/audit_log.json` persistence
- `backend/lambda_handler.py` — `generate_draft_handler()`, `approve_handler()`,
  `list_clients_handler()`, `list_audit_log_handler()` — raise `HandlerError(status_code, message)` on failure
- `backend/server.py` — FastAPI routes that call the handlers above
- `infra/lambda_function.py` — `lambda_handler(event, context)` routes Function URL
  events to the same handler functions

## Common Tasks

**Add a new mock client:**
1. Add an entry to `MOCK_CLIENTS` in `backend/mock_clients.py` with all required fields
   (`client_id`, `name`, `risk_profile`, `portfolio_value`, `ytd_return_pct`, `holdings`,
   `goals`, `last_review_date`, `advisor`)

**Add a new document type (e.g. "Quarterly Update"):**
1. No backend change needed — `request_prompt` is free text passed straight to Bedrock
2. Optionally add a preset button/dropdown option in `frontend/app.py`

**Tighten compliance guardrails:**
1. Edit `COMPLIANCE_SYSTEM_PROMPT` in `backend/bedrock_client.py`
2. Also update `_mock_draft()` if the offline fallback should reflect the same wording

**Add a "Request Revision" loop:**
1. Add a revision endpoint/handler that takes `request_id` + advisor feedback
2. Re-invoke `BedrockDraftGenerator.generate_draft` with the feedback appended to the prompt
3. Update the record in `state_store` rather than creating a new one

**Move state to DynamoDB:**
1. Replace the in-memory dict and JSON file in `backend/state_store.py` with
   `boto3.resource("dynamodb")` table operations, keeping the same function signatures

## Testing

```bash
# Test mock client lookup
python -c "from backend.mock_clients import get_client; print(get_client('C-1001'))"

# Test offline draft generation (no AWS needed)
python -c "from backend.bedrock_client import BedrockDraftGenerator; \
from backend.mock_clients import get_client; \
g = BedrockDraftGenerator(); \
print(g.generate_draft(get_client('C-1001'), 'Draft a portfolio review'))"

# Test full handler flow (generate -> approve)
python -c "
from backend.lambda_handler import generate_draft_handler, approve_handler
draft = generate_draft_handler({'client_id': 'C-1001', 'request_prompt': 'Draft a portfolio review', 'advisor': 'Test'})
print(draft)
print(approve_handler({'request_id': draft['request_id'], 'advisor': 'Test'}))
"
```

## Troubleshooting

**"Could not reach backend" in Streamlit:**
- Make sure `uvicorn backend.server:app --reload --port 8000` is running in another terminal

**"Bedrock AccessDeniedException":**
- Enable model access in AWS Console → Bedrock → Model Access
- Check IAM permissions include `bedrock:InvokeModel`
- Or set `BEDROCK_MOCK_MODE=true` to bypass Bedrock entirely during development

**Audit log not showing entries:**
- Check `data/audit_log.json` exists and is writable
- The backend process must stay running between generate-draft and approve calls
  (state is in-memory per-process)

## Hackathon Tips

1. **Demo in mock mode first** — zero AWS setup required, fast iteration
2. **Switch to real Bedrock last** — once the demo flow is solid, flip `BEDROCK_MOCK_MODE=false`
3. **Prepare 2-3 delegation requests** across different mock clients to show variety
4. **Highlight the guardrail language** in the generated draft during the demo
5. **Show the audit log tab** after approving — proves the human-in-the-loop story

## Post-Hackathon TODO

- [ ] Replace mock client dictionary with real CRM/portfolio API integration
- [ ] Move state store to DynamoDB
- [ ] Add Cognito authentication
- [ ] Add "Request Revision" loop
- [ ] Immutable audit log (QLDB / S3 Object Lock)
- [ ] Unit tests for handlers and state store
- [ ] React frontend option
