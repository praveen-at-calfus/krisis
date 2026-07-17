"""KRISIS Streamlit UI — a thin CLIENT of the FastAPI backend.

Lightweight RBAC (no auth): a landing page ('Use krisis') opens a modal role
picker routing to two role-scoped views — 'Register a ticket' (employees) and
'Manage tickets' (managing team). A top-right 'Swap role' toggles between them.
"""
import os

import requests
import streamlit as st

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

st.set_page_config(page_title="krisis. for your crisis.", page_icon="♾️", layout="wide")

PRIORITY_COLOR = {"High": "🔴 High", "Medium": "🟠 Medium", "Low": "🟢 Low"}


def api_get(path: str, **params):
    r = requests.get(f"{API_BASE}{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def api_post(path: str, payload: dict):
    return requests.post(f"{API_BASE}{path}", json=payload, timeout=60)


@st.dialog("How would you like to use krisis?")
def role_dialog():
    """Semi-transparent modal role picker: a green box and a blue box."""
    st.markdown(
        """
        <style>
        .st-key-pick_employee button {
            background:#16a34a; color:#fff; border:none; font-weight:700; padding:14px 0;
        }
        .st-key-pick_employee button:hover { background:#15803d; color:#fff; }
        .st-key-pick_manager button {
            background:#2563eb; color:#fff; border:none; font-weight:700; padding:14px 0;
        }
        .st-key-pick_manager button:hover { background:#1d4ed8; color:#fff; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Register a ticket", key="pick_employee", use_container_width=True):
        st.session_state["role"] = "employee"
        st.rerun()
    if st.button("Manage tickets", key="pick_manager", use_container_width=True):
        st.session_state["role"] = "manager"
        st.rerun()


def page_header(title: str, current_role: str):
    """Page title with a top-right 'Swap role' button that toggles directly (no consent)."""
    left, right = st.columns([5, 1], vertical_alignment="center")
    with left:
        st.title(title)
    with right:
        if st.button("⇄ Swap role", key="swap_role", use_container_width=True):
            st.session_state["role"] = "manager" if current_role == "employee" else "employee"
            st.rerun()


def render_incident_banner(inc: dict):
    """Pulsing red alarm for the managing team, with a dismiss control (per-incident)."""
    if not inc.get("active"):
        return
    key = f"{inc.get('category')}::{inc.get('since')}"
    if st.session_state.get("dismissed_incident") == key:
        return
    since = (inc.get("since") or "")[:16].replace("T", " ")
    st.markdown(
        f"""
        <style>
        @keyframes krisisPulse {{ 0%{{opacity:1}} 50%{{opacity:.4}} 100%{{opacity:1}} }}
        .krisis-alarm {{
            background:#b00020; color:#fff; padding:16px 20px; border-radius:10px;
            font-weight:800; font-size:1.15rem; text-align:center; margin:4px 0 10px 0;
            box-shadow:0 0 14px rgba(176,0,32,.6); animation:krisisPulse 1s ease-in-out infinite;
        }}
        </style>
        <div class="krisis-alarm">
            🚨 POSSIBLE INCIDENT — {inc['count']} consecutive <u>{inc['category']}</u> tickets
            within {inc['window_min']} min (since {since}). Investigate now.
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Dismiss alarm", key="dismiss_incident_btn"):
        st.session_state["dismissed_incident"] = key
        st.rerun()


# ---------------------------------------------------------------- Landing
def landing():
    st.markdown(
        """
        <div style="text-align:center; margin:14vh 0 2rem 0;">
            <h1 style="font-size:3.4rem; font-weight:800; margin:0; letter-spacing:-1px;">
                ♾️ krisis. <span style="opacity:.6;">for your crisis.</span>
            </h1>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns([2, 1, 2])
    with c2:
        if st.button("Use krisis", type="primary", use_container_width=True, key="use_krisis"):
            role_dialog()


# ---------------------------------------------------------------- Employee
def employee_page():
    page_header("🎫 Register a ticket", "employee")
    ticket = st.text_area(
        "Describe your issue",
        height=140,
        placeholder="e.g. I can't connect to the VPN — it keeps rejecting my credentials.",
    )
    if st.button("Submit ticket", type="primary"):
        if not ticket.strip():
            st.warning("Please describe your issue before submitting.")
            return
        try:
            resp = api_post("/classify", {"ticket": ticket})
        except requests.RequestException as e:
            st.error(f"Couldn't reach the support service right now: {e}")
            return
        if resp.status_code == 200:
            d = resp.json()
            st.success(
                f"✅ **Ticket submitted successfully.** It's been logged as a "
                f"**{d['priority']}**-priority **{d['category']}** ticket, and the "
                f"**{d['assigned_team']}** team will get back to you."
            )
            st.markdown(f"**Why it was routed this way:** {d['reasoning']}")
            st.caption(f"Assessment — impact: `{d['impact']}` · urgency: `{d['urgency']}`")

            # How similar issues have been resolved (solutions, no scores)
            try:
                similar = api_get("/similar", ticket=ticket).get("similar", [])
            except requests.RequestException:
                similar = []
            if similar:
                st.divider()
                st.subheader("💡 How similar issues have been resolved")
                st.caption("These may help you resolve it yourself while you wait.")
                for s in similar:
                    with st.expander(f"{s['category']} — {s['ticket_text'][:80]}"):
                        st.markdown(f"**Resolution:** {s['resolution']}")
        elif resp.status_code == 422:
            st.warning("That message looks empty or too long — please shorten it and try again.")
        else:
            st.error("Something went wrong submitting your ticket. Please try again shortly.")


# ---------------------------------------------------------------- Manager
def manager_page():
    page_header("📊 Manage tickets", "manager")
    if st.button("Refresh"):
        st.rerun()
    try:
        stats = api_get("/stats")
        incident = api_get("/incidents")
        recent = api_get("/tickets", limit=50).get("tickets", [])
    except requests.RequestException as e:
        st.error(f"Could not load the dashboard from {API_BASE}: {e}")
        return

    render_incident_banner(incident)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total tickets", stats.get("total", 0))
    m2.metric("Needs review", stats.get("needs_review", 0))
    m3.metric("Failures", stats.get("failures", 0))
    m4.metric("Avg latency (ms)", stats.get("avg_latency_ms") or "—")

    st.subheader("💰 LLM cost")
    k1, k2, k3 = st.columns(3)
    k1.metric("Total cost", f"${stats.get('total_cost_usd', 0):.4f}")
    k2.metric("Avg / ticket", f"${stats.get('avg_cost_per_ticket_usd', 0):.5f}")
    k3.metric("Saved by cache (est.)", f"${stats.get('est_cost_saved_usd', 0):.4f}",
              help=f"{stats.get('cache_hits', 0)} cache hits skipped the LLM")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("By priority")
        st.bar_chart(stats.get("by_priority", {}))
    with col_b:
        st.subheader("By category")
        st.bar_chart(stats.get("by_category", {}))

    st.subheader("Recent tickets")
    if recent:
        st.dataframe(
            [
                {
                    "when": r["created_at"],
                    "ticket": (r["ticket_text"] or "")[:60],
                    "category": r["category"],
                    "priority": r["priority"],
                    "team": r["assigned_team"],
                    "conf": r.get("confidence"),
                    "review": "⚠️" if r.get("needs_review") else "",
                    "cost $": f"{r.get('cost_usd', 0):.5f}",
                    "status": "✓" if r["ok"] else "⚠ fallback",
                }
                for r in recent
            ],
            use_container_width=True,
        )
    else:
        st.info("No tickets logged yet. Register one, then refresh.")


# ---------------------------------------------------------------- Route by role
_role = st.session_state.get("role")
if _role == "employee":
    employee_page()
elif _role == "manager":
    manager_page()
else:
    landing()
