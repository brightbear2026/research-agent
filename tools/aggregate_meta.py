#!/usr/bin/env python3
"""aggregate_meta.py — 从 chapter_meta.json 派生旁路索引 CSV（阶段五第 2 步）。

确定性聚合，单一事实源：读取 data/chapter_meta.json（由 merge.py 汇总），
生成三个旁路 CSV：
  - data/source_data.csv        ← 各章 data_points
  - evidence/evidence_matrix.csv ← 各章 chapter_conclusion
  - evidence/controversy_matrix.csv ← 各章 controversies

不为正文反向解析——矩阵内容直接来自 meta 的结构化字段。
data_points / controversies 在各章字段名异构（claim/item、level/tier/
source_grade、sources[]、positions{}），本脚本统一归一化。

用法: uv run python tools/aggregate_meta.py --root <项目根> [--chapter-meta <相对路径>]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

SD_HEADER = ["data_name", "value", "unit", "stat_time", "region",
             "definition", "source", "source_org", "source_date",
             "tier", "credibility", "notes"]
EV_HEADER = ["conclusion_id", "core_conclusion", "supporting_evidence",
             "opposing_evidence", "source_tier", "sufficiency", "final_judgment"]
CT_HEADER = ["controversy_id", "question", "view_a", "supporters_a",
             "view_b", "supporters_b", "evidence_comparison", "research_judgment"]

# 中文语境 "A级" / 英文语境独立 "A"。注意 \b 在 "A级" 处无效（汉字也是 \w）。
TIER_CN_RE = re.compile(r"([ABCD])\s*级")
TIER_EN_RE = re.compile(r"(?<![A-Za-z])([ABCD])(?![A-Za-z])")


def first_str(d: dict, *keys) -> str:
    """返回 keys 中首个非空字符串值。"""
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, list) and v:
            joined = "; ".join(str(x) for x in v if x)
            if joined.strip():
                return joined
    return ""


def normalize_tier(*vals: str) -> str:
    """专用字段（tier/level/source_grade/source_tier）统一为 A/B/C/D。

    专用字段可信裸字母（如 'A'）；也接受 'A级'。取不到留空。
    """
    for v in vals:
        if not v:
            continue
        m = TIER_CN_RE.search(v) or TIER_EN_RE.search(v)
        if m:
            return m.group(1)
    return ""


def tier_from_haystack(s: str) -> str:
    """源描述串里只信显式 'X级'，避免 'Series D'/'Model A' 等英文误判。"""
    if not s:
        return ""
    m = TIER_CN_RE.search(s)
    return m.group(1) if m else ""


SRC_FIELDS = ("type", "author", "title", "publication", "date", "url", "access_date", "tier")


def parse_src(tag: str) -> dict:
    """解析 `[[SRC|类型|作者|标题|出版物|日期|url|访问日期|等级]]` → dict。

    任一字段缺失留空。非 SRC 形态返回空 dict。
    """
    out = {k: "" for k in SRC_FIELDS}
    if not isinstance(tag, str):
        return out
    s = tag.strip()
    m = re.match(r"^\[\[SRC\|(.+)\]\]\s*$", s)
    if not m:
        return out
    parts = [p.strip() for p in m.group(1).split("|")]
    for i, key in enumerate(SRC_FIELDS):
        if i < len(parts):
            out[key] = parts[i]
    return out


def confidence_to_sufficiency(conf: str) -> str:
    """confidence(高/中高/中/中低/低) → 充分度。"""
    c = (conf or "").strip()
    if c.startswith("高"):
        return "充分"
    if c.startswith("中高") or "中高" in c:
        return "较充分"
    if c.startswith("中") or "中等" in c:
        return "中等"
    if c.startswith("低") or "较弱" in c:
        return "较弱"
    return "中等"


def domain_of(url: str) -> str:
    """从 url 提取主域作为 source_org；失败留空。"""
    if not url:
        return ""
    m = re.search(r"https?://([^/]+)/?", url)
    if not m:
        return ""
    host = m.group(1)
    host = host.replace("www.", "")
    return host


def write_csv(path: Path, header: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in header})


def emit_source_data(chapters: list[dict]) -> list[dict]:
    rows = []
    for ch in chapters:
        cid = ch.get("chapter_id", "")
        for dp in ch.get("data_points", []) or []:
            claim = first_str(dp, "claim", "item", "name", "point")
            value = first_str(dp, "value")
            # 源字符串：覆盖各章异构字段名（source/source_tag/source_citation/
            # source_label/source_tag_url 等），优先列表其次单值
            src = first_str(dp, "source", "source_tag", "source_citation",
                            "source_label", "source_url", "sources")
            parsed = parse_src(src)
            url = first_str(dp, "url", "source_url", "source_tag_url") or parsed["url"]
            if not url:
                # 从 sources 列表里抓第一个 http 链接，或从源串里提 http
                for s in (dp.get("sources") or []):
                    if isinstance(s, str) and s.startswith("http"):
                        url = s
                        break
                if not url and isinstance(src, str):
                    mu = re.search(r"https?://\S+", src)
                    if mu:
                        url = mu.group(0).rstrip("])|,，")
            # tier：专用字段优先（覆盖 tier/grade/evidence_level/source_tier/source_grade），
            # 再取 SRC 标签内等级，最后扫描源串显式 'X级'
            src_hay = " ".join(
                str(x) for x in (dp.get("sources") or []) if x
            ) + " " + src
            tier = normalize_tier(
                dp.get("tier", ""), dp.get("level", ""), dp.get("grade", ""),
                dp.get("evidence_level", ""),
                dp.get("source_tier", ""), dp.get("source_grade", ""),
            ) or normalize_tier(parsed["tier"]) or tier_from_haystack(src_hay)
            src_date = (parsed["date"] or
                        first_str(dp, "source_date", "publish_date"))
            credibility = first_str(dp, "confidence", "credibility")
            note = first_str(dp, "verification", "note", "notes",
                             "cross_check", "verified", "follow_up", "location")
            rows.append({
                "data_name": claim[:200],
                "value": value,
                "unit": "",
                "stat_time": src_date,
                "region": "",
                "definition": note,
                "source": src,
                "source_org": domain_of(url) or first_str(dp, "source_org"),
                "source_date": src_date,
                "tier": tier,
                "credibility": credibility,
                "notes": f"[{cid}] {note}" if note else f"[{cid}]",
            })
    return rows


def emit_evidence(chapters: list[dict]) -> list[dict]:
    rows = []
    for ch in chapters:
        cc = ch.get("chapter_conclusion") or {}
        if not cc:
            continue
        cid = ch.get("chapter_id", "")
        conf = cc.get("confidence", "")
        judgment = cc.get("judgment", "")
        conditions = cc.get("conditions", "")
        # source_tier：扫描该章 data_points 取主流等级（专用字段优先，源串内显式 X级 兜底）
        tiers = []
        for dp in (ch.get("data_points") or []):
            hay = " ".join(
                str(x) for x in (dp.get("sources") or []) if x
            ) + " " + first_str(dp, "source", "source_url")
            tiers.append(normalize_tier(
                dp.get("tier", ""), dp.get("level", ""),
                dp.get("source_tier", ""), dp.get("source_grade", ""),
            ) or tier_from_haystack(hay))
        tiers = [t for t in tiers if t]
        from collections import Counter
        dom = Counter(tiers).most_common(1)
        source_tier = dom[0][0] if dom else ""
        final = judgment
        if conditions:
            final = f"{judgment} 【适用条件】{conditions}"
        rows.append({
            "conclusion_id": cid,
            "core_conclusion": ch.get("thesis", judgment),
            "supporting_evidence": ch.get("thesis", ""),
            "opposing_evidence": cc.get("counter_evidence", ""),
            "source_tier": f"{source_tier} 级为主" if source_tier else "见 citations.csv",
            "sufficiency": confidence_to_sufficiency(conf),
            "final_judgment": final,
        })
    return rows


def emit_controversies(chapters: list[dict]) -> list[dict]:
    rows = []
    for ch in chapters:
        cid = ch.get("chapter_id", "")
        for cv in ch.get("controversies", []) or []:
            # researcher 显式标注不入矩阵（如 to_matrix:false）则跳过
            if cv.get("to_matrix") is False:
                continue
            # 视图 A/B 与支持来源：覆盖 side_a/position_a/pro/sides[]/positions{}
            view_a = first_str(cv, "side_a", "position_a", "position_A", "pro")
            view_b = first_str(cv, "side_b", "position_b", "position_B", "con")
            sup_a = first_str(cv, "source_a", "side_a_sources", "evidence_a",
                              "side_a_tier", "pro_sources")
            sup_b = first_str(cv, "source_b", "side_b_sources", "evidence_b",
                              "side_b_tier", "con_sources")
            # sides 列表型：[立场A, 立场B, ...]
            sides = cv.get("sides")
            if isinstance(sides, list) and len(sides) >= 2 and not view_a:
                view_a, view_b = str(sides[0]), str(sides[1])
            # positions{} 字典型：把各立场拼成视图
            positions = cv.get("positions")
            if isinstance(positions, dict) and positions and not view_a:
                items = list(positions.items())
                if len(items) >= 1:
                    view_a, sup_a = items[0][0], str(items[0][1])
                if len(items) >= 2:
                    view_b, sup_b = items[1][0], str(items[1][1])
            evidence_cmp = first_str(cv, "caliber_difference", "evidence_tier",
                                     "methodological_difference",
                                     "root_cause_of_disagreement", "stakeholders")
            judgment = first_str(cv, "resolution", "conditional_conclusion",
                                 "resolution_status", "handling_in_this_chapter")
            cid_full = cv.get("id") or f"{cid}-CV{len(rows)+1}"
            rows.append({
                "controversy_id": cid_full,
                "question": cv.get("topic") or cv.get("question") or "",
                "view_a": view_a,
                "supporters_a": sup_a,
                "view_b": view_b,
                "supporters_b": sup_b,
                "evidence_comparison": evidence_cmp,
                "research_judgment": judgment,
            })
    return rows


def run(root: Path, meta_rel: str) -> int:
    meta_path = root / meta_rel
    if not meta_path.exists():
        print(f"✗ 找不到 chapter_meta: {meta_path}", file=sys.stderr)
        return 1
    with meta_path.open(encoding="utf-8") as f:
        chapters = json.load(f)

    sd_rows = emit_source_data(chapters)
    ev_rows = emit_evidence(chapters)
    ct_rows = emit_controversies(chapters)

    write_csv(root / "data" / "source_data.csv", SD_HEADER, sd_rows)
    write_csv(root / "evidence" / "evidence_matrix.csv", EV_HEADER, ev_rows)
    write_csv(root / "evidence" / "controversy_matrix.csv", CT_HEADER, ct_rows)

    print(f"✓ source_data.csv ← {len(sd_rows)} 条数据点")
    print(f"✓ evidence_matrix.csv ← {len(ev_rows)} 条结论")
    print(f"✓ controversy_matrix.csv ← {len(ct_rows)} 项争议")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="从 chapter_meta.json 派生旁路索引 CSV")
    ap.add_argument("--root", default=".", help="项目根目录")
    ap.add_argument("--chapter-meta", default="data/chapter_meta.json",
                    help="chapter_meta.json 相对项目根的路径")
    args = ap.parse_args()
    sys.exit(run(Path(args.root).resolve(), args.chapter_meta))


if __name__ == "__main__":
    main()
