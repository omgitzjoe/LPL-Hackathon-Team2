"""
Streamlit dashboard for the LPL Delegation Assistant.

Sign-in is required. What each role sees and can do:
  assistant  create drafts, edit them, request AI revisions, track their own drafts
  advisor    the same, plus level-1 approval of the final text
  principal  compliance principal: level-2 approval or rejection, chain verification

All business rules (roles, compliance checks, audit hashing) are enforced by the
backend; this app only presents them.
"""
import csv
import difflib
import io
import json
import os
from datetime import datetime, timezone

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

ROLE_LABELS = {"assistant": "Assistant", "advisor": "Advisor", "principal": "Compliance Principal"}
STATUS_LABELS = {
    "PENDING_APPROVAL": "Awaiting advisor approval",
    "PENDING_SUPERVISION": "Awaiting compliance principal",
    "APPROVED": "Approved for release",
    "REJECTED": "Returned by principal",
}
ACTION_LABELS = {
    "DRAFT_GENERATED": "Draft generated",
    "DRAFT_REVISED": "Draft revised (AI)",
    "ADVISOR_APPROVED": "Advisor approved",
    "SUPERVISOR_APPROVED": "Released by principal",
    "SUPERVISOR_REJECTED": "Rejected by principal",
    "APPROVE_AND_EXECUTE": "Approved (legacy record)",
}
EDITABLE_STATUSES = ("PENDING_APPROVAL", "REJECTED")
AUDIT_REFRESH_SECONDS = 5


# ── API access ──

class ApiError(Exception):
    def __init__(self, status_code, detail):
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail

    @property
    def message(self):
        if isinstance(self.detail, dict):
            return self.detail.get("message", "Request failed")
        return str(self.detail)

    @property
    def compliance(self):
        return self.detail.get("compliance") if isinstance(self.detail, dict) else None


def sign_out():
    for key in ("token", "user", "active_id", "flash"):
        st.session_state.pop(key, None)


def api(method, path, body=None, params=None, timeout=60):
    headers = {}
    token = st.session_state.get("token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.request(
            method, f"{BACKEND_URL}{path}", json=body, params=params, headers=headers, timeout=timeout
        )
    except requests.RequestException as e:
        raise ApiError(0, f"Could not reach the backend at {BACKEND_URL}: {e}")
    if resp.status_code == 401 and token:
        sign_out()
        st.session_state.flash = ("warning", "Your session ended. Please sign in again.")
        st.rerun()
    if not resp.ok:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        raise ApiError(resp.status_code, detail)
    return resp.json()


@st.cache_data(ttl=30)
def fetch_clients(token):
    return api("GET", "/clients")["clients"]


# ── Helpers ──

def short(hash_value, n=12):
    return f"{hash_value[:n]}…" if hash_value else "—"


def fmt_time(iso):
    try:
        return datetime.fromisoformat(iso).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except (TypeError, ValueError):
        return iso or "—"


def diff_text(before, after):
    return "\n".join(
        difflib.unified_diff(
            (before or "").splitlines(), (after or "").splitlines(),
            fromfile="AI draft", tofile="Current text", lineterm="", n=1,
        )
    )


def render_steps(active):
    labels = ["1. Delegate & AI draft", "2. Advisor approval", "3. Compliance principal", "4. Released"]
    html = "".join(
        f'<div class="lpl-step{" active" if i == active else ""}">{label}</div>'
        for i, label in enumerate(labels)
    )
    st.markdown(f'<div class="lpl-steps">{html}</div>', unsafe_allow_html=True)


def step_for(status):
    return {"PENDING_APPROVAL": 1, "REJECTED": 1, "PENDING_SUPERVISION": 2, "APPROVED": 3}.get(status, 0)


def render_compliance(result):
    if result["passed"]:
        st.success(f"Compliance checks passed ({result['warnings']} warning(s)).")
    else:
        st.error(f"{result['blocking']} blocking compliance issue(s). Fix them before approval.")
    if result["findings"]:
        with st.expander(f"Review {len(result['findings'])} finding(s)", expanded=not result["passed"]):
            for f in result["findings"]:
                tag = ":red[BLOCKING]" if f["severity"] == "block" else ":orange[WARNING]"
                match = f"  \n> “{f['match']}”" if f.get("match") else ""
                st.markdown(f"{tag} **{f['title']}** ({f['citation']})  \n{f['detail']}{match}")
    st.caption(f"Ruleset {result['ruleset_version']}. Automated checks support, and do not replace, supervisory review.")


