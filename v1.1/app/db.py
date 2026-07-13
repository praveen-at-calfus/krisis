"""PostgreSQL persistence via SQLAlchemy. Logs every classification request."""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean, DateTime, Integer, String, Text, create_engine, func, select,
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, sessionmaker,
)

from app.config import DATABASE_URL


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
            "latency_ms": self.latency_ms,
            "ok": self.ok,
            "error": self.error,
        }


engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_db() -> None:
    """Create tables if they don't exist. Called on API startup."""
    Base.metadata.create_all(engine)


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
        return {
            "total": total,
            "failures": failures,
            "by_category": by_category,
            "by_priority": by_priority,
            "avg_latency_ms": round(float(avg_latency), 1) if avg_latency is not None else None,
            "total_latency_ms": int(total_latency_ms),
            "total_prompt_tokens": int(total_prompt_tokens),
            "total_completion_tokens": int(total_completion_tokens),
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
