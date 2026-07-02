"""Agent Identity Governance — Control Plane (the "engine").

Phase 0: just proves the toolchain works end to end — FastAPI boots and can
reach Postgres. Identity, policy, audit, risk, and the kill switch arrive in
later phases.
"""
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import get_db

app = FastAPI(
    title="Agent Identity Governance — Control Plane",
    description="Governance layer that brokers, audits, and controls AI-agent actions.",
    version="0.0.1",
)

# CORS = which web origins may call this API from a browser. The Vercel
# dashboard runs on a different origin, so it must be allowed. "*" is fine for
# local dev; we tighten it to the real Vercel domain before going public.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    """Liveness + DB connectivity check. The dashboard pings this."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "control-plane", "db": "connected"}
