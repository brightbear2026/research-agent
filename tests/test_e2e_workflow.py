from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.aggregate_meta import run as aggregate
from tools.claim_ledger import audit_text
from tools.merge import main as merge
from tools.scaffold import scaffold
from tools.workflow_policy import advance_state, initial_state, load_config


class EndToEndWorkflowTests(unittest.TestCase):
    def test_minimal_six_phase_execution_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            scaffold(root, force=False)
            config = load_config()
            state = initial_state("execution", config)
            for expected in ("kickoff", "survey", "outline"):
                self.assertEqual(state["phase"], expected)
                state, action = advance_state(state, config)
                self.assertEqual(action, "advanced")

            draft = root / "report" / "_draft_ch01_intro.md"
            draft.write_text(
                "# 第 1 章 市场\n\n## 本章结论\n\n"
                "【事实】2025 年中国目标市场规模为 10 亿元"
                "[[SRC|网页|甲机构|年度报告|官网|2025-01-01|https://example.com/report|2026-08-09|A]]。\n\n"
                "## 对决策的含义\n\n保持观察。\n",
                encoding="utf-8",
            )
            meta = {
                "schema_version": 2,
                "chapter_id": "ch01", "title": "市场", "reader_question": "规模多大？",
                "thesis": "市场规模为 10 亿元", "argument_role": "量化市场",
                "sources": [{"source_id": "S1", "title": "年度报告", "url": "https://example.com/report", "organization": "甲机构", "publish_date": "2025-01-01", "tier": "A", "independence_group": "甲机构"}],
                "claims": [{"claim_id": "C1", "text": "2025 年中国目标市场规模为 10 亿元", "source_ids": ["S1"], "supporting_evidence_ids": ["E1"], "opposing_evidence_ids": [], "confidence": "中高", "limitations": ["单一来源"]}],
                "data_points": [{"evidence_id": "E1", "claim_id": "C1", "source_ids": ["S1"], "value": 10, "unit": "亿元", "stat_time": "2025", "region": "中国", "population_or_scope": "目标市场", "definition": "报告口径", "confidence": "中高", "limitations": ["单一来源"]}],
                "screenshots": [], "controversies": [], "gaps": [],
                "chapter_conclusion": {"claim_id": "C1", "judgment": "2025 年中国目标市场规模为 10 亿元", "supporting_evidence_ids": ["E1"], "opposing_evidence_ids": [], "conditions": "报告口径", "time_range": "2025", "confidence": "中高", "limitations": ["单一来源"], "decision_implication": "保持观察"},
            }
            draft.with_suffix(".meta.json").write_text(
                json.dumps(meta, ensure_ascii=False), encoding="utf-8"
            )

            with patch("sys.argv", ["merge.py", str(root), "--require-meta"]):
                self.assertEqual(merge(), 0)
            self.assertEqual(aggregate(root, "data/chapter_meta.json", force=True), 0)

            assembled = (root / "report" / "_assembled_report.md").read_text(encoding="utf-8")
            ledger = json.loads((root / "data" / "claim_ledger.json").read_text(encoding="utf-8"))
            self.assertEqual(audit_text(assembled, ledger)["errors"], [])
            self.assertTrue((root / "data" / "source_data.csv").exists())
            self.assertTrue((root / "evidence" / "evidence_matrix.csv").exists())

            for expected in ("research", "assemble", "deliver"):
                self.assertEqual(state["phase"], expected)
                state, _ = advance_state(state, config)
            self.assertEqual(state["workflow_status"], "completed")
            self.assertEqual(state["confirmation_count"], 0)


if __name__ == "__main__":
    unittest.main()
