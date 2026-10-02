# 👔 LPL Delegation Assistant

**AI-assisted drafting with human-in-the-loop approval, for LPL Financial advisors**

Built for the AWS Financial Services Hackathon using Amazon Bedrock (Claude 3.5 Sonnet).

---

## 🎯 What It Does

An advisor (or their assistant) delegates a drafting task in plain language —
*"Draft a portfolio review for Jane Doe"* — and the system:

1. Looks up the client's profile and holdings
2. Generates a compliant draft document via Amazon Bedrock (Claude 3.5 Sonnet)
3. Holds the draft in a **`PENDING_APPROVAL`** state
4. Shows the draft to the advisor for review
5. On **Approve & Execute**, logs the action to an audit trail

No draft is ever sent to a client without an advisor explicitly approving it.

---

## 🏗️ Architecture

```
┌─────────────────┐
│ 🧑‍💻 Assistant   │
└────────┬────────┘
         │ 1. Submits delegation request (e.g., "Draft portfolio review for Jane Doe")
         ▼
┌────────────────────────────────────────────────────────┐
│ 🎨 Frontend UI (Streamlit / React)                      │
└────────┬───────────────────────────────────────────────┘
         │ 2. Sends prompt + simulated context data
         ▼
┌────────────────────────────────────────────────────────┐
│ ⚡ AWS Lambda (Function URL / Mock Gate)                │
└────────┬───────────────────────────────────────────────┘
         │ 3. Fetches mock LPL client profile data from hardcoded dictionary
         ▼
┌────────────────────────────────────────────────────────┐
│ 🧠 Amazon Bedrock (Claude 3.5 Sonnet)                   │
└────────┬───────────────────────────────────────────────┘
         │ 4. Generates the draft document & applies LPL compliance guardrails
         ▼
┌────────────────────────────────────────────────────────┐
│ ⚡ AWS Lambda (Function URL / Mock Gate)                │
└────────┬───────────────────────────────────────────────┘
         │ 5. Saves state as "PENDING_APPROVAL" & returns draft payload
         ▼
┌────────────────────────────────────────────────────────┐
│ 🎨 Frontend UI (Advisor Dashboard View)                │
└────────┬───────────────────────────────────────────────┘
         │ 6. Displays generated draft to Advisor for review
         ▼
┌─────────────────┐
│ 👔 LPL Advisor   │
└────────┬────────┘
         │ 7. Reviews draft and clicks [APPROVE & EXECUTE]
         ▼
┌────────────────────────────────────────────────────────┐
│ 🎨 Frontend UI ──> [Success Screen: "Logged to Audit"] │
└────────────────────────────────────────────────────────┘
```

**Tech Stack:**

