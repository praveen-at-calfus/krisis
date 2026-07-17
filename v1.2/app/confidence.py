"""Deterministic confidence via an embedding-prototype (nearest-centroid) margin.

Replaces the LLM's self-reported confidence. We build a centroid embedding per category
from the curated resolved-ticket corpus, then score a new ticket's embedding against those
centroids: does the nearest centroid AGREE with the LLM's chosen category, how close is the
ticket to that category's centroid, and how big is the margin over the runner-up. This is a
classic nearest-centroid / prototype classifier confidence. Conformal calibration on a
labeled set is the documented next step for principled thresholds.
"""
from functools import lru_cache
from typing import Optional

import numpy as np

from app import db
from app.config import CONF_HIGH_SIM, CONF_LOW_SIM, CONF_MARGIN, CONF_TEMP


@lru_cache(maxsize=1)
def _centroids():
    """(labels, matrix) with L2-normalized centroid per category, or None if unseeded."""
    data = db.resolved_label_embeddings()
    if not data:
        return None
    by_cat: dict = {}
    for cat, emb in data:
        by_cat.setdefault(cat, []).append(emb)
    labels = list(by_cat)
    mat = np.array([np.mean(np.array(by_cat[c], dtype=float), axis=0) for c in labels])
    mat = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-12)
    return labels, mat


def assess(embedding: Optional[list], llm_category: str) -> dict:
    """Deterministic confidence for the LLM's chosen category.

    Returns {level: high|medium|low, score, agrees, top_category}. Graceful 'medium'
    (no flag) when the corpus isn't seeded or no embedding is available.
    """
    c = _centroids()
    if c is None or embedding is None:
        return {"level": "medium", "score": None, "agrees": None, "top_category": None}

    labels, mat = c
    q = np.array(embedding, dtype=float)
    q = q / (np.linalg.norm(q) + 1e-12)
    sims = mat @ q                                   # cosine sim to each centroid

    order = np.argsort(sims)[::-1]
    top_category = labels[order[0]]
    top1 = float(sims[order[0]])
    top2 = float(sims[order[1]]) if len(order) > 1 else 0.0
    margin = top1 - top2
    agrees = top_category == llm_category
    assigned_sim = float(sims[labels.index(llm_category)]) if llm_category in labels else -1.0

    # softmax over sims (temperature-scaled) -> a display probability for the chosen category
    z = sims / max(CONF_TEMP, 1e-6)
    z = z - z.max()
    probs = np.exp(z)
    probs = probs / probs.sum()
    score = float(probs[labels.index(llm_category)]) if llm_category in labels else 0.0

    if (not agrees) or assigned_sim < CONF_LOW_SIM:
        level = "low"
    elif agrees and assigned_sim >= CONF_HIGH_SIM and margin >= CONF_MARGIN:
        level = "high"
    else:
        level = "medium"

    return {"level": level, "score": round(score, 4), "agrees": agrees, "top_category": top_category}
