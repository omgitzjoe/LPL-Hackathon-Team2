"""
Streamlit Advisor Dashboard — Frontend UI

Implements the client side of the architecture diagram:
  Step 1: Assistant submits delegation request
  Step 2: Frontend sends prompt + simulated context data to the Lambda mock gate
  Step 6: Displays generated draft to Advisor for review
  Step 7: Advisor reviews draft and clicks [APPROVE & EXECUTE]
  Step 8: Success screen: "Logged to Audit"
"""
import os

import requests
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="LPL Delegation Assistant | AI-Powered", page_icon="👔", layout="wide")

DELEGATION_TEMPLATES = {
    "Portfolio Review": "Draft a comprehensive portfolio review",
    "Rebalancing Recommendation": "Draft a rebalancing recommendation with specific trade suggestions",
    "Tax-Loss Harvesting Analysis": "Analyze the portfolio for tax-loss harvesting opportunities and draft a summary",
    "Quarterly Update Letter": "Draft a quarterly update letter summarizing performance and market outlook",
    "Retirement Readiness Assessment": "Draft a retirement readiness assessment with projected income scenarios",
    "Risk Assessment Update": "Draft an updated risk assessment based on current market conditions",
    "Estate Planning Summary": "Draft an estate planning summary with beneficiary recommendations",
    "Custom Request": "",
}


@st.cache_data(ttl=30)
def fetch_clients():
    resp = requests.get(f"{BACKEND_URL}/clients", timeout=10)
    resp.raise_for_status()
    return resp.json()["clients"]


def fetch_client_detail(client_id: str) -> dict:
    resp = requests.get(f"{BACKEND_URL}/clients/{client_id}", timeout=10)
    resp.raise_for_status()
    return resp.json()["client"]


def fetch_audit_log():
    resp = requests.get(f"{BACKEND_URL}/audit-log", timeout=10)
    resp.raise_for_status()
    return resp.json()["audit_log"]


