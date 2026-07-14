# KRISIS v1.1 — Full evaluation coverage

Smart ticket triage: a raw ticket message in → a structured routing decision out
(`category`, `priority`, `assigned_team`, `reasoning`).

v1.1 builds on v1 and hardens it to be fully evaluable and demo-safe: a three-layer
reliability strategy, edge-case handling, a consistency check, 21 demo tickets, and a
before/after timing comparison on the dashboard.

## Architecture (API-first)

```
Streamlit UI  ──HTTP──▶  FastAPI backend  ──▶ LangChain + OpenAI (structured outputs)
(client only)           (all business logic)  ──▶ PostgreSQL (logs every request)
```

The UI never talks to the LLM or the database directly — only to the API.
`priority` and `assigned_team` are **derived in code** (Impact × Urgency matrix + `TAXONOMY`),
not chosen by the model.

## Layout

```
v1.1/
├── app/
│   ├── config.py      # loads .env (walks up the tree); MAX_TICKET_CHARS, MANUAL_TRIAGE_SECONDS
│   ├── taxonomy.py    # categories→teams, Impact×Urgency matrix, overrides
│   ├── schema.py      # Pydantic: TicketDecision (LLM), ClassifyRequest, RoutedTicket
│   ├── prompt.py      # few-shot prompt (6 examples) + LangChain messages
│   ├── classifier.py  # LLM call + 3-layer retry/fallback; derive_priority()
│   ├── db.py          # SQLAlchemy model; init_db, log_ticket, list_tickets, stats, timing
│   └── api.py         # FastAPI: POST /classify, GET /tickets, /stats, /timing, /health
├── run.py             # single-command launcher (API + UI together)
├── streamlit_app.py   # UI client + dashboard (incl. Time-saved panel)
├── demo_tickets.py    # 21 labeled demo tickets
├── scripts/           # run_demo.py, consistency_check.py, edge_cases.py, interactive.py
├── .env.example       # template for the shared root .env
└── requirements.txt
```

`.venv`, `.env`, and the Postgres `krisis` database are shared at the **project root**
(`../`), not per-version.

## Reliability — three layers (`app/classifier.py`)

1. **Structured output enforcement** — `with_structured_output(TicketDecision)` constrains the model to a fixed schema.
2. **Retry with feedback** — on a parse/validation/API error, retry (up to 2×), feeding the error back so the model can self-correct, with a short backoff.
3. **Safe fallback** — if all attempts fail, return a valid `unclassified` / `Medium` / `Triage` response flagged for review. `classify()` never raises; the API never crashes.

Every request is logged either way (`ok=True/False`, `attempts`, `error`, tokens, latency).

## Edge-case handling

| Input | Behavior |
|---|---|
| Empty / whitespace | `POST /classify` → **422** (no LLM call) |
| Very long | Truncated to `MAX_TICKET_CHARS` (default 8000) before the call — no crash, no runaway tokens |
| Non-English | Classified normally (prompt states tickets may be any language) |
| LLM / API failure | Retries, then the safe fallback (never a stack trace) |

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/classify` | Route a raw ticket → `{category, priority, assigned_team, reasoning, impact, urgency}` |
| GET | `/tickets?limit=N` | Recent logged tickets from Postgres |
| GET | `/stats` | Totals, category/priority breakdowns, avg latency, token totals, failures |
| GET | `/timing` | Before/after: assumed manual triage time vs actual automated latency |
| GET | `/health` | Liveness check |

---

## Prerequisites (one-time)

- Deps installed into the shared venv:
  ```bash
  cd ~/Projects/krisis/krisis
  .venv/bin/pip install -r v1.1/requirements.txt
  ```
- PostgreSQL running and a `krisis` database:
  ```bash
  brew services start postgresql@16
  createdb krisis   # only if it doesn't exist yet
  ```
- The shared root `.env` (copy the template):
  ```bash
  cp v1.1/.env.example .env   # then edit OPENAI_API_KEY
  ```

## Run — single command (recommended)

```bash
cd ~/Projects/krisis/krisis/v1.1
../.venv/bin/python run.py
```
Starts the API (`:8000`) and the Streamlit UI (`:8501`) together; **Ctrl-C stops both**.
Override ports with env vars: `API_PORT=8010 UI_PORT=8511 ../.venv/bin/python run.py`.

Interactive API docs: <http://localhost:8000/docs>. UI: <http://localhost:8501>.

<details><summary>Alternative: two terminals</summary>

```bash
# Terminal 1 — API
cd ~/Projects/krisis/krisis/v1.1 && ../.venv/bin/uvicorn app.api:app --reload
# Terminal 2 — UI
cd ~/Projects/krisis/krisis/v1.1 && ../.venv/bin/streamlit run streamlit_app.py
```
</details>

## Evaluation scripts (run from `v1.1/`)

```bash
../.venv/bin/python scripts/run_demo.py           # classify all 21 demo tickets, log to DB, print table
../.venv/bin/python scripts/consistency_check.py  # same input x3 -> identical output (PASS/FAIL)
../.venv/bin/python scripts/edge_cases.py         # empty / long / non-English / simulated failure
../.venv/bin/python scripts/interactive.py        # type a ticket, see the full result (no DB writes)
```

`run_demo.py` populates the DB so the dashboard's **Time saved** panel shows the before/after
comparison (manual @ 5 min/ticket vs actual latency).

## Eval mapping (`eval.txt`)

| Rubric line | Where it's covered |
|---|---|
| Valid JSON on 10+ inputs; all fields present | Structured output + `run_demo.py` (21 tickets) |
| Consistent (same input → same output) | `temperature=0` + code-derived priority/team; `consistency_check.py` |
| Edge cases: empty / long / non-English | `edge_cases.py`, input guards |
| API failure handled without crashing | 3-layer retry → safe fallback; `edge_cases.py` |
| Angry / vague / ambiguous handled | Few-shot examples 1–3; demo tickets 7–9 |
| Priority defensible | Impact × Urgency matrix + visible `impact`/`urgency` |
| No hardcoded secrets | `.env` (git-ignored) + `.env.example` |
| Before/after timing shown | `/timing` + dashboard "Time saved" panel |
| README to run it | this file |

## Troubleshooting

| Symptom | Fix |
|---|---|
| DB `connection refused` / `/stats` returns 503 | `brew services start postgresql@16` |
| Classifications come back as `unclassified` fallbacks | Check `.env` has a valid `OPENAI_API_KEY=sk-...` (repeated LLM failure → fallback) |
| UI: "Could not reach the API" | Ensure the uvicorn terminal is still running on :8000 |
| `ModuleNotFoundError: app` | Launch uvicorn/streamlit from **inside `v1.1/`** |
| Port already in use | `uvicorn ... --port 8001`; then `API_BASE=http://localhost:8001 ../.venv/bin/streamlit run streamlit_app.py` |
