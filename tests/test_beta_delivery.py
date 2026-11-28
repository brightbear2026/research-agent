from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.merge import main as merge
from tools.qc import Report, check_delivery_length, check_readability, delivery_body, delivery_chars


class DeliveryTests(unittest.TestCase):
    def test_depth_and_length_are_independent(self):
        text = "两组样本的定义不同，需分别核验。\n\n|对象|解释|\n|---|---|\n|甲|原始研究[1]|"
        report = Report()
        check_readability(report, text, "深度", True)
        self.assertFalse(report.errors)
        self.assertTrue(report.warnings)

    def test_stubs_and_table_only_reports_fail(self):
        for text in ("# 标题\n\n待填写[1]", "|对比|来源|\n|---|---|\n|甲|材料[1]|"):
            with self.subTest(text=text):
                report = Report()
                check_readability(report, text, "标准", True)
                self.assertTrue(report.errors)

    def test_explicit_length_counts_table_content_and_excludes_appendix(self):
        text = "## 目录\n- 第一章\n# 发现\n判断[1]。\n\n|项目|值|\n|---|---|\n|甲|乙|\n\n## 参考文献\n资料"
        body = delivery_body(text)
        self.assertEqual(delivery_chars(body), len("判断。项目值甲乙"))
        with tempfile.TemporaryDirectory() as folder:
            brief = Path(folder) / "brief.json"
            for maximum, allowed in [(7, False), (8, True)]:
                brief.write_text(json.dumps({"max_chars": maximum}))
                report = Report()
                check_delivery_length(report, body, brief, True)
                self.assertEqual(not report.errors, allowed)

    def test_synthesis_can_only_reuse_sources_and_preserves_earlier_numbers(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            out = root / "report"
            out.mkdir()
            (root / "data").mkdir()
            source = "[[SRC|网页|研究组|资料页|示例|2026|https://example.com/a|2026|A]]"
            (out / "_draft_ch01_x.md").write_text("# 第 1 章\n原文" + source)
            summary = out / "_synthesis.md"
            summary.write_text("## 执行摘要\n结论" + source)
            with patch("sys.argv", ["merge", folder, "--data-cutoff-date", "2026-11-13"]):
                self.assertEqual(merge(), 0)
                result = (out / "_assembled_report.md").read_text()
                self.assertIn("结论[1]", result)
                self.assertIn("原文[1]", result)
                self.assertIn("2026-11-13", result)
                summary.write_text("未登记结论" + source.replace("/a|", "/new|"))
                with self.assertRaises(SystemExit):
                    merge()
                self.assertEqual((out / "_assembled_report.md").read_text(), result)
                summary.unlink()
                (out / "_draft_ch02_y.md").write_text("# 第 2 章\n补充" + source)
                with patch("sys.argv", ["merge", folder, "--require-synthesis"]):
                    with self.assertRaises(SystemExit):
                        merge()
