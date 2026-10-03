# API reference

Base URL: the backend (`http://localhost:8000` locally; on the deployed instance the backend is reached by the dashboard on the same host). Interactive docs are available at `/docs` when the backend runs.

All routes except `/health`, `/auth/info` and `/auth/login` require `Authorization: Bearer <token>`.

## Errors

| Status | Meaning |
|---|---|
| 400 | Missing or invalid field (for example rejecting without a comment) |
| 401 | Missing, invalid or expired token; wrong credentials |
| 403 | Your role cannot do this, or separation of duties applies |
| 404 | Request or client not found |
| 409 | Wrong state, or someone else acted first |
| 422 | Blocking compliance findings. Body: `{"detail": {"message": "...", "compliance": {...}}}` |
| 429 | Too many failed logins for that user (5 in 5 minutes) |
| 502 | The model call failed |

## Authentication

| Method and path | Body | Response |
|---|---|---|
| `GET /health` | none | `{"status","storage","dynamo"}` |
| `GET /auth/info` | none | `{"demo_mode": bool}` |
| `POST /auth/login` | `{"user_id","password"}` | `{"token","user":{"user_id","name","role"}}` |
| `GET /auth/me` | none | `{"user": {...}}` |

Tokens are HMAC-signed, valid for `AUTH_TOKEN_TTL_HOURS` (default 8) and become invalid when the backend restarts unless `AUTH_SECRET` is set.

## Data

| Method and path | Roles | Purpose |
|---|---|---|
| `GET /clients` | any | Client summaries |
| `GET /clients/{client_id}` | any | Full client profile |
| `GET /requests?statuses=A,B&mine=true` | any | Request summaries, newest first |
| `GET /requests/{request_id}` | any | Full request including a fresh `compliance` result |
| `GET /audit-log` | any | `{"audit_log": [...], "storage": "dynamodb"\|"local"}` |
| `GET /audit-log/verify` | principal | Hash-chain verification (below) |

## Drafting

| Method and path | Roles | Body |
|---|---|---|
| `POST /compliance/check` | any | `{"text", "client_id"?}` returns the compliance result |
| `POST /generate-draft` | assistant, advisor | `{"client_id","request_prompt"}` |
| `POST /revise-draft` | assistant, advisor | `{"request_id","feedback"}` |
| `POST /save-draft` | assistant, advisor | `{"request_id","draft"}` |

`generate-draft`, `revise-draft` and `save-draft` return the request record plus `compliance`.

## Approval

| Method and path | Roles | Body | Result |
|---|---|---|---|
| `POST /advisor-approve` | advisor | `{"request_id","final_draft"?}` | Status becomes `PENDING_SUPERVISION` |
| `POST /supervise` | principal | `{"request_id","decision":"approve"\|"reject","comment"?}` | Status becomes `APPROVED` or `REJECTED` |

Both return `{"request": {...}, "audit_entry": {...}}`.

## Compliance result

```json
{
  "passed": false,
  "blocking": 1,
  "warnings": 0,
  "findings": [
    {"rule_id": "PROMISSORY_LANGUAGE", "severity": "block",
     "title": "Guaranteed or promissory language",
     "detail": "Communications must not state or imply guaranteed results.",
     "citation": "FINRA 2210(d)(1)(B)", "match": "offers guaranteed returns."}
  ],
  "ruleset_version": "2026.10-1",
  "checked_at": "2026-10-03T00:00:00+00:00"
}
```

## Verification result

```json
{"ok": true, "checked": 11, "legacy_unchained": 2,
 "head_hash": "b992f1...", "errors": [], "storage": "dynamodb"}
```

Each error is `{"seq", "audit_id", "problem"}`.

## Example

```bash
TOKEN=$(curl -s -X POST localhost:8000/auth/login -H 'content-type: application/json' \
  -d '{"user_id":"advisor1","password":"lpl-demo"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl -s localhost:8000/requests?statuses=PENDING_APPROVAL -H "Authorization: Bearer $TOKEN"
```
