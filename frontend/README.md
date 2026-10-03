# frontend/ — Advisor Dashboard

Streamlit app for sign-in, drafting, review queues and the audit trail. It holds no
business rules: roles, compliance checks and audit hashing are enforced by the backend.

## Files

| File | Purpose |
|---|---|
| `app.py` | The whole dashboard |

## Screens by role

| Role | Tabs |
|---|---|
| Assistant | Delegate a Task, My Drafts, Audit & Supervision Log |
| Advisor | Delegate a Task, Advisor Review Queue, Audit & Supervision Log |
| Compliance Principal | Supervision Queue, Audit & Supervision Log |

- **Review panel:** editable draft (assistant and advisor), live compliance results with
  blocking and warning findings, and a diff against the AI draft. Approval buttons stay
  disabled while blocking findings exist.
- **Advisor:** "Approve and send to compliance principal".
- **Principal:** "Approve for release" or "Reject and return" (a comment is required to reject).
- **Audit & Supervision Log:** refreshes every 5 seconds. Each event shows the user, role,
  compliance result, hashes and human edits. Principals also see a record-integrity banner
  (hash chain verification) and can download the records as JSON (with verification) or CSV.
  A banner shows whether the trail is the shared DynamoDB one or local-only.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8000` | Where the backend API lives |

## Run

```bash
# from the repository root, with the backend already running
BACKEND_URL=http://localhost:8000 streamlit run frontend/app.py --server.port 8080
```

Requires Streamlit 1.37 or newer. Use `streamlit run`, not `python frontend/app.py`.
Restart Streamlit after replacing `app.py` on disk, as it can keep serving the old script.

## Sign-in

In demo mode the login page lists the demo users (`assistant1`, `advisor1`, `advisor2`,
`principal1`). See [backend/README.md](../backend/README.md) to configure real users.
