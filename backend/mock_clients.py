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
    "C-1004": {
        "client_id": "C-1004",
        "name": "Margaret O'Sullivan",
        "risk_profile": "Conservative",
        "portfolio_value": 2_150_000.00,
        "ytd_return_pct": 2.9,
        "holdings": [
            {"symbol": "BND", "name": "Vanguard Total Bond Market ETF", "allocation_pct": 40},
            {"symbol": "VTIP", "name": "Vanguard Short-Term Inflation-Protected Securities ETF", "allocation_pct": 20},
            {"symbol": "MUB", "name": "iShares National Muni Bond ETF", "allocation_pct": 20},
            {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "allocation_pct": 10},
            {"symbol": "CASH", "name": "Cash & Equivalents", "allocation_pct": 10},
        ],
        "goals": "Recently retired; preserve principal, generate $90,000/yr income, minimize tax impact",
        "last_review_date": "2026-03-10",
        "advisor": "Michael Chen",
    },
    "C-1005": {
        "client_id": "C-1005",
        "name": "David & Lisa Kim",
        "risk_profile": "Moderately Aggressive",
        "portfolio_value": 875_400.00,
        "ytd_return_pct": 9.7,
        "holdings": [
            {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "allocation_pct": 40},
            {"symbol": "VXUS", "name": "Vanguard Total International Stock ETF", "allocation_pct": 20},
            {"symbol": "QQQ", "name": "Invesco QQQ Trust", "allocation_pct": 15},
            {"symbol": "BND", "name": "Vanguard Total Bond Market ETF", "allocation_pct": 15},
            {"symbol": "VNQ", "name": "Vanguard Real Estate ETF", "allocation_pct": 5},
            {"symbol": "CASH", "name": "Cash & Equivalents", "allocation_pct": 5},
        ],
        "goals": "Fund two children's college (ages 8 and 12); retirement in 20 years",
        "last_review_date": "2026-04-01",
        "advisor": "Sarah Kim",
    },
    "C-1006": {
        "client_id": "C-1006",
        "name": "Anthony Williams",
        "risk_profile": "Aggressive",
        "portfolio_value": 340_000.00,
        "ytd_return_pct": 18.3,
        "holdings": [
            {"symbol": "QQQ", "name": "Invesco QQQ Trust", "allocation_pct": 35},
            {"symbol": "ARKK", "name": "ARK Innovation ETF", "allocation_pct": 20},
            {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "allocation_pct": 20},
            {"symbol": "SOXX", "name": "iShares Semiconductor ETF", "allocation_pct": 15},
            {"symbol": "VXUS", "name": "Vanguard Total International Stock ETF", "allocation_pct": 10},
        ],
        "goals": "Maximize growth; 30-year horizon, high risk tolerance, tech sector conviction",
        "last_review_date": "2026-05-15",
        "advisor": "Michael Chen",
    },
    "C-1007": {
        "client_id": "C-1007",
        "name": "Susan & James Patterson",
        "risk_profile": "Moderate",
        "portfolio_value": 1_680_000.00,
        "ytd_return_pct": 5.4,
        "holdings": [
            {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "allocation_pct": 35},
            {"symbol": "BND", "name": "Vanguard Total Bond Market ETF", "allocation_pct": 25},
            {"symbol": "VXUS", "name": "Vanguard Total International Stock ETF", "allocation_pct": 15},
            {"symbol": "VNQ", "name": "Vanguard Real Estate ETF", "allocation_pct": 10},
            {"symbol": "GLD", "name": "SPDR Gold Shares", "allocation_pct": 5},
            {"symbol": "CASH", "name": "Cash & Equivalents", "allocation_pct": 10},
        ],
        "goals": "Retire in 5 years; transition to income-focused portfolio, maintain current lifestyle",
        "last_review_date": "2025-12-18",
        "advisor": "Sarah Kim",
    },
    "C-1008": {
        "client_id": "C-1008",
        "name": "Carlos Mendez",
        "risk_profile": "Moderately Conservative",
        "portfolio_value": 520_000.00,
        "ytd_return_pct": 4.1,
        "holdings": [
            {"symbol": "BND", "name": "Vanguard Total Bond Market ETF", "allocation_pct": 35},
            {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "allocation_pct": 30},
            {"symbol": "VXUS", "name": "Vanguard Total International Stock ETF", "allocation_pct": 10},
            {"symbol": "VTIP", "name": "Vanguard Short-Term Inflation-Protected Securities ETF", "allocation_pct": 10},
            {"symbol": "MUB", "name": "iShares National Muni Bond ETF", "allocation_pct": 10},
            {"symbol": "CASH", "name": "Cash & Equivalents", "allocation_pct": 5},
        ],
        "goals": "Recently divorced; rebuild financial stability, build emergency fund, retire at 62",
        "last_review_date": "2026-06-01",
        "advisor": "Michael Chen",
    },
    "C-1009": {
        "client_id": "C-1009",
        "name": "Emily Zhang",
        "risk_profile": "Aggressive",
        "portfolio_value": 128_500.00,
        "ytd_return_pct": 22.6,
        "holdings": [
            {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "allocation_pct": 30},
            {"symbol": "QQQ", "name": "Invesco QQQ Trust", "allocation_pct": 25},
            {"symbol": "VXUS", "name": "Vanguard Total International Stock ETF", "allocation_pct": 20},
            {"symbol": "ARKK", "name": "ARK Innovation ETF", "allocation_pct": 15},
            {"symbol": "CASH", "name": "Cash & Equivalents", "allocation_pct": 10},
        ],
        "goals": "First-generation wealth builder; save for home down payment in 3 years, then shift to retirement",
        "last_review_date": "2026-07-22",
        "advisor": "Sarah Kim",
    },
    "C-1010": {
        "client_id": "C-1010",
        "name": "William & Grace Thompson",
        "risk_profile": "Conservative",
        "portfolio_value": 3_400_000.00,
        "ytd_return_pct": 2.1,
        "holdings": [
            {"symbol": "BND", "name": "Vanguard Total Bond Market ETF", "allocation_pct": 35},
            {"symbol": "MUB", "name": "iShares National Muni Bond ETF", "allocation_pct": 25},
            {"symbol": "VTIP", "name": "Vanguard Short-Term Inflation-Protected Securities ETF", "allocation_pct": 15},
            {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "allocation_pct": 10},
            {"symbol": "GLD", "name": "SPDR Gold Shares", "allocation_pct": 5},
            {"symbol": "CASH", "name": "Cash & Equivalents", "allocation_pct": 10},
        ],
        "goals": "Estate planning focus; fund grandchildren's education trusts, charitable giving, preserve wealth",
        "last_review_date": "2026-01-30",
        "advisor": "Michael Chen",
    },
    "C-1011": {
        "client_id": "C-1011",
        "name": "Rachel Foster",
        "risk_profile": "Moderate",
        "portfolio_value": 310_000.00,
        "ytd_return_pct": 7.9,
        "holdings": [
            {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "allocation_pct": 40},
            {"symbol": "BND", "name": "Vanguard Total Bond Market ETF", "allocation_pct": 25},
            {"symbol": "VXUS", "name": "Vanguard Total International Stock ETF", "allocation_pct": 15},
            {"symbol": "VNQ", "name": "Vanguard Real Estate ETF", "allocation_pct": 10},
            {"symbol": "CASH", "name": "Cash & Equivalents", "allocation_pct": 10},
        ],
        "goals": "Small business owner; build retirement outside the business, diversify away from concentrated risk",
        "last_review_date": "2026-08-05",
        "advisor": "Sarah Kim",
    },
    "C-1012": {
        "client_id": "C-1012",
        "name": "Marcus & Denise Johnson",
        "risk_profile": "Moderately Aggressive",
        "portfolio_value": 1_100_000.00,
        "ytd_return_pct": 11.2,
        "holdings": [
            {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "allocation_pct": 35},
            {"symbol": "QQQ", "name": "Invesco QQQ Trust", "allocation_pct": 20},
            {"symbol": "VXUS", "name": "Vanguard Total International Stock ETF", "allocation_pct": 15},
            {"symbol": "BND", "name": "Vanguard Total Bond Market ETF", "allocation_pct": 15},
            {"symbol": "SOXX", "name": "iShares Semiconductor ETF", "allocation_pct": 10},
            {"symbol": "CASH", "name": "Cash & Equivalents", "allocation_pct": 5},
        ],
        "goals": "Dual-income household; early retirement at 55, travel, maintain rental property portfolio",
        "last_review_date": "2026-04-18",
        "advisor": "Michael Chen",
    },
    "C-1013": {
        "client_id": "C-1013",
        "name": "Helen Kowalski",
        "risk_profile": "Moderately Conservative",
        "portfolio_value": 780_000.00,
        "ytd_return_pct": 3.8,
        "holdings": [
            {"symbol": "BND", "name": "Vanguard Total Bond Market ETF", "allocation_pct": 30},
            {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "allocation_pct": 25},
            {"symbol": "MUB", "name": "iShares National Muni Bond ETF", "allocation_pct": 15},
            {"symbol": "VXUS", "name": "Vanguard Total International Stock ETF", "allocation_pct": 10},
            {"symbol": "GLD", "name": "SPDR Gold Shares", "allocation_pct": 10},
            {"symbol": "CASH", "name": "Cash & Equivalents", "allocation_pct": 10},
        ],
        "goals": "Widow; protect inheritance, generate steady income, fund long-term care insurance",
        "last_review_date": "2026-02-14",
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
