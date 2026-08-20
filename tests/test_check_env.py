from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.check_env import chromium_install_location, load_chromium_spec


class EnvironmentCheckTests(unittest.TestCase):
    def test_reads_chromium_revision_from_installed_package_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "browsers.json"
            manifest.write_text(json.dumps({
                "browsers": [{"name": "chromium", "revision": "1234", "browserVersion": "151.0"}]
            }), encoding="utf-8")
            self.assertEqual(load_chromium_spec(manifest), ("1234", "151.0"))

    def test_missing_chromium_entry_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "browsers.json"
            manifest.write_text('{"browsers": []}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_chromium_spec(manifest)

    def test_parses_chromium_install_location_from_dry_run(self) -> None:
        output = """Chrome for Testing 151 (playwright chromium v1234)
  Install location:    /tmp/ms-playwright/chromium-1234
  Download url:        https://example.invalid/browser.zip
"""
        self.assertEqual(
            chromium_install_location(output, "1234"),
            Path("/tmp/ms-playwright/chromium-1234"),
        )


if __name__ == "__main__":
    unittest.main()
