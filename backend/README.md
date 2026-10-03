# backend/ — API, Bedrock client and state store

Python package that implements the "mock gate" from the architecture diagram.
The same handler functions run behind a local FastAPI server or inside AWS Lambda.

## Files

| File | Responsibility |
|---|---|
| `server.py` | FastAPI app: routes and request models. Local stand-in for the Lambda Function URL |
| `lambda_handler.py` | Framework-agnostic handler functions (business logic). Raises `HandlerError` with an HTTP status |
| `bedrock_client.py` | `BedrockDraftGenerator`: builds the prompt, applies compliance guardrails and calls Amazon Bedrock. Has a mock mode |
| `mock_clients.py` | Hardcoded client profiles (14 simulated clients). Stands in for a CRM or portfolio API |
| `state_store.py` | Request state (`PENDING_APPROVAL` → `APPROVED`) and the append-only audit log |
| `__init__.py` | Marks the package |

## API

| Method and path | Handler | Purpose |
|---|---|---|
| `GET /health` | `server.health` | Liveness check |
| `GET /clients` | `list_clients_handler` | Client summaries (id, name, risk profile) |
| `GET /clients/{client_id}` | `get_client_handler` | Full client profile |
| `POST /generate-draft` | `generate_draft_handler` | Create a draft and save it as `PENDING_APPROVAL` |
| `POST /revise-draft` | `revise_draft_handler` | Re-draft from advisor feedback |
| `POST /approve` | `approve_handler` | Mark `APPROVED` and write the audit entry |
| `GET /audit-log` | `list_audit_log_handler` | All audit entries plus `storage` (`dynamodb` or `local`) |

## Storage (`state_store.py`)

- **DynamoDB (shared):** tables `lpl-delegation-requests` (key `request_id`) and
  `lpl-audit-log` (key `audit_id`). Used when both tables are reachable.
- **Local fallback:** requests in memory, audit log in `data/audit_log.json`. Entries
  are visible only on that machine.
- `storage_mode()` reports which one is active, and `/audit-log` returns it.
- An audit entry contains `audit_id`, `request_id`, `client_id`, `client_name`,
  `advisor`, `action`, `request_prompt`, `draft` and `timestamp`.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `BEDROCK_MOCK_MODE` | `true` | `true` returns offline placeholder drafts, `false` calls Bedrock |
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | Bedrock model or inference profile |
| `AWS_REGION` | `us-east-1` | Region for Bedrock and DynamoDB |
| `DYNAMODB_REQUESTS_TABLE` | `lpl-delegation-requests` | Requests table name |
| `DYNAMODB_AUDIT_TABLE` | `lpl-audit-log` | Audit table name |
| `REQUIRE_SHARED_STORE` | `false` | `true` fails fast instead of using local storage |

## Run

```bash
# local, no AWS needed (mock drafts, local audit file)
uvicorn backend.server:app --reload --port 8000

# real Bedrock and shared DynamoDB
BEDROCK_MOCK_MODE=false AWS_REGION=us-east-1 REQUIRE_SHARED_STORE=true \
  uvicorn backend.server:app --port 8000
```

AWS credentials come from the standard boto3 chain (environment variables, a
profile in `AWS_PROFILE`, or an instance role). Credentials created with
`aws login` also need `pip install "botocore[crt]"`.

## Permissions needed

`bedrock:InvokeModel` and DynamoDB `GetItem`, `PutItem`, `UpdateItem` and `Scan` on the
two tables.
