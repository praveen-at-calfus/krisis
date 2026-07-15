"""Configuration loaded from the environment (.env)."""
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def _find_env() -> Optional[Path]:
    """Walk up from this file until a .env is found (shared at the project root,
    above the per-version folders). Independent of the launch directory."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return candidate
    return None


_env = _find_env()
if _env is not None:
    load_dotenv(_env)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("MODEL", "gpt-4o-mini")
# SQLAlchemy URL. Default assumes a local Homebrew Postgres and a "krisis" db.
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://localhost:5432/krisis"
)

# Cap runaway-length tickets before sending to the LLM (edge-case guard).
MAX_TICKET_CHARS = int(os.getenv("MAX_TICKET_CHARS", "8000"))
# Assumed human triage time per ticket, for the before/after dashboard comparison.
MANUAL_TRIAGE_SECONDS = int(os.getenv("MANUAL_TRIAGE_SECONDS", "300"))

# Retrieval layer (v1.2): embeddings model + how many similar tickets to return.
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
SIMILAR_K = int(os.getenv("SIMILAR_K", "3"))

# Semantic classification cache (v1.2): if a past ticket_log entry is at least this
# cosine-similar, reuse its classification instead of calling the LLM again.
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "1") not in ("0", "false", "False")
CACHE_THRESHOLD = float(os.getenv("CACHE_THRESHOLD", "0.92"))

# Incident clustering (v1.2): alarm when this many consecutive tickets share a category
# within this time window (a spike). Set INCIDENT_WINDOW_MIN=0 to ignore timing.
INCIDENT_THRESHOLD = int(os.getenv("INCIDENT_THRESHOLD", "3"))
INCIDENT_WINDOW_MIN = int(os.getenv("INCIDENT_WINDOW_MIN", "30"))

# Cost tracking (v1.2): LLM price per 1M tokens (defaults for gpt-4o-mini), env-overridable.
PRICE_INPUT_PER_1M = float(os.getenv("PRICE_INPUT_PER_1M", "0.15"))
PRICE_OUTPUT_PER_1M = float(os.getenv("PRICE_OUTPUT_PER_1M", "0.60"))


def openai_key_ok() -> bool:
    """True if a real (non-placeholder) OpenAI key is configured."""
    k = OPENAI_API_KEY or ""
    return k.startswith("sk-") and not k.startswith("sk-your") and len(k) > 40


def validate() -> list:
    """Return a list of config problems (empty = OK). Used for fail-fast startup checks."""
    problems = []
    if not openai_key_ok():
        problems.append("OPENAI_API_KEY is missing or a placeholder — set it in the root .env")
    if not DATABASE_URL:
        problems.append("DATABASE_URL is not set")
    return problems
