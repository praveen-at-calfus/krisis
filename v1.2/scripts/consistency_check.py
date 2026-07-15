"""Consistency check: same input -> equivalent output (the Integration-Quality rubric line).

Run from v1.1/:  ../.venv/bin/python scripts/consistency_check.py
With temperature=0 and code-derived priority/team, all runs should be identical.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.classifier import classify  # noqa: E402

TICKET = "The entire production cluster is unreachable and every service is returning 500s."
N = 3


def main() -> int:
    print(f"Classifying the same ticket {N} times (temperature=0):\n  {TICKET!r}\n")
    results = []
    for i in range(1, N + 1):
        r, m = classify(TICKET)
        results.append((r.category, r.priority, r.assigned_team))
        print(f"  run {i}: {r.category} / {r.priority} / {r.assigned_team}   ({m.get('latency_ms')} ms)")
    distinct = set(results)
    consistent = len(distinct) == 1
    print(f"\nConsistency: {'PASS' if consistent else 'FAIL'} "
          f"- {len(distinct)} distinct result(s) across {N} runs")
    return 0 if consistent else 1


if __name__ == "__main__":
    raise SystemExit(main())
