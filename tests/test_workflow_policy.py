from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.workflow_policy import (
    advance_state,
    can_retry_source,
    initial_state,
    load_config,
    load_state,
    next_incomplete_chapter,
    record_external_failure,
    register_chapters,
    save_state,
    update_chapter_status,
)


class WorkflowPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config()

    def _run_mode(self, mode: str) -> tuple[dict, list[str]]:
        state = initial_state(mode, self.config)
        actions: list[str] = []
        guard = 0
        while state["workflow_status"] == "running":
            guard += 1
            self.assertLess(guard, 20, "状态机不得无限循环")
            if state["phase"] == "research":
                state = register_chapters(state, ["ch01"])
                state = update_chapter_status(state, "ch01", "completed")
            state, action = advance_state(state, self.config, confirmed=False)
            actions.append(action)
            if action == "needs_confirmation":
                state, action = advance_state(state, self.config, confirmed=True)
                actions.append(action)
        return state, actions

    def test_regular_mode_requires_three_confirmations_and_completes(self) -> None:
        state, actions = self._run_mode("regular")
        self.assertEqual(state["confirmation_count"], 3)
        self.assertEqual(actions.count("needs_confirmation"), 3)
        self.assertEqual(state["workflow_status"], "completed")
        self.assertEqual(len(state["completed_phases"]), 6)

    def test_plan_mode_confirms_once_and_stops_before_research(self) -> None:
        state, actions = self._run_mode("plan")
        self.assertEqual(state["confirmation_count"], 1)
        self.assertEqual(actions.count("needs_confirmation"), 1)
        self.assertEqual(state["workflow_status"], "planned")
        self.assertEqual(state["phase"], "outline")
        self.assertNotIn("research", state["completed_phases"])

    def test_execution_mode_has_zero_confirmations(self) -> None:
        state, actions = self._run_mode("execution")
        self.assertEqual(state["confirmation_count"], 0)
        self.assertNotIn("needs_confirmation", actions)
        self.assertEqual(state["workflow_status"], "completed")

    def test_failure_budget_terminates_source_retries_and_records_gap(self) -> None:
        state = initial_state("execution", self.config)
        actions = []
        for _ in range(3):
            state, action = record_external_failure(state, self.config, "https://blocked.example", "验证码")
            actions.append(action)
        self.assertEqual(actions[-1], "record_gap_and_continue")
        self.assertFalse(can_retry_source(state, self.config, "https://blocked.example"))
        self.assertEqual(len(state["research_gaps"]), 1)

    def test_state_is_persisted_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = initial_state("regular", self.config)
            save_state(root, state)
            self.assertEqual(load_state(root)["mode"], "regular")
            self.assertEqual(list(root.glob("tmp*")), [])

    def test_chapter_progress_resumes_at_first_incomplete_chapter(self) -> None:
        state = initial_state("execution", self.config)
        state = register_chapters(state, ["ch01", "ch02", "ch03"])
        state = update_chapter_status(state, "ch01", "in_progress")
        state = update_chapter_status(state, "ch01", "completed")
        self.assertEqual(next_incomplete_chapter(state), "ch02")
        self.assertEqual(state["chapter_progress"]["ch01"]["attempts"], 1)
        resumed = register_chapters(state, ["ch01", "ch02", "ch03"])
        self.assertEqual(resumed["chapter_progress"]["ch01"]["status"], "completed")

    def test_completed_chapter_cannot_be_reopened(self) -> None:
        state = register_chapters(initial_state("execution", self.config), ["ch01"])
        state = update_chapter_status(state, "ch01", "completed")
        with self.assertRaises(ValueError):
            update_chapter_status(state, "ch01", "in_progress")

    def test_research_phase_cannot_advance_with_incomplete_chapters(self) -> None:
        state = initial_state("execution", self.config)
        for _ in range(3):
            state, _ = advance_state(state, self.config)
        self.assertEqual(state["phase"], "research")
        unchanged, action = advance_state(state, self.config)
        self.assertIs(unchanged, state)
        self.assertEqual(action, "chapters_not_registered")
        state = register_chapters(state, ["ch01"])
        _, action = advance_state(state, self.config)
        self.assertEqual(action, "chapters_incomplete")

    def test_chapter_attempts_cap_blocks_redispatch(self) -> None:
        state = register_chapters(initial_state("execution", self.config), ["ch01"])
        for _ in range(3):
            state = update_chapter_status(state, "ch01", "in_progress")
            state = update_chapter_status(state, "ch01", "failed")
        self.assertEqual(state["chapter_progress"]["ch01"]["attempts"], 3)
        with self.assertRaises(ValueError):
            update_chapter_status(state, "ch01", "in_progress", max_attempts=3)
        # 无上限（默认）仍可推进
        state = update_chapter_status(state, "ch01", "in_progress")
        self.assertEqual(state["chapter_progress"]["ch01"]["attempts"], 4)

    def test_record_debt_subcommand_persists_completeness_debt(self) -> None:
        import json
        import sys
        from tools import workflow_policy

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_state(root, initial_state("execution", self.config))
            (root / "data").mkdir()
            debt = {
                "exit_code": 0, "core_passed": True,
                "summary": {"errors": 0, "warnings": 3,
                            "by_category": {"dead_links": 1, "staleness": 2}},
                "debt": [],
            }
            (root / "data" / "qc_debt.json").write_text(json.dumps(debt), encoding="utf-8")
            old_argv = sys.argv
            sys.argv = ["workflow_policy.py", "record-debt", "--root", str(root)]
            try:
                rc = workflow_policy.main()
            finally:
                sys.argv = old_argv
            self.assertEqual(rc, 0)
            loaded = load_state(root)
            self.assertIsNotNone(loaded["completeness_debt"])
            self.assertEqual(loaded["completeness_debt"]["warnings"], 3)
            self.assertEqual(loaded["completeness_debt"]["by_category"]["staleness"], 2)
            self.assertTrue(loaded["completeness_debt"]["core_passed"])


if __name__ == "__main__":
    unittest.main()
