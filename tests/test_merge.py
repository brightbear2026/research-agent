from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.merge import TAG_RE, extract_url, main, norm_key, normalize_tag_inner, parse_fields, strip_internal_sections


class MergeTests(unittest.TestCase):
    def test_plain_source_tag_is_parsed(self) -> None:
        text = "结论[[SRC|网页|机构|标题|官网|2025-01-01|https://example.com/a|2026-01-01|A]]"
        match = TAG_RE.search(text)
        self.assertIsNotNone(match)
        inner = normalize_tag_inner(match.group(1))  # type: ignore[union-attr]
        self.assertEqual(extract_url(inner), "https://example.com/a")
        self.assertEqual(parse_fields(inner)[-1], "A")

    def test_escaped_table_source_tag_is_parsed(self) -> None:
        text = r"| 指标 | [[SRC\|网页\|机构\|标题\|官网\|2025-01-01\|https://example.com/a\|2026-01-01\|A]] |"
        match = TAG_RE.search(text)
        self.assertIsNotNone(match)
        inner = normalize_tag_inner(match.group(1))  # type: ignore[union-attr]
        fields = parse_fields(inner)
        self.assertEqual(fields[1], "机构")
        self.assertEqual(fields[5], "https://example.com/a")
        self.assertEqual(fields[7], "A")

    def test_url_key_removes_tracking_fragment_and_normalizes_host(self) -> None:
        first = "https://www.Example.com/report/?b=2&utm_source=news&a=1#page=3"
        second = "http://example.com/report?a=1&b=2"
        self.assertEqual(norm_key(first), norm_key(second))

    def test_doi_and_arxiv_versions_are_canonicalized(self) -> None:
        self.assertEqual(
            norm_key("https://dx.doi.org/10.1000/ABC"),
            norm_key("http://doi.org/10.1000/abc/"),
        )
        self.assertEqual(
            norm_key("https://arxiv.org/pdf/2401.01234v2.pdf"),
            norm_key("https://www.arxiv.org/abs/2401.01234"),
        )

    def test_internal_sections_are_removed_but_reader_content_remains(self) -> None:
        draft = """# 第一章

## 本章结论

先给结论。

## 数据小表（供 source_data.csv）

| 指标 | 值 |
|---|---|
| A | 1 |

## 对决策的含义

- 应采取行动。

## 建议截图登记（供 screenshot_manifest.csv）

- FIG-001

## 待补充内容（资料缺口）

- 暂无
"""
        cleaned = strip_internal_sections(draft)
        self.assertIn("先给结论", cleaned)
        self.assertIn("对决策的含义", cleaned)
        self.assertNotIn("数据小表", cleaned)
        self.assertNotIn("建议截图", cleaned)
        self.assertNotIn("待补充内容", cleaned)

    def test_main_writes_assembly_and_chapter_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "report").mkdir()
            (root / "data").mkdir()
            draft = root / "report" / "_draft_ch01_intro.md"
            draft.write_text(
                r"# 第一章" "\n\n## 本章结论\n\n结论"
                r"[[SRC\|网页\|机构\|标题\|官网\|2025-01-01\|https://example.com/a\|2026-01-01\|A]]。"
                "\n\n## 数据小表（供 source_data.csv）\n\n| A | 1 |\n"
                "\n## 对决策的含义\n\n- 行动。\n",
                encoding="utf-8",
            )
            meta = {key: [] for key in (
                "data_points", "screenshots", "controversies", "gaps"
            )}
            meta.update({
                "schema_version": 2,
                "chapter_id": "ch01",
                "title": "第一章",
                "reader_question": "问题",
                "thesis": "结论",
                "argument_role": "建立前提",
                "sources": [],
                "claims": [],
                "chapter_conclusion": {},
            })
            draft.with_suffix(".meta.json").write_text(
                json.dumps(meta, ensure_ascii=False), encoding="utf-8"
            )

            with patch("sys.argv", ["merge.py", str(root), "--require-meta"]):
                self.assertEqual(main(), 0)

            assembled = (root / "report" / "_assembled_report.md").read_text(encoding="utf-8")
            self.assertIn("结论[1]", assembled)
            self.assertNotIn("数据小表", assembled)
            combined = json.loads((root / "data" / "chapter_meta.json").read_text(encoding="utf-8"))
            self.assertEqual(combined[0]["chapter_id"], "ch01")
            ledger = json.loads((root / "data" / "claim_ledger.json").read_text(encoding="utf-8"))
            self.assertEqual(ledger["ledger_version"], 1)

    def test_require_meta_fails_before_writing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "report").mkdir()
            (root / "data").mkdir()
            (root / "report" / "_draft_ch01_intro.md").write_text(
                "# 第一章\n\n## 本章结论\n\n结论。\n", encoding="utf-8"
            )
            with patch("sys.argv", ["merge.py", str(root), "--require-meta"]):
                with self.assertRaises(SystemExit):
                    main()
            self.assertFalse((root / "report" / "_assembled_report.md").exists())
            self.assertFalse((root / "data" / "citations.csv").exists())


if __name__ == "__main__":
    unittest.main()
