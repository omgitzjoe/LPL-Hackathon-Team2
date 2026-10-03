# infra/ — AWS Lambda deployment option

Packaging for running the backend as an AWS Lambda behind a Function URL, instead of
the FastAPI server used locally and on EC2.

## Files

| File | Purpose |
|---|---|
| `lambda_function.py` | Lambda entrypoint. Reads a Function URL (payload v2.0) event, routes to the shared handlers in `backend/lambda_handler.py` and returns JSON |
| `template.yaml` | AWS SAM template: the function, its Function URL and a policy allowing `bedrock:InvokeModel` |
| `setup.sh` | Runs `sam build` and `sam deploy` for the stack `lpl-delegation-assistant` |

## Deploy

Requires the AWS SAM CLI, AWS credentials that can create Lambda and IAM resources,
and Bedrock model access in the target region.

```bash
cd infra
./setup.sh
```

The deploy prints the Function URL. Use it as the frontend's backend address:

```bash
BACKEND_URL=https://<id>.lambda-url.us-east-1.on.aws streamlit run frontend/app.py
```

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `ProjectName` | `lpl-delegation-assistant` | Prefix for resource names |
| `BedrockModelId` | set in `template.yaml` | Passed to the function as `BEDROCK_MODEL_ID` |

## Notes

- This path is **not** what the live site uses. The live app runs on EC2 through
  [`.github/workflows/deploy.yml`](../.github/README.md).
- The handlers now require a signed-in user (roles and two-level approval). This Lambda
  entrypoint does not authenticate callers yet, so protected routes return 401 until
  token handling is added.
- The template does not create DynamoDB tables or grant access to them. To use the
  shared audit trail from Lambda, add the tables and a DynamoDB policy.
- The Function URL is created with `AuthType: NONE` and open CORS. Add authentication
  before using it with real data.
- Check `lambda_function.py` for which routes it exposes. It may lag behind
  `backend/server.py`.
