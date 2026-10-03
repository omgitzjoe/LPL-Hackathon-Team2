# backend/ — API, compliance engine, supervision workflow and audit store

Python package behind the dashboard. The same handlers run behind a local FastAPI
server or, with some work (see `infra/`), inside AWS Lambda.

## Files

| File | Responsibility |
|---|---|
| `server.py` | FastAPI routes, request models and bearer-token authentication |
| `lambda_handler.py` | Framework-agnostic business logic: drafting, role checks, two-level approval |
| `compliance.py` | Deterministic compliance rules run on every draft |
| `auth.py` | Users, roles, password hashing and signed session tokens |
| `audit_chain.py` | Hash chaining, verification and text diffs for audit records |
| `state_store.py` | Request state and the audit log (DynamoDB or local fallback) |
| `bedrock_client.py` | Amazon Bedrock wrapper (with an offline mock mode) |
| `mock_clients.py` | Simulated client profiles standing in for a CRM |

## Two-level supervision workflow

```
PENDING_APPROVAL --advisor approves--> PENDING_SUPERVISION --principal approves--> APPROVED
       ^                                        |
       +---- edit / AI revision <--- REJECTED <-+--principal rejects (comment required)
```

| Role | Can do |
|---|---|
| `assistant` | Create drafts, edit, request AI revisions, see their own drafts |
| `advisor` | Everything an assistant can, plus level-1 approval of the final text |
| `principal` | Level-2 approval or rejection, verify the audit chain |

Rules enforced by the server:
- Identity comes from the signed token, never from the request body.
- A draft with any **blocking** compliance finding cannot be approved at either level.
- A principal cannot supervise a request they created or advisor-approved.
- State changes are atomic (conditional updates), so two people cannot approve the same request.

## Deterministic compliance checks (`compliance.py`)

Run on generation, on every revision, on every edit check and again on the final text at approval.

| Rule | Severity | Basis |
|---|---|---|
| Guaranteed, risk-free or absolute claims (negations such as "does not guarantee" are allowed) | block | FINRA 2210(d)(1)(B) |
| Missing `DRAFT` marker | block | Internal policy |
| Missing informational-purposes disclosure | block | FINRA 2210 |
| Missing past-performance disclosure | block | FINRA 2210 |
| No suitability statement (risk profile and goals) | block | Reg BI |
| Placeholder text (`[Advisor Name]`, `TBD`) | block | Internal policy |
| Possible Social Security number | block | Reg S-P |
| "Will earn/outperform", performance projections, superlatives | warn | FINRA 2210 |
| Long digit strings (possible account numbers), client name missing | warn | Reg S-P / internal |

These rules support supervisory review and are not legal advice. Edit `compliance.py` and bump `RULESET_VERSION` to change them; the version is recorded in every audit entry.

## Defensible records (`audit_chain.py`)

Every event (draft generated, AI revision, advisor approval, principal approval or rejection) is one audit entry containing:
- the real `actor_id`, `actor_name` and `actor_role`
- the request, client and task
- SHA-256 fingerprints of the AI draft and the final text, a line diff of human edits, and the final text itself at approval
- the compliance result and ruleset version
- `seq`, `prev_hash` and `entry_hash`, forming a hash chain

`GET /audit-log/verify` recomputes the chain and detects modified, deleted, re-ordered or truncated entries. In DynamoDB each entry and a `__HEAD__` pointer are written in one transaction conditioned on the previous sequence number, so concurrent writers cannot fork the chain.

This is **tamper-evident**, not tamper-proof. For regulatory retention also write to immutable storage (for example S3 Object Lock) and restrict delete permissions on the table. Entries written before hashing existed are shown as "legacy" and are not covered by verification.

## API

All routes except `/health`, `/auth/info` and `/auth/login` need `Authorization: Bearer <token>`.

| Method and path | Roles | Purpose |
|---|---|---|
| `POST /auth/login` | public | Exchange user ID and password for a token |
| `GET /auth/info`, `GET /auth/me` | public / any | Demo-mode flag / current user |
| `GET /clients`, `GET /clients/{id}` | any | Client data |
| `POST /compliance/check` | any | Run the rules on text |
| `POST /generate-draft` | assistant, advisor | Create a draft |
| `POST /revise-draft` | assistant, advisor | AI revision from feedback |
| `POST /save-draft` | assistant, advisor | Save human edits |
| `POST /advisor-approve` | advisor | Level-1 approval |
| `POST /supervise` | principal | Level-2 `approve` or `reject` |
| `GET /requests`, `GET /requests/{id}` | any | Queue and request detail |
| `GET /audit-log` | any | Audit entries and storage mode |
| `GET /audit-log/verify` | principal | Verify the hash chain |

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `LPL_USERS` | demo users | `id:password:role:Display Name;...` replaces the built-in demo users |
| `LPL_DEMO_PASSWORD` | `lpl-demo` | Password for the built-in demo users |
| `AUTH_SECRET` | random per start | Key that signs session tokens |
| `AUTH_TOKEN_TTL_HOURS` | `8` | Session lifetime |
| `BEDROCK_MOCK_MODE` | `true` | `false` calls Amazon Bedrock |
| `BEDROCK_MODEL_ID` | Claude Sonnet 4.5 profile | Bedrock model or inference profile |
| `AWS_REGION` | `us-east-1` | Region for Bedrock and DynamoDB |
| `DYNAMODB_REQUESTS_TABLE` | `lpl-delegation-requests` | Key `request_id` |
| `DYNAMODB_AUDIT_TABLE` | `lpl-audit-log` | Key `audit_id` |
| `REQUIRE_SHARED_STORE` | `false` | `true` fails instead of using local storage |

Built-in demo users (`assistant1`, `advisor1`, `advisor2`, `principal1`) exist so the prototype can be tried at once. **Set `LPL_USERS` before using the app beyond a demo**, or replace this with an identity provider such as Amazon Cognito. Passwords are stored as salted PBKDF2 hashes, failed logins are rate-limited per user, and tokens are HMAC-signed. Tokens reset when the backend restarts unless `AUTH_SECRET` is set.

## Run

```bash
# local: mock drafts, local audit file, demo users
uvicorn backend.server:app --reload --port 8000

# real Bedrock and shared DynamoDB
BEDROCK_MOCK_MODE=false AWS_REGION=us-east-1 REQUIRE_SHARED_STORE=true \
  uvicorn backend.server:app --port 8000
```

AWS credentials come from the usual boto3 chain. Credentials created with `aws login` also need `pip install "botocore[crt]"`.

## Permissions needed

`bedrock:InvokeModel`, and DynamoDB `GetItem`, `PutItem`, `UpdateItem` and `Scan` on both tables (the audit transaction uses `PutItem`).

## Tests

```bash
python -m unittest discover -s tests -t .
```

Covers the compliance rules, the hash chain (tampering, gaps, truncation), authentication, role enforcement and the full two-level flow.
