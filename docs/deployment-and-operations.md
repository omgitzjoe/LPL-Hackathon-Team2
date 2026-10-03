# Deployment and operations

## Environments

| Environment | URL | Storage | Notes |
|---|---|---|---|
| Team instance (production-like) | <http://98.89.13.40:8080> | Shared DynamoDB tables | Permanent Elastic IP. Rebuilt on every push to `main` |
| Local development | <http://localhost:8080> | Local file, or your own AWS account | Mock drafts by default |

## CI/CD (GitHub Actions)

Workflow: [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml), runs on every push to `main` and on manual dispatch.

1. Configure AWS credentials from the secrets `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` (region `us-east-1`).
2. Find the running instance tagged `Name=LPL-Demo-Final` and terminate it.
3. Launch a new `t3.medium` with the instance profile `LPL-App-EC2-Profile` and a startup script that installs git and Python 3.11, clones this repository, installs `requirements.txt` and runs `start.sh`.
4. Associate the permanent Elastic IP `98.89.13.40`.
5. Wait about 4 minutes, then poll the site until it returns HTTP 200.

Consequences:
- Every push to `main` causes a few minutes of downtime and signs all users out (tokens reset unless `AUTH_SECRET` is set).
- Add `[skip ci]` to a commit message to push documentation-only changes without redeploying.
- Merge conflicts or syntax errors on `main` will deploy a broken app. Run the tests first.

## Runtime

`start.sh` launches two processes:

| Process | Command | Port |
|---|---|---|
| Backend | `python3.11 -m uvicorn backend.server:app` | 8000 |
| Frontend | `python3.11 -m streamlit run frontend/app.py` | 8080 |

`start.sh` sets `BEDROCK_MOCK_MODE=false`, so drafts come from Amazon Bedrock. The instance role provides Bedrock and DynamoDB access; no keys are stored on the instance.

### Environment variables

See [backend/README.md](../backend/README.md#configuration) and [security-and-compliance.md](security-and-compliance.md#configuration). To change them on the instance, export them in `start.sh` (and commit) or on the host before it runs.

## AWS prerequisites

| Resource | Requirement |
|---|---|
| DynamoDB `lpl-delegation-requests` | Partition key `request_id` (string) |
| DynamoDB `lpl-audit-log` | Partition key `audit_id` (string) |
| IAM role permissions | `bedrock:InvokeModel`; DynamoDB `GetItem`, `PutItem`, `UpdateItem`, `Scan` on both tables |
| Bedrock | Model access enabled for the Claude Sonnet 4.5 inference profile in the region |
| Security group | Inbound TCP 8080 for users. Keep 8000 closed |

Create the tables (on-demand):

```bash
aws dynamodb create-table --table-name lpl-delegation-requests \
  --attribute-definitions AttributeName=request_id,AttributeType=S \
  --key-schema AttributeName=request_id,KeyType=HASH --billing-mode PAY_PER_REQUEST
aws dynamodb create-table --table-name lpl-audit-log \
  --attribute-definitions AttributeName=audit_id,AttributeType=S \
  --key-schema AttributeName=audit_id,KeyType=HASH --billing-mode PAY_PER_REQUEST
```

## Health checks

| Check | How |
|---|---|
| Frontend up | `curl -i http://<host>:8080/_stcore/health` returns 200 |
| Backend and storage mode | `GET /health` returns `{"status":"ok","storage":"dynamodb"}`. `local` means DynamoDB is unreachable |
| Audit integrity | Principal opens the audit tab, or `GET /audit-log/verify` returns `"ok": true` |

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Audit tab says "Local-only" | Backend cannot reach DynamoDB. Check credentials, region, table names and permissions. Set `REQUIRE_SHARED_STORE=true` to fail loudly |
| `Script execution error` on the page | A syntax error or leftover merge-conflict markers (`<<<<<<<`) in `frontend/app.py` on `main`. Fix and push |
| Page unchanged after editing `app.py` | Streamlit can keep serving the old script. Restart it |
| Local backend fails on `str \| None` | Python 3.9 cannot evaluate that syntax in Pydantic models. Use `Optional[str]` or Python 3.10+ |
| `aws login` credentials fail inside Python | Install `botocore[crt]` in the virtual environment |
| Browser cannot open the site | Use `http://` and port 8080. Browsers may rewrite to `https://` |
| 401 after a while | Session expired or the backend restarted. Sign in again; set `AUTH_SECRET` to keep sessions across restarts |
| Startup log | On the instance: `/var/log/user-data.log` ends with `DEPLOYMENT COMPLETE` |
| Audit chain reports errors | Entries were modified, removed or written by an unverified path. Preserve the table state, investigate who had write access |

## Costs

EC2 `t3.medium`, DynamoDB on-demand (negligible at this scale) and Bedrock tokens (the main variable cost). Stop or terminate unused instances.
