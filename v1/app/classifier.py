"""LangChain-wired classifier. Assesses the ticket, then derives priority + team in code."""
import time
import warnings
from functools import lru_cache
from typing import Tuple

from langchain_openai import ChatOpenAI

from .config import MODEL, OPENAI_API_KEY
from .prompt import build_messages
from .schema import RoutedTicket, TicketDecision
from .taxonomy import PRIORITY_MATRIX, TAXONOMY


@lru_cache(maxsize=1)
def _structured_llm():
    """Built lazily so importing this module never requires credentials or a network call.
    temperature=0 for run-to-run consistency (the "same input -> same output" rubric);
    include_raw so we can read token usage; json_schema = native OpenAI structured outputs."""
    llm = ChatOpenAI(model=MODEL, temperature=0, api_key=OPENAI_API_KEY)
    return llm.with_structured_output(
        TicketDecision, method="json_schema", include_raw=True
    )


def derive_priority(d: TicketDecision) -> str:
    """Priority is computed, not chosen: overrides first, then the impact x urgency matrix."""
    if d.category == "security":
        return "High"      # a security incident escalates regardless of scope
    if d.category == "unclassified":
        return "Medium"    # safe default, flagged for review
    return PRIORITY_MATRIX[(d.impact, d.urgency)]


def classify(ticket: str) -> Tuple[RoutedTicket, dict]:
    """Return (RoutedTicket, meta). meta carries model/latency/token usage for logging."""
    t0 = time.perf_counter()
    with warnings.catch_warnings():
        # Benign noise from LangChain's include_raw=True serialization path.
        warnings.filterwarnings("ignore", message="Pydantic serializer warnings")
        result = _structured_llm().invoke(build_messages(ticket))
    latency_ms = int((time.perf_counter() - t0) * 1000)

    decision: TicketDecision = result["parsed"]
    raw = result.get("raw")
    usage = getattr(raw, "usage_metadata", None) or {}

    routed = RoutedTicket(
        category=decision.category,
        priority=derive_priority(decision),
        assigned_team=TAXONOMY[decision.category]["team"],
        reasoning=decision.reasoning,
        impact=decision.impact,
        urgency=decision.urgency,
    )
    meta = {
        "model": MODEL,
        "latency_ms": latency_ms,
        "prompt_tokens": usage.get("input_tokens"),
        "completion_tokens": usage.get("output_tokens"),
    }
    return routed, meta


if __name__ == "__main__":  # quick smoke test: python -m app.classifier
    import json

    for t in [
        "The whole prod database is down and no one can log in to the app.",
        "This is RIDICULOUS, reset my password NOW, locked out for hours!",
        "it's broken",
        "CI pipeline says my SSH key is unauthorized so I can't push",
    ]:
        routed, meta = classify(t)
        print(f"\nTICKET: {t}")
        print(json.dumps(routed.model_dump(), indent=2))
        print("meta:", meta)
