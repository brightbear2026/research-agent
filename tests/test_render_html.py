from __future__ import annotations

import unittest

from tools.render_html import link_citations


class RenderHtmlTests(unittest.TestCase):
    def test_citations_render_as_compact_superscript(self) -> None:
        html, cited = link_citations("<p>结论[12]。</p>")
        self.assertEqual(cited, {12})
        self.assertIn('<sup class="cite">', html)
        self.assertIn('href="#ref-12"', html)
        self.assertNotIn(">[12]<", html)


if __name__ == "__main__":
    unittest.main()
