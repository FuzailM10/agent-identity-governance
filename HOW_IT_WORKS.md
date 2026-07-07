# How It Works — Agent Identity Governance

> A governance **control plane** for AI agents: so an enterprise can register,
> authorize, audit, and revoke AI agents the same way it manages human employees.

- **Live demo:** https://agent-identity-governance.vercel.app
- **Repo:** https://github.com/FuzailM10/agent-identity-governance

This document explains, in plain English, **what** each part does and **why** it
was built that way. Read it top-to-bottom and you'll be able to explain the
whole system to an IAM engineer.

---

## 1. The problem

AI agents increasingly act inside cloud environments — approving transactions,
querying databases, calling APIs. But they act **under a human's credentials**.
When something goes wrong, accountability is ambiguous: was it the employee who
ran the agent, or the executive whose account it borrowed?

Human identity is a *solved* problem (SSO, directories, MFA). **Non-human
identity (NHI)** — service accounts, API keys, and now AI agents — is not. Agents
make real decisions, so treating them as unaccountable "puppets" is wrong.

**Thesis:** an AI agent should have its *own* governed identity, act only within
*explicitly granted*, *time-boxed* permissions, and leave a *tamper-evident*
trail that always points back to an accountable human.

## 2. A layer, not a new IAM platform

Enterprises already run Okta, Entra ID, Ping, AWS IAM. Nobody replaces those.
This project is a **governance layer (control plane)** that sits *on top of*
existing IAM and adds the agent-specific controls they lack. It brokers what
agents are allowed to do; it does not try to be the identity provider itself.

## 3. Architecture

```
   Dashboard (web UI)  ─────────────┐         the "face": see & drive the system
                                    │  HTTPS / JSON
   Control Plane  (FastAPI) ────────┤         the real logic (this repo)
     identity · tokens · policy     │
     audit · risk · kill switch     │
                                    │
   Postgres (Neon in the cloud) ────┘         identity + tamper-evident audit
```

Provider-agnostic core + a clean interface means new environments (AWS, Azure,
Keycloak) plug in as adapters without touching the core.

## 4. The building blocks

Each subsystem below maps to a file in `engine/app/` and a set of API endpoints.

### 4.1 Identity — every agent is bound to a human
*(`models.py`, endpoints `/owners`, `/agents`, `/agents/{id}/attribution`)*

- An **Owner** is a human, accountable for one or more agents.
- An **Agent** is a non-human identity, permanently linked to an Owner. It can't
  exist without one (the API rejects an "orphan" agent).
- On registration each agent is issued a **SPIFFE-style ID**
  (`spiffe://aig/agent/<uuid>`). SPIFFE is the industry standard for giving
  *workloads* a verifiable identity — exactly the NHI problem.
- **Why:** accountability starts at creation. `/attribution` answers the core
  question — *"which human is behind this agent?"* — in one call.

### 4.2 Capability tokens — scoped, just-in-time access
*(`tokens.py`, endpoints `/agents/{id}/grants`, `/tokens/introspect`)*

- A **grant** gives an agent a specific **scope** (e.g. `invoice:approve`), under
  **constraints** (e.g. `max_amount: 5000`), for a limited **TTL**.
- The grant is issued as a signed **JWT capability token**. The token carries its
  own claims — scope, constraints, expiry, and crucially the `owner_id`, so
  **attribution travels *inside* the access itself**.
- **Just-in-time (JIT):** the token auto-expires. No standing privilege is left
  lying around — a least-privilege best practice.
- **Introspection** (`/tokens/introspect`) validates a token: signature → expiry
  → revocation. This is the same pattern OAuth uses.
- **Why JWT:** tamper-evident (signature), self-describing (no DB lookup to read
  the claims), and industry-standard. Editing one character invalidates it.

### 4.3 Policy broker — allow / step-up / deny
*(`policy.py`, endpoint `/broker`)*

Every action an agent attempts is **brokered** first. The engine returns one of:
- **ALLOW** — within the granted scope and limits.
- **STEP_UP** — within scope but over a limit → a human must approve.
- **DENY** — outside the granted scope (or invalid/expired/revoked token).

