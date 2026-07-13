"""FastAPI backend. All business logic lives here; the Streamlit UI is just a client."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from . import classifier, config, db
from .schema import ClassifyRequest, RoutedTicket

log = logging.getLogger("krisis.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Best-effort: if Postgres isn't up yet, the API still serves /classify (logging is skipped).
    try:
        db.init_db()
        log.info("DB initialized")
    except Exception as e:  # noqa: BLE001
        log.warning("DB init failed - request logging disabled: %s", e)
    yield


app = FastAPI(title="KRISIS", version="1.0", lifespan=lifespan)


def _log_success(ticket: str, routed: RoutedTicket, meta: dict) -> None:
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
            ok=True,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("failed to log ticket: %s", e)


def _log_failure(ticket: str, error: str) -> None:
    try:
        db.log_ticket(ticket_text=ticket, ok=False, error=error)
    except Exception as e:  # noqa: BLE001
        log.warning("failed to log failure: %s", e)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/classify", response_model=RoutedTicket)
def classify_endpoint(req: ClassifyRequest) -> RoutedTicket:
    ticket = (req.ticket or "").strip()
    if not ticket:
        raise HTTPException(status_code=422, detail="ticket must not be empty")
    try:
        routed, meta = classifier.classify(ticket)
    except Exception as e:  # noqa: BLE001 — surface a clean error, never a 500 stack
        _log_failure(ticket, str(e))
        raise HTTPException(status_code=502, detail=f"classification failed: {e}")
    _log_success(ticket, routed, meta)
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
