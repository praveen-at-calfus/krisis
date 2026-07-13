"""Edge-case & failure-handling checks (the Integration-Quality rubric lines).

Run from v1.1/:  ../.venv/bin/python scripts/edge_cases.py
Exercises: empty input, very long input, non-English input, and a simulated API failure.
Makes ~2 paid LLM calls (long + non-English).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app import classifier as clf  # noqa: E402
from app.api import app  # noqa: E402
from app.config import MAX_TICKET_CHARS  # noqa: E402


def check(name: str, cond: bool, detail: str = "") -> bool:
    print(f"[{'PASS' if cond else 'FAIL'}] {name}{(' - ' + detail) if detail else ''}")
    return cond


def _boom(_messages):
    raise RuntimeError("simulated API failure")


def main() -> int:
    ok = True

    # 1. empty / whitespace input -> 422 (API guard, no LLM call)
    with TestClient(app) as c:
        r = c.post("/classify", json={"ticket": "   "})
        ok &= check("empty input -> 422", r.status_code == 422, f"got {r.status_code}")

    # 2. very long input -> truncated to MAX_TICKET_CHARS, classified, no crash
    long_ticket = "the database is down for everyone. " * 2000  # ~70k chars
    routed, meta = clf.classify(long_ticket)
    ok &= check("very long input handled", routed is not None and meta["ok"],
                f"input {len(long_ticket)} chars, capped at {MAX_TICKET_CHARS}; category={routed.category}")

    # 3. non-English input -> classified, no crash
    routed, meta = clf.classify("No puedo acceder a mi cuenta, la contrasena no funciona.")
    ok &= check("non-English input handled", routed is not None and meta["ok"],
                f"category={routed.category}")

    # 4. simulated API failure -> Layer-3 safe fallback, never a crash
    original = clf._invoke_once
    clf._invoke_once = _boom
    try:
        routed, meta = clf.classify("anything at all")
    finally:
        clf._invoke_once = original
    ok &= check("API failure -> safe fallback",
                (meta["ok"] is False) and meta["fallback"] and routed.category == "unclassified",
                f"attempts={meta['attempts']}, result={routed.category}/{routed.priority}")

    print(f"\n{'ALL EDGE CASES PASS' if ok else 'SOME EDGE CASES FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
