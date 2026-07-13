# KRISIS: Your Smart Triage System
## Project Plan and Version Roadmap

## 1. Overview

KRISIS is a smart triage system built for the internal IT and engineering support desk of an AI-first software engineering and technology services company. Employees submit tickets covering access requests, infrastructure issues, CI/CD failures, security concerns, developer tooling problems, and hardware issues.

Today, a human has to read every ticket and manually decide its category, urgency, and owning team before any actual work can begin. This first sorting step is repetitive, slow, and inconsistent between people. KRISIS automates it. Given a raw ticket message, it returns a structured decision: category, priority, assigned team, and a one line reasoning, so the ticket is already sorted by the time a human looks at it.

## 2. Ticket Format

**Input:** a single raw text message, exactly as an employee would type it into a support form. No other fields are required for the core system.

**Output (JSON):**

```
{
  "category": string,
  "priority": "High" | "Medium" | "Low",
  "assigned_team": string,
  "reasoning": string
}
```

## 3. Domain Taxonomy

| Category | Description | Assigned team |
|---|---|---|
| access_iam | Login, permissions, SSO, credential issues | Identity and access |
| infra_outage | Server, network, or cloud infrastructure failures | Infrastructure operations |
| ci_cd | Build and deployment pipeline failures | Platform engineering |
| security | Vulnerabilities, suspicious activity, security incidents | Security team |
| dev_tooling | IDE, internal tools, environment setup issues | Developer experience |
| hardware | Laptop, peripheral, or device issues | Hardware support |
| unclassified | Ticket lacks enough detail to classify confidently | Triage |

## 4. Priority Definition

Priority is **computed, not guessed**, following the standard IT service-management model **Priority = Impact × Urgency**. It is based on impact and whether the person is blocked, never on tone or wording — this keeps an angry ticket from being scored as more urgent than a calm one describing the same problem. The model assesses the two axes; priority is then derived deterministically in code.

**Impact** — `broad`: multiple people, a whole team, a shared/customer-facing service, or core infra (auth, network, CI that blocks all merges). `narrow`: a single person or a small, non-critical scope.

**Urgency** — `blocked`: cannot do core work and no usable workaround (or an imminent, externally-imposed deadline with no workaround). `workaround`: work can continue — a workaround exists, or the issue is non-blocking / cosmetic / a request or question. (A deadline is folded into urgency rather than being a separate trigger.)

**Matrix:**

| | blocked | workaround |
|---|---|---|
| **broad** | High | Medium |
| **narrow** | Medium | Low |

**Overrides (applied after the matrix):** a `security` incident is **High** regardless of scope; an `unclassified` ticket defaults to **Medium**, flagged for review.

This is collision-free (every impact × urgency maps to exactly one tier), free of subjective triggers, and defensible — the full impact → urgency → matrix → priority chain can be shown for any ticket.

## 5. Prompt and Reliability Approach

**Prompting:** few-shot, with worked examples covering the three required edge cases: an angry tone, a very short or vague message, and a ticket that could fit more than one category. Every example's reasoning field states which rule drove the decision, not just the outcome, so the logic is checkable.

**Reliability, three layers:**

1. Structured output enforcement is the primary defense against malformed JSON. The model is constrained to a fixed schema at generation time.
2. If validation still fails, the system retries once or twice, feeding the exact validation error back to the model.
3. If retries are exhausted, a safe fallback response is returned (unclassified, medium priority, triage team, flagged for manual review) instead of an error or a crash.

Every request is logged regardless of outcome.

## 6. Technical Stack

| Component | Choice |
|---|---|
| Language | Python |
| API / Backend | FastAPI (REST endpoints, auto-generated OpenAPI docs at `/docs`) |
| Orchestration | LangChain |
| LLM | OpenAI (structured outputs) |
| Frontend / UI | Streamlit (thin client that calls the FastAPI backend over HTTP) |
| Schema and validation | Pydantic (shared as both the LLM output schema and the API request/response models) |
| Storage | PostgreSQL |
| Logging | Python logging module for system events, PostgreSQL table for ticket history |

**Architecture (API-first):** All core logic lives behind the FastAPI backend; the Streamlit UI never talks to the LLM or the database directly, only to the API over HTTP. This keeps business logic reusable (any client can call it), testable (endpoints can be exercised with `curl`/pytest, independent of the UI), and cleanly separated from presentation.

| Endpoint | Purpose |
|---|---|
| `POST /classify` | Takes a raw ticket message, returns the structured `{category, priority, assigned_team, reasoning}` decision |
| `GET /tickets` | Returns ticket history from PostgreSQL |
| `GET /stats` | Returns aggregated metrics for the dashboard (volumes, priority mix, before/after timing) |

## 7. Version Roadmap

**Guiding principle:** Version 1.1 is the point at which the project is fully working and fully evaluable. Everything built after that is enhancement, not requirement. If a later version is left unfinished, the core deliverable is still complete and demo ready.

| Day | Version | Focus | Contents |
|---|---|---|---|
| 1 | v0 | Foundation | Domain story finalized, ticket format and JSON schema defined, category and team taxonomy defined, priority rules defined, few-shot prompt drafted with the three required edge cases, one raw API call made by hand to confirm the mechanism works end to end |
| 2 | v1 | Core pipeline, API, and dashboard | LangChain and the LLM wired together with structured output enforcement, few-shot prompt live against the finalized taxonomy, exposed through the FastAPI backend (`POST /classify` first, then `GET /tickets` and `GET /stats`), Streamlit form and result view built as a client that consumes those endpoints, first version of the dashboard, PostgreSQL logging of every request. Covers roughly half of the evaluation criteria |
| 3 | v1.1 | Full evaluation coverage | Complete three-layer retry strategy, all three required edge cases tested and passing, empty input, long input, and non-English input handled without crashing, LLM/API failure handled without crashing and surfaced as a clean error response from the endpoints, consistency check demonstrated, secrets moved out of code, 20 demo tickets assembled, before and after timing comparison completed and shown on the dashboard, README written. This version alone can be demoed with no risk |
| 4 | v1.2 | Retrieval + web UI + auth | Retrieval layer (past resolved tickets embedded + similarity search, shown as a reference panel alongside the classification, not replacing it); a proper **web UI**; and **user login + role-based access control (RBAC)**. Web-UI framework, auth mechanism, and the exact roles are decided at build time. The classification core stays frozen at v1.1 — this layers around it |
| 5 | v1.3 | Production ready | Everything in v1.2, hardened for production: deployment/packaging, config & secrets management, migrations, security hardening, observability/logging, and tests. Specific scope decided at build time |
| 6 to 7 | v1.4 onward | Enhancement backlog | Built in priority order if time allows: confidence aware routing (low confidence tickets flagged for human review instead of auto routed), cost and usage tracking per ticket shown on the dashboard, incident clustering (multiple similar tickets in a short window flagged as one probable incident). Kept as designed next steps: automatically drafted reply suggestions, a feedback loop for correcting misclassified tickets |

## 8. Summary

The project is structured so that a fully working, fully compliant system exists by the end of day 3. Everything from day 4 onward adds capability on top of a system that already satisfies every requirement. Any enhancement not finished by the end of the week becomes a documented next step for the demo, not a gap in the deliverable.
