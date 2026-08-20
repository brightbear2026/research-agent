from __future__ import annotations

import csv
import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.aggregate_meta import AggregateError, run
from tests.test_meta_schema import valid_meta


class AggregateMetaTests(unittest.TestCase):
    def prepare(self, root: Path) -> None:
        (root / "data").mkdir()
        (root / "evidence").mkdir()
        (root / "report").mkdir()
        (root / "data/chapter_meta.json").write_text(
            json.dumps([valid_meta()], ensure_ascii=False), encoding="utf-8"
        )
        (root / "report/_assembled_report.md").write_text("# 第一章\n", encoding="utf-8")

    def test_preserves_numeric_semantics_and_real_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare(root)
            self.assertEqual(run(root, "data/chapter_meta.json"), 0)
            with (root / "data/source_data.csv").open(encoding="utf-8") as handle:
                data = list(csv.DictReader(handle))
            with (root / "evidence/evidence_matrix.csv").open(encoding="utf-8") as handle:
                evidence = list(csv.DictReader(handle))
            self.assertEqual(data[0]["unit"], "%")
            self.assertEqual(data[0]["stat_time"], "2025")
            self.assertEqual(data[0]["region"], "中国")
            self.assertNotEqual(evidence[0]["core_conclusion"], evidence[0]["supporting_evidence"])
            self.assertEqual(evidence[0]["independent_source_groups"], "2")

    def test_refuses_nonempty_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare(root)
            (root / "data/source_data.csv").write_text("a\nold\n", encoding="utf-8")
            with self.assertRaises(AggregateError):
                run(root, "data/chapter_meta.json")
            self.assertEqual((root / "data/source_data.csv").read_text(encoding="utf-8"), "a\nold\n")
            self.assertEqual(run(root, "data/chapter_meta.json", force=True), 0)
            self.assertTrue(any((root / "backups").rglob("source_data.csv")))

    def test_emits_diagram_manifest_with_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare(root)
            meta = copy.deepcopy(valid_meta())
            meta["diagrams"] = [{
                "fig_id": "FIG-101", "title": "信息流", "visual_type": "architecture",
                "source_html": "diagrams/FIG-101.html", "local_path": "images/FIG-101.png",
                "size": "doc-wide", "detail": "balanced", "profile": "default",
                "source_ids": ["ch01-S001"], "supports_claim_ids": ["ch01-C001"],
                "alt_text": "输入、处理与输出之间的信息流",
            }]
            (root / "data/chapter_meta.json").write_text(
                json.dumps([meta], ensure_ascii=False), encoding="utf-8"
            )
            (root / "report/_assembled_report.md").write_text(
                "# 第一章\n\n![信息流](images/FIG-101.png)\n", encoding="utf-8"
            )
            self.assertEqual(run(root, "data/chapter_meta.json"), 0)
            with (root / "data/diagram_manifest.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["fig_id"], "FIG-101")
            self.assertEqual(rows[0]["source_ids"], "ch01-S001")
            self.assertEqual(rows[0]["supports_conclusion"], "ch01-C001")


if __name__ == "__main__":
    unittest.main()
