"""Few-shot prompt construction. Ported from v0.ipynb, emitting LangChain messages."""
import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.taxonomy import IMPACT_LEVELS, TAXONOMY, URGENCY_LEVELS


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
5. reasoning: 2-3 full sentences that (a) name the key signal in the ticket, (b) explain the impact and urgency judgement and any tie-break, and (c) state the resulting category and how it routes. Be specific and complete, not a single terse line.

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
            "reasoning": "The ticket describes a single user locked out of their own account with no workaround, so the impact is narrow and the urgency is blocked. The aggressive, all-caps tone does not change anything, since priority is driven by impact and blockage rather than wording. This is an individual credential problem, so it is categorised access_iam and, as narrow + blocked, resolves to Medium priority.",
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
            "reasoning": "The message gives no system, scope, or symptom, so there is no recognizable category signal to act on. Following the insufficient-detail rule, it is categorised unclassified with neutral defaults of narrow impact and workaround urgency. It is routed to Triage at Medium priority and flagged so a human can request the missing detail.",
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
            "reasoning": "The symptom appears in the CI pipeline, but the root cause is an unauthorized SSH credential, which is an access/IAM problem rather than a pipeline defect. It affects one engineer who is blocked from pushing, so the impact is narrow and the urgency is blocked. Choosing root cause over symptom, it is categorised access_iam and resolves to Medium priority (narrow + blocked).",
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