# ── Review panel ──

def render_review(req, key):
    user = st.session_state.user
    role = user["role"]
    status = req["status"]
    rid = req["request_id"]
    editable = role in ("assistant", "advisor") and status in EDITABLE_STATUSES

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Client", req["client_name"])
    m2.metric("Status", STATUS_LABELS.get(status, status))
    m3.metric("Request ID", rid)
    m4.metric("Created by", req.get("created_by_name", "—"))

    if status == "REJECTED":
        st.warning(f"Returned by {req.get('supervisor_name', 'the principal')}: {req.get('supervisor_comment', '')}")
    if status == "PENDING_SUPERVISION":
        st.info(f"Approved by advisor {req.get('advisor_approved_by_name', '')} on "
                f"{fmt_time(req.get('advisor_approved_at'))}. Waiting for a compliance principal.")
    if status == "APPROVED":
        st.success(f"Approved for release by {req.get('supervisor_name', '')} on {fmt_time(req.get('decided_at'))}.")
    if editable:
        st.warning("AI-generated draft. Review for accuracy, suitability and compliance before approving.")

    widget_key = f"draft_{key}_{rid}_{req.get('revision_count', 0)}_{status}"
    text = st.text_area(
        "Draft document" + (" (editable)" if editable else ""),
        value=req["draft"], height=340, key=widget_key, disabled=not editable,
    )

    result = api("POST", "/compliance/check", {"text": text, "client_id": req["client_id"]})
    render_compliance(result)

    changes = diff_text(req.get("ai_draft", ""), text)
    if changes:
        with st.expander("Changes from the AI draft"):
            st.code(changes, language="diff")

    if editable:
        c1, c2, c3 = st.columns(3)
        if c1.button("Save edits", key=f"save_{key}_{rid}"):
            try:
                api("POST", "/save-draft", {"request_id": rid, "draft": text})
                st.toast("Draft saved")
            except ApiError as e:
                st.error(e.message)
        if c2.button("Request AI revision", key=f"revopen_{key}_{rid}"):
            st.session_state[f"rev_{key}_{rid}"] = True
        if role == "advisor":
            if c3.button(
                "Approve and send to compliance principal", type="primary",
                key=f"approve_{key}_{rid}", disabled=not result["passed"],
            ):
                try:
                    api("POST", "/advisor-approve", {"request_id": rid, "final_draft": text})
                    st.session_state.flash = ("success", f"{rid} approved and sent to the compliance principal.")
                    st.rerun()
                except ApiError as e:
                    st.error(e.message)
        else:
            c3.caption("Only an advisor can approve. Save your edits so the advisor sees them in the queue.")

        if st.session_state.get(f"rev_{key}_{rid}"):
            st.divider()
            feedback = st.text_area(
                "What should be changed?", height=100, key=f"fb_{key}_{rid}_{req.get('revision_count', 0)}",
                placeholder="e.g. Use a more conservative tone, add tax considerations, shorten the introduction...",
            )
            if st.button("Submit revision request", type="primary", key=f"revgo_{key}_{rid}"):
                if not feedback.strip():
                    st.warning("Please describe what to change.")
                else:
                    with st.spinner("Revising the draft with Amazon Bedrock..."):
                        try:
                            api("POST", "/revise-draft", {"request_id": rid, "feedback": feedback})
                            st.session_state.pop(f"rev_{key}_{rid}", None)
                            st.rerun()
                        except ApiError as e:
                            st.error(e.message)

    if role == "principal" and status == "PENDING_SUPERVISION":
        st.divider()
        st.subheader("Supervisory decision")
        comment = st.text_area("Comment (required when rejecting)", key=f"comment_{key}_{rid}", height=90)
        d1, d2 = st.columns(2)
        if d1.button("Approve for release", type="primary", key=f"sup_ok_{key}_{rid}", disabled=not result["passed"]):
            try:
                api("POST", "/supervise", {"request_id": rid, "decision": "approve", "comment": comment})
                st.session_state.flash = ("success", f"{rid} approved for release and logged to the audit trail.")
                st.rerun()
            except ApiError as e:
                st.error(e.message)
        if d2.button("Reject and return to advisor", key=f"sup_no_{key}_{rid}"):
            if not comment.strip():
                st.warning("Add a comment explaining what must change.")
            else:
                try:
                    api("POST", "/supervise", {"request_id": rid, "decision": "reject", "comment": comment})
                    st.session_state.flash = ("info", f"{rid} returned with your comment.")
                    st.rerun()
                except ApiError as e:
                    st.error(e.message)


