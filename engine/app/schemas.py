"""Pydantic schemas = the shapes of data going in/out of the API.

`*Create` schemas validate incoming request bodies. `*Out` schemas define what
we send back (from_attributes lets them read straight off SQLAlchemy models).
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


# --- Owner (the human) ---
class OwnerCreate(BaseModel):
    name: str
    email: str


class OwnerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    created_at: datetime


# --- Agent (the non-human identity) ---
class AgentCreate(BaseModel):
    name: str
    purpose: str
    owner_id: str


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    purpose: str
    spiffe_id: str
    status: str
    risk_score: int
    owner_id: str
    created_at: datetime


class AttributionChain(BaseModel):
    """Answers the project's core question: 'who is behind this agent?'"""
    agent: AgentOut
    owner: OwnerOut


# --- Grants & capability tokens (Phase 2: JIT access) ---
class GrantCreate(BaseModel):
    scope: str                       # what the agent may do, e.g. "invoice:approve"
    constraints: dict = {}           # limits, e.g. {"max_amount": 5000}
    ttl_seconds: int = 300           # how long the access lives (just-in-time)


class GrantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    scope: str
    constraints: dict
    revoked: bool
    issued_at: datetime
    expires_at: datetime


class TokenIssued(BaseModel):
    """What you get back when access is granted: the record + the actual token."""
    grant: GrantOut
    token: str
    expires_at: datetime
    note: str


class IntrospectRequest(BaseModel):
    token: str


class IntrospectResult(BaseModel):
    """Is this token still valid, and what does it allow? (OAuth 'introspection')"""
    active: bool
    reason: str
    claims: dict | None = None


# --- Policy broker & human approvals (Phase 3) ---
class BrokerRequest(BaseModel):
    token: str
    action: str                 # what the agent wants to do, e.g. "invoice:approve"
    context: dict = {}          # request details, e.g. {"amount": 50000}


class BrokerDecision(BaseModel):
    decision: str               # ALLOW | DENY | STEP_UP
    reason: str
    agent_id: str | None = None
    owner_id: str | None = None
    approval_id: str | None = None   # set when STEP_UP creates a pending approval
    risk_score: int | None = None    # the agent's risk score after this decision


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    grant_id: str
    action: str
    context: dict
    reason: str
    status: str
    decided_by: str | None
    created_at: datetime


class ApprovalResolve(BaseModel):
    approve: bool               # True = human approves the exception
    decided_by: str             # who approved (owner name/id)


# --- Audit trail (Phase 4) ---
class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seq: int
    ts: str
    agent_id: str | None
    owner_id: str | None
    grant_id: str | None
    action: str
    context: dict
    decision: str
    reason: str
    prev_hash: str
    hash: str


class AuditVerifyResult(BaseModel):
    valid: bool
    events: int | None = None
    head_hash: str | None = None
    broken_at_seq: int | None = None
    reason: str | None = None
