from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.workflow_policy import (
    complete_stage, confirm_checkpoint, decision, init_state, normalize_mode, resume_execution,
)


class WorkflowPolicyTests(unittest.TestCase):
    @staticmethod
    def create_delivery(root: Path) -> None:
        for rel in (
            "report/research_report.md", "report/research_report.html", "data/citations.csv",
            "data/source_data.csv", "evidence/evidence_matrix.csv",
            "evidence/controversy_matrix.csv", "evidence/research_gaps.md",
        ):
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("ok\n", encoding="utf-8")
        import hashlib
        report_hash = hashlib.sha256((root / "report/research_report.md").read_bytes()).hexdigest()
        (root / "data/qc_strict_result.json").write_text(
            json.dumps({"passed": True, "artifacts_sha256": {"report/research_report.md": report_hash}}) + "\n",
            encoding="utf-8",
        )

    def test_mode_aliases_and_checkpoints(self) -> None:
        self.assertEqual(normalize_mode("常规"), "normal")
        self.assertEqual(normalize_mode("计划模式"), "plan")
        self.assertEqual(normalize_mode("execution"), "execute")
        self.assertTrue(decision("normal", 1).checkpoint_required)
        self.assertTrue(decision("normal", 2).checkpoint_required)
        self.assertTrue(decision("normal", 3).checkpoint_required)
        self.assertFalse(decision("plan", 1).checkpoint_required)
        self.assertTrue(decision("plan", 3).checkpoint_required)
        self.assertTrue(decision("plan", 3).should_stop)
        self.assertFalse(any(decision("execute", stage).checkpoint_required for stage in range(1, 7)))

    def test_state_requires_sequential_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state_path = init_state(root, "执行", "完成报告", "标准")
            with self.assertRaises(ValueError):
                complete_stage(root, 2)
            for stage in range(1, 6):
                _, result = complete_stage(root, stage)
            with self.assertRaises(ValueError):
                complete_stage(root, 6)
            self.create_delivery(root)
            (root / "report/research_report.md").write_text("changed after qc\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                complete_stage(root, 6)
            self.create_delivery(root)
            _, result = complete_stage(root, 6)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "completed")
            self.assertTrue(result.should_stop)

    def test_plan_cannot_cross_stage_three_without_explicit_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_state(root, "计划", "先做计划", "标准")
            for stage in range(1, 4):
                _, result = complete_stage(root, stage)
            self.assertTrue(result.checkpoint_required)
            with self.assertRaises(ValueError):
                complete_stage(root, 4)
            confirm_checkpoint(root)
            with self.assertRaises(ValueError):
                complete_stage(root, 4)
            resume_execution(root)
            complete_stage(root, 4)


if __name__ == "__main__":
    unittest.main()
