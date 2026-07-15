"""Pydantic models shared across the LLM call and the API contract."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

Category = Literal[
    "access_iam", "infra_outage", "ci_cd", "security",
    "dev_tooling", "hardware", "unclassified",
]
Priority = Literal["High", "Medium", "Low"]      # derived, not chosen by the LLM
Impact = Literal["broad", "narrow"]
Urgency = Literal["blocked", "workaround"]
Confidence = Literal["high", "medium", "low"]    # the model's self-reported certainty


class TicketDecision(BaseModel):
    """LLM output schema. Field ORDER matters: the model reasons first, then commits.
    priority and assigned_team are derived in code from these fields."""
    analysis: str = Field(..., description="Think first: weigh impact, urgency, and category")
    impact: Impact = Field(..., description="broad = many people / shared or critical service; narrow = one person / small scope")
    urgency: Urgency = Field(..., description="blocked = no usable workaround; workaround = work can continue")
    category: Category = Field(..., description="One of the fixed taxonomy categories")
    reasoning: str = Field(..., description="2-3 sentences explaining the key signal in the ticket, the impact + urgency judgement (and any tie-break), and the resulting category/routing")
    confidence: Confidence = Field(..., description="How sure you are: high = clear; medium = some ambiguity; low = vague/ambiguous/insufficient detail")


class ClassifyRequest(BaseModel):
    """POST /classify request body."""
    ticket: str = Field(..., description="Raw ticket message, exactly as an employee typed it")


class RoutedTicket(BaseModel):
    """POST /classify response — the canonical 4-field contract plus the model's assessment."""
    category: Category
    priority: Priority
    assigned_team: str
    reasoning: str
    # surfaced for transparency (defensible priority); not part of the minimal contract
    impact: Impact
    urgency: Urgency
    # confidence-aware routing: model's certainty + whether a human should review
    confidence: Confidence = "high"
    needs_review: bool = False
    # cache provenance (set when the answer was reused from a near-duplicate past ticket)
    cached: bool = False
    source_ticket_id: Optional[int] = None
    similarity: Optional[float] = None
    # similar past SUBMITTED tickets (from ticket_log), for the reference panel
    similar_past: list = Field(default_factory=list)
