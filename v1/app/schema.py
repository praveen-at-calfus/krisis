"""Pydantic models shared across the LLM call and the API contract."""
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal[
    "access_iam", "infra_outage", "ci_cd", "security",
    "dev_tooling", "hardware", "unclassified",
]
Priority = Literal["High", "Medium", "Low"]      # derived, not chosen by the LLM
Impact = Literal["broad", "narrow"]
Urgency = Literal["blocked", "workaround"]


class TicketDecision(BaseModel):
    """LLM output schema. Field ORDER matters: the model reasons first, then commits.
    priority and assigned_team are derived in code from these fields."""
    analysis: str = Field(..., description="Think first: weigh impact, urgency, and category")
    impact: Impact = Field(..., description="broad = many people / shared or critical service; narrow = one person / small scope")
    urgency: Urgency = Field(..., description="blocked = no usable workaround; workaround = work can continue")
    category: Category = Field(..., description="One of the fixed taxonomy categories")
    reasoning: str = Field(..., description="One line citing the impact + urgency that drove the decision")


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
