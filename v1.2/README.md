# KRISIS v1.2 — + Retrieval layer

Smart ticket triage: a raw ticket message in → a structured routing decision out
(`category`, `priority`, `assigned_team`, `reasoning`).

Carries over everything from v1.1 (3-layer reliability, edge-case handling, consistency
check, 21 demo tickets, before/after timing) and adds **Stage 1 of v1.2: a retrieval
layer** — new tickets are matched (by embedding similarity) against a corpus of past
**resolved** tickets, shown as a reference panel alongside the classification. The
classification core is unchanged. (Remaining v1.2 stages — confidence-aware routing,
cost/usage tracking, incident clustering, reply suggestions, feedback loop,
production-ready — are not built yet.)

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
v1.2/
├── app/
│   ├── config.py      # loads .env (walks up); MAX_TICKET_CHARS, MANUAL_TRIAGE_SECONDS, EMBED_MODEL, SIMILAR_K
│   ├── taxonomy.py    # categories→teams, Impact×Urgency matrix, overrides
│   ├── schema.py      # Pydantic: TicketDecision (LLM), ClassifyRequest, RoutedTicket
│   ├── prompt.py      # few-shot prompt (6 examples) + LangChain messages
│   ├── classifier.py  # LLM call + 3-layer retry/fallback; derive_priority()
│   ├── embeddings.py  # OpenAI text-embedding-3-small (LangChain), lazy
│   ├── retrieval.py   # similar_tickets(): embed query -> cosine search
│   ├── db.py          # SQLAlchemy: TicketLog + ResolvedTicket; stats, timing, search_similar
│   └── api.py         # FastAPI: POST /classify, GET /tickets, /stats, /timing, /similar, /health
├── run.py             # single-command launcher (API + UI together)
├── streamlit_app.py   # UI client + dashboard + "Similar past tickets" panel
├── demo_tickets.py    # 21 labeled demo tickets
├── resolved_tickets.py # 18 past RESOLVED tickets (retrieval corpus)
├── scripts/           # run_demo, consistency_check, edge_cases, interactive, seed_resolved
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
| GET | `/similar?ticket=...&k=3` | Retrieval: most similar past resolved tickets (reference only; `[]` if corpus unseeded) |
| GET | `/incidents` | Incident alarm: consecutive same-category spike state |
| GET | `/health` | Liveness check |

## Retrieval layer (v1.2 Stage 1)

New tickets are matched against a corpus of past **resolved** tickets (`resolved_tickets.py`)
by embedding similarity, and shown as a **reference panel** in the Classify tab — it never
changes the routing decision.

- **Embeddings:** OpenAI `text-embedding-3-small` (`app/embeddings.py`).
- **Store & search:** vectors are stored in Postgres (`resolved_ticket` table) and ranked by
  **cosine similarity in numpy** (`db.search_similar`) — no extra infra. pgvector is the later
  production upgrade.
- **Seed the corpus once** (one paid, batched embedding call):
  ```bash
  cd ~/Projects/krisis/krisis/v1.2 && ../.venv/bin/python scripts/seed_resolved.py
  ```
  Until seeded, `/similar` returns `[]` and the panel shows a hint (no wasted embedding calls).

## Semantic classification cache (v1.2)

`POST /classify` embeds each ticket and compares it against **past successful classifications**
in `ticket_log`. If a prior ticket is at least `CACHE_THRESHOLD` cosine-similar (default **0.92**),
its answer is **reused and the LLM call is skipped** — saving time and tokens on near-duplicate
tickets. The reused answer carries `cached: true`, `source_ticket_id`, and `similarity` in the
`/classify` response, and the Streamlit result shows a "♻️ reused" banner.

- Only successful (`ok=true`) past rows are cache sources; fallbacks are never reused.
- Every ticket's embedding is stored on its `ticket_log` row (so it can serve future lookups).
- **Backfill embeddings for pre-existing rows** so they can serve as cache sources:
  ```bash
  cd ~/Projects/krisis/krisis/v1.2 && ../.venv/bin/python scripts/backfill_embeddings.py
  ```
- Tune with env vars: `CACHE_THRESHOLD=0.95` (stricter) or `CACHE_ENABLED=0` (off).
- The `/classify` response also returns `similar_past` — the most similar past **submitted**
  tickets (from `ticket_log`), which the Classify tab lists in a panel **even below the reuse
  threshold**, so you can see prior related tickets (the reused one is marked).

## Incident clustering (v1.2)

Raises an alarm when the ticket stream shows a **spike**: `INCIDENT_THRESHOLD` (default **3**)
**consecutive** tickets in the **same category**, all within `INCIDENT_WINDOW_MIN` (default **30**)
minutes. `GET /incidents` returns the state (`active`, `category`, `count`, `since`), and the
**Dashboard** (the managing-team view) shows a **pulsing red alarm banner (dismissible)** when
active — the Classify/employee tab is unaffected. Dismiss hides the current incident; a new or
different incident re-alarms. Tune via `INCIDENT_THRESHOLD` / `INCIDENT_WINDOW_MIN`
(`INCIDENT_WINDOW_MIN=0` ignores timing).

