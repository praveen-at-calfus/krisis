"""Retrieval layer: find past resolved tickets similar to a new one.

Embeds the query and searches the resolved-ticket corpus by cosine similarity.
This is a *reference* alongside the classification - it never changes the routing.
"""
from typing import List

from app import db
from app.config import SIMILAR_K
from app.embeddings import embed_text


def similar_tickets(ticket_text: str, k: int = SIMILAR_K) -> List[dict]:
    """Top-k similar resolved tickets: [{score, ticket_text, category, resolution}].
    Returns [] (never raises) if the ticket is empty or the corpus isn't seeded."""
    ticket_text = (ticket_text or "").strip()
    if not ticket_text:
        return []
    try:
        if db.resolved_count() == 0:      # corpus not seeded -> skip the paid embed call
            return []
        query_embedding = embed_text(ticket_text)
        return db.search_similar(query_embedding, k=k)
    except Exception:  # noqa: BLE001 — retrieval is best-effort; never break the caller
        return []
