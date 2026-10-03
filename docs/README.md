# Documentation

Technical documentation for the LPL Delegation Assistant. Start with the architecture.

| Document | What it covers |
|---|---|
| [architecture.md](architecture.md) | System, request flow, lifecycle, audit chain, deployment and data-model diagrams, design decisions |
| [workflow-and-roles.md](workflow-and-roles.md) | Roles, permission matrix, states, server rules, audit events, compliance rules |
| [api-reference.md](api-reference.md) | Endpoints, bodies, responses and error codes |
| [data-model.md](data-model.md) | DynamoDB tables, audit entry fields, hash scheme |
| [security-and-compliance.md](security-and-compliance.md) | Controls, regulatory mapping, known gaps |
| [deployment-and-operations.md](deployment-and-operations.md) | CI/CD, runtime, AWS prerequisites, health checks, troubleshooting |
| [development-guide.md](development-guide.md) | Local setup, tests, conventions, how to extend |

## Diagrams

| File | Diagram |
|---|---|
| [diagrams/architecture.svg](diagrams/architecture.svg) | Static system architecture image |
| [diagrams/system-architecture.mmd](diagrams/system-architecture.mmd) | System components (Mermaid) |
| [diagrams/approval-sequence.mmd](diagrams/approval-sequence.mmd) | End-to-end approval sequence |
| [diagrams/request-lifecycle.mmd](diagrams/request-lifecycle.mmd) | Request state machine |
| [diagrams/audit-chain.mmd](diagrams/audit-chain.mmd) | Hash-chained audit log |
| [diagrams/deployment.mmd](diagrams/deployment.mmd) | CI/CD and AWS deployment |
| [diagrams/data-model.mmd](diagrams/data-model.mmd) | Entity relationships |

The Mermaid sources are embedded in [architecture.md](architecture.md), where GitHub renders them. If you change a `.mmd` file, update the matching block in `architecture.md`. To export images, use the Mermaid CLI: `npx @mermaid-js/mermaid-cli -i docs/diagrams/system-architecture.mmd -o system-architecture.png`.

Module READMEs sit next to the code: [backend](../backend/README.md), [frontend](../frontend/README.md), [infra](../infra/README.md), [data](../data/README.md), [.github](../.github/README.md).
