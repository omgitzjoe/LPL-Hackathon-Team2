# Development guide

## Repository layout

```
.
├── backend/            API, workflow, compliance, auth, audit chain, storage
├── frontend/           Streamlit dashboard
├── infra/              Lambda and SAM deployment option
├── data/               Local fallback audit log (gitignored file)
├── tests/              Unit and workflow tests
├── docs/               This documentation and architecture diagrams
├── .github/workflows/  Deployment pipeline
├── start.sh            Starts backend and frontend on the server
└── requirements.txt
```

Module documentation: [backend](../backend/README.md), [frontend](../frontend/README.md), [infra](../infra/README.md), [data](../data/README.md), [.github](../.github/README.md).

## Local setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# terminal 1: backend (mock drafts, local audit file, demo users)
uvicorn backend.server:app --reload --port 8000

# terminal 2: frontend
BACKEND_URL=http://localhost:8000 streamlit run frontend/app.py --server.port 8080
```

Open <http://localhost:8080> and sign in with `advisor1` / `lpl-demo`.

### Using real services locally

```bash
export BEDROCK_MOCK_MODE=false AWS_REGION=us-east-1 AWS_PROFILE=<profile>
export REQUIRE_SHARED_STORE=true   # fail instead of falling back to local storage
```

The profile needs the permissions listed in [deployment-and-operations.md](deployment-and-operations.md#aws-prerequisites). A local backend that uses your own account does not share the team's audit trail.

## Tests

```bash
python -m unittest discover -s tests -t .
```

| File | Covers |
|---|---|
| `tests/test_compliance.py` | Each rule, negation handling, warnings versus blocks |
| `tests/test_audit_chain.py` | Hash chain, tampering, gaps, reordering, truncation, legacy entries, diffs |
| `tests/test_workflow.py` | Authentication, role enforcement, the two-level flow, rejection, blocked approvals, tamper detection |

The workflow tests run against local storage in a temporary directory and use mock drafts, so they need no AWS access.

## Conventions

- Business rules live in `backend/`; the frontend only presents them.
- Never read identity from a request body. Use the `actor` passed by `server.py`.
- Audit entries may contain only strings, integers, booleans and lists of strings, so values hash identically after a DynamoDB round trip. Use `""` instead of `None`.
- Keep code compatible with Python 3.9 (local) and 3.11 (server): use `Optional[...]` in Pydantic models.
- Bump `RULESET_VERSION` in `backend/compliance.py` whenever rules change, and add a test.
- Do not commit conflict markers. Run the tests before pushing to `main`, which deploys.

## Extending

| Task | Where |
|---|---|
| Add a compliance rule | `backend/compliance.py` and `tests/test_compliance.py`; update the table in [workflow-and-roles.md](workflow-and-roles.md) |
| Add a document type | `TASK_TEMPLATES` in `frontend/app.py` (and prompt guidance in `backend/bedrock_client.py` if needed) |
| Add a role or action | `backend/auth.py` roles, a handler in `backend/lambda_handler.py`, a route in `backend/server.py` |
| Replace mock client data | `backend/mock_clients.py` (keep `get_client` and `list_clients`) |
| Change the model | `BEDROCK_MODEL_ID` |
| Regenerate the SVG diagram | Edit `docs/diagrams/architecture.svg`; Mermaid sources are the `.mmd` files |

## Roadmap ideas

Real identity provider with MFA, HTTPS and WAF, immutable audit retention, CRM integration, Bedrock Guardrails and a rule evaluation set, cited and number-checked drafts, dashboards for time saved and edit rates.
