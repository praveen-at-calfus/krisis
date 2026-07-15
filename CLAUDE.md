# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

KRISIS is a smart IT/engineering **ticket triage** system: a raw ticket message in → a structured routing decision out (`category`, `priority`, `assigned_team`, `reasoning`). `KRISIS_project_plan.md` is the roadmap; `eval.txt` is the grading rubric the project is built against.

## Repository layout — one folder per version

Each roadmap version lives in its **own folder**, so versions don't clobber each other:
- `v0/v0.ipynb` — foundation notebook (self-contained; proves the mechanism).
- `v1/` — first runnable app (frozen snapshot).
- `v1.1/` — **the current working version**. Do new work here (or in the next version's folder), not in v0/v1.

**Shared at the repo root, not per-version:** the `.venv/`, the `.env`, and the Postgres `krisis` database. `app/config.py` locates `.env` by walking **up** the tree, so code works from any version-folder depth — never hardcode the `.env` path.

When starting a new roadmap version, copy the latest version folder into `<version>/` and build there.

## Conventions (enforced)

- **Absolute imports only.** Always `from app.config import X` / `from app import classifier, db` — never relative (`from .config`). This resolves because uvicorn/Streamlit run from inside the version folder and scripts prepend it to `sys.path`.
- **Run everything from inside the version folder** (e.g. `cd v1.1`) so the `app` package resolves.
- **Target Python is 3.9** — use `typing.Optional[...]`, not `X | None` (union syntax breaks at runtime here).
- LLM calls use **OpenAI structured outputs via LangChain** (`ChatOpenAI(...).with_structured_output(TicketDecision)`) with **`temperature=0`** for run-to-run consistency. Default model `gpt-4o-mini` (env `MODEL`).

## Core architecture (v1.1)

API-first: the Streamlit UI is a thin **client** that only talks to the FastAPI backend over HTTP — it never touches the LLM or DB directly.

The defining design idea is **judgement vs. mapping**:
- The **LLM decides** only what needs judgement: `impact`, `urgency`, `category`, and `reasoning`. Field order in `TicketDecision` matters — assessment fields come before the decision so the model reasons before committing.
- **Code derives** the rest deterministically: `priority = PRIORITY_MATRIX[(impact, urgency)]` with overrides (`security`→High, `unclassified`→Medium), and `assigned_team = TAXONOMY[category]["team"]`. This makes priority/team consistent and impossible to mismatch. See `derive_priority()` in `app/classifier.py`.

**Reliability (3 layers) in `app/classifier.py`:** structured-output enforcement → retry (up to 2×, feeding the error back) → a safe `unclassified`/Medium/Triage fallback. `classify()` never raises; the API never crashes. Every request is logged to Postgres best-effort (a down DB never fails `/classify`).

Module responsibilities under `app/`: `taxonomy.py` (categories→teams, Impact×Urgency matrix, overrides — the single source of truth), `schema.py` (Pydantic: `TicketDecision` LLM output, `ClassifyRequest`, `RoutedTicket` response), `prompt.py` (system prompt + few-shot examples + disambiguation rules), `classifier.py` (LLM call + retries + derivation), `db.py` (SQLAlchemy `TicketLog` + `stats`/`timing`), `api.py` (FastAPI routes).

**Classification rules live in the prompt**, not code — notably the "brief-but-clear tickets must still be classified (not `unclassified`)" rule and the "failure wins" rule (an access/SSO/access-control *system being down* is `infra_outage`, while an individual's access problem is `access_iam`). Change classifier behavior by editing `prompt.py` (rules + few-shot) and/or `taxonomy.py`, then re-run the demo to check for regressions.

Endpoints: `POST /classify`, `GET /tickets`, `GET /stats`, `GET /timing` (before/after manual-vs-automated), `GET /health`.

## Common commands

Run from the repo root unless noted.

```bash
# One-time setup
.venv/bin/pip install -r v1.1/requirements.txt
brew services start postgresql@16 && createdb krisis          # Postgres (Homebrew)
cp v1.1/.env.example .env                                      # then set OPENAI_API_KEY

# Run the app — single command (starts API :8000 + Streamlit :8501; Ctrl-C stops both)
cd v1.1 && ../.venv/bin/python run.py
#   override ports: API_PORT=8010 UI_PORT=8511 ../.venv/bin/python run.py

# Run the two processes separately (alternative)
cd v1.1 && ../.venv/bin/uvicorn app.api:app --reload           # API + docs at /docs
cd v1.1 && ../.venv/bin/streamlit run streamlit_app.py         # UI
```

There is **no unit-test framework or linter configured**. Verification is done via runnable scripts (run from `v1.1/`):

```bash
../.venv/bin/python scripts/run_demo.py           # classify the 21 demo tickets, log to DB, print table + accuracy
../.venv/bin/python scripts/consistency_check.py  # same input x3 -> identical output (PASS/FAIL)
../.venv/bin/python scripts/edge_cases.py         # empty / long / non-English / simulated API failure
../.venv/bin/python scripts/interactive.py        # type a ticket, see the full result (no DB writes)
../.venv/bin/python -m app.classifier             # quick smoke: classify a few hardcoded tickets
```

After any classifier change, re-run `run_demo.py` (regression check) and `edge_cases.py`. Demo tickets live in `v1.1/demo_tickets.py` — add regression cases there.

## Notes

- Only the LLM-call scripts/endpoints make paid OpenAI calls; the offline modules (taxonomy/schema/prompt/derivation) can be exercised without network or key.
- Environment specifics: macOS, Python 3.9 (system) with the project venv at `.venv/`, Homebrew Postgres 16 (`/opt/homebrew/opt/postgresql@16/bin/`).
