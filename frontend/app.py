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

st.set_page_config(page_title="LPL Financial | Advisor Delegation Assistant", page_icon="🏛️", layout="wide")

LPL_NAVY = "#003A70"
LPL_BLUE = "#0073CF"
LPL_GREEN = "#6CC24A"

ST_CSS = f"""
<style>
  .block-container {{ padding-top: 1.5rem; }}
  .lpl-header {{
    background: linear-gradient(90deg, {LPL_NAVY} 0%, {LPL_BLUE} 100%);
    color: #fff; padding: 1.2rem 1.6rem; border-radius: 10px; margin-bottom: 1rem;
    border-bottom: 4px solid {LPL_GREEN};
  }}
  .lpl-header h1 {{ color: #fff; margin: 0; font-size: 1.7rem; }}
  .lpl-header p {{ margin: .25rem 0 0; opacity: .9; }}
  .lpl-steps {{ display: flex; gap: .5rem; margin-bottom: 1rem; flex-wrap: wrap; }}
  .lpl-step {{
    flex: 1; min-width: 150px; padding: .6rem .8rem; border-radius: 8px;
    background: #F2F6FA; border-left: 4px solid {LPL_BLUE}; font-size: .85rem; color: {LPL_NAVY};
  }}
  .lpl-step.active {{ background: {LPL_NAVY}; color: #fff; border-left-color: {LPL_GREEN}; }}
  .lpl-disclosure {{
    font-size: .75rem; color: #5b6b7b; border-top: 1px solid #d9e2ec; margin-top: 2rem; padding-top: .6rem;
  }}
  .lpl-badge {{
    display: inline-block; padding: .1rem .55rem; border-radius: 999px; font-size: .75rem;
    font-weight: 600; background: #E6F0FA; color: {LPL_NAVY};
  }}
  .lpl-badge.ok {{ background: #E8F6E1; color: #2d6a14; }}
  div.stButton > button[kind="primary"] {{ background: {LPL_NAVY}; border-color: {LPL_NAVY}; }}
  div.stButton > button[kind="primary"]:hover {{ background: {LPL_BLUE}; border-color: {LPL_BLUE}; }}
</style>
"""

TASK_TEMPLATES = {
    "Portfolio review": "Draft a portfolio review for {name}",
    "Rebalancing recommendation": "Draft a rebalancing recommendation memo for {name} aligned with their {risk} risk profile",
    "Retirement income plan": "Draft a retirement income planning summary for {name}",
    "Client meeting prep": "Prepare a meeting agenda and talking points for an upcoming review with {name}",
    "Custom request": "",
}


def render_steps(active: int):
    labels = ["1. Delegate", "2. AI drafts", "3. Advisor review", "4. Approve & log"]
    html = "".join(
        f'<div class="lpl-step{" active" if i == active else ""}">{label}</div>'
        for i, label in enumerate(labels)
    )
    st.markdown(f'<div class="lpl-steps">{html}</div>', unsafe_allow_html=True)


@st.cache_data(ttl=30)
def fetch_clients():
    resp = requests.get(f"{BACKEND_URL}/clients", timeout=10)
    resp.raise_for_status()
    return resp.json()["clients"]


def fetch_audit_log():
    resp = requests.get(f"{BACKEND_URL}/audit-log", timeout=10)
    resp.raise_for_status()
    body = resp.json()
    return body["audit_log"], body.get("storage", "unknown")


AUDIT_REFRESH_SECONDS = 5


@st.fragment(run_every=AUDIT_REFRESH_SECONDS)
def render_audit_log():
    """Re-polls the backend on a timer so entries from other advisors appear live."""
    try:
        entries, storage = fetch_audit_log()
    except requests.RequestException as e:
        st.error(f"Could not reach backend at {BACKEND_URL}: {e}")
        return

    if storage == "dynamodb":
        st.success(f"Shared audit trail (DynamoDB). Auto-refreshing every {AUDIT_REFRESH_SECONDS}s.")
    else:
        st.warning(
            "Local-only audit trail. This backend cannot reach DynamoDB, so you will not see other "
            "advisors' entries. Set AWS credentials and AWS_REGION, then restart the backend."
        )

    if not entries:
        st.caption("No approved actions yet. Approve a draft to see it logged here.")
        return

    st.metric("Approved actions", len(entries))
    for e in reversed(entries):
        with st.expander(f"{e['timestamp'][:16]}  —  **{e['client_name']}**  —  {e['request_prompt'][:60]}"):
            col1, col2, col3 = st.columns(3)
            col1.markdown(f"**Advisor:** {e['advisor']}")
            col2.markdown(f"**Request ID:** `{e['request_id']}`")
            col3.markdown(f"**Audit ID:** `{e['audit_id']}`")
            st.markdown(f"**Request:** {e['request_prompt']}")
            if e.get("draft"):
                st.divider()
                st.markdown("**Approved draft:**")
                st.text(e["draft"])
            else:
                st.caption("Draft text not available (approved before this feature was added).")


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


