"""20 diverse demo tickets for evaluation.

Covers all 7 categories, the 3 required edge cases (angry / vague / ambiguous),
non-English input, a very long ticket, and the two brief-but-clear regressions.
`expect_*` are eyeballing hints, not hard assertions (priority can be defensible either way).
"""

DEMO_TICKETS = [
    # --- one clear example per category ---
    {"ticket": "I can't log into the VPN, it rejects my password every time.",
     "expect_category": "access_iam", "expect_priority": "Medium"},
    {"ticket": "The entire production cluster is unreachable and every service is returning 500s.",
     "expect_category": "infra_outage", "expect_priority": "High"},
    {"ticket": "Our Jenkins deploy pipeline is stuck and nobody can ship to production.",
     "expect_category": "ci_cd", "expect_priority": "High"},
    {"ticket": "I got an email asking for my company password and I think I clicked the link.",
     "expect_category": "security", "expect_priority": "High"},
    {"ticket": "VS Code keeps crashing every time I open our monorepo.",
     "expect_category": "dev_tooling", "expect_priority": "Medium"},
    {"ticket": "My laptop battery no longer charges; it dies within an hour.",
     "expect_category": "hardware", "expect_priority": "Medium"},

    # --- required edge cases ---
    # angry tone must NOT inflate priority (and it's a request -> Low)
    {"ticket": "THIS IS COMPLETELY UNACCEPTABLE — I've asked THREE TIMES for access to the analytics dashboard!!!",
     "expect_category": "access_iam", "expect_priority": "Low"},
    # vague / no signal -> unclassified
    {"ticket": "it's broken",
     "expect_category": "unclassified", "expect_priority": "Medium"},
    # ambiguous: symptom in CI, root cause is access
    {"ticket": "I can't push to the repo — CI says my SSH key is unauthorized.",
     "expect_category": "access_iam", "expect_priority": "Medium"},

    # --- brief-but-clear regressions (the deferred v1.1 fix) ---
    {"ticket": "the entire system is down",
     "expect_category": "infra_outage", "expect_priority": "High"},
    {"ticket": "my access is completely blocked",
     "expect_category": "access_iam", "expect_priority": "Medium"},

    # --- non-English (Spanish): need access to the admin panel, can't get in ---
    {"ticket": "Necesito acceso al panel de administración, no puedo entrar.",
     "expect_category": "access_iam", "expect_priority": "Medium"},

    # --- more coverage / priority spread ---
    {"ticket": "Someone is actively brute-forcing logins on our admin portal right now.",
     "expect_category": "security", "expect_priority": "High"},
    {"ticket": "The office wifi drops every few minutes across the whole floor.",
     "expect_category": "infra_outage", "expect_priority": "Medium"},
    {"ticket": "My monitor has a single dead pixel in the corner.",
     "expect_category": "hardware", "expect_priority": "Low"},
    {"ticket": "Could we add a dark mode to the internal dashboard sometime?",
     "expect_category": "dev_tooling", "expect_priority": "Low"},
    {"ticket": "The nightly build has failed on the test stage for two days straight.",
     "expect_category": "ci_cd", "expect_priority": "Medium"},
    {"ticket": "I need a new keyboard; one key is sticky but I can still type.",
     "expect_category": "hardware", "expect_priority": "Low"},
    {"ticket": "help please",
     "expect_category": "unclassified", "expect_priority": "Medium"},

    # --- very long input (must not crash; should still classify) ---
    {"ticket": (
        "Hi team, I wanted to flag something that has been going on since this morning and is "
        "getting worse. Around 9am I noticed that our shared staging environment was responding "
        "very slowly, and by 10am several of my teammates on the payments squad also said they "
        "couldn't reach it at all. We tried the usual things — clearing caches, reconnecting to "
        "the VPN, restarting our machines — but nothing helped. The health dashboard shows the "
        "staging database as unreachable and the API gateway is throwing gateway timeouts for "
        "everyone on the floor. This is blocking the entire squad from testing the release we are "
        "supposed to ship on Friday, and QA can't run their suites either. There is no workaround "
        "that we can find. Could someone from infrastructure take a look as soon as possible? "
        "Happy to jump on a call and share screens if that helps. Thanks so much."),
     "expect_category": "infra_outage", "expect_priority": "High"},
]

assert len(DEMO_TICKETS) == 20, f"expected 20 tickets, got {len(DEMO_TICKETS)}"