- **Why a broker:** it's a single choke point. Nothing an agent does bypasses
  policy. `decide()` is deliberately a clean seam — in production these rules
  move to **OPA/Rego** (Open Policy Agent, the standard authorization engine)
  without changing the rest of the system.
- This is finer-grained than **RBAC** alone: RBAC gives coarse roles; here
  decisions also depend on **attributes/context** (amount, resource) — i.e.
  attribute/policy-based access control (ABAC/PBAC).

### 4.4 Human approval — step-up authentication
*(`models.py` `Approval`, endpoint `/approvals/{id}/resolve`)*

When policy returns STEP_UP, a **pending approval** is created. A human owner
resolves it (approve/deny), and the system records **who** decided. That record
is the accountability artifact for "a human authorized this exception."

### 4.5 Tamper-evident audit trail — a hash chain
*(`audit.py`, endpoints `/audit`, `/audit/verify`)*

- Every brokered decision (and the kill event) is written to an append-only log.
- Each entry stores a **SHA-256 hash of its own contents *plus* the previous
  entry's hash** — a hash chain, the same idea a blockchain uses.
- Alter any past record and its hash — and every hash after it — no longer
  matches. `/audit/verify` recomputes the chain and reports the first break.
- **Why:** accountability is only real if it's *provable*. Even someone with
  direct database access can't silently rewrite what an agent was authorized to
  do. (Demonstrated: editing a past DENY→ALLOW in the DB is detected instantly.)

### 4.6 Risk scoring — adaptive access control
*(`risk.py`)*

- Each agent has a live **risk score** (0–100). Denied attempts push it up
  (+35), step-ups +15, good behavior cools it down (−5).
- Once the score crosses a **threshold (70)**, the policy engine automatically
  gets stricter: actions that would normally be ALLOW now require human approval.
- **Why:** static permissions can't react to behavior. This is **risk-based /
  adaptive** access control — the system tightens itself around a misbehaving
  agent without anyone intervening.

### 4.7 Kill switch — instant revocation
*(endpoint `/agents/{id}/kill`)*

- One call flips the agent to `killed` **and revokes all its grants**.
- Because the broker checks revocation on every action, the agent's **very next
  call is denied** — even with a token that hasn't expired yet.
- **Why:** incident response needs an instant, provable cutoff. The kill is
  itself written to the audit trail.

## 5. Tech stack & why

| Layer | Choice | Why |
|---|---|---|
| API / control plane | **FastAPI** (Python) | fast to build, auto-generated API docs, common in backend/security roles |
| Data | **SQLAlchemy** + **Postgres** (Neon in cloud, SQLite locally) | one-line DB swap; managed Postgres = zero-ops |
| Tokens | **PyJWT** (HS256) | industry-standard, tamper-evident |
| Policy | plain Python now; **OPA/Rego**-ready | readable + a clean path to the standard engine |
| Hosting | **Vercel** (serverless) + **GitHub** | free, auto-deploys on every push |

## 6. How it's deployed

- Code lives on GitHub; **Vercel** builds and hosts it as Python serverless
  functions and **auto-redeploys on every push to `main`**.
- The database is **Neon** (free, managed Postgres). The app reads its
  connection string from the `DATABASE_URL` environment variable — the same code
  runs on SQLite locally and Postgres in the cloud, unchanged.

## 7. What I'd harden for production (known, deliberate scope)

This is a portfolio build; the design leaves clear upgrade paths:
- Move policy rules to **OPA/Rego**; sign tokens with **RS256/asymmetric keys**
  or per-tenant keys instead of a shared HS256 secret.
- Replace built-in owner login with **Keycloak / real OIDC**.
- Use **SPIFFE/SPIRE** for cryptographically attested workload identity.
- Anchor the audit chain externally (periodic notarization) and add DB-level
  append-only constraints.
- Add authn/z on the control-plane endpoints themselves, rate limiting, and
  key rotation.

Naming these *unprompted* is intentional: it shows the boundaries were chosen,
not missed.
