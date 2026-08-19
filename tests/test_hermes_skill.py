from __future__ import annotations

import unittest
from pathlib import Path


class HermesSkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = (Path(__file__).parents[1] / "SKILL.md").read_text(encoding="utf-8")

    def test_chapter_commands_use_project_root(self) -> None:
        self.assertNotIn("--root <slug>", self.skill)
        self.assertIn("chapter --root projects/<slug>", self.skill)

    def test_final_delivery_requires_strict_qc_and_debt_recording(self) -> None:
        self.assertIn("qc.py --strict", self.skill)
        self.assertIn("record-debt --root projects/<slug>", self.skill)
        self.assertNotIn("non-strict passes", self.skill)

    def test_agent_context_uses_canonical_files(self) -> None:
        self.assertIn(".claude/agents/researcher.md", self.skill)
        self.assertIn(".claude/agents/report-editor.md", self.skill)


if __name__ == "__main__":
    unittest.main()
