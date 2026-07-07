# Interview Q&A — Agent Identity Governance

> The questions an IAM engineer or recruiter is likely to ask, with answers in
> plain language you can say out loud. Skim before an interview.

---

## A. The concept

**Q: What is this project in one sentence?**
A governance control plane for AI agents — it gives each agent its own identity,
grants it scoped and time-boxed permissions, brokers every action (allow / step
up to a human / deny), scores its risk, keeps a tamper-evident audit trail, and
can kill it instantly — all tied back to an accountable human.

**Q: What problem does it solve?**
AI agents act in the cloud under a human's credentials, so accountability is
ambiguous when something goes wrong. Human identity is solved; **non-human
identity (NHI)** — service accounts, API keys, AI agents — is not. This makes an
agent a first-class, governed identity.

**Q: Why does this matter now?**
Agents are being given real authority (approve, pay, query, deploy). "Who is
accountable when an autonomous agent acts?" is an open enterprise problem, and
non-human identity governance is an active security category.

## B. Design decisions (they'll dig here)

**Q: Why a *layer* and not a new IAM platform?**
Enterprises already run Okta/Entra/AWS IAM; nobody rips those out. The valuable,
unsolved piece is agent-specific governance *on top of* existing IAM. Building
"a better Okta" would be naive; building the missing control plane is the point.

**Q: Why JWTs for the capability tokens?**
They're tamper-evident (signed), self-describing (the scope, limits, expiry, and
owner are *in* the token — no DB lookup to read them), and industry-standard.
Editing one character breaks the signature. The token also carries `owner_id`, so
attribution travels with the access.

**Q: What's a "capability token"?**
A token that *is* the permission: it names exactly what the holder may do
(scope), under what limits (constraints), until when (expiry). Contrast with a
role the system looks up separately — here the grant is self-contained.

**Q: Why "just-in-time" access?**
Standing permissions are the biggest attack surface in IAM. JIT means the token
auto-expires, so there's no long-lived privilege to steal or forget — a
least-privilege best practice.

**Q: How is this different from RBAC?**
RBAC assigns coarse roles. My broker also evaluates **context/attributes** — the
invoice amount, the target resource, the agent's live risk — which is
attribute/policy-based access control (ABAC/PBAC). RBAC alone can't express
"approve invoices ≤ $5k unless the agent is high-risk."

**Q: Why a hash chain for the audit log?**
Accountability is only real if it's *provable*. Each entry hashes its own
contents plus the previous entry's hash, so altering any past record breaks every
hash after it. Even someone with direct DB access can't silently rewrite history
— and `/audit/verify` proves it.

**Q: What is "step-up"?**
When an action is within scope but crosses a limit, instead of a flat deny the
system escalates to a human approval — step-up authentication. It records *who*
approved, which is the accountability artifact.

**Q: What does the risk score add?**
Adaptive / risk-based access control. Static permissions can't react to behavior;
the score rises on denials and, past a threshold, automatically forces human
approval even for normally-allowed actions. The system tightens around a
misbehaving agent on its own.

## C. IAM depth (senior-level)

**Q: What's SPIFFE and why did you use its ID format?**
SPIFFE is the standard for giving *workloads* a verifiable identity
(`spiffe://…`). Agents are workloads, so I issue SPIFFE-style IDs. In production
you'd use **SPIRE** to cryptographically attest that identity, not just mint a
string.

**Q: Where would OPA fit?**
My `policy.decide()` is a clean seam. In production the rules move to **OPA
(Open Policy Agent)** with **Rego** policies — the industry-standard external
authorization engine — without changing identity, tokens, or audit.

**Q: How does this relate to OAuth 2.0?**
OAuth is about *delegated* access — an app acting on your behalf via a scoped
token, not your password. An AI agent acting for a human is literally that
delegation problem. My grants + introspection mirror OAuth's token + introspect
pattern.

**Q: How is this different from Okta / an IdP?**
An IdP authenticates *who you are*. This governs *what an agent may do*, brokers
each action, and produces the attribution + audit an IdP doesn't. It federates
with an IdP; it doesn't replace it.

## D. Security & scale (be honest about scope)

**Q: What are the weaknesses of the current build?**
It's a portfolio scope with deliberate edges: HS256 shared-secret signing
(should be RS256/asymmetric or per-tenant keys), the control-plane endpoints
aren't themselves authenticated, policy is in-code rather than OPA, and the audit
chain isn't externally notarized. I can name each because they were *chosen*, not
missed.

**Q: How would you harden it for production?**
Asymmetric/rotating token keys; authn/z + rate limiting on the control plane;
OPA/Rego for policy; Keycloak/OIDC for owner auth; SPIRE for attested identity;
append-only DB constraints + periodic external notarization of the audit head;
per-tenant isolation.

**Q: How does it scale?**
Stateless serverless control plane (scales horizontally); all state in Postgres.
The audit hash chain is sequential — at high volume you'd shard chains per
tenant/agent or batch-anchor them. Token validation is local (no DB round-trip)
because JWTs are self-verifying.

**Q: What did you learn building it?**
The IAM vocabulary end-to-end — OAuth delegation, JIT, capability tokens,
introspection, RBAC vs ABAC/PBAC, SPIFFE, step-up, tamper-evidence, adaptive
risk — by implementing each, not reading about it. And the discipline of choosing
where to stop and naming the trade-offs.

## E. Quick-fire

- **Stack?** FastAPI, SQLAlchemy, Postgres (Neon) / SQLite, PyJWT, Vercel, GitHub.
- **Lines of the story?** identity → scoped JIT token → broker (allow/step-up/
  deny) → human approval → hash-chained audit → risk → kill switch.
- **Live link?** https://agent-identity-governance.vercel.app
