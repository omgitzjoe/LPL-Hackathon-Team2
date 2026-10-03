# Data model

Two DynamoDB tables (names overridable by environment variables). Both are on-demand. In local mode the audit log is a JSON file at `data/audit_log.json` and requests are held in memory.

## `lpl-delegation-requests` (partition key `request_id`, string)

| Field | Type | Notes |
|---|---|---|
| `request_id` | string | `REQ-` plus 8 hex characters |
| `client_id`, `client_name` | string | From the client profile |
| `created_by`, `created_by_name`, `created_by_role` | string | The signed-in creator |
| `request_prompt` | string | The delegated task |
| `draft` | string | Current working text (human edits included) |
| `ai_draft` | string | Latest AI output, the baseline for diffs |
| `status` | string | `PENDING_APPROVAL`, `PENDING_SUPERVISION`, `APPROVED`, `REJECTED` |
| `created_at`, `revised_at` | string | ISO 8601 UTC |
| `revision_count` | number | AI revisions so far |
| `last_revision_feedback` | string | Most recent AI-revision feedback |
| `advisor_approved_by`, `advisor_approved_by_name`, `advisor_approved_at` | string | Level-1 approval |
| `supervisor_id`, `supervisor_name`, `supervisor_comment`, `decided_at` | string | Level-2 decision |

## `lpl-audit-log` (partition key `audit_id`, string)

| Field | Type | Notes |
|---|---|---|
| `audit_id` | string | `AUD-` plus 8 hex characters |
| `seq` | number | Position in the hash chain, starting at 1 |
| `timestamp` | string | ISO 8601 UTC |
| `action` | string | See [workflow-and-roles.md](workflow-and-roles.md#audit-events) |
| `request_id`, `client_id`, `client_name`, `request_prompt` | string | What the event was about |
| `actor_id`, `actor_name`, `actor_role` | string | The real signed-in user |
| `status_after` | string | Request status after the event |
| `model_id` | string | Bedrock model, or `mock` |
| `ai_draft_sha256`, `final_draft_sha256` | string | SHA-256 of the text |
| `final_draft` | string | Text at approval or rejection |
| `diff_from_ai` | string | Unified diff from the AI draft to the final text |
| `edited_by_human` | bool | Whether the final text differs from the AI draft |
| `comment` | string | Revision feedback or supervisory comment |
| `advisor_id` | string | On supervisor events, the advisor who approved |
| `compliance_passed`, `compliance_blocking`, `compliance_warnings` | bool, number, number | Rule result at that moment |
| `compliance_findings` | list of string | `RULE_ID:severity` |
| `compliance_ruleset` | string | Rule set version |
| `hash_version` | number | Hash scheme version (currently 1) |
| `prev_hash`, `entry_hash` | string | Hash chain links |

Entries from before hashing was introduced have fields such as `advisor`, `draft` or `final_draft` and no `seq` or hashes. They are displayed as legacy and are not covered by verification.

### Head pointer

One item with `audit_id = "__HEAD__"` stores `seq`, `entry_hash` and `updated_at` of the newest entry. It is written in the same DynamoDB transaction as each new entry and conditioned on the previous `seq`, which serializes concurrent writers and lets verification detect missing entries at the end of the log.

## Hash scheme

`entry_hash = SHA-256(canonical JSON of the entry without entry_hash)`, where canonical JSON has sorted keys, no spaces and UTF-8 text. Each entry includes its `prev_hash`, so changing any earlier entry changes every later hash. Entries must contain only strings, integers, booleans and lists of strings so values survive a DynamoDB round trip unchanged.

## Client data

`backend/mock_clients.py` holds 14 simulated profiles: `client_id`, `name`, `risk_profile`, `portfolio_value`, `ytd_return_pct`, `holdings` (symbol, name, allocation), `goals`, `last_review_date`, `advisor`. Replace this module with a CRM or portfolio API client for production.

## Users

Users are configuration, not data. See `LPL_USERS` in [security-and-compliance.md](security-and-compliance.md).
