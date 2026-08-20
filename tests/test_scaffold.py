from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.scaffold import resolve_project_path, scaffold


class ScaffoldSafetyTests(unittest.TestCase):
    def test_repository_relative_project_path_is_accepted(self) -> None:
        path = resolve_project_path(Path("projects/safe-topic"))
        self.assertEqual(path.name, "safe-topic")

    def test_relative_and_absolute_escape_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "projects"
            parent.mkdir()
            with self.assertRaises(ValueError):
                resolve_project_path(Path("../outside"), parent)
            with self.assertRaises(ValueError):
                resolve_project_path(Path(tmp) / "outside", parent)

    def test_projects_root_itself_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "projects"
            parent.mkdir()
            with self.assertRaises(ValueError):
                resolve_project_path(parent, parent)

    def test_scaffold_can_create_only_inside_explicit_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "projects"
            parent.mkdir()
            root = parent / "topic"
            scaffold(root, force=False, allowed_parent=parent)
            self.assertTrue((root / "report" / "research_report.md").exists())
            broker_list = root / "data" / "broker_report_list.csv"
            self.assertTrue(broker_list.exists())
            self.assertIn("forecast_horizon", broker_list.read_text(encoding="utf-8"))
            self.assertTrue((root / "diagrams").is_dir())
            diagram_manifest = root / "data" / "diagram_manifest.csv"
            self.assertTrue(diagram_manifest.exists())
            self.assertIn("source_html", diagram_manifest.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
