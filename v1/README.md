# KRISIS v1 — Core pipeline, API, dashboard

Smart ticket triage: a raw ticket message in → a structured routing decision out
(`category`, `priority`, `assigned_team`, `reasoning`).

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
v1/
├── app/
│   ├── config.py      # loads .env (found by walking up the tree)
│   ├── taxonomy.py    # categories→teams, Impact×Urgency matrix, overrides
│   ├── schema.py      # Pydantic: TicketDecision (LLM), ClassifyRequest, RoutedTicket
│   ├── prompt.py      # few-shot prompt + LangChain messages
│   ├── classifier.py  # ChatOpenAI.with_structured_output(); derive_priority()
│   ├── db.py          # SQLAlchemy engine/model; init_db, log_ticket, list_tickets, stats
│   └── api.py         # FastAPI: POST /classify, GET /tickets, GET /stats, /health
├── streamlit_app.py   # UI client + dashboard
└── requirements.txt
```

`.venv`, `.env`, and the Postgres `krisis` database are shared at the **project root**
(`../`), not per-version.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/classify` | Route a raw ticket → `{category, priority, assigned_team, reasoning, impact, urgency}` |
| GET | `/tickets?limit=N` | Recent logged tickets from Postgres |
| GET | `/stats` | Totals, category/priority breakdowns, avg latency, failures |
| GET | `/health` | Liveness check |

---

## Prerequisites (one-time)

- Python venv at the project root with deps installed:
  ```bash
  cd ~/Projects/krisis/krisis
  .venv/bin/pip install -r v1/requirements.txt
  ```
- PostgreSQL running and a `krisis` database:
  ```bash
  brew services start postgresql@16
  createdb krisis   # only if it doesn't exist yet
  ```
- `.env` at the project root with:
  ```
  OPENAI_API_KEY=sk-...
  # optional (defaults shown):
  # DATABASE_URL=postgresql+psycopg://localhost:5432/krisis
  # MODEL=gpt-4o-mini
  ```

## Run & verify

Use two terminals. All commands assume the project at `~/Projects/krisis/krisis`.

### Step 0 — Preflight
```bash
cd ~/Projects/krisis/krisis
/opt/homebrew/opt/postgresql@16/bin/pg_isready     # expect: accepting connections
grep -o '^OPENAI_API_KEY=' .env                    # expect: OPENAI_API_KEY=
```

### Step 1 — Start the API (Terminal 1)
```bash
cd ~/Projects/krisis/krisis/v1
../.venv/bin/uvicorn app.api:app --reload
```
Success: `Uvicorn running on http://127.0.0.1:8000` and `Application startup complete.`

### Step 2 — Smoke-test the API (Terminal 2)
```bash
curl -s http://localhost:8000/health
curl -s -X POST http://localhost:8000/classify -H 'content-type: application/json' \
  -d '{"ticket":"The whole prod database is down and no one can log in."}'
```
Expect: health → `{"status":"ok"}`; classify → `infra_outage` / `High` / `Infrastructure operations`.

Edge cases (priority must ignore tone):
```bash
curl -s -X POST http://localhost:8000/classify -H 'content-type: application/json' -d '{"ticket":"THIS IS RIDICULOUS reset my password NOW!!!"}'
curl -s -X POST http://localhost:8000/classify -H 'content-type: application/json' -d '{"ticket":"it'\''s broken"}'
curl -s -X POST http://localhost:8000/classify -H 'content-type: application/json' -d '{"ticket":""}'
```
Expect: angry → `access_iam`/`Medium`; "it's broken" → `unclassified`/`Medium`; empty → HTTP `422`.

### Step 3 — Interactive docs
Open <http://localhost:8000/docs> → `POST /classify` → **Try it out** → **Execute**.

### Step 4 — Confirm persistence
```bash
curl -s http://localhost:8000/stats
curl -s "http://localhost:8000/tickets?limit=5"
/opt/homebrew/opt/postgresql@16/bin/psql krisis \
  -c "select id, category, priority, assigned_team, created_at from ticket_log order by id desc limit 5;"
```
The API results and the `psql` rows should match — proving API → LLM → DB.

### Step 5 — Start the UI (Terminal 2)
```bash
cd ~/Projects/krisis/krisis/v1
../.venv/bin/streamlit run streamlit_app.py
```
Opens <http://localhost:8501>.

### Step 6 — Verify the UI
- **Classify tab:** paste a ticket → **Route ticket** → see category / priority / team + reasoning + impact·urgency.
- **Dashboard tab:** **Refresh** → totals, charts, and a "Recent tickets" table including your submission.

### Step 7 — Stop
`Ctrl+C` in each terminal. To stop Postgres too: `brew services stop postgresql@16`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| DB `connection refused` / `/stats` returns 503 | `brew services start postgresql@16` |
| `/classify` 502 "classification failed" | Check `.env` has a valid `OPENAI_API_KEY=sk-...` |
| UI: "Could not reach the API" | Ensure the uvicorn terminal is still running on :8000 |
| `ModuleNotFoundError: app` | Launch uvicorn/streamlit from **inside `v1/`** |
| Port already in use | `uvicorn ... --port 8001`; then `API_BASE=http://localhost:8001 ../.venv/bin/streamlit run streamlit_app.py` |
