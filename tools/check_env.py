#!/usr/bin/env python3
"""检查 Python、Playwright 包与浏览器二进制是否相互匹配。"""
from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path


def load_chromium_spec(manifest: Path) -> tuple[str, str]:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    for item in data.get("browsers", []):
        if item.get("name") == "chromium":
            return str(item["revision"]), str(item.get("browserVersion") or "")
    raise ValueError("Playwright browsers.json 未定义 chromium")


def playwright_manifest() -> Path:
    spec = importlib.util.find_spec("playwright")
    if spec is None or not spec.submodule_search_locations:
        raise RuntimeError("未安装 playwright Python 包")
    package = Path(next(iter(spec.submodule_search_locations)))
    return package / "driver" / "package" / "browsers.json"


def chromium_install_location(output: str, revision: str) -> Path:
    pattern = re.compile(
        rf"^.*\(playwright chromium v{re.escape(revision)}\)\s*$"
        rf".*?^\s*Install location:\s*(.+?)\s*$",
        flags=re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(output)
    if not match:
        raise ValueError(f"无法从 Playwright dry-run 输出解析 Chromium build {revision} 的安装位置")
    return Path(match.group(1).strip())


def check_environment(*, skip_browser: bool = False) -> list[str]:
    errors: list[str] = []
    if sys.version_info < (3, 13):
        errors.append(f"Python 版本过低：{sys.version.split()[0]}，要求 >=3.13")
    try:
        package_version = importlib.metadata.version("playwright")
        manifest = playwright_manifest()
        revision, browser_version = load_chromium_spec(manifest)
        print(f"✓ Playwright Python {package_version}; Chromium {browser_version} (build {revision})")
    except (OSError, KeyError, ValueError, RuntimeError, importlib.metadata.PackageNotFoundError) as exc:
        errors.append(str(exc))
        return errors

    if not skip_browser:
        try:
            from playwright._impl._driver import compute_driver_executable

            node, cli = compute_driver_executable()
            result = subprocess.run(
                [node, cli, "install", "--dry-run"],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            location = chromium_install_location(result.stdout, revision)
            complete = location / "INSTALLATION_COMPLETE"
            if not location.is_dir() or not complete.exists():
                errors.append(
                    f"Chromium build {revision} 未完整安装：{location}；"
                    "运行 `uv run playwright install chromium`"
                )
            else:
                print(f"✓ Chromium build 已完整安装：{location}")
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            errors.append(f"无法检查 Chromium：{type(exc).__name__}: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="检查研究代理运行环境")
    parser.add_argument("--skip-browser", action="store_true", help="仅检查包内版本映射，不要求已下载浏览器")
    args = parser.parse_args()
    errors = check_environment(skip_browser=args.skip_browser)
    if errors:
        for error in errors:
            print(f"✗ {error}", file=sys.stderr)
        return 1
    print("✓ 环境检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
