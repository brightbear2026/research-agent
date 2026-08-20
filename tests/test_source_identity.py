from __future__ import annotations

import unittest

from tools.source_identity import registrable_host, source_independence_key


class SourceIdentityTests(unittest.TestCase):
    def test_subdomains_of_same_parent_are_not_independent(self) -> None:
        first = {"url": "https://news.example.com/a"}
        second = {"url": "https://data.example.com/b"}
        self.assertEqual(source_independence_key(first), source_independence_key(second))

    def test_multi_label_public_suffix_is_grouped_conservatively(self) -> None:
        self.assertEqual(registrable_host("https://a.example.co.uk/x"), "example.co.uk")

    def test_unknown_sources_do_not_gain_independence_from_arbitrary_ids(self) -> None:
        self.assertEqual(
            source_independence_key({"source_id": "S1"}),
            source_independence_key({"source_id": "S2"}),
        )


if __name__ == "__main__":
    unittest.main()
