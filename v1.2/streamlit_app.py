"""KRISIS Streamlit UI — a thin CLIENT of the FastAPI backend (never talks to LLM/DB directly)."""
import os

import requests
import streamlit as st

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

st.set_page_config(page_title="KRISIS — Smart Triage", page_icon="🛎️", layout="wide")

PRIORITY_COLOR = {"High": "🔴 High", "Medium": "🟠 Medium", "Low": "🟢 Low"}


def api_get(path: str, **params):
    r = requests.get(f"{API_BASE}{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def api_post(path: str, payload: dict):
    r = requests.post(f"{API_BASE}{path}", json=payload, timeout=60)
    return r


st.title("🛎️ KRISIS — Your Smart Triage System")
st.caption(f"Client of the FastAPI backend at `{API_BASE}`")


def render_incident_banner(inc: dict):
    """Pulsing red alarm for the managing team (Dashboard only), with a dismiss control.
    Dismissal is per-incident: a new/different incident re-alarms."""
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


tab_classify, tab_dashboard = st.tabs(["Classify a ticket", "Dashboard"])

# ---------------------------------------------------------------- Classify
with tab_classify:
    ticket = st.text_area(
        "Paste a raw ticket message",
        height=140,
        placeholder="e.g. The CI pipeline rejects my SSH key as unauthorized and I can't push.",
    )
    if st.button("Route ticket", type="primary"):
        if not ticket.strip():
            st.warning("Please enter a ticket message.")
        else:
            try:
                resp = api_post("/classify", {"ticket": ticket})
            except requests.RequestException as e:
                st.error(f"Could not reach the API at {API_BASE}: {e}")
            else:
                if resp.status_code == 200:
                    d = resp.json()
                    if d.get("cached"):
                        st.success(
                            f"♻️ Answer reused from ticket #{d['source_ticket_id']} "
                            f"(similarity {d['similarity']:.2f}) — no LLM call, time & tokens saved."
                        )
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Category", d["category"])
                    c2.metric("Priority", PRIORITY_COLOR.get(d["priority"], d["priority"]))
                    c3.metric("Assigned team", d["assigned_team"])
                    st.markdown(f"**Reasoning:** {d['reasoning']}")
                    st.caption(
                        f"Assessment — impact: `{d['impact']}` · urgency: `{d['urgency']}` "
                        f"· confidence: `{d.get('confidence', 'high')}`"
                    )
                    if d.get("needs_review"):
                        st.warning(
                            "⚠️ Low-confidence classification — **flagged for human review**. "
                            "The suggestion above should be confirmed by an agent."
                        )

                    # Panel 1: similar past SUBMITTED tickets (from ticket_log)
                    st.divider()
                    st.subheader("🗂️ Similar past tickets you've submitted")
                    past = [p for p in d.get("similar_past", []) if p["score"] >= 0.5]
                    if past:
                        for p in past:
                            reused = d.get("cached") and p["id"] == d.get("source_ticket_id")
                            tag = "  ← answer reused from this" if reused else ""
                            with st.expander(
                                f"{p['score']:.2f} · #{p['id']} · {p['category']}/{p['priority']}"
                                f" — {p['ticket_text'][:60]}{tag}"
                            ):
                                st.markdown(f"**Reasoning:** {p['reasoning']}")
                    else:
                        st.caption("No similar past submitted tickets found.")

                    # Panel 2: how similar issues were RESOLVED (curated corpus)
                    try:
                        similar = api_get("/similar", ticket=ticket).get("similar", [])
                    except requests.RequestException:
                        similar = []
                    st.subheader("🔎 How similar issues were resolved")
                    if similar:
                        for s in similar:
                            with st.expander(
                                f"{s['score']:.2f} · {s['category']} — {s['ticket_text'][:70]}"
                            ):
                                st.markdown(f"**Resolution:** {s['resolution']}")
                    else:
                        st.caption("No resolved tickets yet — run `scripts/seed_resolved.py` to seed the corpus.")
                else:
                    detail = resp.json().get("detail", resp.text)
                    st.error(f"API returned {resp.status_code}: {detail}")

# ---------------------------------------------------------------- Dashboard
with tab_dashboard:
    if st.button("Refresh"):
        st.rerun()
    try:
        stats = api_get("/stats")
        timing = api_get("/timing")
        incident = api_get("/incidents")
        recent = api_get("/tickets", limit=50).get("tickets", [])
    except requests.RequestException as e:
        st.error(f"Could not load dashboard from {API_BASE}: {e}")
    else:
        # Incident alarm — managing team only (Dashboard), dismissible
        render_incident_banner(incident)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total tickets", stats.get("total", 0))
        m2.metric("Needs review", stats.get("needs_review", 0))
        m3.metric("Failures", stats.get("failures", 0))
        m4.metric("Avg latency (ms)", stats.get("avg_latency_ms") or "—")

        # Before/after: manual triage vs KRISIS
        st.subheader("⏱️ Time saved vs manual triage")
        def _mins(sec):
            return f"{sec/60:.1f} min" if sec else "—"
        t1, t2, t3 = st.columns(3)
        t1.metric("Manual (est.)", _mins(timing.get("manual_total_seconds", 0)),
                  help=f"{timing.get('manual_baseline_seconds_per_ticket', 300)}s/ticket assumed")
        t2.metric("KRISIS (actual)", f"{timing.get('automated_total_seconds', 0):.1f} s")
        t3.metric("Time saved", _mins(timing.get("time_saved_seconds", 0)))

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
                        "ok": r["ok"],
                    }
                    for r in recent
                ],
                use_container_width=True,
            )
        else:
            st.info("No tickets logged yet. Classify one, then refresh.")
