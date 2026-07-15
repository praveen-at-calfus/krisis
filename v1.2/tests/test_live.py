"""Live tests — make real (paid) OpenAI calls. Deselected by default; run with `-m live`."""
import pytest

from app.classifier import classify


@pytest.mark.live
def test_classify_clear_outage():
    routed, meta = classify("The entire production database is down and no one can log in.")
    assert routed.category == "infra_outage"
    assert routed.priority == "High"
    assert meta["ok"] is True
