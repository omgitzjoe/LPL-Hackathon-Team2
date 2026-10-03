"""
Deterministic compliance checks for AI-generated advisor drafts.

These rules run on every draft (and again on the final, human-edited text) and do
not depend on the language model. They are a first-line control that sits in front of
human supervision: a draft with any blocking finding cannot be approved.

Each rule maps to the kind of review a compliance principal would perform under
FINRA Rule 2210 (communications with the public), Regulation Best Interest and
general books-and-records practice. The rule set is intentionally conservative and
simple to read; it is not legal advice and does not replace supervisory review.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

RULESET_VERSION = "2026.10-1"

BLOCK = "block"
WARN = "warn"

_NEGATORS = ("not ", "no ", "n't", "cannot", "never", "without", "nor ", "neither ")

_GUARANTEE_RE = re.compile(r"\bguarantee(?:d|s|ing)?\b", re.I)
_ABSOLUTE_RE = re.compile(
    r"\b(?:risk[- ]free|no[- ]risk|zero risk|cannot lose|can'?t lose|sure thing|"
    r"assured returns?|certain to (?:earn|gain|grow|return)|"
    r"will (?:definitely|certainly|always) )",
    re.I,
)
_WILL_RETURN_RE = re.compile(
    r"\bwill\s+(?:earn|return|yield|outperform|beat|grow to|double|triple)\b", re.I
)
_SUPERLATIVE_RE = re.compile(
    r"\b(?:best(?!\s+interest)|top[- ]performing|superior|market[- ]beating|unbeatable)\b", re.I
)
_PROJECTION_RE = re.compile(
    r"\b(?:expected|projected|forecast(?:ed)?|anticipated|estimated)\s+"
    r"(?:annual(?:ized)?\s+)?(?:return|growth|performance|yield|gain)s?\b",
    re.I,
)
_PLACEHOLDER_RE = re.compile(
    r"\[\s*(?:insert|advisor|client|name|date|tbd|todo|placeholder)[^\]]*\]|\bTBD\b|\bTODO\b|lorem ipsum",
    re.I,
)
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_LONG_NUMBER_RE = re.compile(r"\b\d{9,}\b")


def _finding(rule_id: str, severity: str, title: str, detail: str, citation: str, match: str = "") -> dict:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "title": title,
        "detail": detail,
        "citation": citation,
        "match": match,
    }


def _is_negated(text: str, start: int) -> bool:
    window = text[max(0, start - 30):start].lower()
    return any(n in window for n in _NEGATORS)


def _snippet(text: str, start: int, end: int) -> str:
    return text[max(0, start - 20):min(len(text), end + 20)].strip()


def check_draft(text: str, client_profile: Optional[dict] = None) -> dict:
    """Run every rule against `text` and return a structured result."""
    findings: list[dict] = []
    raw = text or ""
    norm = re.sub(r"\s+", " ", raw)

    if not norm.strip():
        findings.append(_finding(
            "EMPTY_DRAFT", BLOCK, "Draft is empty",
            "There is no text to review.", "Internal policy",
        ))
        return _result(findings)

    # Promissory or guaranteed-return language (block).
    for m in _GUARANTEE_RE.finditer(norm):
        if not _is_negated(norm, m.start()):
            findings.append(_finding(
                "PROMISSORY_LANGUAGE", BLOCK, "Guaranteed or promissory language",
                "Communications must not state or imply guaranteed results.",
                "FINRA 2210(d)(1)(B)", _snippet(norm, m.start(), m.end()),
            ))
    for m in _ABSOLUTE_RE.finditer(norm):
        if not _is_negated(norm, m.start()):
            findings.append(_finding(
                "PROMISSORY_LANGUAGE", BLOCK, "Absolute or risk-free claim",
                "Do not describe an investment as free of risk or certain to perform.",
                "FINRA 2210(d)(1)(B)", _snippet(norm, m.start(), m.end()),
            ))

    for m in _WILL_RETURN_RE.finditer(norm):
        findings.append(_finding(
            "FUTURE_RESULT_CLAIM", WARN, "Statement of future results",
            "Phrases like 'will earn' or 'will outperform' read as a promise. Use 'may' or 'seeks to'.",
            "FINRA 2210(d)(1)(B)", _snippet(norm, m.start(), m.end()),
        ))
    for m in _PROJECTION_RE.finditer(norm):
        findings.append(_finding(
            "PERFORMANCE_PROJECTION", WARN, "Performance projection",
            "Projections of investment performance are restricted in retail communications.",
            "FINRA 2210(d)(1)(F)", _snippet(norm, m.start(), m.end()),
        ))
    for m in _SUPERLATIVE_RE.finditer(norm):
        findings.append(_finding(
            "SUPERLATIVE_CLAIM", WARN, "Superlative or exaggerated claim",
            "Claims must be fair, balanced and not exaggerated.",
            "FINRA 2210(d)(1)(A)", _snippet(norm, m.start(), m.end()),
        ))

    # Required content (block).
    if not re.search(r"\bDRAFT\b", norm):
        findings.append(_finding(
            "MISSING_DRAFT_MARKER", BLOCK, "Document is not marked as DRAFT",
            "AI-generated documents must be labelled DRAFT until supervisory approval.",
            "Internal policy",
        ))
    if not re.search(r"informational\s+purposes", norm, re.I):
        findings.append(_finding(
            "MISSING_DISCLOSURE_INFORMATIONAL", BLOCK, "Missing informational-purposes disclosure",
            "Include: 'This material is for informational purposes only and does not constitute investment advice.'",
            "FINRA 2210(d)(1)(A)",
        ))
    if not re.search(r"past\s+performance", norm, re.I):
        findings.append(_finding(
            "MISSING_DISCLOSURE_PAST_PERFORMANCE", BLOCK, "Missing past-performance disclosure",
            "Include: 'Past performance is not indicative of future results.'",
            "FINRA 2210(d)(1)(A)",
        ))
    has_suitability = re.search(r"suitab|best interest", norm, re.I) or (
        re.search(r"risk profile", norm, re.I) and re.search(r"\bgoals?\b|\bobjectives?\b", norm, re.I)
    )
    if not has_suitability:
        findings.append(_finding(
            "MISSING_SUITABILITY", BLOCK, "No suitability statement",
            "Tie the content to the client's risk profile and goals.",
            "Regulation Best Interest",
        ))

    # Unfinished text and sensitive data.
    for m in _PLACEHOLDER_RE.finditer(norm):
        findings.append(_finding(
            "PLACEHOLDER_TEXT", BLOCK, "Unfinished placeholder text",
            "Replace placeholders before submitting.", "Internal policy",
            _snippet(norm, m.start(), m.end()),
        ))
    if _SSN_RE.search(norm):
        findings.append(_finding(
            "SENSITIVE_SSN", BLOCK, "Possible Social Security number",
            "Do not include SSNs in client communications.", "Reg S-P",
        ))
    if _LONG_NUMBER_RE.search(norm):
        findings.append(_finding(
            "POSSIBLE_ACCOUNT_NUMBER", WARN, "Long number that may be an account number",
            "Mask full account numbers (show the last four digits only).", "Reg S-P",
        ))

    # Grounding against the client record.
    if client_profile:
        name = client_profile.get("name", "")
        if name and name.lower() not in norm.lower():
            findings.append(_finding(
                "CLIENT_NAME_MISSING", WARN, "Client name not found in the text",
                f"The draft does not mention {name}. Check that it is addressed to the right client.",
                "Internal policy",
            ))

    return _result(findings)


def _result(findings: list[dict]) -> dict:
    blocking = sum(1 for f in findings if f["severity"] == BLOCK)
    warnings = sum(1 for f in findings if f["severity"] == WARN)
    return {
        "passed": blocking == 0,
        "blocking": blocking,
        "warnings": warnings,
        "findings": findings,
        "ruleset_version": RULESET_VERSION,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def summarize(result: dict) -> list[str]:
    """Flat, hash-friendly list like ['PROMISSORY_LANGUAGE:block', ...]."""
    return sorted({f"{f['rule_id']}:{f['severity']}" for f in result["findings"]})
