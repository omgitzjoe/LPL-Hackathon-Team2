# Security and compliance

This is a hackathon prototype. This page lists the controls that exist, how they work, and what is still missing.

## Controls in place

| Area | Control |
|---|---|
| Authentication | Sign-in with user ID and password. Passwords stored as salted PBKDF2-HMAC-SHA256 (200,000 iterations). Unknown users take the same time as wrong passwords |
| Brute force | 5 failed logins per user in 5 minutes returns HTTP 429 |
| Sessions | HMAC-SHA256 signed tokens with expiry (default 8 hours). Tokens are rejected if the user or role changed |
| Authorization | Roles enforced server-side for every state-changing route. The client UI is not trusted |
| Identity in records | The actor in every audit entry comes from the verified token, never from the request body |
| Separation of duties | A principal cannot supervise a request they created or advisor-approved |
| Content gate | Deterministic rules re-run on the server at every approval. Blocking findings stop the workflow |
| Concurrency | Conditional writes prevent two approvals of the same request |
| Audit integrity | Hash-chained entries, transactional head pointer, verification endpoint |
| Data minimization | Client data is simulated; the SSN rule blocks SSNs in drafts |
| Secrets | No keys in the repository. AWS access uses an instance role on EC2 |

## Configuration

| Variable | Purpose |
|---|---|
| `LPL_USERS` | `id:password:role:Display Name;...`. Replaces the demo users. Do not use `:` or `;` inside values |
| `LPL_DEMO_PASSWORD` | Password for the demo users (default `lpl-demo`) |
| `AUTH_SECRET` | Signing key for tokens. Set a long random value in production; otherwise a random key is generated per start and sessions end on restart |
| `AUTH_TOKEN_TTL_HOURS` | Session lifetime |
| `REQUIRE_SHARED_STORE` | `true` refuses to run on local storage |

## Regulatory mapping

| Topic | Where it shows up |
|---|---|
| FINRA 2210 (communications with the public) | Promissory, projection, superlative and disclosure rules |
| Regulation Best Interest | Suitability statement rule |
| Reg S-P (privacy) | SSN and account-number rules |
| Supervision (FINRA 3110 style review) | Two-level approval, principal queue, rejection with reasons |
| Books and records | Complete event log, exportable with verification status |

This mapping is a design aid, not a compliance certification. A registered principal must still review every document.

## Known gaps before real use

1. **Demo credentials.** The default accounts and password are public in the repository. Set `LPL_USERS`, or integrate Amazon Cognito or the firm's identity provider with MFA.
2. **No TLS.** The site is plain HTTP. Put it behind an Application Load Balancer or CloudFront with HTTPS.
3. **Network exposure.** Restrict the security group to expected users and do not expose port 8000. Consider AWS WAF.
4. **Immutable retention.** The hash chain is tamper-evident, not tamper-proof. Add S3 Object Lock or a ledger store, and deny delete permissions on the audit table. SEC 17a-4 style retention needs write-once storage.
5. **Tail truncation outside DynamoDB.** In local mode there is no external head pointer, so removal of the newest entries cannot be detected.
6. **Rule coverage.** Rules are patterns. Add Amazon Bedrock Guardrails, an evaluation set for false positives and negatives, and compliance-owned rule maintenance.
7. **Model risk.** Drafts can contain wrong numbers. Add citations from the client record and automated number checks.
8. **Client data.** Replace mock data with governed CRM access, and apply data-loss controls before sending real data to a model.
9. **Lambda path.** The Lambda entrypoint does not authenticate callers.
10. **Monitoring.** Add CloudWatch alarms for failed verification, repeated login failures and error rates.
