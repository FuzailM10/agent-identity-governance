"""Risk scoring for agents.

Each agent carries a live score (0..MAX_RISK). Risky outcomes push it up; good
behavior slowly cools it down. When the score crosses HIGH_RISK_THRESHOLD, the
policy engine tightens up automatically (see policy.decide) — this is
"risk-based" / adaptive access control.
"""
HIGH_RISK_THRESHOLD = 70
MAX_RISK = 100

# How much each brokered decision moves an agent's score.
DELTAS = {
    "ALLOW": -5,     # good behavior slowly cools the score
    "STEP_UP": 15,   # needed a human -> mildly risky
    "DENY": 35,      # blocked attempt -> strongly risky
}


def next_score(current: int, decision: str) -> int:
    delta = DELTAS.get(decision, 0)
    return max(0, min(MAX_RISK, current + delta))
