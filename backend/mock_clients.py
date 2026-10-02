"""
Hardcoded LPL client profile data.

Diagram step 3: "Fetches mock LPL client profile data from hardcoded dictionary"

In production this dictionary would be replaced with a call to LPL's CRM /
portfolio management APIs. For the hackathon, we hardcode a handful of
realistic client profiles so the draft-generation flow can be demoed without
any external data dependency.
"""
from __future__ import annotations

MOCK_CLIENTS = {
    "C-1001": {
        "client_id": "C-1001",
        "name": "Jane Doe",
        "risk_profile": "Moderate",
        "portfolio_value": 482_300.00,
        "ytd_return_pct": 6.8,
        "holdings": [
            {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "allocation_pct": 45},
            {"symbol": "BND", "name": "Vanguard Total Bond Market ETF", "allocation_pct": 30},
            {"symbol": "VXUS", "name": "Vanguard Total International Stock ETF", "allocation_pct": 15},
            {"symbol": "CASH", "name": "Cash & Equivalents", "allocation_pct": 10},
        ],
        "goals": "Retirement in 15 years; target retirement income of $85,000/yr",
        "last_review_date": "2026-01-15",
        "advisor": "Michael Chen",
    },
    "C-1002": {
        "client_id": "C-1002",
        "name": "Robert Alvarez",
        "risk_profile": "Conservative",
        "portfolio_value": 1_250_000.00,
        "ytd_return_pct": 3.2,
        "holdings": [
            {"symbol": "BND", "name": "Vanguard Total Bond Market ETF", "allocation_pct": 55},
            {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "allocation_pct": 25},
            {"symbol": "MUB", "name": "iShares National Muni Bond ETF", "allocation_pct": 15},
            {"symbol": "CASH", "name": "Cash & Equivalents", "allocation_pct": 5},
        ],
        "goals": "Capital preservation; annual distributions of $50,000 for living expenses",
        "last_review_date": "2025-11-02",
        "advisor": "Michael Chen",
    },
    "C-1003": {
        "client_id": "C-1003",
        "name": "Priya Natarajan",
        "risk_profile": "Aggressive",
        "portfolio_value": 215_600.00,
        "ytd_return_pct": 14.1,
        "holdings": [
            {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "allocation_pct": 55},
            {"symbol": "VXUS", "name": "Vanguard Total International Stock ETF", "allocation_pct": 25},
            {"symbol": "QQQ", "name": "Invesco QQQ Trust", "allocation_pct": 15},
            {"symbol": "CASH", "name": "Cash & Equivalents", "allocation_pct": 5},
        ],
        "goals": "Long-term growth; 25+ year time horizon, no near-term withdrawals",
        "last_review_date": "2026-02-20",
        "advisor": "Sarah Kim",
    },
}


def get_client(client_id: str) -> dict | None:
    """Look up a mock client profile by ID."""
    return MOCK_CLIENTS.get(client_id)


def list_clients() -> list[dict]:
    """Return a lightweight summary of all mock clients (for dropdowns)."""
    return [
        {"client_id": c["client_id"], "name": c["name"], "risk_profile": c["risk_profile"]}
        for c in MOCK_CLIENTS.values()
    ]
