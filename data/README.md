# data/ — local fallback storage

Runtime storage used only when the backend cannot reach DynamoDB (for example local
development without AWS credentials).

## Contents

| File | Purpose |
|---|---|
| `.gitkeep` | Keeps the folder in git |
| `audit_log.json` | Generated at runtime. A JSON list of audit entries written by `backend/state_store.py` |

`audit_log.json` is listed in `.gitignore`, so it is never committed or shared.

## Why it matters

- Entries here exist **only on one machine**. Other advisors cannot see them.
- To use the shared audit trail, run the backend with AWS credentials that can reach
  the DynamoDB tables. The dashboard's audit tab shows a green banner when it is.
- Delete `audit_log.json` to reset local test data.

See [backend/README.md](../backend/README.md) for the storage settings.
