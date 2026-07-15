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
