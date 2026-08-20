from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from tools.qc import (
    Report,
    _categorize_warning,
    _parse_year_month,
    check_editor_baseline,
    check_diagrams,
    check_evidence_independence,
    check_fact_citation_locality,
    check_figures,
    check_links,
    check_numeric_claim_sourcing,
    check_prohibited_content,
    check_readability,
    check_source_freshness,
    run,
    wayback_snapshot,
)


class QCTests(unittest.TestCase):
    def test_diagram_requires_static_source_export_index_and_body_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "diagrams").mkdir()
            (root / "images").mkdir()
            source = root / "diagrams/FIG-101.html"
            source.write_text(
                '<svg viewBox="0 0 10 10" role="img" aria-labelledby="t d">'
                '<title id="t">图</title><desc id="d">说明</desc></svg>',
                encoding="utf-8",
            )
            image = root / "images/FIG-101.png"
            image.write_bytes(b"png")
            diagrams = [{
                "fig_id": "FIG-101", "source_html": "diagrams/FIG-101.html",
                "local_path": "images/FIG-101.png", "source_ids": "S1",
                "supports_conclusion": "C1",
            }]
            figures = [{
                "fig_id": "FIG-101", "local_path": "images/FIG-101.png",
                "status": "已生成(Diagram Design)",
            }]
            report = Report()
            check_diagrams(
                report, "![信息流](images/FIG-101.png)", diagrams, figures, root, strict=True,
            )
            self.assertFalse(report.errors)

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


class WaybackAndLinkTests(unittest.TestCase):
    def test_wayback_snapshot_returns_url_when_archived(self) -> None:
        with patch("httpx.Client") as mock_client_cls:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "archived_snapshots": {
                    "closest": {"available": True, "url": "http://web.archive.org/web/1/https://x.example"}
                }
            }
            client = MagicMock()
            client.__enter__.return_value = client
            client.get.return_value = resp
            mock_client_cls.return_value = client
            self.assertEqual(
                wayback_snapshot("https://x.example"),
                "http://web.archive.org/web/1/https://x.example",
            )

    def test_wayback_snapshot_returns_none_when_no_archive_or_error(self) -> None:
        with patch("httpx.Client") as mock_client_cls:
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {"archived_snapshots": {}}
            client = MagicMock()
            client.__enter__.return_value = client
            client.get.return_value = resp
            mock_client_cls.return_value = client
            self.assertIsNone(wayback_snapshot("https://x.example"))
        # 网络异常优雅降级为 None
        with patch("httpx.Client", side_effect=RuntimeError("boom")):
            self.assertIsNone(wayback_snapshot("https://x.example"))

    def test_dead_and_archived_links_are_warnings_not_errors(self) -> None:
        def fake_classify(url: str) -> tuple[str, str]:
            return {
                "https://a.example": ("dead", "HTTP 404"),
                "https://b.example": ("archived", "HTTP 410；Wayback 已归档：http://web.archive.org/x"),
                "https://c.example": ("warn", "HTTP 403"),
                "https://d.example": ("ok", "HTTP 200"),
            }[url]

        with patch("tools.qc.classify_url", side_effect=fake_classify):
            report = Report()
            citations = [
                {"id": str(i), "url": u}
                for i, u in enumerate(
                    ["https://a.example", "https://b.example", "https://c.example", "https://d.example"], 1
                )
            ]
            check_links(report, citations, [])
        self.assertFalse(report.errors)
        joined = "\n".join(report.warnings)
        self.assertIn("死链 1 个", joined)
        self.assertIn("已归档死链 1 个", joined)
        self.assertIn("链接警告 1 个", joined)


