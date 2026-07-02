# Agent Identity Governance

A governance **control plane** for AI agents — so an enterprise can audit, grant,
revoke, authorize, and monitor AI agents the same way it does human employees.

## The problem

AI agents act in cloud environments under a *human's* name. When something goes
wrong, accountability is ambiguous — was it the user, or the CEO who owns the
account? Agents make real decisions, so treating them as unaccountable "puppets"
is wrong. This project gives every agent a governed identity and a
tamper-evident trail of **who authorized what**.

## Architecture

This is a **layer**, not a new IAM platform — it sits on top of existing IAM.

```
  Dashboard (Next.js, on Vercel)        <- the "face": see + drive the system
        |  HTTPS
  Control Plane / Engine (FastAPI)      <- the real logic (this repo, /engine)
        |
  Postgres  (+ Keycloak, OPA later)     <- identity, audit, policy
```

- `engine/` — FastAPI control plane (identity, policy, risk, audit, kill switch)
- `dashboard/` — Next.js dashboard, mobile-responsive, deployed to Vercel *(coming)*

## Run locally

Requires Docker.

```bash
cp .env.example .env      # then edit .env
docker compose up --build
```

Then open http://localhost:8000/health — you should see
`{"status":"ok","db":"connected"}`, and the interactive API docs at
http://localhost:8000/docs.

## Roadmap

- [x] **Phase 0** — Skeleton: FastAPI + Postgres run via `docker compose`.
- [ ] **Phase 1** — Identity: register an agent + assign a human owner.
- [ ] **Phase 2** — JIT access: scoped, time-boxed capability tokens.
- [ ] **Phase 3** — Policy engine (OPA): allow / deny / step-up.
- [ ] **Phase 4** — Tamper-evident audit trail (agent → grant → owner → action).
- [ ] **Phase 5** — Risk score that feeds the policy engine.
- [ ] **Phase 6** — Kill switch: instant revoke, next action blocked live.
- [ ] **Phase 7** — Dashboard on Vercel.
- [ ] **Phase 8** — Swap built-in identity for real Keycloak (OIDC).
