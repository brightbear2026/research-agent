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
    record_external_failure,
    save_state,
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


if __name__ == "__main__":
    unittest.main()
