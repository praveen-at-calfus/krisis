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
6. confidence: high / medium / low - how sure you are of the category. Use "low" when the ticket is vague, could fit multiple categories, or lacks detail; "medium" when there is some ambiguity you had to resolve; "high" when the category is clear. (Low-confidence tickets are flagged for human review downstream.)

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
- Classify by the clearest signal, even when the ticket is brief. A short message that names or
  clearly implies a category MUST be classified (e.g. "my access is blocked" -> access_iam;
  "the entire system is down" -> infra_outage). Brevity alone is NOT a reason to use unclassified.
- Use category "unclassified" ONLY when there is no recognizable category signal at all
  (e.g. "it's broken", "help", "please fix"), with neutral defaults impact="narrow",
  urgency="workaround" (priority is set to Medium downstream).
- Scope words like "everyone", "all", "entire", "company-wide" indicate broad impact.
- A security incident is category "security" regardless of scope.
- Outage vs individual access: if a ticket says a system, service, or platform is
  down / unavailable / not responding / offline - INCLUDING an authentication, SSO, or
  access-control SYSTEM - classify it as "infra_outage" (a service outage the infra team
  restores). Use "access_iam" only for an INDIVIDUAL's access problem (e.g. "I can't log in",
  "my access is blocked", "my permissions"), where no system-wide outage is described.
- Tickets may be written in any language; classify them the same way.
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
            "confidence": "high",
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
            "confidence": "low",
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
            "confidence": "medium",
        },
    },
    # Edge case 4 - brief BUT has a clear category signal -> classify, do NOT use unclassified
    {
        "ticket": "my access is completely blocked",
        "decision": {
            "analysis": "Brief, but 'access' is a clear access/credentials signal. One person cannot get in and no workaround is implied.",
            "impact": "narrow",
            "urgency": "blocked",
            "category": "access_iam",
            "reasoning": "Although the ticket is brief, the word 'access' is a clear individual access/credentials signal, so it should be classified rather than sent to unclassified. One person cannot get in and no workaround is described, which makes the impact narrow and the urgency blocked. It is categorised access_iam and, as narrow + blocked, resolves to Medium priority.",
            "confidence": "high",
        },
    },
    # Edge case 5 - brief BUT scope word signals a broad outage -> infra_outage, not unclassified
    {
        "ticket": "the entire system is down",
        "decision": {
            "analysis": "'Entire system' signals a broad infrastructure outage affecting everyone, with no workaround. Brief, but the signal is clear.",
            "impact": "broad",
            "urgency": "blocked",
            "category": "infra_outage",
            "reasoning": "The phrase 'entire system' signals a broad outage affecting everyone rather than a single user, so the impact is broad. With the system down and no workaround available, the urgency is blocked. A system being unavailable is an infrastructure failure, so it is categorised infra_outage and, as broad + blocked, resolves to High priority.",
            "confidence": "high",
        },
    },
    # Edge case 6 - an access SYSTEM being down is an OUTAGE (failure wins), not an individual access issue
    {
        "ticket": "the access control system is down",
        "decision": {
            "analysis": "The access-control SYSTEM itself is down - a shared service outage, not one person's access problem. It blocks many users from authenticating.",
            "impact": "broad",
            "urgency": "blocked",
            "category": "infra_outage",
            "reasoning": "The access-control system itself is down, which is a shared service outage rather than one individual's access problem, so 'failure wins' and it belongs to infra_outage instead of access_iam. Because the outage blocks many users from authenticating, the impact is broad and the urgency is blocked. It is routed to Infrastructure operations at High priority (broad + blocked).",
            "confidence": "high",
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
