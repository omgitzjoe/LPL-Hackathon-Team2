# Quick Start Guide (2 Minutes, No AWS Required)

## Prerequisites
- Python 3.9+

## Steps

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the Backend (Mock Gate) — Terminal 1
```bash
uvicorn backend.server:app --reload --port 8000
```
Runs in `BEDROCK_MOCK_MODE=true` by default — generates deterministic offline
drafts, no AWS credentials needed.

### 3. Start the Frontend — Terminal 2
```bash
streamlit run frontend/app.py
```

### 4. Try It Out
Open **http://localhost:8501**:

1. Pick a client (e.g. "Jane Doe")
2. Enter a request: *"Draft a portfolio review for Jane Doe"*
3. Click **🚀 Submit for Draft**
4. Review the generated draft (status: `PENDING_APPROVAL`)
5. Click **✅ Approve & Execute**
6. See **"✅ Logged to Audit"**
7. Open the **📜 Audit Log** tab to see the recorded action

---

## Switching to Real Amazon Bedrock

```bash
cp .env.example .env
# Edit .env: set BEDROCK_MOCK_MODE=false

export BEDROCK_MOCK_MODE=false
uvicorn backend.server:app --reload --port 8000
```

Make sure Bedrock model access is enabled first — see [AWS_SETUP.md](AWS_SETUP.md).

## Deploying to Real AWS Lambda

```bash
cd infra
./setup.sh
# Copy the FunctionUrl output, then:
BACKEND_URL=<function-url> streamlit run frontend/app.py
```

## Troubleshoot

If the frontend can't reach the backend:
1. Confirm the backend terminal shows `Uvicorn running on http://127.0.0.1:8000`
2. Check `BACKEND_URL` matches (default `http://localhost:8000`)

If using real Bedrock and errors occur:
1. AWS credentials: `aws sts get-caller-identity`
2. Bedrock model access enabled in console
3. IAM permissions include `bedrock:InvokeModel`