def approve_and_execute(request_id: str, advisor: str, edited_draft: str) -> dict:
    resp = requests.post(
        f"{BACKEND_URL}/approve",
        json={"request_id": request_id, "advisor": advisor, "edited_draft": edited_draft},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()

def main():
    st.markdown(ST_CSS, unsafe_allow_html=True)
    st.markdown(
        """
        <div class="lpl-header">
          <h1>LPL Financial &middot; Advisor Delegation Assistant</h1>
          <p>Delegate client-service drafting to AI. Every document stays under advisor
          supervision and is logged to the audit trail before it is released.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("Advisor workspace")
        advisor_name = st.text_input("Advisor name", value="Michael Chen")
        st.divider()
        st.markdown(
            """
            **How it works**
            1. Choose a client and a task
            2. AI drafts the document via Amazon Bedrock (Claude Sonnet 4.5) using
               client data and LPL compliance guardrails
            3. You review, request revisions, or approve
            4. Approval is recorded in the audit log
            """
        )
        st.divider()
        st.markdown("**Compliance reminders**")
        st.caption(
            "- No performance guarantees or promissory language\n"
            "- Fair, balanced and not misleading (FINRA 2210)\n"
            "- Best-interest standard (Reg BI)\n"
            "- Advisor remains responsible for all client communications"
        )
        st.caption(f"Backend: {BACKEND_URL}")

    if "active_request" not in st.session_state:
        st.session_state.active_request = None
    if "just_approved" not in st.session_state:
        st.session_state.just_approved = None

    tab_delegate, tab_audit = st.tabs(["Delegate a Task", "Audit & Supervision Log"])

    with tab_delegate:
        try:
            clients = fetch_clients()
        except requests.RequestException as e:
            st.error(f"Could not reach backend at {BACKEND_URL}: {e}")
            st.info("Start the backend with: `uvicorn backend.server:app --reload --port 8000`")
            return

        by_id = {c["client_id"]: c for c in clients}
        has_draft = bool(st.session_state.active_request)
        render_steps(2 if has_draft else (3 if st.session_state.just_approved else 0))

        st.subheader("Submit delegation request")
        col1, col2 = st.columns(2)
        with col1:
            client_id = st.selectbox(
                "Client",
                list(by_id.keys()),
                format_func=lambda cid: f"{by_id[cid]['name']} ({cid})",
            )
            client = by_id[client_id]
            st.markdown(
                f"Risk profile: <span class='lpl-badge'>{client['risk_profile']}</span>",
                unsafe_allow_html=True,
            )
        with col2:
            task_type = st.selectbox("Task type", list(TASK_TEMPLATES.keys()))

        template = TASK_TEMPLATES[task_type].format(name=client["name"], risk=client["risk_profile"].lower())
        request_prompt = st.text_input(
            "What do you want to delegate?",
            value=template,
            key=f"prompt_{client_id}_{task_type}",
            placeholder="Describe the task for the assistant",
        )

        if st.button("Generate draft", type="primary", disabled=not request_prompt.strip()):
            with st.spinner("Generating draft via Amazon Bedrock..."):
                try:
                    result = submit_delegation_request(client_id, request_prompt, advisor_name)
                    st.session_state.active_request = result
                    st.session_state.just_approved = None
                except requests.RequestException as e:
                    st.error(f"Error generating draft: {e}")

        req = st.session_state.active_request
        if req:
            st.divider()
            revision_count = req.get("revision_count", 0)
            revision_label = f" (Revision #{revision_count})" if revision_count > 0 else ""
            st.subheader(f"Advisor review{revision_label}")
            m1, m2, m3 = st.columns(3)
            m1.metric("Client", req["client_name"])
            m2.metric("Status", str(req["status"]).replace("_", " ").title())
            m3.metric("Request ID", req["request_id"])
            st.warning(
                "AI-generated draft. Review for accuracy, suitability and compliance "
                "before it is approved or shared with the client."
            )
            edited_draft = st.text_area("Draft document (editable — make changes before approving)", value=req["draft"], height=320, key=f"draft_area_{req.get('revision_count', 0)}")
            if edited_draft != req["draft"]:
                st.session_state.active_request["draft"] = edited_draft
                st.caption("You have unsaved manual edits. These will be included when you approve.")

            colA, colB, colC = st.columns(3)
            with colA:
                if st.button("Approve & log to audit", type="primary"):
                    try:
                        approval = approve_and_execute(req["request_id"], advisor_name, edited_draft)
                        st.session_state.just_approved = approval
                        st.session_state.active_request = None
                        st.rerun()
                    except requests.RequestException as e:
                        st.error(f"Error approving request: {e}")
            with colB:
                if st.button("Request revision"):
                    st.session_state.show_revision = True
            with colC:
                if st.button("Discard draft"):
                    st.session_state.active_request = None
                    st.session_state.pop("show_revision", None)
                    st.rerun()

            if st.session_state.get("show_revision"):
                st.divider()
                st.subheader("Request revision")
                feedback = st.text_area(
                    "What should be changed?",
                    placeholder="e.g. Use a more conservative tone, add a section on tax considerations, shorten the introduction...",
                    height=100,
                    key=f"revision_feedback_{req.get('revision_count', 0)}",
                )
                if st.button("Submit revision request", type="primary"):
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
            st.success("Approved and logged to the audit trail. The document is ready for client delivery.")
            with st.expander("Audit entry", expanded=True):
                st.json(approval["audit_entry"])
            if st.button("Start new request"):
                st.session_state.just_approved = None
                st.rerun()

    with tab_audit:
        st.subheader("Audit & supervision trail")
        st.caption("Every advisor approval is recorded for supervisory review and books-and-records requirements.")
        render_audit_log()

    st.markdown(
        '<div class="lpl-disclosure">Hackathon prototype using simulated client data. Not an official '
        "LPL Financial product. AI-generated content must be reviewed by a registered advisor and "
        "does not constitute investment advice or a guarantee of future results.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
