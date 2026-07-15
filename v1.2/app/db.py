"""PostgreSQL persistence via SQLAlchemy. Logs every classification request,
and stores the resolved-ticket corpus + embeddings for the retrieval layer."""
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import numpy as np
from sqlalchemy import (
    JSON, Boolean, DateTime, Float, Integer, String, Text, create_engine, func,
    select, text,
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, sessionmaker,
)

from app.config import DATABASE_URL, PRICE_INPUT_PER_1M, PRICE_OUTPUT_PER_1M


def cost_usd(prompt_tokens, completion_tokens) -> float:
    """USD cost of one classification from its token usage (0 for cache hits / no tokens)."""
    inp = (prompt_tokens or 0) / 1_000_000 * PRICE_INPUT_PER_1M
    out = (completion_tokens or 0) / 1_000_000 * PRICE_OUTPUT_PER_1M
    return inp + out


class Base(DeclarativeBase):
    pass


class TicketLog(Base):
    __tablename__ = "ticket_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    ticket_text: Mapped[str] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String(32))
    priority: Mapped[Optional[str]] = mapped_column(String(16))
    assigned_team: Mapped[Optional[str]] = mapped_column(String(64))
    impact: Mapped[Optional[str]] = mapped_column(String(16))
    urgency: Mapped[Optional[str]] = mapped_column(String(16))
    reasoning: Mapped[Optional[str]] = mapped_column(Text)
    model: Mapped[Optional[str]] = mapped_column(String(64))
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[Optional[str]] = mapped_column(Text)
    # semantic cache: embedding of the ticket + provenance when an answer was reused
    embedding: Mapped[Optional[list]] = mapped_column(JSON)  # list[float]
    reused_from_id: Mapped[Optional[int]] = mapped_column(Integer)
    similarity: Mapped[Optional[float]] = mapped_column(Float)
    # confidence-aware routing
    confidence: Mapped[Optional[str]] = mapped_column(String(8))
    needs_review: Mapped[Optional[bool]] = mapped_column(Boolean)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "ticket_text": self.ticket_text,
            "category": self.category,
            "priority": self.priority,
            "assigned_team": self.assigned_team,
            "impact": self.impact,
            "urgency": self.urgency,
            "reasoning": self.reasoning,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost_usd": round(cost_usd(self.prompt_tokens, self.completion_tokens), 6),
            "latency_ms": self.latency_ms,
            "ok": self.ok,
            "error": self.error,
            "reused_from_id": self.reused_from_id,
            "similarity": self.similarity,
            "confidence": self.confidence,
            "needs_review": self.needs_review,
        }


