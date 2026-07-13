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
