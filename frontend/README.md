# frontend/ — Advisor Dashboard

Streamlit app that gives advisors a single place to delegate drafting, review AI
output and see the audit trail. It holds no business logic: every action is a call
to the backend over HTTP.

## Files

| File | Purpose |
|---|---|
| `app.py` | The whole dashboard (page layout, API calls, audit tab) |

## Screens

- **Delegate a Task**
  1. Choose a client and a task type (portfolio review, rebalancing, retirement
     income, meeting prep or a custom request).
  2. **Generate draft** calls the backend and the draft appears for review.
  3. The advisor can edit the draft by hand, **Request revision** (AI re-drafts from
     feedback), **Discard**, or **Approve & log to audit**.
- **Audit & Supervision Log**
  - Shows every approved action. The view re-polls the backend every 5 seconds
    (`@st.fragment(run_every=...)`), so entries from other advisors appear live.
  - A banner shows the storage mode: green means the shared DynamoDB trail, orange
    means this backend is using local-only storage.
- **Sidebar:** advisor name, a short "how it works" and compliance reminders
  (no performance guarantees, FINRA 2210, Reg BI).

## Backend calls

| Function | Endpoint |
|---|---|
| `fetch_clients()` | `GET /clients` |
| `submit_delegation_request()` | `POST /generate-draft` |
| `request_revision()` | `POST /revise-draft` |
| `approve_and_execute()` | `POST /approve` |
| `fetch_audit_log()` | `GET /audit-log` (returns `audit_log` and `storage`) |

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8000` | Where the backend API lives |

## Run

```bash
# from the repository root, with the backend already running
BACKEND_URL=http://localhost:8000 streamlit run frontend/app.py --server.port 8080
```

Requires Streamlit 1.37 or newer (the live-refreshing audit view uses fragments).

## Notes

- Use `streamlit run`, not `python frontend/app.py`.
- The audit tab refreshes only while a browser tab is open on it.
