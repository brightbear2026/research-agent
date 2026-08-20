#!/usr/bin/env python3
"""screenshot.py — 用 Playwright 无头浏览器对 manifest 中的 URL 做**真实截图**，并维护 figures.csv 索引。

用法:
  uv run python tools/screenshot.py <manifest.csv> [--root <项目根>] [--figures <figures.csv>] [--force]

manifest.csv 列（由 scaffold 生成表头）:
  fig_id,url,capture,selector,wait_ms,local_path,title,source_org,source_doc,
  publish_date,supports_conclusion,is_primary_source

- capture ∈ {full, viewport, element, pdf}；
  - full=整页、viewport=视口、element=按 CSS selector 截区块、
  - pdf=下载 PDF 并渲染指定页（selector 填页码，如 "1" / "1-3" / "2,4"，默认第 1 页；多页纵向拼接）。
- 成功 → 写真实 PNG，status=已截图。
- 失败 → **绝不伪造**真实内容；写一张**明确标注的占位 PNG**（写明"截图占位/失败原因"），status=失败(占位)。
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

FIGURES_COLS = [
    "fig_id", "title", "source_org", "source_doc", "url",
    "publish_date", "access_date", "page_or_location",
    "supports_conclusion", "is_primary_source", "local_path", "status",
]

NAV_TIMEOUT_MS = 30000
MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_PDF_PAGES = 5
MAX_IMAGE_PIXELS = 40_000_000
MAX_STITCH_HEIGHT = 30_000
MAX_WEB_HEIGHT = 20_000
RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}
VIEWPORT = {"width": 1366, "height": 900}
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def find_cjk_font() -> str | None:
    for p in [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
    ]:
        if Path(p).exists():
            return p
    return None


def make_placeholder(out_path: Path, fig_id: str, reason: str) -> None:
    """生成**明确标注的占位图**——仅作占位，绝不模仿任何真实来源内容。"""
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (VIEWPORT["width"], 560), color="#f4f4f5")
        d = ImageDraw.Draw(img)
        font = None
        font_path = find_cjk_font()
        if font_path:
            from PIL import ImageFont
            font = ImageFont.truetype(font_path, 28)
        lines = [
            f"[{fig_id}] 截图占位 / Placeholder",
            "此为占位图，非原始截图内容。",
            "原因:",
            reason,
            "请人工后补或检查 URL/付费墙/JS 拦截。",
        ]
        y = 60
        for ln in lines:
            d.text((40, y), ln, fill="#b91c1c" if "占位" not in ln else "#52525b", font=font)
            y += 50
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path)
    except Exception as e:  # 即使占位生成失败也不伪造
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            f"PLACEHOLDER (not a real screenshot) fig_id={fig_id} reason={reason} pil_error={e}",
            encoding="utf-8",
        )


def load_existing(figures_path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    if figures_path.exists():
        with figures_path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("fig_id"):
                    rows[r["fig_id"]] = r
    return rows


def write_figures(figures_path: Path, rows: dict[str, dict]) -> None:
    figures_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{figures_path.name}.", suffix=".tmp", dir=figures_path.parent)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIGURES_COLS)
            w.writeheader()
            for fig_id in sorted(rows):
                w.writerow({k: rows[fig_id].get(k, "") for k in FIGURES_COLS})
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, figures_path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def resolve_output_path(root: Path, relative: str) -> Path:
    """截图只能写入 <root>/images，拒绝绝对路径、父目录和符号链接逃逸。"""
    if not relative or Path(relative).is_absolute():
        raise ValueError("local_path 必须是 images/ 下的相对 PNG 路径")
    images_root = (root / "images").resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(images_root)
    except ValueError as exc:
        raise ValueError(f"local_path 越界: {relative}") from exc
    if candidate.suffix.lower() != ".png":
        raise ValueError("截图输出必须是 .png")
    return candidate


def capture_one(page, row: dict) -> tuple[bool, str]:
    """返回 (是否成功, 失败原因)。成功时 page 已导航就绪。"""
    url = row.get("url", "").strip()
    if not url or not url.startswith(("http://", "https://")):
        return False, f"无效 URL: {url!r}"
    capture = (row.get("capture") or "full").strip().lower()
    selector = (row.get("selector") or "").strip()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    except Exception as e:
        return False, f"导航失败: {e}"
    try:
        wait = int(row.get("wait_ms") or 1500)
    except ValueError:
        wait = 1500
    try:
        if selector:
            try:
                page.wait_for_selector(selector, timeout=min(max(wait, 1000), 15000))
            except Exception:
                pass
        page.wait_for_timeout(wait)
    except Exception:
        pass
    return True, ""


def do_screenshot(page, out_path: Path, capture: str, selector: str) -> tuple[bool, str]:
    try:
        if capture == "element":
            if not selector:
                return False, "element 截图缺 selector"
            el = page.locator(selector).first
            el.screenshot(path=str(out_path))
        elif capture == "viewport":
            page.screenshot(path=str(out_path), full_page=False)
        else:  # full
            height = int(page.evaluate("Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)"))
            if height > MAX_WEB_HEIGHT:
                return False, f"页面高度 {height}px 超过安全上限 {MAX_WEB_HEIGHT}px；请改用 element/viewport"
            page.screenshot(path=str(out_path), full_page=True)
        return True, ""
    except Exception as e:
        return False, f"截图异常: {e}"


def parse_pages(spec: str, max_pages: int) -> list[int]:
    """解析页码规格 → 0-based 页索引列表。支持 '1'、'1-3'、'2,4'；默认第 1 页。"""
    spec = (spec or "").strip().lower()
    for tok in ("page", "页", "p", ":"):
        spec = spec.replace(tok, " ")
    spec = spec.replace("，", ",").replace("、", ",")
    if not spec.strip():
        spec = "1"
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            try:
                lo, hi = int(a), int(b)
            except ValueError:
                continue
            out.extend(i - 1 for i in range(lo, hi + 1) if 1 <= i <= max_pages)
        else:
            try:
                n = int(part)
            except ValueError:
                continue
            if 1 <= n <= max_pages:
                out.append(n - 1)
    seen: set[int] = set()
    res = [x for x in out if not (x in seen or seen.add(x))]
    return res or [0]


def download_binary(
    url: str,
    *,
    max_bytes: int = MAX_PDF_BYTES,
    max_attempts: int = 3,
    total_deadline_s: float = 240.0,
) -> tuple[bytes | None, str, str]:
    """受限下载；返回 (内容, content-type, 错误)。"""
    try:
        import httpx
    except ImportError as exc:
        return None, "", f"缺依赖 httpx: {exc}"
    started = time.monotonic()
    timeout = httpx.Timeout(connect=10.0, read=45.0, write=10.0, pool=10.0)
    last_error = ""
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={
        "User-Agent": UA, "Accept": "application/pdf,*/*",
    }) as client:
        for attempt in range(1, max_attempts + 1):
            if time.monotonic() - started >= total_deadline_s:
                return None, "", f"超过总下载时限 {total_deadline_s:.0f}s"
            try:
                with client.stream("GET", url) as response:
                    if response.status_code in RETRYABLE_STATUSES:
                        retry_after = response.headers.get("retry-after", "")
                        delay = min(float(retry_after), 30.0) if retry_after.isdigit() else min(2 ** (attempt - 1), 8)
                        last_error = f"HTTP {response.status_code}"
                        if attempt < max_attempts:
                            time.sleep(delay)
                            continue
                        return None, response.headers.get("content-type", ""), last_error
                    if response.status_code >= 400:
                        return None, response.headers.get("content-type", ""), f"HTTP {response.status_code}"
                    declared = response.headers.get("content-length", "")
                    if declared.isdigit() and int(declared) > max_bytes:
                        return None, response.headers.get("content-type", ""), f"文件声明大小超过 {max_bytes} 字节"
                    payload = bytearray()
                    for chunk in response.iter_bytes():
                        if time.monotonic() - started >= total_deadline_s:
                            return None, response.headers.get("content-type", ""), f"超过总下载时限 {total_deadline_s:.0f}s"
                        payload.extend(chunk)
                        if len(payload) > max_bytes:
                            return None, response.headers.get("content-type", ""), f"文件超过 {max_bytes} 字节"
                    return bytes(payload), response.headers.get("content-type", ""), ""
            except httpx.HTTPError as exc:
                last_error = type(exc).__name__
                if attempt < max_attempts:
                    time.sleep(min(2 ** (attempt - 1), 8))
                    continue
    return None, "", last_error or "下载失败"


def capture_pdf(url: str, out_path: Path, page_spec: str) -> tuple[bool, str]:
    """下载 PDF 并把指定页渲染成 PNG（多页纵向拼接）。无需浏览器，独立于 Playwright。"""
    try:
        import io
        import pymupdf
        from PIL import Image
    except ImportError as e:
        return False, f"缺依赖（pymupdf/httpx/Pillow）: {e}"
    content, ctype, error = download_binary(url)
    if content is None:
        return False, f"PDF 下载失败: {error}"
    ctype = ctype.lower()
    is_pdf = ("pdf" in ctype) or url.lower().endswith(".pdf") or content[:5].startswith(b"%PDF-")
    if not is_pdf:
        return False, f"非 PDF 内容 (content-type={ctype})"
    try:
        doc = pymupdf.open(stream=content, filetype="pdf")
    except Exception as e:
        return False, f"PDF 解析失败: {type(e).__name__}"
    if doc.page_count == 0:
        return False, "PDF 无页面"
    pages = parse_pages(page_spec, doc.page_count)
    if len(pages) > MAX_PDF_PAGES:
        doc.close()
        return False, f"请求渲染 {len(pages)} 页，超过安全上限 {MAX_PDF_PAGES} 页"
    pngs: list[bytes] = []
    dimensions: list[tuple[int, int]] = []
    for pidx in pages:
        if 0 <= pidx < doc.page_count:
            pix = doc[pidx].get_pixmap(dpi=150)
            dimensions.append((pix.width, pix.height))
            pngs.append(pix.tobytes("png"))
    doc.close()
    if not pngs:
        return False, "指定页超出范围"
    total_pixels = sum(width * height for width, height in dimensions)
    total_height = sum(height for _, height in dimensions)
    if total_pixels > MAX_IMAGE_PIXELS or total_height > MAX_STITCH_HEIGHT:
        return False, f"渲染尺寸超过安全上限（{total_pixels} 像素 / {total_height}px 高）"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if len(pngs) == 1:
        out_path.write_bytes(pngs[0])
    else:  # 多页纵向拼接
        ims = [Image.open(io.BytesIO(b)).convert("RGB") for b in pngs]
        w = max(im.width for im in ims)
        canvas = Image.new("RGB", (w, sum(im.height for im in ims)), "white")
        y = 0
        for im in ims:
            canvas.paste(im, (0, y))
            y += im.height
        canvas.save(out_path)
    return True, ""


def run(manifest_path: Path, figures_path: Path, root: Path, force: bool) -> int:
    if not manifest_path.exists():
        sys.exit(f"✗ 找不到 manifest: {manifest_path}")
    with manifest_path.open(encoding="utf-8") as f:
        manifest = list(csv.DictReader(f))
    if not manifest:
        print("manifest 为空，无操作。")
        return 0

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("✗ 未安装 playwright，请: uv add playwright && uv run playwright install chromium")

    # 始终合并已有索引（--force 仅控制是否重拍已截图项，绝不丢弃既有行）
    rows = load_existing(figures_path)
    today = date.today().isoformat()
    ok = fail = skipped = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport=VIEWPORT, user_agent=UA, locale="zh-CN")
            page = context.new_page()

            for row in manifest:
                fig_id = (row.get("fig_id") or "").strip()
                if not fig_id:
                    continue
                rel = (row.get("local_path") or f"images/{fig_id}.png").strip()
                try:
                    out_path = resolve_output_path(root, rel)
                except ValueError as exc:
                    print(f"    ✗ {fig_id}: {exc}")
                    rows[fig_id] = {**row, "fig_id": fig_id, "local_path": rel, "status": "失败(路径越界)"}
                    fail += 1
                    continue
                if fig_id in rows and not force and rows[fig_id].get("status") == "已截图":
                    print(f"  ⊘ 跳过(已截图): {fig_id}")
                    skipped += 1
                    continue

                url = (row.get("url") or "").strip()
                cap = (row.get("capture") or "full").strip().lower()
                is_pdf = cap == "pdf" or url.lower().endswith(".pdf")
                tag = "[PDF]" if is_pdf else ("[element]" if cap == "element" else "")
                print(f"  → {fig_id} {tag} {url[:80]}")
                captured, reason = False, ""
                if is_pdf:
                    captured, reason = capture_pdf(url, out_path, row.get("selector", ""))
                else:
                    nav_ok, reason = capture_one(page, row)
                    if nav_ok:
                        captured, reason = do_screenshot(page, out_path, cap, row.get("selector", ""))
                if not captured:
                    make_placeholder(out_path, fig_id, reason)
                    status = "失败(占位)"
                    fail += 1
                    print(f"    ✗ {status}: {reason}")
                else:
                    status = "已截图"
                    ok += 1
                    print(f"    ✓ {status} → {out_path}")

                rows[fig_id] = {
                    "fig_id": fig_id,
                    "title": row.get("title", ""),
                    "source_org": row.get("source_org", ""),
                    "source_doc": row.get("source_doc", ""),
                    "url": row.get("url", ""),
                    "publish_date": row.get("publish_date", ""),
                    "access_date": today,
                    "page_or_location": (f"PDF p.{row.get('selector', '1')}" if is_pdf else row.get("selector", "")),
                    "supports_conclusion": row.get("supports_conclusion", ""),
                    "is_primary_source": row.get("is_primary_source", ""),
                    "local_path": rel,
                    "status": status,
                }

            context.close()
            browser.close()
    except Exception as e:
        if "Executable doesn't appear" in str(e) or "playwright install" in str(e).lower():
            sys.exit("✗ 未安装浏览器，请: uv run playwright install chromium\n" + str(e))
        raise

    write_figures(figures_path, rows)
    print(f"\n汇总: 成功 {ok} / 失败 {fail} / 跳过 {skipped} | 索引: {figures_path}")
    return 0 if fail == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="Playwright 真实截图 + figures 索引")
    ap.add_argument("manifest", help="screenshot_manifest.csv 路径")
    ap.add_argument("--root", default=".", help="项目根目录（解析 local_path）")
    ap.add_argument("--figures", default=None, help="figures.csv 输出路径（默认 <root>/data/figures.csv）")
    ap.add_argument("--force", action="store_true", help="即使已截图也重拍")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    figures = Path(args.figures).resolve() if args.figures else root / "data" / "figures.csv"
    sys.exit(run(Path(args.manifest).resolve(), figures, root, args.force))


if __name__ == "__main__":
    main()
