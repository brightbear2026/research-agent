from __future__ import annotations

import copy
import unittest

from tools.meta_schema import migrate_v1_to_v2, validate_chapter_meta


def valid_meta() -> dict:
    return {
        "schema_version": 2,
        "chapter_id": "ch01", "title": "第一章", "reader_question": "问题",
        "thesis": "结论", "argument_role": "建立前提",
        "sources": [
            {"source_id": "ch01-S001", "type": "报告", "organization": "机构甲",
             "title": "报告甲", "publication": "官网", "publish_date": "2025-01-01",
             "url": "https://a.example/report", "access_date": "2026-08-09", "tier": "A",
             "independence_group": "机构甲"},
            {"source_id": "ch01-S002", "type": "数据集", "organization": "机构乙",
             "title": "数据乙", "publication": "官网", "publish_date": "2025-02-01",
             "url": "https://b.example/data", "access_date": "2026-08-09", "tier": "B",
             "independence_group": "机构乙"},
        ],
        "evidence_items": [
            {"evidence_id": "ch01-E001", "summary": "两项原始统计共同显示指标上升",
             "source_ids": ["ch01-S001", "ch01-S002"], "stance": "support", "limitations": "口径不同"},
            {"evidence_id": "ch01-E002", "summary": "部分样本没有上升",
             "source_ids": ["ch01-S002"], "stance": "oppose", "limitations": "样本较小"},
        ],
        "claims": [{"claim_id": "ch01-C001", "statement": "指标整体上升",
                    "supporting_evidence_ids": ["ch01-E001"], "opposing_evidence_ids": ["ch01-E002"],
                    "conditions": "限定样本", "confidence": "中高", "decision_implication": "继续观察"}],
        "data_points": [{"data_id": "ch01-D001", "claim": "增长率", "value": "42",
                         "unit": "%", "stat_time": "2025", "region": "中国",
                         "definition": "同比增长率", "source_ids": ["ch01-S001", "ch01-S002"],
                         "is_key": True, "notes": ""}],
        "screenshots": [], "controversies": [], "gaps": [],
        "chapter_conclusion": {"claim_id": "ch01-C001", "judgment": "指标整体上升",
                               "counter_evidence": "部分样本没有上升", "conditions": "限定样本",
                               "time_range": "2025", "confidence": "中高", "decision_implication": "继续观察"},
    }


class MetaSchemaTests(unittest.TestCase):
    def test_valid_v2_meta(self) -> None:
        self.assertEqual(validate_chapter_meta(valid_meta()), [])

    def test_valid_diagram_links_sources_and_claims(self) -> None:
        meta = copy.deepcopy(valid_meta())
        meta["diagrams"] = [{
            "fig_id": "FIG-101", "title": "信息流", "visual_type": "architecture",
            "source_html": "diagrams/FIG-101.html", "local_path": "images/FIG-101.png",
            "size": "doc-wide", "detail": "balanced", "profile": "default",
            "source_ids": ["ch01-S001"], "supports_claim_ids": ["ch01-C001"],
            "alt_text": "输入、处理与输出之间的信息流",
        }]
        self.assertEqual(validate_chapter_meta(meta), [])

    def test_rejects_invalid_diagram_provenance_and_path(self) -> None:
        meta = copy.deepcopy(valid_meta())
        meta["diagrams"] = [{
            "fig_id": "FIG-101", "title": "信息流", "visual_type": "architecture",
            "source_html": "../escape.html", "local_path": "images/FIG-101.png",
            "size": "doc-wide", "detail": "balanced", "profile": "default",
            "source_ids": ["ch01-S999"], "supports_claim_ids": ["ch01-C999"],
            "alt_text": "信息流",
        }]
        errors = validate_chapter_meta(meta)
        self.assertTrue(any("source_html" in error for error in errors))
        self.assertTrue(any("不存在的来源" in error for error in errors))
        self.assertTrue(any("不存在的结论" in error for error in errors))

    def test_rejects_self_support_and_missing_numeric_scope(self) -> None:
        meta = copy.deepcopy(valid_meta())
        meta["evidence_items"][0]["summary"] = meta["claims"][0]["statement"]
        meta["data_points"][0]["unit"] = ""
        errors = validate_chapter_meta(meta)
        self.assertTrue(any("自我支撑" in error for error in errors))
        self.assertTrue(any("缺少 unit" in error for error in errors))

    def test_v1_migration_does_not_invent_evidence_links(self) -> None:
        migrated = migrate_v1_to_v2({
            "chapter_id": "ch02", "title": "旧章", "reader_question": "问题",
            "thesis": "旧结论", "argument_role": "背景", "data_points": [],
            "screenshots": [], "controversies": [], "gaps": [], "chapter_conclusion": {},
        })
        self.assertEqual(migrated["claims"][0]["supporting_evidence_ids"], [])
        self.assertTrue(any(gap["impact"] == "high" for gap in migrated["gaps"]))


if __name__ == "__main__":
    unittest.main()