## Confidence-aware routing (v1.2)

The LLM reports a categorical **confidence** (`high` / `medium` / `low`) with each classification.
A ticket is flagged **`needs_review = true`** when confidence is `low` **or** the category is
`unclassified` — the suggestion is kept (not hidden or rerouted), just marked for a human to
confirm. Surfaced as `confidence` + `needs_review` in the `/classify` response, a warning on the
Classify result, and a **"Needs review"** count + per-row flag on the Dashboard. (LLM
self-reported confidence is indicative, not perfectly calibrated.)

---

## Prerequisites (one-time)

- Deps installed into the shared venv:
  ```bash
  cd ~/Projects/krisis/krisis
  .venv/bin/pip install -r v1.2/requirements.txt
  ```
- PostgreSQL running and a `krisis` database:
  ```bash
  brew services start postgresql@16
  createdb krisis   # only if it doesn't exist yet
  ```
- The shared root `.env` (copy the template **only if you don't already have one** —
  `cp -n` will NOT overwrite an existing `.env`):
  ```bash
  cp -n v1.2/.env.example .env   # then edit OPENAI_API_KEY
  ```

## Run — single command (recommended)

```bash
cd ~/Projects/krisis/krisis/v1.2
../.venv/bin/python run.py
```
Starts the API (`:8000`) and the Streamlit UI (`:8501`) together; **Ctrl-C stops both**.
Override ports with env vars: `API_PORT=8010 UI_PORT=8511 ../.venv/bin/python run.py`.

Interactive API docs: <http://localhost:8000/docs>. UI: <http://localhost:8501>.

<details><summary>Alternative: two terminals</summary>

```bash
# Terminal 1 — API
cd ~/Projects/krisis/krisis/v1.2 && ../.venv/bin/uvicorn app.api:app --reload
# Terminal 2 — UI
cd ~/Projects/krisis/krisis/v1.2 && ../.venv/bin/streamlit run streamlit_app.py
```
</details>

## Evaluation scripts (run from `v1.2/`)

```bash
../.venv/bin/python scripts/run_demo.py           # classify all 21 demo tickets, log to DB, print table
../.venv/bin/python scripts/consistency_check.py  # same input x3 -> identical output (PASS/FAIL)
../.venv/bin/python scripts/edge_cases.py         # empty / long / non-English / simulated failure
../.venv/bin/python scripts/interactive.py        # type a ticket, see the full result (no DB writes)
../.venv/bin/python scripts/seed_resolved.py      # seed the retrieval corpus (one-time, paid embeddings)
../.venv/bin/python scripts/backfill_embeddings.py # embed existing ticket_log rows for the cache (one-time)
```

`run_demo.py` populates the DB so the dashboard's **Time saved** panel shows the before/after
comparison (manual @ 5 min/ticket vs actual latency).

## Cost tracking (v1.2)

Each classification's token usage is priced (`PRICE_INPUT_PER_1M` / `PRICE_OUTPUT_PER_1M`,
defaults for `gpt-4o-mini`) and shown **on the Dashboard only**: total cost, avg/ticket, and
**est. cost saved by the cache** (cache hits skip the LLM → ~$0). Per-ticket cost is a column in
the recent-tickets table. (Not shown on the employee Classify tab.)

## Production notes (v1.2)

- **Readiness:** `GET /health` returns `{status, openai_key, db}`; `status` is `degraded` if the
  key is missing/placeholder or the DB is unreachable. Config problems are logged at startup
  (`config.validate()`).
- **Input guard:** `/classify` rejects tickets over 20,000 chars (422); normal long input is
  truncated to `MAX_TICKET_CHARS`.
- **Run in production:** drop `--reload` and add workers, e.g.
  `../.venv/bin/uvicorn app.api:app --host 0.0.0.0 --port 8000 --workers 4`.
- **Tests:** `../.venv/bin/pytest` (offline units + API; live LLM tests are `-m live`, deselected
  by default).
- **Migrations:** dev/tests auto-create the schema via `init_db()` (`create_all`). For production
  use **Alembic**: `cd v1.2 && ../.venv/bin/alembic upgrade head` (initial revision creates
  `ticket_log` + `resolved_ticket`). On an existing dev DB already created by `create_all`, run
  `alembic stamp head` once to adopt Alembic without re-creating tables.

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
| `ModuleNotFoundError: app` | Launch uvicorn/streamlit from **inside `v1.2/`** |
| Port already in use | `uvicorn ... --port 8001`; then `API_BASE=http://localhost:8001 ../.venv/bin/streamlit run streamlit_app.py` |
