"""Few-shot prompt construction. Ported from v0.ipynb, emitting LangChain messages."""
import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .taxonomy import IMPACT_LEVELS, TAXONOMY, URGENCY_LEVELS


def build_system_prompt() -> str:
    taxonomy_lines = "\n".join(
        f"- {cat}: {info['description']} (routed to: {info['team']})"
        for cat, info in TAXONOMY.items()
    )
    impact_lines = "\n".join(f"- {k}: {v}" for k, v in IMPACT_LEVELS.items())
    urgency_lines = "\n".join(f"- {k}: {v}" for k, v in URGENCY_LEVELS.items())
    return f"""You are KRISIS, a smart triage system for an internal IT and engineering support desk.

For each raw ticket, reason step by step, THEN commit:
1. analysis: briefly weigh the situation - what is affected, who is blocked, is there a workaround.
2. impact: choose one.
3. urgency: choose one.
4. category: choose exactly one.
5. reasoning: one line naming the impact + urgency (and any tie-break) that drove the decision.

You do NOT choose priority or the team. Priority is computed from impact x urgency, and the
team is assigned from the category - both automatically, downstream. Judge on facts, not tone:
an angry ticket is not more urgent than a calm one describing the same problem.

Impact:
{impact_lines}

Urgency:
{urgency_lines}

Categories (pick exactly one) and the team each is routed to:
{taxonomy_lines}

Calibration anchors (impact + urgency -> resulting priority):
- broad + blocked  -> High   e.g. "Prod API returns 500s for everyone, no workaround."
- broad + workaround -> Medium  e.g. "Team wiki is down but the info is mirrored in Slack."
- narrow + blocked -> Medium  e.g. "I'm locked out of my account and can't work."
- narrow + workaround -> Low  e.g. "Typo on the internal dashboard header." / "Please grant me access to the analytics tool."

Rules:
- If the message lacks enough detail to classify confidently, use category "unclassified" and
  neutral defaults impact="narrow", urgency="workaround" (priority is set to Medium downstream).
- A security incident is category "security" regardless of scope.
"""


FEWSHOT = [
    # Edge case 1 - angry tone must NOT inflate priority
    {
        "ticket": "This is RIDICULOUS. I've been locked out of my account for two hours and nobody is helping. Reset my password NOW.",
        "decision": {
            "analysis": "One person locked out of their account, no workaround mentioned. Angry tone is irrelevant to impact. This is an account/credential issue.",
            "impact": "narrow",
            "urgency": "blocked",
            "category": "access_iam",
            "reasoning": "narrow + blocked -> Medium; category access_iam (account lockout). Tone ignored per the impact-only rule.",
        },
    },
    # Edge case 2 - very short / vague message
    {
        "ticket": "it's broken",
        "decision": {
            "analysis": "No system, scope, or impact can be identified from the message. Not enough detail to classify confidently.",
            "impact": "narrow",
            "urgency": "workaround",
            "category": "unclassified",
            "reasoning": "Insufficient-detail rule -> unclassified with neutral defaults; priority set to Medium downstream, flagged for review.",
        },
    },
    # Edge case 3 - could fit more than one category
    {
        "ticket": "I can't push my code - the CI pipeline rejects my SSH key as unauthorized.",
        "decision": {
            "analysis": "Symptom is in CI, but the root cause is an unauthorized credential (SSH key), which is access/IAM. Affects one engineer, who is blocked from pushing.",
            "impact": "narrow",
            "urgency": "blocked",
            "category": "access_iam",
            "reasoning": "Fits ci_cd and access_iam; chose access_iam because the root cause is an unauthorized credential, not a pipeline defect. narrow + blocked -> Medium.",
        },
    },
]


def build_messages(ticket: str):
    """System prompt + few-shot turns + the live ticket, as LangChain messages."""
    messages = [SystemMessage(content=build_system_prompt())]
    for ex in FEWSHOT:
        messages.append(HumanMessage(content=ex["ticket"]))
        messages.append(AIMessage(content=json.dumps(ex["decision"])))
    messages.append(HumanMessage(content=ticket))
    return messages
