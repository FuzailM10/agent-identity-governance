# Using It — Demo & Walkthrough

> How to run the demo and walk through both surfaces: the **dashboard** (the web
> UI) and the **API docs** (the developer view).

- **Live:** https://agent-identity-governance.vercel.app
- **API docs (Swagger):** https://agent-identity-governance.vercel.app/docs

---

## 1. What it's for (30-second version)

An AI agent gets its own identity, is granted **scoped, time-boxed** permission,
and every action it takes is **brokered** (allowed / stepped-up to a human /
denied), **risk-scored**, and written to a **tamper-evident** log — all tracing
back to an accountable human. A **kill switch** cuts it off instantly.

## 2. The example story (the demo narrative)

You spin up an "invoice approver" agent with just-in-time access to *approve
invoices ≤ $5,000*, then watch the control plane react:

| The agent tries… | The system says | Why it matters |
|---|---|---|
| Approve a **$4,000** invoice | 🟢 **ALLOW** | within its granted limit |
| Approve a **$50,000** invoice | 🟡 **STEP-UP** | over limit → a human must approve |
| Write to the **prod database** | 🔴 **DENY** | outside its scope entirely; risk score spikes |
| *(after repeated denials)* the same $4k invoice | 🟡 **STEP-UP** | agent is now high-risk → auto-tightened |
| — hit the **KILL SWITCH** — | ☠️ revoked | its next action dies instantly |
| Open the **audit trail** | ✅ verifiable | proves who authorized what, un-tamperable |

That's the whole thesis in ~90 seconds.

---

## 3. Walkthrough A — the Dashboard (the web page)

Open **https://agent-identity-governance.vercel.app** (works on desktop and
phone).

1. **"Register agent + issue JIT access"** — creates a human owner, an AI agent,
   and a scoped token (*approve invoices ≤ $5,000*). The right panel now shows
   the agent, status `active`, and risk `0`.
2. **"Approve $4,000 invoice"** → a green **ALLOW** appears in *Live decisions*.
3. **"Approve $50,000 invoice"** → a yellow **STEP_UP** (over the limit).
4. **"Write to prod database"** → a red **DENY**, and watch the **risk meter
   climb**. Click it a few times — once risk crosses 70, the meter turns to a
   warning.
5. **"Approve $4,000 invoice"** again → now it's **STEP_UP**, not ALLOW — the
   agent got risky, so the system tightened automatically.
6. **🔴 KILL SWITCH** → the agent's status flips to `killed`. Click any action
   again → **DENY ("grant was revoked")**. Dead on arrival.
7. **"Verify chain integrity"** → confirms the audit trail hasn't been tampered
   with (✅ intact).

> Talking point while demoing: *"Notice every decision shows the agent and its
> owner — accountability is on every single action, not bolted on afterward."*

## 4. Walkthrough B — the API docs (`/docs`, Swagger UI)

Open **/docs**. This is the auto-generated, interactive API. Each row is one
**endpoint**; the colored verb is the action type.

**GET vs POST (the two you'll use):**
- **GET** = *read / fetch* existing data (no body). e.g. "list agents".
- **POST** = *create / send* new data (you provide a JSON body). e.g. "register
  an agent".

To run any endpoint: click it → **"Try it out"** → fill the body → **Execute** →
read the **Response body**.

### Run the full demo through the API (order matters)

1. **`POST /owners`** — body `{"name":"Fuzail","email":"me@example.com"}` →
   copy the returned `id`.
2. **`POST /agents`** — body
   `{"name":"invoice-bot","purpose":"approve invoices","owner_id":"<owner id>"}`
   → returns the agent + its `spiffe_id` (identity issued). Copy the agent `id`.
3. **`POST /agents/{agent_id}/grants`** — body
   `{"scope":"invoice:approve","constraints":{"max_amount":5000},"ttl_seconds":3600}`
   → returns a **token**. Copy it.
4. **`POST /broker`** — this is the core. Try each:
   - `{"token":"<token>","action":"invoice:approve","context":{"amount":4000}}` → **ALLOW**
   - `{"token":"<token>","action":"invoice:approve","context":{"amount":50000}}` → **STEP_UP** (returns an `approval_id`)
   - `{"token":"<token>","action":"db:write","context":{"target":"prod-db"}}` → **DENY**
5. **`POST /approvals/{approval_id}/resolve`** — body
   `{"approve":true,"decided_by":"Fuzail (owner)"}` → a human approves the $50k
   exception; records who decided.
6. **`GET /agents/{agent_id}`** — see the agent's **risk_score** climb.
7. **`POST /agents/{agent_id}/kill`** — the kill switch. Re-run a `/broker` call
   → now **DENY ("grant was revoked")**.
8. **`GET /audit`** — the full hash-chained trail.
   **`GET /audit/verify`** — `valid: true`. (Tampering flips it to `false` with
   the exact broken entry.)

### Endpoint cheat-sheet
| Endpoint | Verb | Does |
|---|---|---|
| `/health` | GET | liveness + DB check |
| `/owners` | POST/GET | create / list humans |
| `/agents` | POST/GET | register / list agents |
| `/agents/{id}/attribution` | GET | who's behind this agent |
| `/agents/{id}/grants` | POST/GET | issue / list capability tokens |
| `/tokens/introspect` | POST | validate a token |
| `/broker` | POST | **allow / step-up / deny** an action |
| `/approvals` · `/approvals/{id}/resolve` | GET · POST | human approvals |
| `/agents/{id}/kill` | POST | **kill switch** |
| `/audit` · `/audit/verify` | GET | trail + integrity check |

---

## 5. Running it locally (optional)

```bash
cd engine
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
DATABASE_URL="sqlite:///./aig_dev.db" .venv/bin/python -m uvicorn app.main:app --port 8000
# dashboard  -> http://127.0.0.1:8000/
# API docs   -> http://127.0.0.1:8000/docs
```

The only difference between local and cloud is the `DATABASE_URL` (SQLite vs
Neon Postgres). Same code.
