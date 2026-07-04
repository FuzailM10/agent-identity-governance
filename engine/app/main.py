"""Agent Identity Governance — Control Plane (the "engine").

Phase 1 — Identity:
  * Register a human Owner.
  * Register an Agent, which issues it an identity (SPIFFE-style ID) and
    permanently links it to its Owner.
  * Trace the attribution chain: agent -> owner.
"""
import uuid

import jwt
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import audit, models, policy, risk, schemas
from .db import Base, engine, get_db
from .tokens import decode_token, issue_capability_token

# Create tables on startup (fine for a demo; real apps use migrations/Alembic).
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Agent Identity Governance — Control Plane",
    description="Governance layer that brokers, audits, and controls AI-agent actions.",
    version="0.1.0",
)

# CORS lets the Vercel dashboard (different origin) call this API from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to the Vercel domain before going public
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    """Liveness + DB connectivity check."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "control-plane", "db": "connected"}


# ---------------------------------------------------------------------------
# Owners (humans)
# ---------------------------------------------------------------------------
@app.post("/owners", response_model=schemas.OwnerOut, status_code=201)
def create_owner(payload: schemas.OwnerCreate, db: Session = Depends(get_db)):
    if db.query(models.Owner).filter_by(email=payload.email).first():
        raise HTTPException(status_code=409, detail="An owner with that email already exists.")
    owner = models.Owner(name=payload.name, email=payload.email)
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return owner


@app.get("/owners", response_model=list[schemas.OwnerOut])
def list_owners(db: Session = Depends(get_db)):
    return db.query(models.Owner).all()


# ---------------------------------------------------------------------------
# Agents (non-human identities)
# ---------------------------------------------------------------------------
@app.post("/agents", response_model=schemas.AgentOut, status_code=201)
def register_agent(payload: schemas.AgentCreate, db: Session = Depends(get_db)):
    """Register an agent -> issue its identity, linked to a human owner."""
    owner = db.get(models.Owner, payload.owner_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Owner not found — an agent must have a human owner.")

    agent_id = str(uuid.uuid4())
    agent = models.Agent(
        id=agent_id,
        name=payload.name,
        purpose=payload.purpose,
        spiffe_id=f"spiffe://aig/agent/{agent_id}",  # identity issued
        owner_id=owner.id,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@app.get("/agents", response_model=list[schemas.AgentOut])
def list_agents(db: Session = Depends(get_db)):
    return db.query(models.Agent).all()


@app.get("/agents/{agent_id}", response_model=schemas.AgentOut)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.get(models.Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return agent


@app.get("/agents/{agent_id}/attribution", response_model=schemas.AttributionChain)
def get_attribution(agent_id: str, db: Session = Depends(get_db)):
    """The accountability answer: which human is behind this agent?"""
    agent = db.get(models.Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return {"agent": agent, "owner": agent.owner}


@app.post("/agents/{agent_id}/kill", response_model=schemas.AgentOut)
def kill_agent(agent_id: str, db: Session = Depends(get_db)):
    """Kill switch: instantly deactivate an agent and revoke ALL its grants.

    After this, any action the agent attempts (even with an unexpired token)
    is denied at the broker, because every grant is now revoked.
    """
    agent = db.get(models.Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found.")

    agent.status = "killed"
    revoked = 0
    for grant in db.query(models.Grant).filter_by(agent_id=agent_id, revoked=False).all():
        grant.revoked = True
        revoked += 1
    db.commit()
    db.refresh(agent)

    audit.record_event(
        db, agent_id=agent.id, owner_id=agent.owner_id, grant_id=None,
        action="agent:kill", context={"grants_revoked": revoked},
        decision="KILLED", reason="kill switch activated — agent deactivated, all grants revoked",
    )
    return agent


# ---------------------------------------------------------------------------
# Grants & capability tokens (Phase 2: just-in-time scoped access)
# ---------------------------------------------------------------------------
@app.post("/agents/{agent_id}/grants", response_model=schemas.TokenIssued, status_code=201)
def issue_grant(agent_id: str, payload: schemas.GrantCreate, db: Session = Depends(get_db)):
    """Grant an agent scoped, time-boxed access and mint its capability token."""
    agent = db.get(models.Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found.")
    if agent.status != "active":
        raise HTTPException(status_code=403, detail=f"Agent is '{agent.status}', cannot be granted access.")

    grant_id = str(uuid.uuid4())
    token, _issued, exp = issue_capability_token(
        grant_id=grant_id,
        agent=agent,
        scope=payload.scope,
        constraints=payload.constraints,
        ttl_seconds=payload.ttl_seconds,
    )
    grant = models.Grant(
        id=grant_id,
        agent_id=agent.id,
        scope=payload.scope,
        constraints=payload.constraints,
        expires_at=exp,
    )
    db.add(grant)
    db.commit()
    db.refresh(grant)
    return {
        "grant": grant,
        "token": token,
        "expires_at": exp,
        "note": f"JIT access '{payload.scope}' granted for {payload.ttl_seconds}s — auto-expires.",
    }


@app.get("/agents/{agent_id}/grants", response_model=list[schemas.GrantOut])
def list_grants(agent_id: str, db: Session = Depends(get_db)):
    return db.query(models.Grant).filter_by(agent_id=agent_id).all()


def validate_token(token: str, db: Session):
    """Shared check: signature -> expiry -> grant exists -> not revoked.

    Returns (claims, "valid") on success, or (None, reason) on failure.
    """
    try:
        claims = decode_token(token)
    except jwt.ExpiredSignatureError:
        return None, "token expired — JIT access timed out"
    except jwt.InvalidTokenError as exc:
        return None, f"invalid token: {exc}"

    grant = db.get(models.Grant, claims.get("jti"))
    if grant is None:
        return None, "grant no longer exists"
    if grant.revoked:
        return None, "grant was revoked"
    return claims, "valid"


@app.post("/tokens/introspect", response_model=schemas.IntrospectResult)
def introspect_token(payload: schemas.IntrospectRequest, db: Session = Depends(get_db)):
    """Validate a capability token: is it still active, and what does it allow?

    This is the 'token introspection' pattern from OAuth.
    """
    claims, reason = validate_token(payload.token, db)
    return {"active": claims is not None, "reason": reason, "claims": claims}


# ---------------------------------------------------------------------------
# Policy broker (Phase 3): every agent action is brokered here first
# ---------------------------------------------------------------------------
@app.post("/broker", response_model=schemas.BrokerDecision)
def broker(payload: schemas.BrokerRequest, db: Session = Depends(get_db)):
    """The gate every agent action passes through: ALLOW / STEP_UP / DENY."""
    claims, reason = validate_token(payload.token, db)
    if claims is None:
        # A bad/expired/revoked token is an automatic DENY — but still audited.
        audit.record_event(
            db, agent_id=None, owner_id=None, grant_id=None,
            action=payload.action, context=payload.context,
            decision=policy.DENY, reason=reason,
        )
        return {"decision": policy.DENY, "reason": reason}

    agent = db.get(models.Agent, claims.get("agent_id"))
    current_risk = agent.risk_score if agent else 0
    result = policy.decide(claims, payload.action, payload.context, current_risk)
    response = {
        "decision": result.decision,
        "reason": result.reason,
        "agent_id": claims.get("agent_id"),
        "owner_id": claims.get("owner_id"),
    }

    # Update the agent's risk score based on this outcome, feeding future decisions.
    if agent:
        agent.risk_score = risk.next_score(agent.risk_score, result.decision)
        db.commit()
        response["risk_score"] = agent.risk_score

    # STEP_UP creates a pending human-approval record.
    if result.decision == policy.STEP_UP:
        approval = models.Approval(
            agent_id=claims["agent_id"],
            grant_id=claims["jti"],
            action=payload.action,
            context=payload.context,
            reason=result.reason,
        )
        db.add(approval)
        db.commit()
        db.refresh(approval)
        response["approval_id"] = approval.id

    # Every brokered decision is written to the tamper-evident audit trail.
    audit.record_event(
        db,
        agent_id=claims.get("agent_id"),
        owner_id=claims.get("owner_id"),
        grant_id=claims.get("jti"),
        action=payload.action,
        context=payload.context,
        decision=result.decision,
        reason=result.reason,
    )
    return response


@app.get("/approvals", response_model=list[schemas.ApprovalOut])
def list_approvals(db: Session = Depends(get_db)):
    return db.query(models.Approval).all()


@app.post("/approvals/{approval_id}/resolve", response_model=schemas.ApprovalOut)
def resolve_approval(approval_id: str, payload: schemas.ApprovalResolve, db: Session = Depends(get_db)):
    """A human owner approves or denies a stepped-up action."""
    approval = db.get(models.Approval, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found.")
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail=f"Already {approval.status}.")

    approval.status = "approved" if payload.approve else "denied"
    approval.decided_by = payload.decided_by
    db.commit()
    db.refresh(approval)
    return approval


# ---------------------------------------------------------------------------
# Audit trail (Phase 4): tamper-evident, hash-chained log
# ---------------------------------------------------------------------------
@app.get("/audit", response_model=list[schemas.AuditEventOut])
def list_audit(db: Session = Depends(get_db)):
    return db.query(models.AuditEvent).order_by(models.AuditEvent.seq.asc()).all()


@app.get("/audit/verify", response_model=schemas.AuditVerifyResult)
def verify_audit(db: Session = Depends(get_db)):
    """Recompute the hash chain and report whether it's intact."""
    return audit.verify_chain(db)
