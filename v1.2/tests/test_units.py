"""Offline unit tests — no network, no DB required."""
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.classifier import derive_priority, needs_review
from app.db import compute_incident, cost_usd
from app.prompt import FEWSHOT, build_messages
from app.schema import ClassifyRequest, RoutedTicket, TicketDecision


def _dec(**kw):
    base = dict(analysis="a", impact="narrow", urgency="workaround",
                category="dev_tooling", reasoning="r", confidence="high")
    base.update(kw)
    return TicketDecision(**base)


@pytest.mark.parametrize("impact,urgency,expected", [
    ("broad", "blocked", "High"),
    ("broad", "workaround", "Medium"),
    ("narrow", "blocked", "Medium"),
    ("narrow", "workaround", "Low"),
])
def test_priority_matrix(impact, urgency, expected):
    assert derive_priority(_dec(category="infra_outage", impact=impact, urgency=urgency)) == expected


def test_priority_overrides():
    assert derive_priority(_dec(category="security", impact="narrow", urgency="workaround")) == "High"
    assert derive_priority(_dec(category="unclassified")) == "Medium"


def test_needs_review():
    assert needs_review(_dec(confidence="low")) is True
    assert needs_review(_dec(category="unclassified")) is True
    assert needs_review(_dec(confidence="high", category="ci_cd")) is False


def test_cost_usd():
    assert cost_usd(1_000_000, 0) == pytest.approx(0.15)
    assert cost_usd(0, 1_000_000) == pytest.approx(0.60)
    assert cost_usd(None, None) == 0.0


def test_incident_active():
    now = datetime.now(timezone.utc)
    rows = [("security", now - timedelta(minutes=m)) for m in (0, 1, 2)]
    r = compute_incident(rows, threshold=3, window_min=30)
    assert r["active"] and r["category"] == "security" and r["count"] == 3


def test_incident_reset_on_category_change():
    now = datetime.now(timezone.utc)
    rows = [("hardware", now),
            ("security", now - timedelta(minutes=1)),
            ("security", now - timedelta(minutes=2))]
    assert compute_incident(rows, 3, 30)["active"] is False


def test_incident_window_trims_run():
    now = datetime.now(timezone.utc)
    rows = [("security", now),
            ("security", now - timedelta(minutes=5)),
            ("security", now - timedelta(minutes=45))]  # outside 30-min window
    r = compute_incident(rows, 3, 30)
    assert r["active"] is False and r["count"] == 2


def test_fewshot_has_confidence():
    assert len(FEWSHOT) == 6
    assert all(ex["decision"]["confidence"] in ("high", "medium", "low") for ex in FEWSHOT)


def test_build_messages_count():
    assert len(build_messages("x")) == 1 + 2 * len(FEWSHOT) + 1


def test_classify_request_max_length():
    ClassifyRequest(ticket="x" * 20000)                     # ok
    with pytest.raises(ValidationError):
        ClassifyRequest(ticket="x" * 20001)                 # rejected


def test_routed_defaults():
    rt = RoutedTicket(category="ci_cd", priority="Low", assigned_team="Platform engineering",
                      reasoning="r", impact="narrow", urgency="workaround")
    assert rt.cached is False and rt.needs_review is False and rt.confidence == "high"
