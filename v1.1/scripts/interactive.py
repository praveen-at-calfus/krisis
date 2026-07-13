"""Interactive test CLI: type a ticket, see the full classification.

Run from v1.1/:  ../.venv/bin/python scripts/interactive.py
Quit with an empty line, 'q'/'quit'/'exit', or Ctrl-C. Does NOT write to the database.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.classifier import classify  # noqa: E402


def main() -> int:
    print("KRISIS interactive tester - type a ticket; empty line / 'q' to quit.\n")
    while True:
        try:
            ticket = input("Ticket> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if ticket.lower() in ("", "q", "quit", "exit"):
            break
        routed, meta = classify(ticket)
        status = "ok" if meta.get("ok") else f"FALLBACK (attempts={meta.get('attempts')})"
        print(f"  category      : {routed.category}")
        print(f"  priority      : {routed.priority}")
        print(f"  assigned_team : {routed.assigned_team}")
        print(f"  impact/urgency: {routed.impact} / {routed.urgency}")
        print(f"  reasoning     : {routed.reasoning}")
        print(f"  meta          : {meta.get('latency_ms')} ms | {status}\n")
    print("bye.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
