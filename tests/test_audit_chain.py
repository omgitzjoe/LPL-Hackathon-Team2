import copy
import unittest

from backend import audit_chain


def build(n):
    entries, prev = [], audit_chain.GENESIS
    for seq in range(1, n + 1):
        e = audit_chain.seal({"audit_id": f"AUD-{seq}", "action": "X", "note": f"event {seq}"}, prev, seq)
        entries.append(e)
        prev = e["entry_hash"]
    return entries


class AuditChainTests(unittest.TestCase):
    def test_intact_chain_verifies(self):
        result = audit_chain.verify_chain(build(5))
        self.assertTrue(result["ok"])
        self.assertEqual(result["checked"], 5)

    def test_modified_entry_is_detected(self):
        entries = build(4)
        entries[1]["note"] = "tampered"
        result = audit_chain.verify_chain(entries)
        self.assertFalse(result["ok"])
        self.assertEqual(result["errors"][0]["seq"], 2)

    def test_deleted_entry_is_detected(self):
        entries = build(5)
        del entries[2]
        self.assertFalse(audit_chain.verify_chain(entries)["ok"])

    def test_reordering_is_detected(self):
        entries = build(3)
        entries[0], entries[1] = entries[1], entries[0]
        entries[0]["seq"], entries[1]["seq"] = 1, 2
        self.assertFalse(audit_chain.verify_chain(entries)["ok"])

    def test_recomputed_hash_after_edit_still_breaks_the_next_link(self):
        entries = build(3)
        entries[0]["note"] = "tampered"
        entries[0]["entry_hash"] = audit_chain.compute_entry_hash(entries[0])
        self.assertFalse(audit_chain.verify_chain(entries)["ok"])

    def test_truncated_tail_detected_with_head(self):
        entries = build(4)
        head = {"seq": 4, "entry_hash": entries[-1]["entry_hash"]}
        self.assertTrue(audit_chain.verify_chain(entries, head)["ok"])
        self.assertFalse(audit_chain.verify_chain(entries[:3], head)["ok"])

    def test_legacy_entries_are_counted_not_failed(self):
        entries = build(2) + [{"audit_id": "OLD", "advisor": "x", "timestamp": "2025"}]
        result = audit_chain.verify_chain(entries)
        self.assertTrue(result["ok"])
        self.assertEqual(result["legacy_unchained"], 1)

    def test_hash_is_independent_of_key_order(self):
        a = {"b": 1, "a": 2}
        b = {"a": 2, "b": 1}
        self.assertEqual(audit_chain.compute_entry_hash(a), audit_chain.compute_entry_hash(b))

    def test_input_not_mutated_by_seal(self):
        original = {"audit_id": "A", "x": 1}
        snapshot = copy.deepcopy(original)
        audit_chain.seal(original, audit_chain.GENESIS, 1)
        self.assertEqual(original, snapshot)

    def test_unified_diff_shows_human_edit(self):
        diff = audit_chain.unified_diff("line one\nline two", "line one\nline 2")
        self.assertIn("-line two", diff)
        self.assertIn("+line 2", diff)
        self.assertEqual(audit_chain.unified_diff("same", "same"), "")


if __name__ == "__main__":
    unittest.main()
