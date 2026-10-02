"""
Streamlit Advisor Dashboard — Frontend UI

Implements the client side of the architecture diagram:
  Step 1: Assistant submits delegation request (e.g. "Draft portfolio review for Jane Doe")
  Step 2: Frontend sends prompt + simulated context data to the Lambda mock gate
  Step 6: Displays generated draft to Advisor for review
  Step 7: Advisor reviews draft and clicks [APPROVE & EXECUTE]
  Step 8: Success screen: "Logged to Audit"
"""
import os

import requests
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="LPL Delegation Assistant", page_icon="👔", layout="wide")


@st.cache_data(ttl=30)
def fetch_clients():
    resp = requests.get(f"{BACKEND_URL}/clients", timeout=10)
    resp.raise_for_status()
    return resp.json()["clients"]


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


def main():
    st.title("👔 LPL Delegation Assistant")
    st.caption("Submit a delegation request → AI drafts the document → Advisor reviews & approves")

    with st.sidebar:
        st.header("ℹ️ About")
        st.markdown(
            """
            This dashboard lets an advisor **delegate** document drafting
            (e.g. portfolio reviews) to an AI assistant.

            **Flow:**
            1. Submit a delegation request
            2. AI drafts the document via Amazon Bedrock (Claude 3.5 Sonnet),
               using mock client data and LPL compliance guardrails
            3. Review the draft
            4. Approve & Execute → action is logged to the audit trail
            """
        )
        st.divider()
        advisor_name = st.text_input("Advisor name", value="Michael Chen")
        st.caption(f"Backend: {BACKEND_URL}")

    if "active_request" not in st.session_state:
        st.session_state.active_request = None
    if "just_approved" not in st.session_state:
        st.session_state.just_approved = None

    tab_delegate, tab_audit = st.tabs(["📝 Delegate a Task", "📜 Audit Log"])

    with tab_delegate:
        try:
            clients = fetch_clients()
        except requests.RequestException as e:
            st.error(f"❌ Could not reach backend at {BACKEND_URL}: {e}")
            st.info("Start the backend with: `uvicorn backend.server:app --reload --port 8000`")
            return

        client_options = {f"{c['name']} ({c['client_id']}, {c['risk_profile']})": c["client_id"] for c in clients}

        st.subheader("1️⃣ Submit delegation request")
        col1, col2 = st.columns([1, 2])
        with col1:
            selected_label = st.selectbox("Client", list(client_options.keys()))
            client_id = client_options[selected_label]
        with col2:
            request_prompt = st.text_input(
                "What do you want to delegate?",
                value=f"Draft a portfolio review for {selected_label.split(' (')[0]}",
            )

        if st.button("🚀 Submit for Draft", type="primary"):
            with st.spinner("Generating draft via Amazon Bedrock..."):
                try:
                    result = submit_delegation_request(client_id, request_prompt, advisor_name)
                    st.session_state.active_request = result
                    st.session_state.just_approved = None
                except requests.RequestException as e:
                    st.error(f"❌ Error generating draft: {e}")

        req = st.session_state.active_request
        if req:
            st.divider()
            revision_count = req.get("revision_count", 0)
            revision_label = f"  (Revision #{revision_count})" if revision_count > 0 else ""
            st.subheader(f"2️⃣ Review draft{revision_label}")
            st.info(f"**Status:** `{req['status']}`  •  Request ID: `{req['request_id']}`  •  Client: {req['client_name']}")
            st.text_area("Draft document", value=req["draft"], height=320, key="draft_area")

            colA, colB, colC = st.columns(3)
            with colA:
                if st.button("✅ Approve & Execute", type="primary"):
                    try:
                        approval = approve_and_execute(req["request_id"], advisor_name)
                        st.session_state.just_approved = approval
                        st.session_state.active_request = None
                    except requests.RequestException as e:
                        st.error(f"❌ Error approving request: {e}")
            with colB:
                if st.button("✏️ Request Revision"):
                    st.session_state.show_revision = True
            with colC:
                if st.button("🔄 Discard draft"):
                    st.session_state.active_request = None
                    st.session_state.pop("show_revision", None)
                    st.rerun()

            if st.session_state.get("show_revision"):
                st.divider()
                st.subheader("✏️ Request Revision")
                feedback = st.text_area(
                    "What should be changed?",
                    placeholder="e.g. Make the tone more conservative, add a section on tax implications, shorten the intro...",
                    height=100,
                    key="revision_feedback",
                )
                if st.button("📤 Submit Revision Request", type="primary"):
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
                                st.error(f"❌ Error revising draft: {e}")

        if st.session_state.just_approved:
            approval = st.session_state.just_approved
            st.success("✅ Logged to Audit")
            st.json(approval["audit_entry"])

    with tab_audit:
        st.subheader("Audit Trail")
        try:
            entries = fetch_audit_log()
        except requests.RequestException as e:
            st.error(f"❌ Could not reach backend at {BACKEND_URL}: {e}")
            return

        if not entries:
            st.caption("No approved actions yet. Approve a draft to see it logged here.")
        else:
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
            )


if __name__ == "__main__":
    main()
