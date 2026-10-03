import tempfile
import unittest
from pathlib import Path

from backend import audit_chain, auth, state_store
from backend import lambda_handler as h
from backend.lambda_handler import HandlerError

ASSISTANT = {"user_id": "assistant1", "name": "Alex Rivera", "role": "assistant"}
ADVISOR = {"user_id": "advisor1", "name": "Michael Chen", "role": "advisor"}
ADVISOR2 = {"user_id": "advisor2", "name": "Priya Nair", "role": "advisor"}
PRINCIPAL = {"user_id": "principal1", "name": "Dana Okafor", "role": "principal"}


class AuthTests(unittest.TestCase):
    def test_demo_login_and_token_roundtrip(self):
        user = auth.authenticate("advisor1", "lpl-demo")
        self.assertEqual(user["role"], "advisor")
        verified = auth.verify_token(auth.issue_token(user))
        self.assertEqual(verified["user_id"], "advisor1")

    def test_wrong_password_and_unknown_user_fail_the_same_way(self):
        for uid in ("advisor1", "nobody"):
            with self.assertRaises(auth.AuthError) as ctx:
                auth.authenticate(uid, "wrong")
            self.assertEqual(ctx.exception.status_code, 401)

    def test_tampered_token_is_rejected(self):
        token = auth.issue_token(auth.authenticate("assistant1", "lpl-demo"))
        body, sig = token.rsplit(".", 1)
        with self.assertRaises(auth.AuthError):
            auth.verify_token(body + "x." + sig)
        with self.assertRaises(auth.AuthError):
            auth.verify_token("")

    def test_expired_token_is_rejected(self):
        original = auth._TTL_SECONDS
        auth._TTL_SECONDS = -10
        try:
            token = auth.issue_token(auth.authenticate("principal1", "lpl-demo"))
        finally:
            auth._TTL_SECONDS = original
        with self.assertRaises(auth.AuthError):
            auth.verify_token(token)

    def test_lockout_after_repeated_failures(self):
        auth._failures.pop("advisor2", None)
        for _ in range(5):
            with self.assertRaises(auth.AuthError):
                auth.authenticate("advisor2", "bad")
        with self.assertRaises(auth.AuthError) as ctx:
            auth.authenticate("advisor2", "lpl-demo")
        self.assertEqual(ctx.exception.status_code, 429)
        auth._failures.pop("advisor2", None)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = {
            "_init_dynamo": state_store._init_dynamo,
            "_use_dynamo": state_store._use_dynamo,
            "DATA_DIR": state_store.DATA_DIR,
            "AUDIT_LOG_PATH": state_store.AUDIT_LOG_PATH,
        }
        state_store._init_dynamo = lambda: None
        state_store._use_dynamo = False
        state_store.DATA_DIR = Path(self.tmp.name)
        state_store.AUDIT_LOG_PATH = Path(self.tmp.name) / "audit_log.json"
        state_store._requests.clear()

    def tearDown(self):
        for name, value in self.patches.items():
            setattr(state_store, name, value)
        state_store._requests.clear()
        self.tmp.cleanup()

    def draft(self):
        return h.generate_draft_handler({"client_id": "C-1001", "request_prompt": "Portfolio review for Jane Doe"}, ASSISTANT)

    def test_full_two_level_flow_records_real_users(self):
        req = self.draft()
        rid = req["request_id"]
        self.assertEqual(req["status"], "PENDING_APPROVAL")
        self.assertTrue(req["compliance"]["passed"])

        edited = req["draft"].replace("broadly aligned", "well aligned")
        step1 = h.advisor_approve_handler({"request_id": rid, "final_draft": edited}, ADVISOR)
        self.assertEqual(step1["request"]["status"], "PENDING_SUPERVISION")
        self.assertTrue(step1["audit_entry"]["edited_by_human"])
        self.assertIn("+", step1["audit_entry"]["diff_from_ai"])

        step2 = h.supervise_handler({"request_id": rid, "decision": "approve"}, PRINCIPAL)
        self.assertEqual(step2["request"]["status"], "APPROVED")

        log = state_store.list_audit_log()
        self.assertEqual([e["action"] for e in log],
                         ["DRAFT_GENERATED", "ADVISOR_APPROVED", "SUPERVISOR_APPROVED"])
        self.assertEqual([e["actor_id"] for e in log], ["assistant1", "advisor1", "principal1"])
        self.assertEqual([e["actor_role"] for e in log], ["assistant", "advisor", "principal"])
        self.assertEqual(log[1]["final_draft_sha256"], audit_chain.sha256_text(edited))
        self.assertTrue(state_store.verify_audit_log()["ok"])

    def test_roles_are_enforced(self):
        rid = self.draft()["request_id"]
        with self.assertRaises(HandlerError) as ctx:
            h.advisor_approve_handler({"request_id": rid}, ASSISTANT)
        self.assertEqual(ctx.exception.status_code, 403)
        with self.assertRaises(HandlerError) as ctx:
            h.supervise_handler({"request_id": rid, "decision": "approve"}, ADVISOR)
        self.assertEqual(ctx.exception.status_code, 403)
        with self.assertRaises(HandlerError) as ctx:
            h.generate_draft_handler({"client_id": "C-1001", "request_prompt": "x"}, PRINCIPAL)
        self.assertEqual(ctx.exception.status_code, 403)
        with self.assertRaises(HandlerError) as ctx:
            h.list_clients_handler(None)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_supervision_requires_advisor_approval_first(self):
        rid = self.draft()["request_id"]
        with self.assertRaises(HandlerError) as ctx:
            h.supervise_handler({"request_id": rid, "decision": "approve"}, PRINCIPAL)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_blocking_findings_stop_approval(self):
        req = self.draft()
        bad = req["draft"] + "\nThis portfolio offers guaranteed returns."
        with self.assertRaises(HandlerError) as ctx:
            h.advisor_approve_handler({"request_id": req["request_id"], "final_draft": bad}, ADVISOR)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertFalse(ctx.exception.extra["compliance"]["passed"])
        self.assertEqual(state_store.get_request(req["request_id"])["status"], "PENDING_APPROVAL")

    def test_rejection_needs_comment_and_returns_to_editing(self):
        rid = self.draft()["request_id"]
        h.advisor_approve_handler({"request_id": rid}, ADVISOR)
        with self.assertRaises(HandlerError) as ctx:
            h.supervise_handler({"request_id": rid, "decision": "reject"}, PRINCIPAL)
        self.assertEqual(ctx.exception.status_code, 400)
        out = h.supervise_handler({"request_id": rid, "decision": "reject", "comment": "Add risk language"}, PRINCIPAL)
        self.assertEqual(out["request"]["status"], "REJECTED")
        self.assertEqual(out["audit_entry"]["comment"], "Add risk language")

        saved = h.save_draft_handler({"request_id": rid, "draft": out["request"]["draft"] + " Extra."}, ASSISTANT)
        self.assertEqual(saved["status"], "PENDING_APPROVAL")
        self.assertEqual(state_store.get_request(rid)["status"], "PENDING_APPROVAL")

    def test_second_approval_attempt_is_rejected(self):
        rid = self.draft()["request_id"]
        h.advisor_approve_handler({"request_id": rid}, ADVISOR)
        with self.assertRaises(HandlerError) as ctx:
            h.advisor_approve_handler({"request_id": rid}, ADVISOR2)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_tampering_with_the_stored_log_is_detected(self):
        rid = self.draft()["request_id"]
        h.advisor_approve_handler({"request_id": rid}, ADVISOR)
        self.assertTrue(state_store.verify_audit_log()["ok"])

        entries = state_store._load_audit_log_file()
        entries[0]["actor_id"] = "someone_else"
        state_store._save_audit_log_file(entries)
        result = state_store.verify_audit_log()
        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"][0]["seq"], 1)

    def test_text_is_not_reformatted_on_approval(self):
        req = self.draft()
        text = req["draft"]
        out = h.advisor_approve_handler({"request_id": req["request_id"], "final_draft": text}, ADVISOR)
        self.assertEqual(out["audit_entry"]["final_draft"], text)
        self.assertIn("\n", out["audit_entry"]["final_draft"])


if __name__ == "__main__":
    unittest.main()
