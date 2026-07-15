"""Curated corpus of past RESOLVED tickets for the retrieval layer.

Each entry is a previously-handled ticket plus how it was resolved. New tickets are
matched against these (by embedding similarity) and shown as a reference panel.
Seed them into Postgres with:  ../.venv/bin/python scripts/seed_resolved.py
"""

RESOLVED_TICKETS = [
    # access_iam
    {"ticket": "I can't connect to the VPN, it keeps rejecting my credentials.",
     "category": "access_iam",
     "resolution": "User's AD account was locked after failed attempts; unlocked it and reset the password. Advised re-enrolling the VPN MFA token."},
    {"ticket": "I don't have permission to view the finance dashboard anymore.",
     "category": "access_iam",
     "resolution": "Group membership was dropped during a role change; re-added the user to the finance-viewers group in Okta. Access restored within 15 min."},
    {"ticket": "SSO keeps looping back to the login page when I open the wiki.",
     "category": "access_iam",
     "resolution": "Stale SAML session cookie; cleared the user's cookies and re-established the SSO assertion. Root cause was a clock skew on the user's laptop, later fixed via NTP."},

    # infra_outage
    {"ticket": "The staging environment is completely unreachable for the whole team.",
     "category": "infra_outage",
     "resolution": "Load balancer health checks were failing after a bad deploy; rolled back the ingress config and restarted the LB. Added an alert on 5xx rates."},
    {"ticket": "Production API is returning 500s for everyone since this morning.",
     "category": "infra_outage",
     "resolution": "A database connection-pool exhaustion caused by a runaway job; killed the job, raised the pool size, and added a statement timeout."},
    {"ticket": "Office wifi drops every few minutes across the third floor.",
     "category": "infra_outage",
     "resolution": "Access point on the 3rd floor was overheating and rebooting; replaced the AP and rebalanced channels. No drops since."},

    # ci_cd
    {"ticket": "The deploy pipeline is stuck and nobody can ship to production.",
     "category": "ci_cd",
     "resolution": "The deploy runner ran out of disk; cleared old build artifacts and expanded the runner volume. Added a disk-usage alert."},
    {"ticket": "Nightly build has failed on the test stage for two days straight.",
     "category": "ci_cd",
     "resolution": "A flaky integration test depended on a third-party sandbox that changed its response; pinned the mock and quarantined the flaky test."},

    # security
    {"ticket": "I got a suspicious email asking for my password and I clicked the link.",
     "category": "security",
     "resolution": "Confirmed phishing; forced a password reset, revoked active sessions, and enabled step-up MFA. Reported the domain to the mail provider."},
    {"ticket": "Someone is trying to brute-force logins on our admin portal right now.",
     "category": "security",
     "resolution": "Enabled rate-limiting and temporary IP blocks at the WAF, rotated admin credentials, and reviewed access logs. No breach confirmed."},

    # dev_tooling
    {"ticket": "VS Code keeps crashing whenever I open our monorepo.",
     "category": "dev_tooling",
     "resolution": "The language server was indexing node_modules; added it to files.watcherExclude and bumped the memory limit. Crashes stopped."},
    {"ticket": "My local dev environment won't start after the latest pull.",
     "category": "dev_tooling",
     "resolution": "A new required env var wasn't documented; added it to .env.example and the setup script, and posted a migration note in the dev channel."},
    {"ticket": "Docker compose fails with a port conflict on startup.",
     "category": "dev_tooling",
     "resolution": "Another local service held port 5432; parameterized the port via env var and documented how to override it."},

    # hardware
    {"ticket": "My laptop battery no longer charges and dies within an hour.",
     "category": "hardware",
     "resolution": "Battery health was at 42%; replaced the battery under warranty and calibrated it. Loaner provided during the repair."},
    {"ticket": "My external monitor isn't detected when I dock the laptop.",
     "category": "hardware",
     "resolution": "Faulty dock DisplayPort; swapped the dock and updated the graphics driver. Both monitors now detected."},
    {"ticket": "The keyboard has several sticky keys and mistypes.",
     "category": "hardware",
     "resolution": "Debris under the keycaps; cleaned it, and when that didn't fully fix it, replaced the keyboard."},

    # unclassified / triage
    {"ticket": "Nothing works, please help.",
     "category": "unclassified",
     "resolution": "Reached out for detail; turned out to be a full building network outage already tracked under a separate incident. Linked the tickets."},

    # cross-category / ambiguous
    {"ticket": "I can't push my code because CI says my SSH key is unauthorized.",
     "category": "access_iam",
     "resolution": "Expired SSH key in the git provider; user re-added a fresh key and pushes succeeded. Documented the key-rotation steps."},
]