class FreshnessTests(unittest.TestCase):
    def test_stale_fast_moving_ab_source_flagged_others_ignored(self) -> None:
        citations = [
            {"id": "1", "tier": "A", "url": "https://www.yolegroup.com/old",
             "publish_date": "2024-01", "title": "Old Yole Report"},
            {"id": "2", "tier": "A", "url": "https://www.yolegroup.com/new",
             "publish_date": "2026-06", "title": "New Yole Report"},
            {"id": "3", "tier": "C", "url": "https://www.yolegroup.com/c-tier",
             "publish_date": "2019-01", "title": "C tier ignored"},
            {"id": "4", "tier": "A", "url": "https://example.edu/research",
             "publish_date": "2020-01", "title": "Non-fast domain ignored"},
        ]
        report = Report()
        check_source_freshness(report, citations, strict=True, reference_date=datetime(2026, 8, 1))
        joined = "\n".join(report.warnings)
        self.assertIn("时效性", joined)
        self.assertIn("Old Yole Report", joined)   # ~31 个月 > 18
        self.assertNotIn("New Yole Report", joined)  # 新鲜
        self.assertNotIn("C tier ignored", joined)   # 非 A/B
        self.assertNotIn("Non-fast domain", joined)  # 非快变域名

    def test_parse_year_month_handles_common_formats(self) -> None:
        self.assertEqual(_parse_year_month("2024-06"), (2024, 6))
        self.assertEqual(_parse_year_month("2024"), (2024, 1))
        self.assertEqual(_parse_year_month("访问日期 2023/05/01"), (2023, 5))
        self.assertIsNone(_parse_year_month("未注明"))
        self.assertIsNone(_parse_year_month(None))


class NumericSourcingTests(unittest.TestCase):
    def test_single_cd_numeric_fact_flagged(self) -> None:
        report = Report()
        check_numeric_claim_sourcing(
            report, "【事实】某公司投资 400 亿建厂[5]。", [{"id": "5", "tier": "C"}], strict=True
        )
        self.assertTrue(any("段落级数值声明" in w for w in report.warnings))

    def test_second_source_clears_flag(self) -> None:
        report = Report()
        check_numeric_claim_sourcing(
            report,
            "【事实】某公司投资 400 亿建厂[5][6]。",
            [{"id": "5", "tier": "C"}, {"id": "6", "tier": "B"}],
            strict=True,
        )
        self.assertFalse(any("段落级数值声明" in w for w in report.warnings))

    def test_ab_single_source_not_flagged(self) -> None:
        report = Report()
        check_numeric_claim_sourcing(
            report, "【事实】规模 500 亿美元[7]。", [{"id": "7", "tier": "B"}], strict=True
        )
        self.assertFalse(any("段落级数值声明" in w for w in report.warnings))


class QcDebtManifestTests(unittest.TestCase):
    def test_categorize_warning_buckets(self) -> None:
        self.assertEqual(_categorize_warning("死链 1 个：x"), "dead_links")
        self.assertEqual(_categorize_warning("已归档死链 1 个：x"), "archived_links")
        self.assertEqual(_categorize_warning("链接警告 1 个：x"), "link_warnings")
        self.assertEqual(_categorize_warning("时效性：x"), "staleness")
        self.assertEqual(_categorize_warning("段落级数值声明仅依赖单一 C/D 级来源"), "numeric_sourcing")
        self.assertEqual(_categorize_warning("其他"), "other")

    def test_run_always_writes_qc_debt_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "report").mkdir()
            report_md = root / "report" / "research_report.md"
            report_md.write_text("# 空报告\n\n几乎无内容。\n", encoding="utf-8")
            for name in ("citations.csv", "figures.csv"):
                (root / "data" / name).write_text("id\n", encoding="utf-8")
            code = run(
                root, report_md, skip_links=True, strict=False,
                depth="快速", skip_readability=True,
            )
            debt_path = root / "data" / "qc_debt.json"
            self.assertTrue(debt_path.exists())
            manifest = json.loads(debt_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["exit_code"], code)
            self.assertEqual(manifest["core_passed"], code == 0)
            self.assertIn("by_category", manifest["summary"])
            self.assertIsInstance(manifest["debt"], list)


if __name__ == "__main__":
    unittest.main()
