from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.claim_ledger import audit_text, build_ledger, extract_anchors, write_ledger
from tools.qc import Report, check_claim_ledger


class ClaimLedgerTests(unittest.TestCase):
    def test_build_ledger_keeps_claim_evidence_relationships(self) -> None:
        chapters = [{
            "chapter_id": "ch01",
            "claims": [{"claim_id": "C1", "text": "收入增长", "source_ids": ["S1"], "supporting_evidence_ids": ["E1"], "opposing_evidence_ids": ["E2"], "confidence": "中高", "limitations": ["样本有限"]}],
            "data_points": [
                {"evidence_id": "E1", "value": "10亿元"},
                {"evidence_id": "E2", "value": "8亿元"},
            ],
        }]
        ledger = build_ledger("Alpha Corp 2025 年收入为 10 亿元[1]。", chapters)
        claim = ledger["claims"][0]
        self.assertEqual(claim["supporting_evidence_ids"], ["E1"])
        self.assertEqual(claim["opposing_evidence_ids"], ["E2"])
        self.assertIn("10亿元", claim["evidence_anchors"]["E1"]["numbers"])

    def test_rephrasing_with_same_anchors_is_allowed(self) -> None:
        baseline = "Alpha Corp 在 2025 年收入为 10 亿元，但可能受样本限制[1]。"
        ledger = build_ledger(baseline, [])
        result = audit_text("2025 年，Alpha Corp 收入达到 10 亿元；样本限制意味着结论可能变化[1]。", ledger)
        self.assertEqual(result["errors"], [])

    def test_new_number_date_entity_and_certainty_are_errors(self) -> None:
        ledger = build_ledger("Alpha Corp 在 2025 年收入为 10 亿元[1]。", [])
        result = audit_text("Beta Corp 在 2026 年收入一定达到 12 亿元[1]。", ledger)
        joined = "\n".join(result["errors"])
        self.assertIn("数字/数量", joined)
        self.assertIn("日期", joined)
        self.assertIn("实体", joined)
        self.assertIn("确定性", joined)

    def test_removing_limitations_is_warning_and_strict_qc_error(self) -> None:
        baseline = "该结论可能受样本限制，尚未完全验证[1]。"
        ledger = build_ledger(baseline, [])
        result = audit_text("该结论得到验证[1]。", ledger)
        self.assertTrue(any("限制/不确定性" in item for item in result["warnings"]))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            write_ledger(path, ledger)
            report = Report()
            check_claim_ledger(report, "该结论得到验证[1]。", path, strict=True)
            self.assertTrue(any("限制/不确定性" in item for item in report.errors))

    def test_anchor_extraction_ignores_fenced_code(self) -> None:
        anchors = extract_anchors("正文 2025。\n```\nSecret Corp 999\n```")
        self.assertNotIn("999", anchors["numbers"])
        self.assertNotIn("Secret Corp", anchors["entities"])


if __name__ == "__main__":
    unittest.main()
