"""Domain taxonomy, priority axes, and the Impact x Urgency matrix.

Single source of truth for categories -> teams and for how priority is derived.
Ported from v0.ipynb.
"""

TAXONOMY = {
    "access_iam":   {"team": "Identity and access",       "description": "An individual's login, permissions, SSO, or credential problem - NOT a system-wide outage"},
    "infra_outage": {"team": "Infrastructure operations", "description": "A system/service is down or unavailable (server, network, cloud, or a shared auth/SSO/access-control system being down)"},
    "ci_cd":        {"team": "Platform engineering",      "description": "Build and deployment pipeline failures"},
    "security":     {"team": "Security team",             "description": "Vulnerabilities, suspicious activity, security incidents"},
    "dev_tooling":  {"team": "Developer experience",      "description": "IDE, internal tools, environment setup issues"},
    "hardware":     {"team": "Hardware support",          "description": "Laptop, peripheral, or device issues"},
    "unclassified": {"team": "Triage",                    "description": "Ticket lacks enough detail to classify confidently"},
}

IMPACT_LEVELS = {
    "broad":  "Multiple people, a whole team, a shared/customer-facing service, or core infra (auth, network, CI that blocks all merges)",
    "narrow": "A single person or a small, non-critical scope",
}

URGENCY_LEVELS = {
    "blocked":    "Cannot do core work and no usable workaround (or an imminent, externally-imposed deadline with no workaround)",
    "workaround": "Work can continue - a workaround exists, or the issue is non-blocking / cosmetic / a request or question",
}

# Impact x Urgency -> Priority
PRIORITY_MATRIX = {
    ("broad",  "blocked"):    "High",
    ("broad",  "workaround"): "Medium",
    ("narrow", "blocked"):    "Medium",
    ("narrow", "workaround"): "Low",
}

# Applied in code AFTER the matrix (see classifier.derive_priority).
OVERRIDES = {
    "security":     "High",    # a security incident escalates regardless of assessed scope
    "unclassified": "Medium",  # safe default, flagged for review
}
