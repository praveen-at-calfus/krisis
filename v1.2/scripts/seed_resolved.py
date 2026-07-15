"""Seed the resolved-ticket retrieval corpus into Postgres (embeds each ticket).

Run once from v1.2/:  ../.venv/bin/python scripts/seed_resolved.py
Idempotent - re-running replaces the corpus. Makes one batched embedding call (paid).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402
from app.embeddings import embed_texts  # noqa: E402
from resolved_tickets import RESOLVED_TICKETS  # noqa: E402


def main() -> int:
    db.init_db()
    print(f"Embedding {len(RESOLVED_TICKETS)} resolved tickets ...")
    vectors = embed_texts([t["ticket"] for t in RESOLVED_TICKETS])
    items = [
        {
            "ticket_text": t["ticket"],
            "category": t["category"],
            "resolution": t["resolution"],
            "embedding": vec,
        }
        for t, vec in zip(RESOLVED_TICKETS, vectors)
    ]
    n = db.seed_resolved_tickets(items)
    print(f"Seeded {n} resolved tickets (embedding dim = {len(vectors[0])}).")
    print(f"resolved_count() = {db.resolved_count()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
