"""
Users, roles and sessions for the two-level supervision workflow.

Roles
  assistant  creates drafts, edits them and asks the AI for revisions
  advisor    everything an assistant can do, plus first-level approval
  principal  compliance principal: second-level approval or rejection

Configuration
  LPL_USERS              "id:password:role:Display Name;id2:..." (replaces the demo users)
  LPL_DEMO_PASSWORD      password for the built-in demo users (default "lpl-demo")
  AUTH_SECRET            key used to sign session tokens; random per process if unset
  AUTH_TOKEN_TTL_HOURS   session lifetime (default 8)

The built-in demo users exist so the prototype can be tried immediately. Set LPL_USERS
(or move to an identity provider such as Amazon Cognito) before using real data.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Optional

ROLE_ASSISTANT = "assistant"
ROLE_ADVISOR = "advisor"
ROLE_PRINCIPAL = "principal"
ROLES = (ROLE_ASSISTANT, ROLE_ADVISOR, ROLE_PRINCIPAL)
ROLE_LABELS = {
    ROLE_ASSISTANT: "Assistant",
    ROLE_ADVISOR: "Advisor",
    ROLE_PRINCIPAL: "Compliance Principal",
}

_ITERATIONS = 200_000
_MAX_FAILURES = 5
_LOCKOUT_SECONDS = 300

_DEMO_USERS = (
    ("assistant1", ROLE_ASSISTANT, "Alex Rivera"),
    ("advisor1", ROLE_ADVISOR, "Michael Chen"),
    ("advisor2", ROLE_ADVISOR, "Priya Nair"),
    ("principal1", ROLE_PRINCIPAL, "Dana Okafor"),
)

_SECRET = os.environ.get("AUTH_SECRET") or secrets.token_hex(32)
_TTL_SECONDS = int(float(os.environ.get("AUTH_TOKEN_TTL_HOURS", "8")) * 3600)

_users: dict[str, dict] = {}
_demo_mode = False
_failures: dict[str, list[float]] = {}


def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS).hex()


def _make_user(user_id: str, password: str, role: str, name: str) -> dict:
    if role not in ROLES:
        raise ValueError(f"Unknown role '{role}' for user '{user_id}'")
    salt = secrets.token_bytes(16)
    return {
        "user_id": user_id,
        "name": name,
        "role": role,
        "salt": salt,
        "hash": _hash_password(password, salt),
    }


def load_users() -> None:
    """(Re)load users from the environment. Called at import time."""
    global _demo_mode
    _users.clear()
    configured = os.environ.get("LPL_USERS", "").strip()
    if configured:
        _demo_mode = False
        for item in configured.split(";"):
            item = item.strip()
            if not item:
                continue
            parts = item.split(":", 3)
            if len(parts) != 4:
                raise ValueError("LPL_USERS entries must look like id:password:role:Display Name")
            user_id, password, role, name = (p.strip() for p in parts)
            _users[user_id] = _make_user(user_id, password, role, name)
    else:
        _demo_mode = True
        password = os.environ.get("LPL_DEMO_PASSWORD", "lpl-demo")
        for user_id, role, name in _DEMO_USERS:
            _users[user_id] = _make_user(user_id, password, role, name)


def is_demo_mode() -> bool:
    return _demo_mode


def public_user(user: dict) -> dict:
    return {"user_id": user["user_id"], "name": user["name"], "role": user["role"]}


class AuthError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def authenticate(user_id: str, password: str) -> dict:
    now = time.time()
    recent = [t for t in _failures.get(user_id, []) if now - t < _LOCKOUT_SECONDS]
    _failures[user_id] = recent
    if len(recent) >= _MAX_FAILURES:
        raise AuthError(429, "Too many failed attempts. Try again in a few minutes.")

    user = _users.get(user_id)
    # Hash even for unknown users so timing does not reveal which IDs exist.
    salt = user["salt"] if user else b"\x00" * 16
    candidate = _hash_password(password or "", salt)
    if not user or not hmac.compare_digest(candidate, user["hash"]):
        _failures[user_id].append(now)
        raise AuthError(401, "Invalid user ID or password")

    _failures.pop(user_id, None)
    return public_user(user)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue_token(user: dict) -> str:
    payload = {**public_user(user), "exp": int(time.time()) + _TTL_SECONDS}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = _b64(hmac.new(_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_token(token: Optional[str]) -> dict:
    if not token or "." not in token:
        raise AuthError(401, "Not signed in")
    body, sig = token.rsplit(".", 1)
    expected = _b64(hmac.new(_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise AuthError(401, "Invalid session")
    try:
        payload = json.loads(_unb64(body))
    except (ValueError, json.JSONDecodeError):
        raise AuthError(401, "Invalid session")
    if int(payload.get("exp", 0)) < time.time():
        raise AuthError(401, "Session expired. Please sign in again.")
    user = _users.get(payload.get("user_id"))
    if not user or user["role"] != payload.get("role"):
        raise AuthError(401, "Account no longer valid")
    return public_user(user)


load_users()
