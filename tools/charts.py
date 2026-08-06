#!/usr/bin/env python3
"""charts.py — 自制图表生成器（用于市场规模趋势/对比/份额等）。

注意：自制图必须标注来源，**不得冒充机构原图**。本工具默认在图底加
「数据来源：根据公开资料整理/计算」，若 --source 指定机构名则标注该机构。

用法示例:
  uv run python tools/charts.py bar --data data/source_data.csv --x company --y revenue \\
      --out images/FIG-005.png --title "头部企业营收对比" --source "各公司财报"
  uv run python tools/charts.py line --data data/source_data.csv --x year --y market_size \\
      --out images/FIG-006.png --title "市场规模趋势 2019-2025"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

# 中性、色盲友好的品牌无关配色（可替换为品牌色）
PALETTE = ["#1f4e79", "#2e75b6", "#5b9bd5", "#a5a5a5", "#ed7d31",
           "#ffc000", "#70ad47", "#264478", "#9e480e", "#636363"]


def _setup() -> None:
    plt.rcParams.update({
        "font.sans-serif": ["PingFang SC", "Microsoft YaHei", "Heiti SC", "Arial Unicode MS", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "figure.dpi": 150,
        "savefig.bbox": "tight",
        "axes.edgecolor": "#71717a",
        "axes.grid": True,
        "grid.color": "#e4e4e7",
        "grid.linewidth": 0.6,
    })


def _annotate_source(ax, source: str | None, out: Path) -> None:
    note = f"数据来源：{source}" if source else "数据来源：根据公开资料整理/计算"
    fig = ax.figure
    fig.text(0.01, 0.01, note, fontsize=8, color="#71717a", ha="left")
    fig.text(0.99, 0.01, "（自制图）", fontsize=7, color="#a1a1aa", ha="right")


def load_xy(data: Path, x: str, y: str) -> pd.DataFrame:
    df = pd.read_csv(data)
    if x not in df.columns or y not in df.columns:
        sys.exit(f"✗ CSV 缺列: 需 {x} 与 {y}；实际列 {list(df.columns)}")
    return df[[x, y]].dropna()


def plot(kind: str, data: Path, x: str, y: str, out: Path, title: str, source: str | None,
         ylabel: str | None, stacked: bool) -> None:
    _setup()
    df = load_xy(data, x, y)
    fig, ax = plt.subplots(figsize=(8, 4.6))
    colors = PALETTE[: max(1, len(df))]

    if kind == "bar":
        ax.bar(df[x].astype(str), df[y], color=colors, edgecolor="white", linewidth=0.5)
        for i, v in enumerate(df[y]):
            ax.text(i, v, f"{v:g}", ha="center", va="bottom", fontsize=8.5)
    elif kind == "line":
        ax.plot(df[x].astype(str), df[y], marker="o", linewidth=2, color=PALETTE[0])
        for xi, yi in zip(df[x].astype(str), df[y]):
            ax.text(xi, yi, f"{yi:g}", fontsize=8.5, ha="center", va="bottom")
    elif kind == "pie":
        wedges, _, autotexts = ax.pie(df[y], labels=df[x].astype(str), autopct="%1.1f%%",
                                      colors=colors, startangle=90,
                                      textprops={"fontsize": 9})
        ax.set_aspect("equal")
    else:
        sys.exit(f"✗ 未知图表类型: {kind}")

    ax.set_title(title, fontsize=14, pad=12, color="#18181b")
    if kind != "pie":
        ax.set_xlabel(x)
        ax.set_ylabel(ylabel or y)
    if source is None:
        source = None
    _annotate_source(ax, source, out)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    print(f"✓ 自制图已生成: {out}")
    print(f"  报告中引用：![{title}]({out.as_posix()})")
    print(f"  请在 data/figures.csv 登记 fig_id（status=自制图，is_primary_source=false）。")


def main() -> None:
    ap = argparse.ArgumentParser(description="自制图表生成")
    ap.add_argument("type", choices=["bar", "line", "pie"], help="图表类型")
    ap.add_argument("--data", required=True, help="数据 CSV 路径")
    ap.add_argument("--x", required=True, help="X 轴列名")
    ap.add_argument("--y", required=True, help="Y 轴列名")
    ap.add_argument("--out", required=True, help="输出 PNG 路径（如 images/FIG-005.png）")
    ap.add_argument("--title", required=True, help="图表标题")
    ap.add_argument("--source", default=None, help="数据来源（默认标注「根据公开资料整理/计算」）")
    ap.add_argument("--ylabel", default=None, help="Y 轴标签")
    args = ap.parse_args()
    plot(args.type, Path(args.data), args.x, args.y, Path(args.out),
         args.title, args.source, args.ylabel, False)


if __name__ == "__main__":
    main()
