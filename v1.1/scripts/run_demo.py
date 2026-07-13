"""Classify all 20 demo tickets, log them to Postgres, and print a summary table.

Run from the v1.1/ folder:  ../.venv/bin/python scripts/run_demo.py
Populates the DB so the Streamlit dashboard (incl. the Time-saved panel) reflects the run.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402
from app.classifier import classify  # noqa: E402
from demo_tickets import DEMO_TICKETS  # noqa: E402


def main() -> int:
    db.init_db()
    print(f"Classifying {len(DEMO_TICKETS)} demo tickets...\n")
    rows = []
    for i, t in enumerate(DEMO_TICKETS, 1):
        routed, meta = classify(t["ticket"])
        try:
            db.log_ticket(
                ticket_text=t["ticket"], category=routed.category, priority=routed.priority,
                assigned_team=routed.assigned_team, impact=routed.impact, urgency=routed.urgency,
                reasoning=routed.reasoning, model=meta.get("model"),
                prompt_tokens=meta.get("prompt_tokens"), completion_tokens=meta.get("completion_tokens"),
                latency_ms=meta.get("latency_ms"), ok=meta.get("ok", True), error=meta.get("error"),
            )
        except Exception as e:  # noqa: BLE001
            print(f"   (log failed: {e})")
        flag = "ok" if routed.category == t["expect_category"] else "XX"
        rows.append((routed, meta, t, flag))
        print(f"{i:2d}. [{flag}] {routed.category:13s} {routed.priority:6s} "
              f"{routed.assigned_team:24s} | expected {t['expect_category']}/{t['expect_priority']}")
        print(f"       {t['ticket'][:72]}")

    n = len(rows)
    cat_match = sum(1 for _, _, t, f in rows if f == "ok")
    total_lat = sum((m.get("latency_ms") or 0) for _, m, _, _ in rows)
    print(f"\nCategory matches vs expected: {cat_match}/{n}")
    print(f"Total automated time: {total_lat/1000:.1f}s  (avg {total_lat/max(n,1):.0f} ms/ticket)")
    print("Open the Streamlit dashboard's 'Time saved' panel for the before/after comparison.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
