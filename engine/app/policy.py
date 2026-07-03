"""Policy engine: given a *validated* token's claims + a requested action,
return a decision.

Three outcomes:
  ALLOW   - action is within the granted scope and within limits
  STEP_UP - within scope but over a limit -> a human must approve
  DENY    - outside the granted scope (or missing required info)

Kept as plain, readable Python on purpose. In a production IAM stack these rules
would live in OPA/Rego (Open Policy Agent); `decide()` is exactly the seam where
you'd call out to OPA instead. Same inputs, same outputs.
"""
from dataclasses import dataclass

ALLOW = "ALLOW"
DENY = "DENY"
STEP_UP = "STEP_UP"


@dataclass
class Decision:
    decision: str
    reason: str


def decide(claims: dict, action: str, context: dict) -> Decision:
    granted_scope = claims.get("scope")
    constraints = claims.get("constraints", {})

    # 1) The action must fall within the scope the agent was actually granted.
    #    (An invoice-approver trying to write to a DB fails here -> DENY.)
    if action != granted_scope:
        return Decision(DENY, f"action '{action}' is outside granted scope '{granted_scope}'")

    # 2) Scope-specific limit checks.
    if action == "invoice:approve":
        amount = context.get("amount")
        limit = constraints.get("max_amount")
        if amount is None or limit is None:
            return Decision(DENY, "missing 'amount' in request or 'max_amount' in grant")
        if amount <= limit:
            return Decision(ALLOW, f"amount {amount} is within limit {limit}")
        return Decision(STEP_UP, f"amount {amount} exceeds limit {limit} — human approval required")

    # 3) Default: within scope and no extra limits configured.
    return Decision(ALLOW, f"within granted scope '{granted_scope}'")