class ResolvedTicket(Base):
    """A past, resolved ticket + its embedding, used as the retrieval corpus."""
    __tablename__ = "resolved_ticket"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_text: Mapped[str] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String(32))
    resolution: Mapped[Optional[str]] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(JSON)  # list[float]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def ping() -> bool:
    """True if the database is reachable (for readiness checks)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False


def init_db() -> None:
    """Create tables if they don't exist, then add any newer columns to an
    already-existing ticket_log (no Alembic; ADD COLUMN IF NOT EXISTS is idempotent)."""
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE ticket_log ADD COLUMN IF NOT EXISTS embedding JSONB"))
        conn.execute(text("ALTER TABLE ticket_log ADD COLUMN IF NOT EXISTS reused_from_id INTEGER"))
        conn.execute(text("ALTER TABLE ticket_log ADD COLUMN IF NOT EXISTS similarity DOUBLE PRECISION"))
        conn.execute(text("ALTER TABLE ticket_log ADD COLUMN IF NOT EXISTS confidence VARCHAR(8)"))
        conn.execute(text("ALTER TABLE ticket_log ADD COLUMN IF NOT EXISTS needs_review BOOLEAN"))


def log_ticket(**fields) -> int:
    """Insert one row; returns its id. Raises on DB error (caller decides how to handle)."""
    with SessionLocal() as session:
        row = TicketLog(**fields)
        session.add(row)
        session.commit()
        return row.id


def list_tickets(limit: int = 50) -> List[dict]:
    with SessionLocal() as session:
        rows = session.execute(
            select(TicketLog).order_by(TicketLog.created_at.desc()).limit(limit)
        ).scalars().all()
        return [r.to_dict() for r in rows]


def stats() -> dict:
    """Aggregates for the dashboard: totals, category/priority breakdowns, avg latency."""
    with SessionLocal() as session:
        total = session.scalar(select(func.count(TicketLog.id))) or 0
        by_category = dict(
            session.execute(
                select(TicketLog.category, func.count())
                .where(TicketLog.category.is_not(None))
                .group_by(TicketLog.category)
            ).all()
        )
        by_priority = dict(
            session.execute(
                select(TicketLog.priority, func.count())
                .where(TicketLog.priority.is_not(None))
                .group_by(TicketLog.priority)
            ).all()
        )
        avg_latency = session.scalar(select(func.avg(TicketLog.latency_ms)))
        total_latency_ms = session.scalar(select(func.sum(TicketLog.latency_ms))) or 0
        total_prompt_tokens = session.scalar(select(func.sum(TicketLog.prompt_tokens))) or 0
        total_completion_tokens = session.scalar(select(func.sum(TicketLog.completion_tokens))) or 0
        failures = session.scalar(
            select(func.count(TicketLog.id)).where(TicketLog.ok.is_(False))
        ) or 0
        needs_review = session.scalar(
            select(func.count(TicketLog.id)).where(TicketLog.needs_review.is_(True))
        ) or 0
        cache_hits = session.scalar(
            select(func.count(TicketLog.id)).where(TicketLog.reused_from_id.is_not(None))
        ) or 0
        llm_tickets = session.scalar(
            select(func.count(TicketLog.id)).where(TicketLog.prompt_tokens.is_not(None))
        ) or 0

    total_cost = cost_usd(total_prompt_tokens, total_completion_tokens)
    avg_llm_cost = total_cost / llm_tickets if llm_tickets else 0.0
    return {
        "total": total,
        "failures": failures,
        "needs_review": needs_review,
        "by_category": by_category,
        "by_priority": by_priority,
        "avg_latency_ms": round(float(avg_latency), 1) if avg_latency is not None else None,
        "total_latency_ms": int(total_latency_ms),
        "total_prompt_tokens": int(total_prompt_tokens),
        "total_completion_tokens": int(total_completion_tokens),
        "total_cost_usd": round(total_cost, 4),
        "avg_cost_per_ticket_usd": round(total_cost / total, 6) if total else 0.0,
        "cache_hits": cache_hits,
        "est_cost_saved_usd": round(cache_hits * avg_llm_cost, 4),
    }


def timing(manual_seconds_per_ticket: int) -> dict:
    """Before/after comparison: assumed manual triage time vs actual automated latency."""
    s = stats()
    n = s["total"]
    automated_s = s["total_latency_ms"] / 1000.0
    manual_s = n * manual_seconds_per_ticket
    return {
        "tickets": n,
        "manual_baseline_seconds_per_ticket": manual_seconds_per_ticket,
        "manual_total_seconds": manual_s,
        "automated_total_seconds": round(automated_s, 1),
        "time_saved_seconds": round(manual_s - automated_s, 1),
        "avg_latency_ms": s["avg_latency_ms"],
    }


# --- Retrieval layer (v1.2) -------------------------------------------------

def resolved_count() -> int:
    with SessionLocal() as session:
        return session.scalar(select(func.count(ResolvedTicket.id))) or 0


def seed_resolved_tickets(items: List[dict]) -> int:
    """Replace the corpus with `items` (each: ticket_text, category, resolution, embedding).
    Idempotent: clears the table first so re-seeding never duplicates."""
    from sqlalchemy import delete
    with SessionLocal() as session:
        session.execute(delete(ResolvedTicket))
        session.add_all([
            ResolvedTicket(
                ticket_text=it["ticket_text"], category=it.get("category"),
                resolution=it.get("resolution"), embedding=it["embedding"],
            )
            for it in items
        ])
        session.commit()
        return len(items)


def search_similar(query_embedding: List[float], k: int) -> List[dict]:
    """Return the k most cosine-similar resolved tickets to the query embedding."""
    with SessionLocal() as session:
        rows = session.execute(select(ResolvedTicket)).scalars().all()
    if not rows:
        return []
    mat = np.array([r.embedding for r in rows], dtype=float)      # (n, d)
    q = np.array(query_embedding, dtype=float)                    # (d,)
    # cosine similarity = normalized dot product
    mat_norm = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12)
    q_norm = q / (np.linalg.norm(q) + 1e-12)
    scores = mat_norm @ q_norm                                   # (n,)
    top = np.argsort(scores)[::-1][:k]
    return [
        {
            "score": round(float(scores[i]), 4),
            "ticket_text": rows[i].ticket_text,
            "category": rows[i].category,
            "resolution": rows[i].resolution,
        }
        for i in top
    ]


# --- Semantic classification cache over ticket_log --------------------------

def search_similar_logs(query_embedding: List[float], k: int = 1) -> List[dict]:
    """Most cosine-similar PAST successful classifications from ticket_log.
    Only rows that (a) succeeded (ok) and (b) have an embedding are candidates."""
    with SessionLocal() as session:
        rows = session.execute(
            select(TicketLog).where(TicketLog.ok.is_(True), TicketLog.embedding.is_not(None))
        ).scalars().all()
    if not rows:
        return []
    mat = np.array([r.embedding for r in rows], dtype=float)
    q = np.array(query_embedding, dtype=float)
    mat_norm = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12)
    q_norm = q / (np.linalg.norm(q) + 1e-12)
    scores = mat_norm @ q_norm
    top = np.argsort(scores)[::-1][:k]
    return [
        {
            "score": round(float(scores[i]), 4),
            "id": rows[i].id,
            "ticket_text": rows[i].ticket_text,
            "category": rows[i].category,
            "priority": rows[i].priority,
            "assigned_team": rows[i].assigned_team,
            "impact": rows[i].impact,
            "urgency": rows[i].urgency,
            "reasoning": rows[i].reasoning,
            "confidence": rows[i].confidence or "high",
            "needs_review": bool(rows[i].needs_review),
        }
    for i in top
    ]


def compute_incident(rows, threshold: int, window_min: int) -> dict:
    """Pure trailing-run computation (testable). `rows` = [(category, created_at)] newest-first."""
    if not rows:
        return {"active": False, "count": 0, "threshold": threshold, "window_min": window_min}
    newest_cat, newest_at = rows[0]
    cutoff = newest_at - timedelta(minutes=window_min) if window_min else None
    run = 0
    since = newest_at
    for cat, at in rows:
        if cat != newest_cat:
            break
        if cutoff is not None and at < cutoff:
            break
        run += 1
        since = at
    return {
        "active": run >= threshold,
        "category": newest_cat,
        "count": run,
        "threshold": threshold,
        "window_min": window_min,
        "since": since.isoformat() if since else None,
    }


def incident_status(threshold: int, window_min: int) -> dict:
    """Incident alarm: are the most recent tickets a consecutive same-category spike?
    Fetches recent rows, then delegates to compute_incident()."""
    with SessionLocal() as session:
        rows = session.execute(
            select(TicketLog.category, TicketLog.created_at)
            .where(TicketLog.category.is_not(None))
            .order_by(TicketLog.created_at.desc())
            .limit(200)
        ).all()
    return compute_incident([(r[0], r[1]) for r in rows], threshold, window_min)


def logs_missing_embeddings() -> List[dict]:
    """[{id, ticket_text}] for successful log rows that have no embedding yet (for backfill)."""
    with SessionLocal() as session:
        rows = session.execute(
            select(TicketLog.id, TicketLog.ticket_text)
            .where(TicketLog.ok.is_(True), TicketLog.embedding.is_(None))
        ).all()
    return [{"id": r[0], "ticket_text": r[1]} for r in rows]


def set_log_embeddings(id_to_vec: dict) -> int:
    """Backfill: set embeddings for the given {log_id: vector}. Returns rows updated."""
    with SessionLocal() as session:
        n = 0
        for row in session.execute(
            select(TicketLog).where(TicketLog.id.in_(list(id_to_vec)))
        ).scalars().all():
            row.embedding = id_to_vec[row.id]
            n += 1
        session.commit()
        return n
