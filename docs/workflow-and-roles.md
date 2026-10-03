# Workflow and roles

## Roles

| Role | Created by | Can do |
|---|---|---|
| Assistant (`assistant`) | Configuration | Generate drafts, edit, request AI revisions, view own drafts, view the audit log |
| Advisor (`advisor`) | Configuration | Everything an assistant can, plus level-1 approval of the final text |
| Compliance Principal (`principal`) | Configuration | Level-2 approval or rejection, verify the audit chain, export records. Cannot create drafts |

Built-in demo users: `assistant1`, `advisor1`, `advisor2`, `principal1` (default password `lpl-demo`). Replace them with `LPL_USERS` or an identity provider before real use. See [security-and-compliance.md](security-and-compliance.md).

## Permission matrix

| Action | Assistant | Advisor | Principal |
|---|---|---|---|
| Sign in, view clients, view audit log | yes | yes | yes |
| Run a compliance check | yes | yes | yes |
| Generate, edit, revise a draft | yes | yes | no |
| Level-1 approval | no | yes | no |
| Level-2 approval or rejection | no | no | yes |
| Verify audit chain | no | no | yes |

## Request states

| Status | Meaning | Who acts next |
|---|---|---|
| `PENDING_APPROVAL` | Draft exists and can be edited | Advisor |
| `PENDING_SUPERVISION` | Advisor approved the final text | Principal |
| `APPROVED` | Principal approved for release | None |
| `REJECTED` | Principal returned it with a comment | Assistant or advisor edits, which moves it back to `PENDING_APPROVAL` |

State diagram: see [architecture.md](architecture.md#4-request-lifecycle).

## Rules enforced by the server

1. Every approval re-runs the compliance rules on the final text. Any **blocking** finding returns HTTP 422 and nothing changes.
2. A principal cannot supervise a request they created or advisor-approved (separation of duties).
3. Rejection requires a comment.
4. State changes are conditional on the current status, so concurrent actions cannot both succeed (the loser gets HTTP 409).
5. If writing the audit entry fails after a state change, the state change is rolled back.
6. Text is stored exactly as entered; no reformatting.

## Audit events

| Action | Written when | Notable fields |
|---|---|---|
| `DRAFT_GENERATED` | A draft is created | `ai_draft_sha256`, compliance result |
| `DRAFT_REVISED` | The AI revises a draft from feedback | `comment` (the feedback), new `ai_draft_sha256` |
| `ADVISOR_APPROVED` | Level-1 approval | `final_draft`, `final_draft_sha256`, `diff_from_ai`, `edited_by_human` |
| `SUPERVISOR_APPROVED` | Level-2 approval | `final_draft`, `final_draft_sha256`, `advisor_id` |
| `SUPERVISOR_REJECTED` | Principal rejects | `comment`, `final_draft` |

Manual edits that are saved without approval are not logged individually; their net effect is captured in the diff at approval.

## Compliance rules

| Rule ID | Severity | Basis |
|---|---|---|
| `PROMISSORY_LANGUAGE` (guarantee, risk-free, certain to...) | block | FINRA 2210(d)(1)(B) |
| `MISSING_DRAFT_MARKER` | block | Internal policy |
| `MISSING_DISCLOSURE_INFORMATIONAL` | block | FINRA 2210 |
| `MISSING_DISCLOSURE_PAST_PERFORMANCE` | block | FINRA 2210 |
| `MISSING_SUITABILITY` | block | Reg BI |
| `PLACEHOLDER_TEXT` | block | Internal policy |
| `SENSITIVE_SSN` | block | Reg S-P |
| `EMPTY_DRAFT` | block | Internal policy |
| `FUTURE_RESULT_CLAIM` ("will earn...") | warn | FINRA 2210(d)(1)(B) |
| `PERFORMANCE_PROJECTION` | warn | FINRA 2210(d)(1)(F) |
| `SUPERLATIVE_CLAIM` | warn | FINRA 2210(d)(1)(A) |
| `POSSIBLE_ACCOUNT_NUMBER` | warn | Reg S-P |
| `CLIENT_NAME_MISSING` | warn | Internal policy |

Negated phrases such as "does not guarantee" are allowed. The rule set version is `RULESET_VERSION` in [backend/compliance.py](../backend/compliance.py) and is stored in every audit entry. These rules support, and do not replace, supervisory review.