# ── Tabs ──

def render_delegate(clients):
    by_id = {c["client_id"]: c for c in clients}
    active_id = st.session_state.get("active_id")
    req = api("GET", f"/requests/{active_id}")["request"] if active_id else None
    render_steps(step_for(req["status"]) if req else 0)

    if req is None:
        st.subheader("Submit delegation request")
        col1, col2 = st.columns(2)
        with col1:
            client_id = st.selectbox(
                "Client", list(by_id.keys()), format_func=lambda cid: f"{by_id[cid]['name']} ({cid})"
            )
            client = by_id[client_id]
            st.markdown(f"Risk profile: <span class='lpl-badge'>{client['risk_profile']}</span>", unsafe_allow_html=True)
        with col2:
            task_type = st.selectbox("Task type", list(TASK_TEMPLATES.keys()))
        template = TASK_TEMPLATES[task_type].format(name=client["name"], risk=client["risk_profile"].lower())
        request_prompt = st.text_input(
            "What do you want to delegate?", value=template, key=f"prompt_{client_id}_{task_type}",
            placeholder="Describe the task for the assistant",
        )
        if st.button("Generate draft", type="primary", disabled=not request_prompt.strip()):
            with st.spinner("Generating draft with Amazon Bedrock..."):
                try:
                    created = api("POST", "/generate-draft", {"client_id": client_id, "request_prompt": request_prompt})
                    st.session_state.active_id = created["request_id"]
                    st.rerun()
                except ApiError as e:
                    st.error(e.message)
        return

    st.divider()
    render_review(req, "delegate")
    if req["status"] not in EDITABLE_STATUSES:
        if st.button("Start a new request", key="new_request"):
            st.session_state.pop("active_id", None)
            st.rerun()
    else:
        if st.button("Close (the draft stays in the queue)", key="close_request"):
            st.session_state.pop("active_id", None)
            st.rerun()


def render_queue(role):
    labels = list(STATUS_LABELS.keys())
    defaults = {
        "principal": ["PENDING_SUPERVISION"],
        "advisor": ["PENDING_APPROVAL", "REJECTED"],
        "assistant": labels,
    }[role]
    c1, c2 = st.columns([4, 1])
    chosen = c1.multiselect("Show", labels, default=defaults, format_func=lambda s: STATUS_LABELS[s], key=f"filter_{role}")
    c2.write("")
    c2.button("Refresh", key=f"refresh_{role}")

    params = {"statuses": ",".join(chosen)} if chosen else {}
    if role == "assistant":
        params["mine"] = "true"
    rows = api("GET", "/requests", params=params)["requests"]
    if not rows:
        st.caption("Nothing here right now.")
        return

    by_id = {r["request_id"]: r for r in rows}
    picked = st.selectbox(
        "Request", list(by_id.keys()), key=f"pick_{role}",
        format_func=lambda rid: (
            f"{rid} · {by_id[rid]['client_name']} · {STATUS_LABELS.get(by_id[rid]['status'])} "
            f"· {by_id[rid].get('created_by_name', '')}"
        ),
    )
    st.divider()
    render_review(api("GET", f"/requests/{picked}")["request"], f"queue_{role}")


