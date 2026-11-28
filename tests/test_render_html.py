from __future__ import annotations

import unittest
from pathlib import Path

from tools.render_html import enhance_figures, link_citations


class RenderHtmlTests(unittest.TestCase):
    def test_citations_render_as_compact_superscript(self) -> None:
        html, cited = link_citations("<p>结论[12]。</p>")
        self.assertEqual(cited, {12})
        self.assertIn('<sup class="cite">', html)
        self.assertIn('href="#ref-12"', html)
        self.assertNotIn(">[12]<", html)

    def test_captured_screenshot_opens_original_without_limiting_analysis_figures(self) -> None:
        image = '<p><img src="images/FIG-001.png" alt="原图"></p>'
        row = {"local_path": "images/FIG-001.png", "status": "已截图"}
        result = enhance_figures(image, [row])
        self.assertIn('href="../images/FIG-001.png"', result)
        self.assertIn('class="source-capture"', result)
        self.assertNotIn('class="source-capture"', enhance_figures(image, []))

    def test_template_adds_back_button_in_html_layer_only(self) -> None:
        template = (Path(__file__).parents[1] / "templates" / "report.html.j2").read_text(encoding="utf-8")
        self.assertIn("document.createElement('button')", template)
        self.assertNotIn("javascript:void(0)", template)


if __name__ == "__main__":
    unittest.main()
