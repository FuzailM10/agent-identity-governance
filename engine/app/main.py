"""Agent Identity Governance — Control Plane (the "engine").

Phase 1 — Identity:
  * Register a human Owner.
  * Register an Agent, which issues it an identity (SPIFFE-style ID) and
    permanently links it to its Owner.
  * Trace the attribution chain: agent -> owner.
"""
import uuid

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import models, schemas
from .db import Base, engine, get_db

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
