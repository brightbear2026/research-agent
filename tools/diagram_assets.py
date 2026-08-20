#!/usr/bin/env python3
"""校验 Diagram Design 静态 HTML，导出 PNG，并合并写入 figures.csv。

Diagram Design 负责视觉语义与 SVG 布局；本工具只承担确定性边界：
路径限制、静态单文件安全检查、可访问 SVG 合约、PNG 导出和旁路索引登记。
它不会生成图形内容，也不会把生成图冒充原始来源截图。
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import date
from pathlib import Path

try:
    from tools.screenshot import load_existing, resolve_image_output, write_figures
except ModuleNotFoundError:  # 直接执行 tools/diagram_assets.py
    from screenshot import load_existing, resolve_image_output, write_figures

SUCCESS_STATUS = "已生成(Diagram Design)"
FAILURE_STATUS = "失败(Diagram Design)"
REMOTE_ATTR_RE = re.compile(r"\b(?:src|href|xlink:href)\s*=\s*(['\"])(https?://[^'\"]+)\1", re.I)
REMOTE_CSS_RE = re.compile(r"url\(\s*(['\"]?)(https?://[^)'\"]+)\1\s*\)", re.I)
EVENT_HANDLER_RE = re.compile(r"\son[a-z]+\s*=", re.I)


def resolve_input_path(root: Path, relative: str) -> Path:
    """Diagram HTML 只能来自 <root>/diagrams，拒绝绝对路径和目录逃逸。"""
    if not relative or Path(relative).is_absolute():
        raise ValueError("source_html 必须是 diagrams/ 下的相对 HTML 路径")
    diagrams_root = (root / "diagrams").resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(diagrams_root)
    except ValueError as exc:
        raise ValueError(f"source_html 越界: {relative}") from exc
    if candidate.suffix.lower() != ".html":
        raise ValueError("Diagram Design 源文件必须是 .html")
    return candidate


def validate_diagram_html(path: Path) -> list[str]:
    """验证研究报告允许的 Diagram Design 静态子集。"""
    if not path.exists():
        return [f"找不到源文件: {path}"]
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    openings = list(re.finditer(r"<svg\b[^>]*>", text, flags=re.I | re.S))
    closings = re.findall(r"</svg\s*>", text, flags=re.I)
    if len(openings) != 1 or len(closings) != 1:
        errors.append(f"必须恰好包含一个 SVG（open={len(openings)}, close={len(closings)}）")
        return errors
    opening = openings[0].group(0)
    if not re.search(r"\bviewBox\s*=", opening, flags=re.I):
        errors.append("SVG 缺少 viewBox")
    if not re.search(r"\brole\s*=\s*(['\"])img\1", opening, flags=re.I):
        errors.append('SVG 缺少 role="img"')
    if not re.search(r"\baria-labelledby\s*=", opening, flags=re.I):
        errors.append("SVG 缺少 aria-labelledby")
    svg_body = text[openings[0].end(): text.lower().find("</svg", openings[0].end())]
    if not re.search(r"<title\b", svg_body, flags=re.I):
        errors.append("SVG 缺少 <title>")
    if not re.search(r"<desc\b", svg_body, flags=re.I):
        errors.append("SVG 缺少 <desc>")
    if re.search(r"<script\b", text, flags=re.I):
        errors.append("研究报告只允许静态 Diagram Design 图，禁止 <script>")
    if EVENT_HANDLER_RE.search(text):
        errors.append("禁止 on* 可执行 HTML/SVG 属性")
    remote_urls = [match.group(2) for match in REMOTE_ATTR_RE.finditer(text)]
    remote_urls += [match.group(2) for match in REMOTE_CSS_RE.finditer(text)]
    disallowed = sorted({url for url in remote_urls if "fonts.googleapis.com/" not in url})
    if disallowed:
        errors.append(f"存在未允许的远程资源: {disallowed}")
    return errors


def _figure_row(row: dict[str, str], status: str) -> dict[str, str]:
    source_orgs = (row.get("source_orgs") or "").strip()
    return {
        "fig_id": (row.get("fig_id") or "").strip(),
        "title": (row.get("title") or "").strip(),
        "source_org": f"根据公开资料整理：{source_orgs}" if source_orgs else "research-agent 自制图",
        "source_doc": (row.get("source_docs") or "").strip(),
        "url": "",
        "publish_date": "",
        "access_date": date.today().isoformat(),
        "page_or_location": (
            f"Diagram Design {row.get('visual_type', '')}; {row.get('size', '')}/"
            f"{row.get('detail', '')}; profile={row.get('profile', '')}; "
            f"sources={row.get('source_ids', '')}"
        ),
        "supports_conclusion": (row.get("supports_conclusion") or "").strip(),
        "is_primary_source": "false",
        "local_path": (row.get("local_path") or "").strip(),
        "status": status,
    }


def _render(page, source: Path, output: Path) -> None:
    page.goto(source.as_uri(), wait_until="domcontentloaded", timeout=30_000)
    try:
        page.wait_for_function(
            "!document.fonts || document.fonts.status === 'loaded'",
            timeout=15_000,
        )
    except Exception:
        # 远程字体不可用时仍保留系统字体回退；结构验证不依赖字体网络。
        pass
    svg = page.locator("svg").first
    svg.wait_for(state="visible", timeout=15_000)
    output.parent.mkdir(parents=True, exist_ok=True)
    svg.screenshot(path=str(output), omit_background=True)


def run(
    manifest_path: Path,
    figures_path: Path,
    root: Path,
    *,
    force: bool = False,
    validate_only: bool = False,
    scale: float = 2,
) -> int:
    if not manifest_path.exists():
        print(f"✗ 找不到 manifest: {manifest_path}", file=sys.stderr)
        return 1
    with manifest_path.open(encoding="utf-8") as handle:
        manifest = list(csv.DictReader(handle))
    if not manifest:
        print("Diagram Design manifest 为空，无操作。")
        return 0
    if not 1 <= scale <= 4:
        print("✗ scale 必须在 1–4 之间", file=sys.stderr)
        return 1

    prepared: list[tuple[dict[str, str], Path, Path]] = []
    failures: list[tuple[dict[str, str], str]] = []
    seen: set[str] = set()
    for row in manifest:
        fig_id = (row.get("fig_id") or "").strip()
        if not re.fullmatch(r"FIG-\d{3,}", fig_id):
            failures.append((row, f"fig_id 无效: {fig_id!r}"))
            continue
        if fig_id in seen:
            failures.append((row, f"fig_id 重复: {fig_id}"))
            continue
        seen.add(fig_id)
        try:
            source = resolve_input_path(root, (row.get("source_html") or "").strip())
            output, normalized_rel = resolve_image_output(
                root,
                (row.get("local_path") or "").strip(),
                fig_id,
            )
            row["local_path"] = normalized_rel
        except ValueError as exc:
            failures.append((row, str(exc)))
            continue
        errors = validate_diagram_html(source)
        if errors:
            failures.append((row, "; ".join(errors)))
            continue
        prepared.append((row, source, output))

    for row, reason in failures:
        print(f"  ✗ {row.get('fig_id', '?')}: {reason}", file=sys.stderr)
    if validate_only:
        for row, source, _ in prepared:
            print(f"  ✓ {row['fig_id']}: {source}")
        print(f"校验: 通过 {len(prepared)} / 失败 {len(failures)}")
        return 0 if not failures else 1

    rows = load_existing(figures_path)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("✗ 未安装 playwright，请运行 uv sync && uv run playwright install chromium", file=sys.stderr)
        return 1

    ok = skipped = 0
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(device_scale_factor=scale, locale="zh-CN")
            page = context.new_page()
            for row, source, output in prepared:
                fig_id = row["fig_id"]
                if (
                    not force
                    and rows.get(fig_id, {}).get("status") == SUCCESS_STATUS
                    and output.exists()
                ):
                    print(f"  ⊘ 跳过(已生成): {fig_id}")
                    skipped += 1
                    continue
                try:
                    _render(page, source, output)
                    rows[fig_id] = _figure_row(row, SUCCESS_STATUS)
                    print(f"  ✓ {fig_id} → {output}")
                    ok += 1
                except Exception as exc:
                    output.unlink(missing_ok=True)
                    reason = f"导出异常: {type(exc).__name__}: {exc}"
                    failures.append((row, reason))
                    rows[fig_id] = _figure_row(row, FAILURE_STATUS)
                    print(f"  ✗ {fig_id}: {reason}", file=sys.stderr)
            context.close()
            browser.close()
    except Exception as exc:
        print(f"✗ Playwright 启动失败: {exc}\n请运行 uv run playwright install chromium", file=sys.stderr)
        return 1

    for row, _ in failures:
        fig_id = (row.get("fig_id") or "").strip()
        if fig_id and fig_id not in rows:
            rows[fig_id] = _figure_row(row, FAILURE_STATUS)
    write_figures(figures_path, rows)
    print(f"汇总: 生成 {ok} / 跳过 {skipped} / 失败 {len(failures)} | 索引: {figures_path}")
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagram Design 静态资产校验、PNG 导出与 figures 索引")
    parser.add_argument("manifest", help="diagram_manifest.csv 路径")
    parser.add_argument("--root", default=".", help="项目根目录")
    parser.add_argument("--figures", default=None, help="figures.csv 路径（默认 <root>/data/figures.csv）")
    parser.add_argument("--force", action="store_true", help="重新导出已有成功项")
    parser.add_argument("--validate-only", action="store_true", help="仅检查路径与静态 HTML 合约")
    parser.add_argument("--scale", type=float, default=2, help="PNG 像素倍率，1–4（默认 2）")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    figures = Path(args.figures).resolve() if args.figures else root / "data/figures.csv"
    return run(
        Path(args.manifest).resolve(), figures, root,
        force=args.force, validate_only=args.validate_only, scale=args.scale,
    )


if __name__ == "__main__":
    sys.exit(main())
