from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools.aggregate_meta import emit_evidence, run, validate_chapters
from tools.migrate_chapter_meta import migrate_chapter


def valid_chapter() -> dict:
    return {
        "schema_version": 2,
        "chapter_id": "ch01",
        "title": "章节",
        "reader_question": "问题？",
        "thesis": "结论",
        "argument_role": "论证",
        "sources": [
            {"source_id": "S1", "title": "来源一", "url": "https://one.example/a", "organization": "甲", "publish_date": "2025-01-01", "tier": "A", "independence_group": "甲"},
            {"source_id": "S2", "title": "来源二", "url": "https://two.example/b", "organization": "乙", "publish_date": "2025-02-01", "tier": "B", "independence_group": "乙"},
        ],
        "claims": [
            {"claim_id": "C1", "text": "市场规模为 10 亿元", "source_ids": ["S1", "S2"], "supporting_evidence_ids": ["E1", "E2"], "opposing_evidence_ids": [], "confidence": "高", "limitations": []},
        ],
        "data_points": [
            {"evidence_id": "E1", "claim_id": "C1", "source_ids": ["S1"], "value": 10, "unit": "亿元", "stat_time": "2025", "region": "中国", "population_or_scope": "目标市场", "definition": "公开口径", "confidence": "高", "limitations": []},
            {"evidence_id": "E2", "claim_id": "C1", "source_ids": ["S2"], "value": 10, "unit": "亿元", "stat_time": "2025", "region": "中国", "population_or_scope": "目标市场", "definition": "公开口径", "confidence": "中高", "limitations": []},
        ],
        "screenshots": [],
        "controversies": [],
        "gaps": [],
        "chapter_conclusion": {"claim_id": "C1", "judgment": "市场规模为 10 亿元", "supporting_evidence_ids": ["E1", "E2"], "opposing_evidence_ids": [], "conditions": "公开口径", "time_range": "2025", "confidence": "高", "limitations": [], "decision_implication": "继续观察"},
    }


class MigrationTests(unittest.TestCase):
    def test_v1_migration_preserves_qualifiers_and_does_not_invent_conclusion_support(self) -> None:
        old = {
            "chapter_id": "ch01", "title": "章节", "reader_question": "问题？",
            "thesis": "结论", "argument_role": "论证",
            "data_points": [{"id": "DP1", "claim": "收入", "value": 10, "unit": "亿元", "stat_time": "2025", "region": "中国", "population_or_scope": "企业", "definition": "财报口径", "source": "年报", "url": "https://example.com/report", "level": "A"}],
            "screenshots": [], "controversies": [], "gaps": [],
            "chapter_conclusion": {"judgment": "收入增长", "counter_evidence": "", "conditions": "", "time_range": "2025", "confidence": "高", "decision_implication": ""},
        }
        migrated = migrate_chapter(old)
        point = migrated["data_points"][0]
        self.assertEqual(point["unit"], "亿元")
        self.assertEqual(point["stat_time"], "2025")
        self.assertEqual(point["region"], "中国")
        self.assertEqual(migrated["chapter_conclusion"]["supporting_evidence_ids"], [])
        self.assertTrue(any("人工补录" in item for item in migrated["chapter_conclusion"]["limitations"]))


class AggregateTests(unittest.TestCase):
    def test_evidence_matrix_uses_ids_not_conclusion_text_as_support(self) -> None:
        chapter = valid_chapter()
        rows = emit_evidence([chapter])
        self.assertEqual(rows[0]["supporting_evidence"], "E1; E2")
        self.assertNotEqual(rows[0]["supporting_evidence"], rows[0]["core_conclusion"])
        self.assertEqual(rows[0]["sufficiency"], "充分")

    def test_numeric_evidence_requires_qualifiers(self) -> None:
        chapter = valid_chapter()
        chapter["data_points"][0]["unit"] = None
        chapter["data_points"][0]["stat_time"] = None
        chapter["data_points"][0]["region"] = None
        chapter["data_points"][0]["population_or_scope"] = None
        _, result = validate_chapters([chapter])
        joined = "\n".join(result.errors)
        self.assertIn("缺少 unit", joined)
        self.assertIn("缺少 stat_time", joined)
        self.assertIn("region 或 population_or_scope", joined)

    def test_validation_failure_does_not_overwrite_existing_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "evidence").mkdir()
            sentinel = root / "data" / "source_data.csv"
            sentinel.write_text("old,data\n", encoding="utf-8")
            chapter = valid_chapter()
            chapter["chapter_conclusion"]["supporting_evidence_ids"] = []
            (root / "data" / "chapter_meta.json").write_text(json.dumps([chapter], ensure_ascii=False), encoding="utf-8")
            self.assertEqual(run(root, "data/chapter_meta.json", force=True), 1)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "old,data\n")

    def test_force_writes_all_outputs_and_creates_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "evidence").mkdir()
            (root / "data" / "chapter_meta.json").write_text(json.dumps([valid_chapter()], ensure_ascii=False), encoding="utf-8")
            (root / "data" / "source_data.csv").write_text("old\n", encoding="utf-8")
            self.assertEqual(run(root, "data/chapter_meta.json", force=True), 0)
            self.assertTrue((root / "evidence" / "evidence_matrix.csv").exists())
            backups = list((root / ".aggregate-backups").glob("*/data/source_data.csv"))
            self.assertEqual(len(backups), 1)
            with (root / "data" / "source_data.csv").open(encoding="utf-8") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["unit"], "亿元")
            self.assertEqual(row["stat_time"], "2025")
            self.assertEqual(row["region"], "中国")

    def test_meta_path_cannot_escape_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(run(root, "../outside.json", dry_run=True), 2)


if __name__ == "__main__":
    unittest.main()