def submit_delegation_request(client_id: str, request_prompt: str, advisor: str) -> dict:
    resp = requests.post(
        f"{BACKEND_URL}/generate-draft",
        json={"client_id": client_id, "request_prompt": request_prompt, "advisor": advisor},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def request_revision(request_id: str, feedback: str) -> dict:
    resp = requests.post(
        f"{BACKEND_URL}/revise-draft",
        json={"request_id": request_id, "feedback": feedback},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def approve_and_execute(request_id: str, advisor: str) -> dict:
    resp = requests.post(
        f"{BACKEND_URL}/approve",
        json={"request_id": request_id, "advisor": advisor},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def render_client_card(client: dict):
    """Render a client profile card in the sidebar."""
    risk_colors = {
        "Conservative": "🟢",
        "Moderately Conservative": "🟢",
        "Moderate": "🟡",
        "Moderately Aggressive": "🟠",
        "Aggressive": "🔴",
    }
    risk_icon = risk_colors.get(client["risk_profile"], "⚪")

    st.markdown(f"### {client['name']}")
    st.markdown(f"**{risk_icon} {client['risk_profile']}**")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Portfolio Value", f"${client['portfolio_value']:,.0f}")
    with col2:
        delta_color = "normal" if client["ytd_return_pct"] >= 0 else "inverse"
        st.metric("YTD Return", f"{client['ytd_return_pct']}%", delta=f"{client['ytd_return_pct']}%", delta_color=delta_color)

    st.markdown(f"**Goals:** {client['goals']}")
    st.markdown(f"**Last Review:** {client['last_review_date']}")
    st.markdown(f"**Advisor:** {client['advisor']}")

    with st.expander("Holdings"):
        for h in client.get("holdings", []):
            st.markdown(f"- **{h['symbol']}** {h['name']} — {h['allocation_pct']}%")


def main():
    st.markdown(
        """
        <style>
        .block-container { padding-top: 2rem; }
        [data-testid="stMetricValue"] { font-size: 1.3rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("👔 LPL Delegation Assistant")
    st.caption("AI-powered document drafting with human-in-the-loop approval  •  Powered by Amazon Bedrock (Claude 3.5 Sonnet)")

    if "active_request" not in st.session_state:
        st.session_state.active_request = None
    if "just_approved" not in st.session_state:
        st.session_state.just_approved = None

    try:
        clients = fetch_clients()
    except requests.RequestException as e:
        st.error(f"Could not reach backend at {BACKEND_URL}: {e}")
        st.info("Start the backend with: `uvicorn backend.server:app --reload --port 8000`")
        return

    client_options = {f"{c['name']} ({c['risk_profile']})": c["client_id"] for c in clients}

    with st.sidebar:
        st.markdown("### 👤 Advisor")
        advisor_name = st.text_input("Your name", value="Michael Chen", label_visibility="collapsed")
        st.divider()

        st.markdown("### 📋 Select Client")
        selected_label = st.selectbox("Client", list(client_options.keys()), label_visibility="collapsed")
        client_id = client_options[selected_label]

        try:
            client_detail = fetch_client_detail(client_id)
            st.divider()
            render_client_card(client_detail)
        except requests.RequestException:
            pass

    tab_delegate, tab_audit = st.tabs(["📝 Delegate a Task", "📜 Audit Log"])

    with tab_delegate:
        if not st.session_state.active_request:
            st.subheader("New Delegation Request")

            template_name = st.selectbox("Request type", list(DELEGATION_TEMPLATES.keys()))
            template_text = DELEGATION_TEMPLATES[template_name]

            client_name = selected_label.split(" (")[0]
            if template_name == "Custom Request":
                request_prompt = st.text_area(
                    "Describe what you want drafted",
                    placeholder=f"e.g. Draft a portfolio review for {client_name} focusing on recent market changes...",
                    height=100,
                )
            else:
                default_prompt = f"{template_text} for {client_name}"
                request_prompt = st.text_area(
                    "Request details (edit to customize)",
                    value=default_prompt,
                    height=100,
                )

            st.divider()
            if st.button("🚀 Generate Draft", type="primary", use_container_width=True):
                if not request_prompt.strip():
                    st.warning("Please describe what you want drafted.")
                else:
                    with st.spinner("Generating draft via Amazon Bedrock..."):
                        try:
                            result = submit_delegation_request(client_id, request_prompt, advisor_name)
                            st.session_state.active_request = result
                            st.session_state.just_approved = None
                            st.rerun()
                        except requests.RequestException as e:
                            st.error(f"Error generating draft: {e}")

        req = st.session_state.active_request
        if req:
            revision_count = req.get("revision_count", 0)
            revision_badge = f"  ·  Revision #{revision_count}" if revision_count > 0 else ""

            st.subheader("Review Draft")

            status_color = "🟡" if req["status"] == "PENDING_APPROVAL" else "🟢"
            st.markdown(
                f"{status_color} **{req['status']}**  ·  "
                f"`{req['request_id']}`  ·  "
                f"**{req['client_name']}**"
                f"{revision_badge}"
            )

            st.text_area("Draft document", value=req["draft"], height=400, key="draft_area", disabled=True)

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("✅ Approve & Execute", type="primary", use_container_width=True):
                    try:
                        approval = approve_and_execute(req["request_id"], advisor_name)
                        st.session_state.just_approved = approval
                        st.session_state.active_request = None
                        st.rerun()
                    except requests.RequestException as e:
                        st.error(f"Error approving request: {e}")
            with col2:
                if st.button("✏️ Request Revision", use_container_width=True):
                    st.session_state.show_revision = True
            with col3:
                if st.button("🗑️ Discard", use_container_width=True):
                    st.session_state.active_request = None
                    st.session_state.pop("show_revision", None)
                    st.rerun()

            if st.session_state.get("show_revision"):
                st.divider()
                st.markdown("#### ✏️ Revision Feedback")
                feedback = st.text_area(
                    "What should be changed?",
                    placeholder="e.g. Make the tone more conservative, add a section on tax implications, shorten the intro...",
                    height=100,
                    key="revision_feedback",
                )
                if st.button("📤 Submit Revision", type="primary"):
                    if not feedback.strip():
                        st.warning("Please provide feedback describing what to change.")
                    else:
                        with st.spinner("Revising draft via Amazon Bedrock..."):
                            try:
                                revised = request_revision(req["request_id"], feedback)
                                st.session_state.active_request = revised
                                st.session_state.pop("show_revision", None)
                                st.rerun()
                            except requests.RequestException as e:
                                st.error(f"Error revising draft: {e}")

        if st.session_state.just_approved:
            approval = st.session_state.just_approved
            st.balloons()
            st.success("Approved and logged to audit trail")
            with st.expander("Audit Entry Details", expanded=True):
                st.json(approval["audit_entry"])
            if st.button("📝 Start New Request"):
                st.session_state.just_approved = None
                st.rerun()

    with tab_audit:
        st.subheader("Audit Trail")
        try:
            entries = fetch_audit_log()
        except requests.RequestException as e:
            st.error(f"Could not reach backend at {BACKEND_URL}: {e}")
            return

        if not entries:
            st.info("No approved actions yet. Approve a draft to see it logged here.")
        else:
            st.caption(f"{len(entries)} total approved actions")

            col1, col2 = st.columns([3, 1])
            with col2:
                csv_data = "Timestamp,Request ID,Client,Advisor,Action,Request\n"
                for e in reversed(entries):
                    csv_data += f"{e['timestamp']},{e['request_id']},{e['client_name']},{e['advisor']},{e['action']},\"{e['request_prompt']}\"\n"
                st.download_button(
                    "📥 Export CSV",
                    data=csv_data,
                    file_name="lpl_audit_log.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

            st.dataframe(
                [
                    {
                        "Timestamp": e["timestamp"],
                        "Request ID": e["request_id"],
                        "Client": e["client_name"],
                        "Advisor": e["advisor"],
                        "Action": e["action"],
                        "Request": e["request_prompt"],
                    }
                    for e in reversed(entries)
                ],
                use_container_width=True,
                hide_index=True,
            )


if __name__ == "__main__":
    main()
