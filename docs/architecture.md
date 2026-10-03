# Architecture

This document describes how the LPL Delegation Assistant is built. The diagrams are Mermaid, which GitHub renders directly; the same sources are stored in [diagrams/](diagrams/) with a static [architecture.svg](diagrams/architecture.svg).

## 1. Purpose

Advisors delegate client-document drafting to an AI assistant while keeping control. Each document passes automated compliance checks, advisor approval and compliance-principal approval, and every step is written to a tamper-evident audit trail.

## 2. System architecture

```mermaid
flowchart LR
  subgraph Users["People"]
    A["Assistant"]
    V["Advisor"]
    P["Compliance Principal"]
  end

  subgraph EC2["Amazon EC2 instance"]
    UI["Streamlit dashboard :8080"]
    API["FastAPI backend :8000<br/>bearer-token auth"]
    subgraph Core["backend package"]
      H["lambda_handler<br/>roles + two-level workflow"]
      C["compliance<br/>deterministic rules"]
      AU["auth<br/>users, roles, tokens"]
      S["state_store<br/>requests + audit log"]
      AC["audit_chain<br/>hash chain + diff"]
      BC["bedrock_client<br/>prompt + guardrails"]
      MC["mock_clients<br/>simulated CRM"]
    end
  end

  BR["Amazon Bedrock<br/>Claude Sonnet 4.5"]
  DDB[("Amazon DynamoDB<br/>lpl-delegation-requests<br/>lpl-audit-log")]

  A --> UI
  V --> UI
  P --> UI
  UI -->|"HTTP + Bearer token"| API
  API --> H
  H --> AU
  H --> C
  H --> MC
  H --> BC
  H --> S
  S --> AC
  S -->|"conditional writes<br/>transactional audit append"| DDB
  BC -->|"InvokeModel"| BR
```

### Components

| Component | Responsibility | Source |
|---|---|---|
| Streamlit dashboard | Sign-in, drafting, review queues, audit view. No business rules | [frontend/app.py](../frontend/app.py) |
| FastAPI server | Routes, request validation, bearer-token check | [backend/server.py](../backend/server.py) |
| Handlers | Role checks, workflow transitions, orchestration | [backend/lambda_handler.py](../backend/lambda_handler.py) |
| Compliance engine | Deterministic rules on every draft | [backend/compliance.py](../backend/compliance.py) |
| Auth | Users, roles, PBKDF2 hashes, signed tokens, login throttling | [backend/auth.py](../backend/auth.py) |
| State store | Request state and audit log, DynamoDB with local fallback | [backend/state_store.py](../backend/state_store.py) |
| Audit chain | SHA-256 hash chain, verification, diffs | [backend/audit_chain.py](../backend/audit_chain.py) |
| Bedrock client | Prompt construction, model invocation, mock mode | [backend/bedrock_client.py](../backend/bedrock_client.py) |
| Mock clients | Simulated client profiles standing in for a CRM | [backend/mock_clients.py](../backend/mock_clients.py) |

## 3. Request flow

```mermaid
sequenceDiagram
  autonumber
  actor Asst as Assistant
  actor Adv as Advisor
  actor Prin as Principal
  participant UI as Streamlit UI
  participant API as FastAPI backend
  participant CE as Compliance engine
  participant BR as Amazon Bedrock
  participant ST as State store (DynamoDB)

  Asst->>UI: Sign in, choose client and task
  UI->>API: POST /generate-draft (token)
  API->>BR: Prompt with client profile and guardrails
  BR-->>API: AI draft
  API->>ST: Create request PENDING_APPROVAL
  API->>CE: Check draft
  API->>ST: Append audit DRAFT_GENERATED
  API-->>UI: Draft + compliance result
  Asst->>UI: Edit and save
  UI->>API: POST /save-draft

  Adv->>UI: Review draft and findings
  UI->>API: POST /advisor-approve
  API->>CE: Re-check final text (server side)
  alt blocking findings
    API-->>UI: 422 with findings
  else clean
    API->>ST: Conditional update to PENDING_SUPERVISION
    API->>ST: Append audit ADVISOR_APPROVED (hash, diff)
    API-->>UI: Approved, sent to principal
  end

  Prin->>UI: Open supervision queue
  UI->>API: POST /supervise (approve or reject)
  API->>CE: Re-check final text
  API->>ST: Conditional update to APPROVED or REJECTED
  API->>ST: Append audit SUPERVISOR_APPROVED or SUPERVISOR_REJECTED
  Prin->>UI: Audit tab
  UI->>API: GET /audit-log/verify
  API-->>UI: Chain intact or broken entries
```

## 4. Request lifecycle

```mermaid
stateDiagram-v2
  [*] --> PENDING_APPROVAL: assistant or advisor generates draft
  PENDING_APPROVAL --> PENDING_APPROVAL: edit, save, or AI revision
  PENDING_APPROVAL --> PENDING_SUPERVISION: advisor approves (no blocking findings)
  PENDING_SUPERVISION --> APPROVED: principal approves (no blocking findings)
  PENDING_SUPERVISION --> REJECTED: principal rejects (comment required)
  REJECTED --> PENDING_APPROVAL: edit, save, or AI revision
  APPROVED --> [*]
```

