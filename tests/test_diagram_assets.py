from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from tools.diagram_assets import resolve_input_path, run, validate_diagram_html


VALID_HTML = """<!doctype html>
<html><head><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist"></head>
<body><svg viewBox="0 0 640 360" role="img" aria-labelledby="fig-title fig-desc">
<title id="fig-title">研究信息流</title><desc id="fig-desc">输入经过分析形成结论</desc>
<rect width="640" height="360" fill="#fff"/></svg></body></html>
"""


class DiagramAssetTests(unittest.TestCase):
    def test_validate_static_accessible_diagram(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "diagram.html"
            path.write_text(VALID_HTML, encoding="utf-8")
            self.assertEqual(validate_diagram_html(path), [])

    def test_rejects_script_and_remote_asset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "diagram.html"
            path.write_text(
                VALID_HTML.replace("</body>", '<img src="https://example.com/a.png"><script>x()</script></body>'),
                encoding="utf-8",
            )
            errors = validate_diagram_html(path)
            self.assertTrue(any("script" in error.lower() for error in errors))
            self.assertTrue(any("远程资源" in error for error in errors))

    def test_validate_only_manifest_and_path_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "diagrams").mkdir()
            (root / "images").mkdir()
            (root / "data").mkdir()
            source = root / "diagrams/FIG-101.html"
            source.write_text(VALID_HTML, encoding="utf-8")
            manifest = root / "data/diagram_manifest.csv"
            fields = [
                "fig_id", "source_html", "local_path", "title", "alt_text", "visual_type",
                "size", "detail", "profile", "source_ids", "source_orgs", "source_docs",
                "supports_conclusion",
            ]
            with manifest.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({
                    "fig_id": "FIG-101", "source_html": "diagrams/FIG-101.html",
                    "local_path": "images/FIG-101.png", "title": "信息流", "alt_text": "信息流",
                    "visual_type": "architecture", "size": "doc-wide", "detail": "balanced",
                    "profile": "default", "source_ids": "ch01-S001", "source_orgs": "机构甲",
                    "source_docs": "报告甲", "supports_conclusion": "ch01-C001",
                })
            self.assertEqual(run(manifest, root / "data/figures.csv", root, validate_only=True), 0)
            with self.assertRaises(ValueError):
                resolve_input_path(root, "../escape.html")

    def test_exports_png_and_merges_figure_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "diagrams").mkdir()
            (root / "images").mkdir()
            (root / "data").mkdir()
            (root / "diagrams/FIG-101.html").write_text(VALID_HTML, encoding="utf-8")
            manifest = root / "data/diagram_manifest.csv"
            fields = [
                "fig_id", "source_html", "local_path", "title", "alt_text", "visual_type",
                "size", "detail", "profile", "source_ids", "source_orgs", "source_docs",
                "supports_conclusion",
            ]
            with manifest.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({
                    "fig_id": "FIG-101", "source_html": "diagrams/FIG-101.html",
                    "local_path": "images/FIG-101.png", "title": "信息流", "alt_text": "信息流",
                    "visual_type": "architecture", "size": "doc-wide", "detail": "balanced",
                    "profile": "default", "source_ids": "ch01-S001", "source_orgs": "机构甲",
                    "source_docs": "报告甲", "supports_conclusion": "ch01-C001",
                })
            figures = root / "data/figures.csv"
            self.assertEqual(run(manifest, figures, root), 0)
            self.assertTrue((root / "images/FIG-101.png").read_bytes().startswith(b"\x89PNG"))
            with figures.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["status"], "已生成(Diagram Design)")
            self.assertEqual(rows[0]["supports_conclusion"], "ch01-C001")


if __name__ == "__main__":
    unittest.main()