- **LLM:** AWS Bedrock (Claude 3.5 Sonnet)
- **Mock Gate:** AWS Lambda (Function URL) — run locally as a FastAPI server for development
- **Frontend:** Streamlit advisor dashboard
- **Client data:** Hardcoded mock dictionary (stands in for LPL's CRM/portfolio APIs)
- **State:** In-memory request store (`PENDING_APPROVAL` → `APPROVED`) + append-only audit log (JSON)

---

## 📁 Project Structure

```
lpl-delegation-assistant/
├── frontend/
│   └── app.py                 # Streamlit advisor dashboard (diagram steps 1-2, 6-8)
├── backend/
│   ├── server.py              # FastAPI app — local stand-in for the Lambda "Mock Gate"
│   ├── lambda_handler.py      # Core handler logic (steps 3-5, 7-8), framework-agnostic
│   ├── bedrock_client.py      # Bedrock Claude 3.5 Sonnet wrapper + compliance guardrails (step 4)
│   ├── mock_clients.py        # Hardcoded LPL client profile dictionary (step 3)
│   └── state_store.py         # PENDING_APPROVAL/APPROVED state + audit log (steps 5, 8)
├── infra/
│   ├── lambda_function.py     # Real AWS Lambda Function URL entrypoint (wraps backend/)
│   ├── template.yaml          # AWS SAM template to deploy the Lambda Function URL
│   └── setup.sh               # Deployment script
├── data/
│   └── audit_log.json         # Generated at runtime (gitignored) — the audit trail
├── requirements.txt
├── .env.example
├── QUICKSTART.md
├── AWS_SETUP.md
└── CLAUDE.md
```

Each box in the architecture diagram maps directly to a file above — see the
inline comments in each module for the exact step it implements.

---

## ⚡ Quick Start (Local Mock Mode — No AWS Required)

### 1️⃣ Install dependencies
```bash
pip install -r requirements.txt
```

### 2️⃣ Start the backend ("Mock Gate")
```bash
uvicorn backend.server:app --reload --port 8000
```
By default this runs in `BEDROCK_MOCK_MODE=true`, generating deterministic
offline drafts — no AWS credentials needed.

### 3️⃣ Start the frontend (in a second terminal)
```bash
streamlit run frontend/app.py
```
Open **http://localhost:8501**.

### 4️⃣ Try the flow
1. Pick a client, enter a request like *"Draft a portfolio review for Jane Doe"*
2. Click **🚀 Submit for Draft** → draft appears (status `PENDING_APPROVAL`)
3. Review the draft, click **✅ Approve & Execute**
4. See the **"Logged to Audit"** success screen
5. Check the **📜 Audit Log** tab to see the recorded action

---

## 🧠 Using Real Amazon Bedrock

1. Enable Claude 3.5 Sonnet model access (see [AWS_SETUP.md](AWS_SETUP.md))
2. Set environment variables before starting the backend:
   ```bash
   export BEDROCK_MOCK_MODE=false
   export AWS_REGION=us-east-1
   export BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
   uvicorn backend.server:app --reload --port 8000
   ```
3. Ensure your AWS credentials have `bedrock:InvokeModel` permission:
   ```bash
   aws sts get-caller-identity
   ```

---

## ☁️ Deploying the Mock Gate to Real AWS Lambda

```bash
cd infra
./setup.sh
```

This uses AWS SAM to deploy `lambda_function.py` as a Lambda with a Function
URL. Point the frontend at the deployed URL:

```bash
BACKEND_URL=https://xxxx.lambda-url.us-east-1.on.aws/ streamlit run frontend/app.py
```

---

## 🛡️ Compliance Guardrails

Every draft generated via Bedrock is instructed (via system prompt in
[`backend/bedrock_client.py`](backend/bedrock_client.py)) to:

- Never guarantee or imply guaranteed investment returns
- Include a suitability statement tied to the client's risk profile and goals
- Include a standard disclosure (informational purposes only, past performance disclaimer)
- Stay professional and non-speculative in tone
- Clearly mark the output as a **DRAFT pending advisor approval**

Nothing is sent to a client without a human advisor explicitly clicking
**Approve & Execute**.

---

## 💰 Cost Estimate

For typical hackathon usage (dozens of draft generations):

- **Bedrock (Claude 3.5 Sonnet):** ~$3-5
- **Lambda Function URL:** Free tier covers hackathon usage

**Total:** <$10 for 2 days

---

## 🚀 Post-Hackathon Roadmap

- [ ] Replace mock client dictionary with real LPL CRM/portfolio API integration
- [ ] Persist request/audit state in DynamoDB instead of in-memory + JSON
- [ ] Add authentication (AWS Cognito) and per-advisor audit scoping
- [ ] Support additional document types (quarterly updates, rebalance summaries, IPS updates)
- [ ] Add a "Request Revision" loop (advisor edits → re-draft)
- [ ] React frontend option for a production-grade advisor dashboard
- [ ] Immutable audit log (e.g., QLDB or S3 Object Lock) for regulatory requirements
- [ ] Unit & integration tests

---

## 📚 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** — Detailed setup instructions
- **[AWS_SETUP.md](AWS_SETUP.md)** — Enabling Bedrock model access & IAM permissions
- **[CLAUDE.md](CLAUDE.md)** — Developer guide for Claude Code
- **[CLAUDE_CODE_SETUP.md](CLAUDE_CODE_SETUP.md)** — Team setup guide for Claude Code in Cloud Shell

---

## 👥 Team

Built for the AWS Financial Services Hackathon by Team 2.

---

## 📄 License

MIT License - see LICENSE file for details
