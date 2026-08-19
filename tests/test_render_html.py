from __future__ import annotations

import unittest
from pathlib import Path

from tools.render_html import link_citations


class RenderHtmlTests(unittest.TestCase):
    def test_citations_render_as_compact_superscript(self) -> None:
        html, cited = link_citations("<p>结论[12]。</p>")
        self.assertEqual(cited, {12})
        self.assertIn('<sup class="cite">', html)
        self.assertIn('href="#ref-12"', html)
        self.assertNotIn(">[12]<", html)

    def test_template_adds_back_button_in_html_layer_only(self) -> None:
        template = (Path(__file__).parents[1] / "templates" / "report.html.j2").read_text(encoding="utf-8")
        self.assertIn("document.createElement('button')", template)
        self.assertNotIn("javascript:void(0)", template)


if __name__ == "__main__":
    unittest.main()
