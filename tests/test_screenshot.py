from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.screenshot import (
    MAX_PDF_BYTES,
    _needs_browser,
    capture_pdf,
    classify_access_obstacle,
    load_existing,
    parse_pages,
    resolve_image_output,
    retry_after_seconds,
    run,
)


class _Response:
    def __init__(self, status: int, headers: dict[str, str] | None = None, chunks: list[bytes] | None = None):
        self.status_code = status
        self.headers = headers or {}
        self._chunks = chunks or []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_bytes(self, _size: int):
        yield from self._chunks


class _Client:
    def __init__(self, responses: list[_Response], *args, **kwargs):
        self.responses = responses
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def stream(self, _method: str, _url: str):
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


class ScreenshotSafetyTests(unittest.TestCase):
    def test_output_must_stay_in_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target, rel = resolve_image_output(root, "images/FIG-001.png", "FIG-001")
            self.assertEqual(target, root.resolve() / "images" / "FIG-001.png")
            self.assertEqual(rel, "images/FIG-001.png")
            for unsafe in ("../escape.png", "/tmp/escape.png", "report/escape.png"):
                with self.assertRaises(ValueError):
                    resolve_image_output(root, unsafe, "FIG-001")

    def test_page_selection_has_hard_limit(self) -> None:
        self.assertEqual(parse_pages("1-3", 10), [0, 1, 2])
        with self.assertRaises(ValueError):
            parse_pages("1-7", 10)

    def test_access_obstacles_are_distinguished(self) -> None:
        self.assertEqual(classify_access_obstacle("请登录后查看全文"), "登录要求")
        self.assertEqual(classify_access_obstacle("Subscribe to continue"), "付费墙")
        self.assertEqual(classify_access_obstacle("Verify you are human captcha"), "验证码")
        self.assertEqual(classify_access_obstacle("Access denied Cloudflare Ray ID"), "WAF/访问控制")

    def test_retry_after_is_capped(self) -> None:
        self.assertEqual(retry_after_seconds("120", 1), 30.0)
        self.assertEqual(retry_after_seconds(None, 3), 4.0)

    def test_pdf_content_length_limit_stops_before_download_and_cleans_temp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "FIG-001.png"
            client = _Client([_Response(200, {
                "content-length": str(MAX_PDF_BYTES + 1),
                "content-type": "application/pdf",
            })])
            with patch("httpx.Client", return_value=client):
                ok, reason = capture_pdf("https://example.com/a.pdf", out, "1", time.monotonic() + 30)
            self.assertFalse(ok)
            self.assertIn("超限", reason)
            self.assertFalse(out.exists())
            self.assertEqual(list(Path(tmp).glob("pdf-download-*")), [])

    def test_retryable_responses_stop_after_three_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "FIG-001.png"
            client = _Client([_Response(429), _Response(503), _Response(500)])
            with patch("httpx.Client", return_value=client), patch("time.sleep"):
                ok, reason = capture_pdf("https://example.com/a.pdf", out, "1", time.monotonic() + 30)
            self.assertFalse(ok)
            self.assertIn("有限重试耗尽", reason)
            self.assertEqual(client.calls, 3)


class LazyBrowserTests(unittest.TestCase):
    """纯 PDF 清单不应依赖浏览器：没有 Chromium 也能完成。"""

    def test_needs_browser_only_for_pending_web_rows(self) -> None:
        pdf_row = {"fig_id": "FIG-001", "url": "https://example.com/a.pdf", "capture": "pdf"}
        web_row = {"fig_id": "FIG-002", "url": "https://example.com/", "capture": "viewport"}
        self.assertFalse(_needs_browser([pdf_row], {}, force=False))
        self.assertTrue(_needs_browser([pdf_row, web_row], {}, force=False))
        self.assertFalse(_needs_browser([web_row], {"FIG-002": {"status": "已截图"}}, force=False))
        self.assertTrue(_needs_browser([web_row], {"FIG-002": {"status": "已截图"}}, force=True))

    def test_pdf_only_manifest_does_not_launch_browser(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "screenshot_manifest.csv"
            manifest.write_text(
                "fig_id,url,capture,selector\nFIG-001,https://example.com/a.pdf,pdf,1\n",
                encoding="utf-8",
            )
            figures = root / "figures.csv"

            def fake_pdf(url: str, out_path: Path, page_spec: str, deadline: float):
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(b"\x89PNG\r\n")
                return True, ""

            with patch(
                "playwright.sync_api.sync_playwright",
                side_effect=AssertionError("纯 PDF 清单不应启动浏览器"),
            ), patch("tools.screenshot.capture_pdf", side_effect=fake_pdf):
                code = run(manifest, figures, root, force=False)

            self.assertEqual(code, 0)
            self.assertTrue((root / "images" / "FIG-001.png").exists())
            self.assertEqual(load_existing(figures)["FIG-001"]["status"], "已截图")


if __name__ == "__main__":
    unittest.main()