def audit_csv(entries):
    columns = [
        "timestamp", "seq", "action", "actor_id", "actor_name", "actor_role", "request_id", "client_name",
        "status_after", "compliance_passed", "compliance_blocking", "final_draft_sha256", "prev_hash", "entry_hash",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for e in entries:
        writer.writerow(e)
    return buf.getvalue()


@st.fragment(run_every=AUDIT_REFRESH_SECONDS)
def render_audit_log(actions):
    """Re-polls the backend on a timer so entries from other users appear live."""
    role = st.session_state.user["role"]
    try:
        body = api("GET", "/audit-log")
        verification = api("GET", "/audit-log/verify") if role == "principal" else None
    except ApiError as e:
        st.error(e.message)
        return

    entries, storage = body["audit_log"], body.get("storage", "unknown")
    if storage == "dynamodb":
        st.success(f"Shared audit trail (DynamoDB). Auto-refreshing every {AUDIT_REFRESH_SECONDS}s.")
    else:
        st.warning("Local-only audit trail. This backend cannot reach DynamoDB, so you will not see other users' entries.")

    if verification is not None:
        if verification["ok"]:
            st.success(
                f"Record integrity verified: {verification['checked']} chained entries, latest hash "
                f"`{short(verification['head_hash'])}`"
                + (f" ({verification['legacy_unchained']} older entries predate hashing)." if verification["legacy_unchained"] else ".")
            )
        else:
            st.error("RECORD INTEGRITY FAILURE. The audit log was altered or entries are missing.")
            st.dataframe(verification["errors"], hide_index=True)

    if not entries:
        st.caption("No activity recorded yet.")
        return

    released = sum(1 for e in entries if e.get("action") in ("SUPERVISOR_APPROVED", "APPROVE_AND_EXECUTE"))
    k1, k2, k3 = st.columns(3)
    k1.metric("Recorded events", len(entries))
    k2.metric("Released documents", released)
    k3.metric("Rejected by principal", sum(1 for e in entries if e.get("action") == "SUPERVISOR_REJECTED"))

    if role == "principal":
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        d1, d2 = st.columns(2)
        d1.download_button(
            "Download records (JSON with verification)",
            json.dumps({"exported_at": stamp, "exported_by": st.session_state.user["user_id"],
                        "verification": verification, "entries": entries}, indent=2),
            file_name=f"lpl-audit-{stamp}.json", mime="application/json", key="dl_json",
        )
        d2.download_button("Download records (CSV)", audit_csv(entries),
                           file_name=f"lpl-audit-{stamp}.csv", mime="text/csv", key="dl_csv")

    shown = [e for e in entries if not actions or e.get("action") in actions]
    for e in reversed(shown):
        label = ACTION_LABELS.get(e.get("action"), e.get("action", "Event"))
        who = e.get("actor_name") or e.get("advisor") or "unknown"
        with st.expander(f"{fmt_time(e.get('timestamp'))}  ·  {label}  ·  {e.get('client_name', '')}  ·  {who}"):
            c1, c2, c3 = st.columns(3)
            if e.get("actor_id"):
                c1.markdown(f"**User:** {who} (`{e['actor_id']}`, {ROLE_LABELS.get(e.get('actor_role'), e.get('actor_role'))})")
            else:
                c1.markdown(f"**User (name only):** {who}")
            c2.markdown(f"**Request:** `{e.get('request_id', '')}`")
            c3.markdown(f"**Audit ID:** `{e.get('audit_id', '')}`" + (f"  ·  #{e['seq']}" if e.get("seq") else ""))
            if e.get("request_prompt"):
                st.markdown(f"**Task:** {e['request_prompt']}")
            if e.get("comment"):
                st.markdown(f"**Comment:** {e['comment']}")
            if "compliance_passed" in e:
                outcome = "passed" if e["compliance_passed"] else "FAILED"
                st.markdown(
                    f"**Compliance:** {outcome} · {e.get('compliance_blocking', 0)} blocking · "
                    f"{e.get('compliance_warnings', 0)} warning(s) · ruleset {e.get('compliance_ruleset', '')}"
                )
                if e.get("compliance_findings"):
                    st.caption("Findings: " + ", ".join(e["compliance_findings"]))
            if e.get("entry_hash"):
                st.caption(
                    f"AI draft `{short(e.get('ai_draft_sha256', ''))}` · final text `{short(e.get('final_draft_sha256', ''))}` · "
                    f"previous `{short(e.get('prev_hash', ''))}` · this record `{short(e['entry_hash'])}`"
                )
            if e.get("diff_from_ai"):
                st.markdown("**Human changes to the AI draft:**")
                st.code(e["diff_from_ai"], language="diff")
            final = e.get("final_draft") or e.get("draft")
            if final:
                st.markdown("**Text at this step:**")
                st.text(final)


# ── Page ──

def login_view():
    try:
        info = api("GET", "/auth/info")
    except ApiError as e:
        st.error(e.message)
        st.info("Start the backend with: `uvicorn backend.server:app --reload --port 8000`")
        return
    left, _ = st.columns([1, 1])
    with left:
        st.subheader("Sign in")
        with st.form("login"):
            user_id = st.text_input("User ID")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", type="primary")
        if submitted:
            try:
                out = api("POST", "/auth/login", {"user_id": user_id, "password": password})
                st.session_state.token = out["token"]
                st.session_state.user = out["user"]
                st.rerun()
            except ApiError as e:
                st.error(e.message)
        if info.get("demo_mode"):
            st.caption(
                "Demo accounts (prototype only): `assistant1`, `advisor1`, `advisor2` and `principal1`. "
                "The default password is `lpl-demo` unless the administrator changed it."
            )


def main():
    st.markdown(ST_CSS, unsafe_allow_html=True)
    st.markdown(
        """
        <div class="lpl-header">
          <h1>LPL Financial &middot; Advisor Delegation Assistant</h1>
          <p>Delegate client-service drafting to AI. Every document passes automated compliance checks,
          advisor approval and compliance-principal approval, and every step is recorded in a tamper-evident audit trail.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not st.session_state.get("token"):
        flash = st.session_state.pop("flash", None)
        if flash:
            getattr(st, flash[0])(flash[1])
        login_view()
        return

    user = st.session_state.user
    role = user["role"]

    with st.sidebar:
        st.header("Signed in")
        st.markdown(f"**{user['name']}**  \n`{user['user_id']}` · {ROLE_LABELS.get(role, role)}")
        if st.button("Sign out"):
            sign_out()
            st.rerun()
        st.divider()
        st.markdown(
            """
            **How it works**
            1. An assistant or advisor delegates a task
            2. AI drafts it (Amazon Bedrock, Claude Sonnet 4.5) and automated compliance checks run
            3. An advisor reviews, edits and approves
            4. A compliance principal approves or returns it
            5. Every step is logged with the user ID and a hash chain
            """
        )
        st.divider()
        st.markdown("**Compliance reminders**")
        st.caption(
            "- No performance guarantees or promissory language\n"
            "- Fair, balanced and not misleading (FINRA 2210)\n"
            "- Best-interest standard (Reg BI)\n"
            "- Advisors remain responsible for client communications"
        )
        st.caption(f"Backend: {BACKEND_URL}")

    flash = st.session_state.pop("flash", None)
    if flash:
        getattr(st, flash[0])(flash[1])

    if role == "principal":
        tab_names = ["Supervision Queue", "Audit & Supervision Log"]
    elif role == "advisor":
        tab_names = ["Delegate a Task", "Advisor Review Queue", "Audit & Supervision Log"]
    else:
        tab_names = ["Delegate a Task", "My Drafts", "Audit & Supervision Log"]
    tabs = dict(zip(tab_names, st.tabs(tab_names)))

    try:
        if role != "principal":
            with tabs["Delegate a Task"]:
                render_delegate(fetch_clients(st.session_state.token))
        queue_tab = "Supervision Queue" if role == "principal" else tab_names[1]
        with tabs[queue_tab]:
            if role == "principal":
                render_steps(2)
            render_queue(role)
    except ApiError as e:
        st.error(e.message)

    with tabs["Audit & Supervision Log"]:
        st.subheader("Audit & supervision trail")
        st.caption(
            "Every draft, revision, approval and rejection is recorded with the signed-in user, the compliance "
            "result and a hash that links it to the previous record."
        )
        actions = st.multiselect(
            "Filter by event", list(ACTION_LABELS.keys()), format_func=lambda a: ACTION_LABELS[a], key="audit_filter"
        )
        render_audit_log(actions)

    st.markdown(
        '<div class="lpl-disclosure">Hackathon prototype using simulated client data. Not an official '
        "LPL Financial product. AI-generated content must be reviewed by a registered advisor and "
        "does not constitute investment advice or a guarantee of future results.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
