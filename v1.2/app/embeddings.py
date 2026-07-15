"""Text embeddings via OpenAI (text-embedding-3-small), wrapped with LangChain.

Lazy init so importing this module never requires credentials or a network call.
"""
from functools import lru_cache
from typing import List

from langchain_openai import OpenAIEmbeddings

from app.config import EMBED_MODEL, OPENAI_API_KEY


@lru_cache(maxsize=1)
def _embedder() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(model=EMBED_MODEL, api_key=OPENAI_API_KEY)


def embed_text(text: str) -> List[float]:
    """Embed a single string -> vector."""
    return _embedder().embed_query(text)


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed many strings in one batched call -> list of vectors."""
    return _embedder().embed_documents(texts)
