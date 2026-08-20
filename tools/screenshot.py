#!/usr/bin/env python3
"""screenshot.py — 用 Playwright 无头浏览器对 manifest 中的 URL 做**真实截图**，并维护 figures.csv 索引。

用法:
  uv run python tools/screenshot.py <manifest.csv> [--root <项目根>] [--figures <figures.csv>] [--force]

manifest.csv 列（由 scaffold 生成表头）:
  fig_id,url,capture,selector,wait_ms,local_path,title,source_org,source_doc,
  publish_date,supports_conclusion,is_primary_source,alternative_url

- capture ∈ {full, viewport, element, pdf}；
  - full=整页、viewport=视口、element=按 CSS selector 截区块、
  - pdf=下载 PDF 并渲染指定页（selector 填页码，如 "1" / "1-3" / "2,4"，默认第 1 页；多页纵向拼接）。
- 成功 → 写真实 PNG，status=已截图。
- 失败 → **绝不伪造**真实内容；写一张**明确标注的占位 PNG**（写明"截图占位/失败原因"），status=失败(占位)。
- local_path 只能写入项目 `images/`；PDF 与整页截图受文件大小、页数、像素、拼接高度和总任务截止时间限制。
- 登录、验证码、付费墙、WAF、限流和资源超限分别记录；工具不会绕过访问控制。
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

FIGURES_COLS = [
    "fig_id", "title", "source_org", "source_doc", "url",
    "publish_date", "access_date", "page_or_location",
    "supports_conclusion", "is_primary_source", "local_path", "status",
    "failure_category", "failure_reason", "alternative_url",
]

NAV_TIMEOUT_MS = 30000
MAX_WAIT_MS = 15000
MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_PDF_PAGES = 1000
MAX_RENDERED_PAGES = 6
MAX_IMAGE_PIXELS = 25_000_000
MAX_STITCH_HEIGHT = 30_000
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
MAX_DOWNLOAD_ATTEMPTS = 3
VIEWPORT = {"width": 1366, "height": 900}
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def resolve_image_output(root: Path, rel: str, fig_id: str) -> tuple[Path, str]:
    """把输出限制在 <root>/images；返回绝对路径和规范相对路径。"""
    root = root.resolve()
    images = (root / "images").resolve()
    requested = Path((rel or f"images/{fig_id}.png").strip())
    if requested.is_absolute():
        raise ValueError("local_path 不得为绝对路径")
    target = (root / requested).resolve()
    try:
        target.relative_to(images)
    except ValueError as exc:
        raise ValueError("local_path 必须位于项目 images/ 目录") from exc
    if target.suffix.lower() != ".png":
        raise ValueError("截图输出必须使用 .png 扩展名")
    return target, target.relative_to(root).as_posix()


def classify_access_obstacle(text: str, title: str = "") -> str:
    """按页面可见内容分类外部访问阻碍；不尝试绕过。"""
    haystack = f"{title}\n{text}".lower()[:20000]
    categories = (
        ("验证码", ("captcha", "验证码", "人机验证", "verify you are human")),
        ("登录要求", ("sign in to continue", "login required", "请登录", "登录后查看")),
        ("付费墙", ("subscribe to continue", "subscription required", "订阅后阅读", "付费阅读")),
        ("WAF/访问控制", ("access denied", "request blocked", "web application firewall", "cloudflare ray id", "访问被拒绝")),
    )
    for category, markers in categories:
        if any(marker in haystack for marker in markers):
            return category
    return ""


def retry_after_seconds(value: str | None, attempt: int) -> float:
    """Retry-After 秒值优先，否则指数退避；单次最多等待 30 秒。"""
    if value:
        try:
            return min(max(float(value.strip()), 0.0), 30.0)
        except ValueError:
            pass
    return min(2.0 ** (attempt - 1), 30.0)


def failure_category(reason: str) -> str:
    for category in ("验证码", "登录要求", "付费墙", "WAF/访问控制"):
        if category in reason:
            return category
    if "HTTP 429" in reason:
        return "限流"
    if "超限" in reason or "截止时间" in reason:
        return "资源预算"
    if "路径安全" in reason:
        return "路径安全"
    if "超时" in reason or "Transport" in reason:
        return "网络/超时"
    return "其他"


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
    wait = min(max(wait, 0), MAX_WAIT_MS)
    try:
        if selector:
            try:
                page.wait_for_selector(selector, timeout=min(max(wait, 1000), 15000))
            except Exception:
                pass
        page.wait_for_timeout(wait)
    except Exception:
        pass
    try:
        obstacle = classify_access_obstacle(
            page.locator("body").inner_text(timeout=3000), page.title()
        )
        if obstacle:
            return False, f"外部访问阻碍: {obstacle}"
    except Exception:
        pass
    return True, ""


def do_screenshot(page, out_path: Path, capture: str, selector: str) -> tuple[bool, str]:
    try:
        if capture == "element":
            if not selector:
                return False, "element 截图缺 selector"
            el = page.locator(selector).first
            box = el.bounding_box()
            if box and box["width"] * box["height"] > MAX_IMAGE_PIXELS:
                return False, "element 截图像素超限"
            el.screenshot(path=str(out_path))
        elif capture == "viewport":
            page.screenshot(path=str(out_path), full_page=False)
        else:  # full
            dimensions = page.evaluate("() => ({width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight})")
            width = int(dimensions.get("width", VIEWPORT["width"]))
            height = int(dimensions.get("height", VIEWPORT["height"]))
            if height > MAX_STITCH_HEIGHT or width * height > MAX_IMAGE_PIXELS:
                return False, f"整页截图尺寸超限: {width}x{height}"
            page.screenshot(path=str(out_path), full_page=True)
        return True, ""
    except Exception as e:
        return False, f"截图异常: {e}"


def parse_pages(spec: str, max_pages: int, selection_limit: int = MAX_RENDERED_PAGES) -> list[int]:
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
    if len(res) > selection_limit:
        raise ValueError(f"请求渲染 {len(res)} 页，超过上限 {selection_limit}")
    return res or [0]


def _capture_pdf_impl(
    url: str,
    out_path: Path,
    page_spec: str,
    temp_name: str,
    deadline: float | None = None,
) -> tuple[bool, str]:
    """下载 PDF 并把指定页渲染成 PNG（多页纵向拼接）。无需浏览器，独立于 Playwright。"""
    try:
        import io
        import pymupdf
        from PIL import Image
    except ImportError as e:
        return False, f"缺依赖（pymupdf/httpx/Pillow）: {e}"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        timeout = httpx.Timeout(connect=15.0, read=45.0, write=15.0, pool=15.0)
        downloaded = False
        last_reason = "无响应"
        with httpx.Client(timeout=timeout, follow_redirects=True, headers={
            "User-Agent": UA, "Accept": "application/pdf,*/*",
        }) as client:
            for attempt in range(1, MAX_DOWNLOAD_ATTEMPTS + 1):
                if deadline is not None and time.monotonic() >= deadline:
                    return False, "PDF 总任务截止时间已到"
                try:
                    with client.stream("GET", url) as response:
                        if response.status_code in RETRYABLE_STATUS:
                            last_reason = f"HTTP {response.status_code}"
                            delay = retry_after_seconds(response.headers.get("retry-after"), attempt)
                            if attempt < MAX_DOWNLOAD_ATTEMPTS:
                                if deadline is not None and time.monotonic() + delay >= deadline:
                                    return False, f"PDF 下载终止: {last_reason}，无剩余重试预算"
                                time.sleep(delay)
                                continue
                            return False, f"PDF 下载失败（有限重试耗尽）: {last_reason}"
                        if response.status_code >= 400:
                            return False, f"PDF 下载失败 HTTP {response.status_code}"
                        length = response.headers.get("content-length")
                        if length and int(length) > MAX_PDF_BYTES:
                            return False, f"PDF 文件超限: Content-Length={length}"
                        total = 0
                        first = b""
                        with open(temp_name, "wb") as handle:
                            for chunk in response.iter_bytes(64 * 1024):
                                if deadline is not None and time.monotonic() >= deadline:
                                    return False, "PDF 总任务截止时间已到"
                                total += len(chunk)
                                if total > MAX_PDF_BYTES:
                                    return False, f"PDF 文件超过 {MAX_PDF_BYTES} 字节上限"
                                if not first:
                                    first = chunk[:5]
                                handle.write(chunk)
                        ctype = response.headers.get("content-type", "").lower()
                        if "pdf" not in ctype and not first.startswith(b"%PDF-"):
                            return False, f"非 PDF 内容 (content-type={ctype})"
                        downloaded = True
                        break
                except (httpx.TransportError, httpx.HTTPError, OSError, ValueError) as exc:
                    last_reason = type(exc).__name__
                    if attempt < MAX_DOWNLOAD_ATTEMPTS:
                        delay = retry_after_seconds(None, attempt)
                        if deadline is not None and time.monotonic() + delay >= deadline:
                            return False, f"PDF 下载终止: {last_reason}，无剩余重试预算"
                        time.sleep(delay)
        if not downloaded:
            return False, f"PDF 下载失败（有限重试耗尽）: {last_reason}"
        try:
            doc = pymupdf.open(temp_name, filetype="pdf")
        except Exception as exc:
            return False, f"PDF 解析失败: {type(exc).__name__}"
    except Exception as exc:
        return False, f"PDF 下载异常: {type(exc).__name__}"
    if doc.page_count == 0:
        doc.close()
        return False, "PDF 无页面"
    if doc.page_count > MAX_PDF_PAGES:
        doc.close()
        return False, f"PDF 页数超限: {doc.page_count} > {MAX_PDF_PAGES}"
    try:
        pages = parse_pages(page_spec, doc.page_count)
    except ValueError as exc:
        doc.close()
        return False, str(exc)
    pngs: list[bytes] = []
    dimensions: list[tuple[int, int]] = []
    for pidx in pages:
        if 0 <= pidx < doc.page_count:
            pixmap = doc[pidx].get_pixmap(dpi=150)
            if pixmap.width * pixmap.height > MAX_IMAGE_PIXELS:
                doc.close()
                return False, f"PDF 第 {pidx + 1} 页渲染像素超限"
            pngs.append(pixmap.tobytes("png"))
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
        height = sum(im.height for im in ims)
        if height > MAX_STITCH_HEIGHT or w * height > MAX_IMAGE_PIXELS:
            return False, f"PDF 拼接图片尺寸超限: {w}x{height}"
        canvas = Image.new("RGB", (w, height), "white")
        y = 0
        for im in ims:
            canvas.paste(im, (0, y))
            y += im.height
        canvas.save(out_path)
    return True, ""


def capture_pdf(
    url: str,
    out_path: Path,
    page_spec: str,
    deadline: float | None = None,
) -> tuple[bool, str]:
    """流式下载 PDF，在所有成功/失败路径清理临时文件。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix="pdf-download-", suffix=".pdf", dir=out_path.parent, delete=False
    ) as temp:
        temp_name = temp.name
    try:
        return _capture_pdf_impl(url, out_path, page_spec, temp_name, deadline)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def run(
    manifest_path: Path,
    figures_path: Path,
    root: Path,
    force: bool,
    deadline_seconds: int = 600,
) -> int:
    root = root.resolve()
    deadline = time.monotonic() + max(deadline_seconds, 1)
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
                if not re.fullmatch(r"FIG-\d{3,}", fig_id):
                    print(f"    ✗ 无效 fig_id（要求 FIG-###）：{fig_id!r}")
                    fail += 1
                    continue
                try:
                    out_path, rel = resolve_image_output(
                        root, row.get("local_path") or f"images/{fig_id}.png", fig_id
                    )
                    path_error = ""
                except ValueError as exc:
                    out_path, rel = resolve_image_output(root, f"images/{fig_id}.png", fig_id)
                    path_error = f"路径安全检查失败: {exc}"
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
                if path_error:
                    reason = path_error
                elif time.monotonic() >= deadline:
                    reason = "截图总任务截止时间已到"
                elif is_pdf:
                    captured, reason = capture_pdf(
                        url, out_path, row.get("selector", ""), deadline
                    )
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
                    "failure_category": "" if captured else failure_category(reason),
                    "failure_reason": "" if captured else reason[:1000],
                    "alternative_url": row.get("alternative_url", ""),
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
    ap.add_argument("--deadline-seconds", type=int, default=600,
                    help="整个截图任务的总时间上限（默认 600 秒）")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    figures = Path(args.figures).resolve() if args.figures else root / "data" / "figures.csv"
    sys.exit(run(Path(args.manifest).resolve(), figures, root, args.force,
                 args.deadline_seconds))


if __name__ == "__main__":
    main()
