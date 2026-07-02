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
    owner_id: str
    created_at: datetime


class AttributionChain(BaseModel):
    """Answers the project's core question: 'who is behind this agent?'"""
    agent: AgentOut
    owner: OwnerOut
