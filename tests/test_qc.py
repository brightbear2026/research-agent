from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.qc import (
    Report,
    check_editor_baseline,
    check_evidence_independence,
    check_fact_citation_locality,
    check_figures,
    check_prohibited_content,
    check_readability,
)


class QCTests(unittest.TestCase):
    def test_internal_markers_fail_only_in_strict_mode(self) -> None:
        md = "# 第一章\n\n## 本章结论\n\n清晰结论。\n\n## 建议截图项\n\nFIG-001\n"

        normal = Report()
        check_readability(normal, md, "标准", strict=False)
        self.assertFalse(normal.errors)
        self.assertTrue(any("生产过程文字" in x for x in normal.warnings))

        strict = Report()
        check_readability(strict, md, "标准", strict=True)
        self.assertTrue(any("生产过程文字" in x for x in strict.errors))

    def test_residual_source_tag_is_always_an_error(self) -> None:
        report = Report()
        check_readability(
            report,
            r"# 第一章\n\n结论[[SRC\|网页\|机构\|标题\|官网\|2025\|https://example.com\|2026\|A]]。",
            "标准",
            strict=False,
        )
        self.assertTrue(any("未转换" in x for x in report.errors))

    def test_argument_chapter_requires_answer_and_decision_implication(self) -> None:
        report = Report()
        check_readability(
            report,
            "# 第 1 章 风险\n\n## 1.1 现状\n\n只有材料，没有答案。\n",
            "标准",
            strict=True,
        )
        self.assertTrue(any("本章结论" in x for x in report.errors))
        self.assertTrue(any("对决策的含义" in x for x in report.errors))

    def test_tiny_report_cannot_pass_strict_delivery(self) -> None:
        report = Report()
        check_readability(
            report,
            "# 第 1 章\n\n## 本章结论\n\n只有一句。\n\n## 对决策的含义\n\n观察。",
            "快速",
            strict=True,
        )
        self.assertTrue(any("最低完整度" in x for x in report.errors))

    def test_placeholder_figure_fails_in_strict_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "images" / "FIG-001.png"
            image.parent.mkdir()
            image.write_bytes(b"placeholder")
            figures = [{
                "fig_id": "FIG-001",
                "local_path": "images/FIG-001.png",
                "status": "失败(占位)",
            }]
            report = Report()
            check_figures(
                report,
                "![图](images/FIG-001.png)",
                figures,
                root,
                strict=True,
            )
            self.assertTrue(any("占位" in x for x in report.errors))

    def test_editor_cannot_introduce_new_citations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "assembled.md"
            baseline.write_text("原结论[1]。", encoding="utf-8")
            report = Report()
            check_editor_baseline(report, "编辑后结论[1][2]。", baseline)
            self.assertTrue(any("不存在的引用" in x for x in report.errors))

    def test_fact_tag_requires_citation_in_same_paragraph(self) -> None:
        report = Report()
        check_fact_citation_locality(
            report,
            "【事实】这是没有出处的事实。\n\n【事实】这是有出处的事实[1]。",
            strict=True,
        )
        self.assertTrue(any("没有同段引用" in x for x in report.errors))

    def test_banned_phrase_ascii_frame_and_long_quote_fail_strict_qc(self) -> None:
        report = Report()
        md = (
            "毫无疑问，这项技术必将成功。\n\n"
            "```text\n┌──┐\n│ A │\n└──┘\n```\n\n"
            '原文称 "one two three four five six seven eight nine ten eleven twelve thirteen '
            'fourteen fifteen sixteen seventeen eighteen nineteen twenty twenty-one twenty-two '
            'twenty-three twenty-four twenty-five twenty-six"。'
        )
        check_prohibited_content(report, md, strict=True)
        joined = "\n".join(report.errors)
        self.assertIn("禁用", joined)
        self.assertIn("框线图", joined)
        self.assertIn("英文直接引语", joined)

    def test_mermaid_box_characters_are_not_treated_as_ascii_frame(self) -> None:
        report = Report()
        check_prohibited_content(report, "```mermaid\nflowchart LR\n A-->B\n```", strict=True)
        self.assertFalse(report.errors)

    def test_chapter_conclusion_and_numeric_claim_need_independent_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            chapter = {
                "chapter_id": "ch01",
                "sources": [{"source_id": "S1", "url": "https://example.com/a", "independence_group": "甲"}],
                "claims": [{"claim_id": "C1", "text": "规模为 10", "source_ids": ["S1"], "supporting_evidence_ids": ["E1"]}],
                "data_points": [{"evidence_id": "E1", "value": 10, "source_ids": ["S1"]}],
                "chapter_conclusion": {"claim_id": "C1", "supporting_evidence_ids": ["E1"]},
            }
            (root / "data" / "chapter_meta.json").write_text(
                __import__("json").dumps([chapter], ensure_ascii=False), encoding="utf-8"
            )
            report = Report()
            check_evidence_independence(report, root, "标准", strict=True)
            joined = "\n".join(report.errors)
            self.assertIn("重要结论", joined)
            self.assertIn("数值声明", joined)


if __name__ == "__main__":
    unittest.main()
