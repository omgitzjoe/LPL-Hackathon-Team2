"""
Bedrock client wrapper for draft generation.

Diagram step 4: "Generates the draft document & applies LPL compliance
guardrails" via Amazon Bedrock (Claude Sonnet 4.5).

Supports a MOCK_MODE fallback (no AWS credentials required) so the rest of
the delegation workflow can be demoed/developed without a deployed Bedrock
model access grant.
"""
import json
import os

COMPLIANCE_SYSTEM_PROMPT = """You are an AI drafting assistant for LPL Financial advisors.
You draft client-facing documents (portfolio reviews, account updates, summaries)
that a human advisor will review, edit, and approve before anything is sent to a client.

You MUST follow these LPL compliance guardrails in every draft:
1. Never guarantee or imply guaranteed investment returns.
2. Always include a brief suitability statement tying recommendations to the
   client's stated risk profile and goals.
3. Include a standard disclosure: "This material is for informational purposes
   only and does not constitute investment advice. Past performance is not
   indicative of future results. Please consult your advisor before making any
   changes to your portfolio."
4. Keep tone professional, concise, and free of speculative or promissory language.
5. Clearly mark the document as a DRAFT pending advisor approval.

Produce only the draft document text (no preamble, no meta-commentary).
"""


class Config:
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
    BEDROCK_MODEL_ID = os.environ.get(
        "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    )
    MOCK_MODE = os.environ.get("BEDROCK_MOCK_MODE", "true").lower() in ("1", "true", "yes")


def _build_user_message(client_profile: dict, request_prompt: str) -> str:
    holdings = "\n".join(
        f"  - {h['symbol']} ({h['name']}): {h['allocation_pct']}%"
        for h in client_profile.get("holdings", [])
    )
    return f"""Advisor request: {request_prompt}

Client profile:
  Name: {client_profile['name']}
  Risk profile: {client_profile['risk_profile']}
  Portfolio value: ${client_profile['portfolio_value']:,.2f}
  YTD return: {client_profile['ytd_return_pct']}%
  Goals: {client_profile['goals']}
  Last review date: {client_profile['last_review_date']}
  Current holdings:
{holdings}

Draft the requested document now, following all compliance guardrails.
"""


def _mock_draft(client_profile: dict, request_prompt: str) -> str:
    """Deterministic offline fallback draft (no AWS credentials needed)."""
    holdings = "\n".join(
        f"  • {h['symbol']} – {h['name']}: {h['allocation_pct']}%"
        for h in client_profile.get("holdings", [])
    )
    return f"""[DRAFT — PENDING ADVISOR APPROVAL]

Subject: {request_prompt}

Dear {client_profile['name']},

Here is a summary prepared on your behalf ahead of our upcoming review.

Portfolio value: ${client_profile['portfolio_value']:,.2f} (YTD return: {client_profile['ytd_return_pct']}%)
Risk profile: {client_profile['risk_profile']}
Goals: {client_profile['goals']}

Current allocation:
{holdings}

Based on your {client_profile['risk_profile'].lower()} risk profile and stated goals, your
current allocation remains broadly aligned with your long-term objectives. We will
continue to monitor market conditions and rebalance as needed.

This material is for informational purposes only and does not constitute investment
advice. Past performance is not indicative of future results. Please consult your
advisor before making any changes to your portfolio.

[Generated in MOCK MODE — set BEDROCK_MOCK_MODE=false and configure AWS credentials
to generate this draft with Amazon Bedrock Claude Sonnet 4.5.]
"""


class BedrockDraftGenerator:
    """Generates advisor drafts via Amazon Bedrock, with an offline fallback."""

    def __init__(self):
        self.config = Config()
        self._client = None
        if not self.config.MOCK_MODE:
            import boto3  # imported lazily so MOCK_MODE doesn't require boto3 creds

            self._client = boto3.client(
                "bedrock-runtime", region_name=self.config.AWS_REGION
            )

    def generate_draft(self, client_profile: dict, request_prompt: str) -> str:
        if self.config.MOCK_MODE or self._client is None:
            return _mock_draft(client_profile, request_prompt)

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "system": COMPLIANCE_SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": _build_user_message(client_profile, request_prompt),
                }
            ],
        }

        response = self._client.invoke_model(
            modelId=self.config.BEDROCK_MODEL_ID,
            body=json.dumps(body),
        )
        payload = json.loads(response["body"].read())
        return payload["content"][0]["text"]
