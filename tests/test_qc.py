from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.qc import Report, check_diagrams, check_editor_baseline, check_figures, check_readability


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

    def test_diagram_requires_exported_png_and_success_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "diagrams").mkdir()
            (root / "images").mkdir()
            (root / "diagrams/FIG-101.html").write_text(
                '<svg viewBox="0 0 10 10" role="img" aria-labelledby="t d"><title id="t">图</title><desc id="d">说明</desc></svg>',
                encoding="utf-8",
            )
            (root / "data/diagram_manifest.csv").write_text(
                "fig_id,source_html,local_path,title,alt_text,visual_type,size,detail,profile,source_ids,source_orgs,source_docs,supports_conclusion\n"
                "FIG-101,diagrams/FIG-101.html,images/FIG-101.png,图,说明,architecture,doc-wide,balanced,default,ch01-S001,机构,报告,ch01-C001\n",
                encoding="utf-8",
            )
            report = Report()
            check_diagrams(report, "![说明](images/FIG-101.png)", [], root, strict=True)
            self.assertTrue(any("尚未导出 PNG" in error for error in report.errors))
            self.assertTrue(any("未登记到 figures.csv" in error for error in report.errors))


if __name__ == "__main__":
    unittest.main()
