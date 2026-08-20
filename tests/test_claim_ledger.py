from __future__ import annotations

import unittest

from tools.claim_ledger import audit_ledger, build_ledger


class ClaimLedgerTests(unittest.TestCase):
    def test_rejects_new_number(self) -> None:
        ledger = build_ledger("截至 2025 年，指标约为 42%[1]。")
        errors = audit_ledger("截至 2025 年，指标约为 43%[1]。", ledger)
        self.assertTrue(any("新增数字" in error for error in errors))

    def test_rejects_dropped_uncertainty(self) -> None:
        ledger = build_ledger("该变化可能在特定条件下发生[1]。")
        errors = audit_ledger("该变化会发生[1]。", ledger)
        self.assertTrue(any("限定" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
