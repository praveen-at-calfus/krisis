"""Backfill embeddings for existing ticket_log rows so they can serve the semantic cache.

Run once from v1.2/:  ../.venv/bin/python scripts/backfill_embeddings.py
Only touches successful (ok=True) rows that don't have an embedding yet. One batched
(paid) embedding call. Safe to re-run.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app import db  # noqa: E402
from app.embeddings import embed_texts  # noqa: E402


def main() -> int:
    db.init_db()
    pending = db.logs_missing_embeddings()
    if not pending:
        print("Nothing to backfill — all successful log rows already have embeddings.")
        return 0
    print(f"Embedding {len(pending)} existing ticket_log rows ...")
    vectors = embed_texts([p["ticket_text"] for p in pending])
    updated = db.set_log_embeddings({p["id"]: v for p, v in zip(pending, vectors)})
    print(f"Backfilled {updated} rows (embedding dim = {len(vectors[0])}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
