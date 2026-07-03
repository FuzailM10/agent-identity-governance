"""Tamper-evident audit trail via a hash chain.

Every recorded event stores:
  - a SHA-256 `hash` of its own contents + the previous event's hash
  - the `prev_hash` it chained from

Because each hash depends on the one before it, altering any past event breaks
that event's hash AND every hash after it. `verify_chain()` recomputes the whole
chain and reports the first break. This is the same idea a blockchain uses.
"""
import hashlib
import json
from datetime import datetime, timezone

from . import models

GENESIS = "0" * 64  # the "previous hash" of the very first event


def _canonical(payload: dict) -> str:
    """Deterministic JSON so the same data always hashes the same way."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_hash(payload: dict) -> str:
    return hashlib.sha256(_canonical(payload).encode()).hexdigest()


def _payload(e) -> dict:
    """The exact fields that get hashed (everything except the hash itself)."""
    return {
        "seq": e["seq"], "ts": e["ts"], "agent_id": e["agent_id"],
        "owner_id": e["owner_id"], "grant_id": e["grant_id"], "action": e["action"],
        "context": e["context"], "decision": e["decision"], "reason": e["reason"],
        "prev_hash": e["prev_hash"],
    }


def record_event(db, *, agent_id, owner_id, grant_id, action, context, decision, reason):
    """Append one event to the chain."""
    last = db.query(models.AuditEvent).order_by(models.AuditEvent.seq.desc()).first()
    seq = 1 if last is None else last.seq + 1
    prev_hash = GENESIS if last is None else last.hash

    fields = {
        "seq": seq,
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id, "owner_id": owner_id, "grant_id": grant_id,
        "action": action, "context": context, "decision": decision, "reason": reason,
        "prev_hash": prev_hash,
    }
    event = models.AuditEvent(**fields, hash=compute_hash(_payload(fields)))
    db.add(event)
    db.commit()
    return event


def verify_chain(db) -> dict:
    """Recompute the whole chain; report the first tampered/broken link."""
    events = db.query(models.AuditEvent).order_by(models.AuditEvent.seq.asc()).all()
    prev = GENESIS
    for e in events:
        fields = {
            "seq": e.seq, "ts": e.ts, "agent_id": e.agent_id, "owner_id": e.owner_id,
            "grant_id": e.grant_id, "action": e.action, "context": e.context,
            "decision": e.decision, "reason": e.reason, "prev_hash": e.prev_hash,
        }
        if e.prev_hash != prev:
            return {"valid": False, "broken_at_seq": e.seq, "reason": "chain link mismatch (an event was inserted/removed/reordered)"}
        if compute_hash(_payload(fields)) != e.hash:
            return {"valid": False, "broken_at_seq": e.seq, "reason": "hash mismatch — this record was altered after the fact"}
        prev = e.hash
    return {"valid": True, "events": len(events), "head_hash": prev}
