"""FastAPI backend. All business logic lives here; the Streamlit UI is just a client."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app import classifier, config, db, embeddings, retrieval
from app.schema import ClassifyRequest, RoutedTicket

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("krisis.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail-fast visibility: surface config problems clearly at startup.
    for problem in config.validate():
        log.warning("CONFIG: %s", problem)
    # Best-effort: if Postgres isn't up yet, the API still serves /classify (logging is skipped).
    try:
        db.init_db()
        log.info("DB initialized")
    except Exception as e:  # noqa: BLE001
        log.warning("DB init failed - request logging disabled: %s", e)
    yield


app = FastAPI(title="KRISIS", version="1.0", lifespan=lifespan)


def _log(ticket: str, routed: RoutedTicket, meta: dict, embedding=None) -> None:
    """Best-effort log of every request, including its embedding (for the cache) and,
    on a cache hit, the source ticket + similarity."""
    try:
        db.log_ticket(
            ticket_text=ticket,
            category=routed.category,
            priority=routed.priority,
            assigned_team=routed.assigned_team,
            impact=routed.impact,
            urgency=routed.urgency,
            reasoning=routed.reasoning,
            model=meta.get("model"),
            prompt_tokens=meta.get("prompt_tokens"),
            completion_tokens=meta.get("completion_tokens"),
            latency_ms=meta.get("latency_ms"),
            ok=meta.get("ok", True),   # fix: honor fallback outcome (was hardcoded True)
            error=meta.get("error"),
            embedding=embedding,
            reused_from_id=meta.get("source_ticket_id"),
            similarity=meta.get("similarity"),
            confidence=routed.confidence,
            needs_review=routed.needs_review,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("failed to log ticket: %s", e)


@app.get("/health")
def health() -> dict:
    """Readiness check: is a real key configured and the database reachable?"""
    key_ok = config.openai_key_ok()
    db_ok = db.ping()
    return {
        "status": "ok" if (key_ok and db_ok) else "degraded",
        "openai_key": key_ok,
        "db": db_ok,
    }


@app.post("/classify", response_model=RoutedTicket)
def classify_endpoint(req: ClassifyRequest) -> RoutedTicket:
    ticket = (req.ticket or "").strip()
    if not ticket:
        raise HTTPException(status_code=422, detail="ticket must not be empty")

    # Embed once — used both for the cache lookup and stored on the log row.
    embedding = None
    try:
        embedding = embeddings.embed_text(ticket[: config.MAX_TICKET_CHARS])
    except Exception as e:  # noqa: BLE001 — embedding is best-effort; fall through to LLM
        log.warning("embedding failed (no cache this request): %s", e)

    # Similar PAST SUBMITTED tickets (computed before the current one is logged, so no
    # self-match). Top match drives the cache; the full list is shown in the UI panel.
    matches = []
    if embedding is not None:
        try:
            matches = db.search_similar_logs(embedding, k=config.SIMILAR_K)
        except Exception as e:  # noqa: BLE001
            log.warning("similar-log lookup failed: %s", e)

    # Semantic cache: if the closest past ticket is similar enough, reuse it and skip the LLM.
    if config.CACHE_ENABLED and matches and matches[0]["score"] >= config.CACHE_THRESHOLD:
        m = matches[0]
        routed = RoutedTicket(
            category=m["category"], priority=m["priority"],
            assigned_team=m["assigned_team"], reasoning=m["reasoning"],
            impact=m["impact"], urgency=m["urgency"],
            confidence=m.get("confidence", "high"), needs_review=m.get("needs_review", False),
            cached=True, source_ticket_id=m["id"], similarity=m["score"],
            similar_past=matches,
        )
        _log(ticket, routed,
             {"ok": True, "source_ticket_id": m["id"], "similarity": m["score"]},
             embedding)
        return routed

    # Cache miss -> classify with the LLM (classify() never raises; it falls back safely).
    routed, meta = classifier.classify(ticket)
    routed.similar_past = matches
    _log(ticket, routed, meta, embedding)
    return routed


@app.get("/tickets")
def tickets_endpoint(limit: int = 50) -> dict:
    try:
        return {"tickets": db.list_tickets(limit=limit)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"database unavailable: {e}")


@app.get("/stats")
def stats_endpoint() -> dict:
    try:
        return db.stats()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"database unavailable: {e}")


@app.get("/timing")
def timing_endpoint() -> dict:
    """Before/after: assumed manual triage time vs actual automated latency."""
    try:
        return db.timing(config.MANUAL_TRIAGE_SECONDS)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"database unavailable: {e}")


@app.get("/incidents")
def incidents_endpoint() -> dict:
    """Incident clustering: alarm when recent tickets are a consecutive same-category spike."""
    try:
        return db.incident_status(config.INCIDENT_THRESHOLD, config.INCIDENT_WINDOW_MIN)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"database unavailable: {e}")


@app.get("/similar")
def similar_endpoint(ticket: str, k: int = config.SIMILAR_K) -> dict:
    """Retrieval: past resolved tickets most similar to `ticket` (reference only).
    Returns an empty list if the corpus isn't seeded - never an error."""
    return {"similar": retrieval.similar_tickets(ticket, k=k)}