Details and the permission matrix are in [workflow-and-roles.md](workflow-and-roles.md).

## 5. Audit hash chain

```mermaid
flowchart LR
  G["GENESIS"] --> E1
  subgraph E1["Entry seq 1"]
    A1["action, actor, request,<br/>compliance, hashes"]
    H1["prev_hash = GENESIS<br/>entry_hash = SHA-256(entry)"]
  end
  E1 -->|"entry_hash"| E2
  subgraph E2["Entry seq 2"]
    A2["action, actor, request,<br/>compliance, hashes"]
    H2["prev_hash = hash of seq 1<br/>entry_hash = SHA-256(entry)"]
  end
  E2 -->|"entry_hash"| E3
  subgraph E3["Entry seq 3"]
    A3["..."]
    H3["prev_hash = hash of seq 2<br/>entry_hash = SHA-256(entry)"]
  end
  E3 -.->|"latest seq + hash stored in"| HEAD["__HEAD__ item<br/>(updated in the same transaction)"]
  V["GET /audit-log/verify"] -.->|"recomputes every hash,<br/>checks links, sequence and head"| E1
```

## 6. Deployment

```mermaid
flowchart LR
  DEV["Developer"] -->|"git push main"| GH["GitHub repository"]
  GH -->|"push event"| GA["GitHub Actions<br/>Deploy to EC2"]
  GA -->|"1. find and terminate old instance<br/>2. launch new instance<br/>3. associate Elastic IP"| EC2

  subgraph AWS["AWS account (us-east-1)"]
    EC2["EC2 t3.medium<br/>Amazon Linux<br/>user-data: git clone, pip install, start.sh"]
    IAM["IAM instance profile<br/>Bedrock + DynamoDB access"]
    SG["Security group<br/>8080 open to users"]
    DDB[("DynamoDB tables")]
    BR["Amazon Bedrock"]
  end

  EC2 --- IAM
  EC2 --- SG
  EC2 --> DDB
  EC2 --> BR
  USER["Browser"] -->|"http://Elastic IP:8080"| SG
  EC2 -.->|"git clone on boot"| GH
```

See [deployment-and-operations.md](deployment-and-operations.md).

## 7. Data model

```mermaid
erDiagram
  REQUEST ||--o{ AUDIT_ENTRY : "is recorded by"
  AUDIT_ENTRY ||--o| AUDIT_HEAD : "latest one is pointed to by"
  CLIENT ||--o{ REQUEST : "is the subject of"

  REQUEST {
    string request_id PK
    string client_id
    string client_name
    string created_by
    string created_by_role
    string request_prompt
    string draft
    string ai_draft
    string status
    string created_at
    int revision_count
    string advisor_approved_by
    string supervisor_id
    string supervisor_comment
  }

  AUDIT_ENTRY {
    string audit_id PK
    int seq
    string timestamp
    string action
    string request_id
    string actor_id
    string actor_role
    bool compliance_passed
    string final_draft_sha256
    string diff_from_ai
    string prev_hash
    string entry_hash
  }

  AUDIT_HEAD {
    string audit_id PK "constant __HEAD__"
    int seq
    string entry_hash
  }

  CLIENT {
    string client_id PK
    string name
    string risk_profile
    float portfolio_value
  }
```

Field-level detail is in [data-model.md](data-model.md).

## 8. Key design decisions

| Decision | Reason | Trade-off |
|---|---|---|
| Handlers are framework-agnostic | The same logic can run under FastAPI or Lambda | The Lambda entrypoint needs auth wiring before use |
| Compliance rules are deterministic code, not model prompts | Predictable, testable, explainable to a reviewer | Pattern rules miss subtle problems and can flag false positives |
| Server re-checks compliance at every approval | The client cannot be trusted to enforce the gate | Slight extra work per approval |
| Identity comes only from the signed token | Audit entries cannot be spoofed by request bodies | Needs real user management for production |
| Conditional updates for state changes | Two people cannot approve the same request | Requires DynamoDB conditional writes |
| Hash-chained audit log with a transactional head | Tampering, deletion and reordering are detectable | Tamper-evident only; needs immutable storage for retention |
| DynamoDB with local fallback | Works offline for development | Fallback data is per machine; `REQUIRE_SHARED_STORE=true` disables it |
| Rebuild-on-deploy EC2 | Simple, reproducible instance | Brief downtime on every push to `main` |

## 9. Technology stack

Python 3.11 on EC2 (3.9 compatible), FastAPI and Uvicorn, Streamlit, boto3, Amazon Bedrock (Claude Sonnet 4.5), Amazon DynamoDB, Amazon EC2, GitHub Actions.

## 10. Known limitations

- Client data is simulated; there is no CRM integration.
- Demo accounts and a shared default password are for prototyping only.
- The site is served over plain HTTP without a load balancer or WAF.
- The audit chain is tamper-evident, not tamper-proof; no immutable (WORM) storage yet.
- Compliance rules are simple patterns and do not replace supervisory review.
- The Lambda and SAM path does not authenticate callers yet.
