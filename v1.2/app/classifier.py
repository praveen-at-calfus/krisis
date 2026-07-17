"""LangChain-wired classifier with a three-layer reliability strategy.

Layer 1: structured output enforcement (with_structured_output).
Layer 2: retry (with the error fed back) on parse/validation/API failure.
Layer 3: a safe fallback response instead of ever crashing.
"""
import time
import warnings
from functools import lru_cache
from typing import Tuple

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from app.config import MAX_TICKET_CHARS, MODEL, OPENAI_API_KEY
from app.prompt import build_messages
from app.schema import RoutedTicket, TicketDecision
from app.taxonomy import PRIORITY_MATRIX, TAXONOMY

MAX_RETRIES = 2          # up to 3 total attempts (1 + 2 retries)
_RETRY_BACKOFF_S = 0.5   # linear backoff between attempts


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


def _fallback() -> RoutedTicket:
    """Layer 3: a valid, safe response when the LLM path fails after all retries."""
    return RoutedTicket(
        category="unclassified",
        priority="Medium",
        assigned_team=TAXONOMY["unclassified"]["team"],
        reasoning="Automatic fallback after repeated classification failures - flagged for manual review.",
        impact="narrow",
        urgency="workaround",
        confidence="low",
        needs_review=True,
    )


def _invoke_once(messages):
    with warnings.catch_warnings():
        # Benign noise from LangChain's include_raw=True serialization path.
        warnings.filterwarnings("ignore", message="Pydantic serializer warnings")
        result = _structured_llm().invoke(messages)
    decision = result.get("parsed")
    if decision is None:  # structured parsing failed
        raise ValueError(f"structured output did not parse: {result.get('parsing_error')}")
    return decision, result.get("raw")


def classify(ticket: str) -> Tuple[RoutedTicket, dict]:
    """Classify a ticket with retries + fallback. Never raises; always returns (RoutedTicket, meta).

    meta carries model/latency/token usage plus attempts/ok/error/fallback for logging.
    """
    ticket = ticket[:MAX_TICKET_CHARS]          # Layer-0 guard: cap runaway-length input
    messages = build_messages(ticket)
    last_error = None
    t0 = time.perf_counter()

    for attempt in range(1, MAX_RETRIES + 2):   # attempts 1..3
        try:
            decision, raw = _invoke_once(messages)
            usage = getattr(raw, "usage_metadata", None) or {}
            routed = RoutedTicket(
                category=decision.category,
                priority=derive_priority(decision),
                assigned_team=TAXONOMY[decision.category]["team"],
                reasoning=decision.reasoning,
                impact=decision.impact,
                urgency=decision.urgency,
                # confidence/needs_review are set deterministically in api.py (app/confidence.py)
            )
            return routed, {
                "model": MODEL,
                "latency_ms": int((time.perf_counter() - t0) * 1000),
                "prompt_tokens": usage.get("input_tokens"),
                "completion_tokens": usage.get("output_tokens"),
                "attempts": attempt,
                "ok": True,
                "fallback": False,
                "error": None,
            }
        except Exception as e:  # noqa: BLE001 — any failure triggers retry, then fallback
            last_error = str(e)
            if attempt <= MAX_RETRIES:
                # Layer 2: feed the error back so the model can self-correct, then back off.
                messages = build_messages(ticket) + [
                    HumanMessage(
                        content=f"Your previous response failed ({last_error}). "
                                f"Return a valid structured decision with all required fields."
                    )
                ]
                time.sleep(_RETRY_BACKOFF_S * attempt)

    # Layer 3: exhausted retries -> safe fallback, never a crash.
    return _fallback(), {
        "model": MODEL,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
        "prompt_tokens": None,
        "completion_tokens": None,
        "attempts": MAX_RETRIES + 1,
        "ok": False,
        "fallback": True,
        "error": last_error,
    }


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
