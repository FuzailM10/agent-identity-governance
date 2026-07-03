"""Database tables for the control plane.

Phase 1 introduces the two identities at the core of the accountability thesis:

- `Owner`  — a *human* who is accountable for an agent.
- `Agent`  — a *non-human* (AI) identity, permanently linked to one Owner.

Every Agent carries a SPIFFE-style ID (spiffe://...). SPIFFE is the industry
standard for giving workloads (non-humans) a verifiable identity — using its
naming here is a deliberate nod to how real systems do this.
"""
import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Owner(Base):
    __tablename__ = "owners"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    agents: Mapped[list["Agent"]] = relationship(back_populates="owner")


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    purpose: Mapped[str] = mapped_column(String, nullable=False)

    # Verifiable workload identity, e.g. spiffe://aig/agent/<uuid>
    spiffe_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    # Lifecycle: active -> suspended -> killed (kill switch lands in Phase 6).
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)

    # The permanent link to a human. This is the accountability chain.
    owner_id: Mapped[str] = mapped_column(ForeignKey("owners.id"), nullable=False)
    owner: Mapped["Owner"] = relationship(back_populates="agents")

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    grants: Mapped[list["Grant"]] = relationship(back_populates="agent")


class Grant(Base):
    """A just-in-time, scoped, time-boxed grant of access to one agent.

    Each grant is the DB record behind one capability token (JWT). The token
    self-expires via its `exp`; `revoked` lets us kill it early (Phase 6).
    """
    __tablename__ = "grants"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)

    scope: Mapped[str] = mapped_column(String, nullable=False)          # e.g. "invoice:approve"
    constraints: Mapped[dict] = mapped_column(JSON, default=dict)       # e.g. {"max_amount": 5000}

    revoked: Mapped[bool] = mapped_column(default=False)
    issued_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(nullable=False)

    agent: Mapped["Agent"] = relationship(back_populates="grants")


class Approval(Base):
    """A pending human-approval request, created when the policy says STEP_UP.

    This is the accountability record for 'a human said yes to this exception'.
    """
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    grant_id: Mapped[str] = mapped_column(String, nullable=False)   # the token's jti
    action: Mapped[str] = mapped_column(String, nullable=False)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(String, nullable=False)

    status: Mapped[str] = mapped_column(String, default="pending")  # pending|approved|denied
    decided_by: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AuditEvent(Base):
    """One tamper-evident entry in the hash-chained audit log.

    `hash` = SHA-256 of this row's fields + `prev_hash`. See app/audit.py.
    """
    __tablename__ = "audit_events"

    seq: Mapped[int] = mapped_column(primary_key=True)  # explicit order, 1..N
    ts: Mapped[str] = mapped_column(String, nullable=False)  # ISO8601, hashed as-is

    agent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String, nullable=True)
    grant_id: Mapped[str | None] = mapped_column(String, nullable=True)

    action: Mapped[str] = mapped_column(String, nullable=False)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)

    prev_hash: Mapped[str] = mapped_column(String, nullable=False)
    hash: Mapped[str] = mapped_column(String, nullable=False)
