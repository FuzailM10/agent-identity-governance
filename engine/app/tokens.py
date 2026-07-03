"""Capability tokens = signed JWTs that carry an agent's just-in-time access.

A JWT (JSON Web Token) is a tamper-evident, self-describing token: it holds
"claims" (facts) and is signed with a secret key, so anyone with the key can
verify it wasn't altered. We use it as the agent's short-lived "key card".

Security-first: the signing secret comes from an env var and NEVER ships in the
repo. The default below is clearly-labelled dev-only.
"""
import os
from datetime import datetime, timedelta, timezone

import jwt

SECRET_KEY = os.getenv("AIG_SECRET_KEY", "dev-insecure-secret-change-me")
ALGORITHM = "HS256"
ISSUER = "aig-control-plane"


def issue_capability_token(*, grant_id, agent, scope, constraints, ttl_seconds):
    """Mint a signed, time-boxed token for one agent + one scope.

    Note the token carries `owner_id` — attribution travels *with* the access,
    so every action taken with this token still points back to a human.
    """
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=ttl_seconds)
    payload = {
        "iss": ISSUER,
        "sub": agent.spiffe_id,   # the agent's verifiable identity
        "agent_id": agent.id,
        "owner_id": agent.owner_id,
        "scope": scope,
        "constraints": constraints,
        "jti": grant_id,          # links token -> grant row in the DB
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),  # expiry = the "just-in-time" part
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, now, exp


def decode_token(token: str) -> dict:
    """Verify signature + expiry and return the claims. Raises on invalid/expired."""
    return jwt.decode(
        token,
        SECRET_KEY,
        algorithms=[ALGORITHM],
        options={"require": ["exp", "iat", "jti"]},
    )
