from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.screenshot import download_binary, resolve_output_path


class FakeResponse:
    def __init__(self, status: int, payload: bytes = b"", headers: dict | None = None) -> None:
        self.status_code = status
        self.payload = payload
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_bytes(self):
        yield self.payload


class FakeClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def stream(self, *_args, **_kwargs):
        return self.responses.pop(0)


class ScreenshotTests(unittest.TestCase):
    def test_output_must_stay_under_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            self.assertEqual(resolve_output_path(root, "images/FIG-001.png"), root / "images/FIG-001.png")
            with self.assertRaises(ValueError):
                resolve_output_path(root, "../outside.png")
            with self.assertRaises(ValueError):
                resolve_output_path(root, "/tmp/outside.png")

    def test_retries_429_then_streams_success(self) -> None:
        client = FakeClient([
            FakeResponse(429, headers={"retry-after": "0"}),
            FakeResponse(200, b"%PDF-test", {"content-type": "application/pdf"}),
        ])
        with patch("httpx.Client", return_value=client), patch("time.sleep"):
            payload, content_type, error = download_binary("https://example.com/a.pdf")
        self.assertEqual(payload, b"%PDF-test")
        self.assertEqual(content_type, "application/pdf")
        self.assertEqual(error, "")


if __name__ == "__main__":
    unittest.main()
