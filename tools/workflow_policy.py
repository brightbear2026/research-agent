#!/usr/bin/env python3
"""统一研究模式与六阶段状态机。Claude、ChatGPT Work 和 CLI 共用。"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


STATE_REL = ".research-workflow.json"
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "workflow_modes.yaml"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("version") != 1:
        raise ValueError("workflow 配置版本无效")
    phases = config.get("phases")
    modes = config.get("modes")
    if not isinstance(phases, list) or len(phases) != 6 or len(set(phases)) != 6:
        raise ValueError("workflow 必须定义六个不重复阶段")
    if not isinstance(modes, dict) or set(modes) != {"regular", "plan", "execution"}:
        raise ValueError("workflow 必须定义 regular/plan/execution 三种模式")
    for name, policy in modes.items():
        if policy.get("stop_after") not in phases:
            raise ValueError(f"{name}.stop_after 不在阶段列表")
        unknown = set(policy.get("confirmation_after", [])) - set(phases)
        if unknown:
            raise ValueError(f"{name}.confirmation_after 含未知阶段：{sorted(unknown)}")
    return config


def initial_state(mode: str, config: dict[str, Any]) -> dict[str, Any]:
    if mode not in config["modes"]:
        raise ValueError(f"未知模式：{mode}")
    return {
        "state_version": 1,
        "mode": mode,
        "phase": config["phases"][0],
        "phase_status": "in_progress",
        "workflow_status": "running",
        "confirmation_count": 0,
        "completed_phases": [],
        "completeness_debt": None,
        "source_failures": {},
        "external_failures": [],
        "research_gaps": [],
        "chapter_progress": {},
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def register_chapters(state: dict[str, Any], chapter_ids: list[str]) -> dict[str, Any]:
    """登记阶段四章节；幂等保留已完成状态，供中断后恢复。"""
    invalid = [item for item in chapter_ids if not re.fullmatch(r"ch\d{2}", item)]
    if invalid:
        raise ValueError(f"章节 ID 必须匹配 chNN：{invalid}")
    if len(set(chapter_ids)) != len(chapter_ids):
        raise ValueError("章节 ID 不得重复")
    updated = json.loads(json.dumps(state, ensure_ascii=False))
    progress = updated.setdefault("chapter_progress", {})
    for index, chapter_id in enumerate(chapter_ids):
        current = progress.setdefault(chapter_id, {})
        current.setdefault("status", "pending")
        current.setdefault("attempts", 0)
        current["order"] = index
        current.setdefault("updated_at", now_iso())
    updated["updated_at"] = now_iso()
    return updated


def update_chapter_status(
    state: dict[str, Any],
    chapter_id: str,
    status: str,
    *,
    max_attempts: int | None = None,
) -> dict[str, Any]:
    if status not in {"pending", "in_progress", "completed", "failed"}:
        raise ValueError(f"无效章节状态：{status}")
    progress = state.get("chapter_progress", {})
    if chapter_id not in progress:
        raise ValueError(f"章节尚未登记：{chapter_id}")
    updated = json.loads(json.dumps(state, ensure_ascii=False))
    item = updated["chapter_progress"][chapter_id]
    if item.get("status") == "completed" and status != "completed":
        raise ValueError(f"已完成章节不能回退：{chapter_id}")
    if status == "in_progress" and item.get("status") != "in_progress":
        # 熔断：章节重派次数达上限则拒绝，防止卡死章节无限重派（35 轮式空转）。
        if max_attempts is not None and int(item.get("attempts", 0)) >= max_attempts:
            raise ValueError(
                f"章节 {chapter_id} 的重派次数已达上限 {max_attempts}，不再重派；"
                "请升级检索策略、放宽研究维度，或转资料缺口（record-failure）后继续"
            )
        item["attempts"] = int(item.get("attempts", 0)) + 1
    item["status"] = status
    item["updated_at"] = now_iso()
    updated["updated_at"] = now_iso()
    return updated


def next_incomplete_chapter(state: dict[str, Any]) -> str | None:
    progress = state.get("chapter_progress", {})
    candidates = [
        (int(item.get("order", 0)), chapter_id)
        for chapter_id, item in progress.items()
        if item.get("status") != "completed"
    ]
    return min(candidates)[1] if candidates else None


def advance_state(
    state: dict[str, Any],
    config: dict[str, Any],
    *,
    confirmed: bool = False,
) -> tuple[dict[str, Any], str]:
    """完成当前阶段并推进；需要确认时未确认则不改变状态。"""
    if state.get("workflow_status") != "running":
        return state, f"workflow_already_{state.get('workflow_status')}"
    mode = state["mode"]
    phase = state["phase"]
    policy = config["modes"][mode]
    if phase == "research":
        progress = state.get("chapter_progress", {})
        if not progress:
            return state, "chapters_not_registered"
        if next_incomplete_chapter(state) is not None:
            return state, "chapters_incomplete"
    needs_confirmation = phase in policy.get("confirmation_after", [])
    if needs_confirmation and not confirmed:
        return state, "needs_confirmation"

    updated = json.loads(json.dumps(state, ensure_ascii=False))
    if needs_confirmation:
        updated["confirmation_count"] += 1
    if phase not in updated["completed_phases"]:
        updated["completed_phases"].append(phase)
    updated["phase_status"] = "completed"
    updated["updated_at"] = now_iso()
    if phase == policy["stop_after"]:
        updated["workflow_status"] = "planned" if mode == "plan" else "completed"
        return updated, "stop"
    phases = config["phases"]
    index = phases.index(phase)
    if index + 1 >= len(phases):
        updated["workflow_status"] = "completed"
        return updated, "stop"
    updated["phase"] = phases[index + 1]
    updated["phase_status"] = "in_progress"
    return updated, "advanced"


def can_retry_source(state: dict[str, Any], config: dict[str, Any], source: str) -> bool:
    budgets = config["budgets"]
    per_source = int(budgets["per_source_retries"])
    total = int(budgets["total_external_failures"])
    return (
        int(state.get("source_failures", {}).get(source, 0)) < per_source
        and len(state.get("external_failures", [])) < total
    )


def record_external_failure(
    state: dict[str, Any],
    config: dict[str, Any],
    source: str,
    reason: str,
    alternative_url: str = "",
) -> tuple[dict[str, Any], str]:
    updated = json.loads(json.dumps(state, ensure_ascii=False))
    counts = updated.setdefault("source_failures", {})
    counts[source] = int(counts.get(source, 0)) + 1
    event = {
        "source": source,
        "reason": reason,
        "alternative_url": alternative_url,
        "phase": updated.get("phase"),
        "at": now_iso(),
    }
    updated.setdefault("external_failures", []).append(event)
    updated["updated_at"] = now_iso()
    if can_retry_source(updated, config, source):
        return updated, "retry_allowed"
    gap = dict(event)
    gap["disposition"] = "retry_budget_exhausted"
    updated.setdefault("research_gaps", []).append(gap)
    return updated, "record_gap_and_continue"


def state_path(root: Path) -> Path:
    return root.resolve() / STATE_REL


def load_state(root: Path) -> dict[str, Any]:
    return json.loads(state_path(root).read_text(encoding="utf-8"))


def save_state(root: Path, state: dict[str, Any]) -> None:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = state_path(root)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=root, delete=False) as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, destination)


def _print_state(state: dict[str, Any], action: str = "") -> None:
    progress = state.get("chapter_progress", {})
    chapter_counts: dict[str, int] = {}
    for item in progress.values():
        status = str(item.get("status", "pending"))
        chapter_counts[status] = chapter_counts.get(status, 0) + 1
    payload = {
        "action": action,
        "mode": state.get("mode"),
        "phase": state.get("phase"),
        "phase_status": state.get("phase_status"),
        "workflow_status": state.get("workflow_status"),
        "confirmation_count": state.get("confirmation_count"),
        "completed_phases": state.get("completed_phases"),
        "research_gap_count": len(state.get("research_gaps", [])),
        "chapter_counts": chapter_counts,
        "next_incomplete_chapter": next_incomplete_chapter(state),
        "completeness_debt": state.get("completeness_debt"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="统一研究模式状态机")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--root", required=True)
    init.add_argument("--mode", choices=("regular", "plan", "execution"), required=True)
    init.add_argument("--force", action="store_true")
    advance = sub.add_parser("advance")
    advance.add_argument("--root", required=True)
    advance.add_argument("--confirmed", action="store_true")
    status = sub.add_parser("status")
    status.add_argument("--root", required=True)
    failure = sub.add_parser("record-failure")
    failure.add_argument("--root", required=True)
    failure.add_argument("--source", required=True)
    failure.add_argument("--reason", required=True)
    failure.add_argument("--alternative-url", default="")
    register = sub.add_parser("register-chapters")
    register.add_argument("--root", required=True)
    register.add_argument("--chapter", action="append", required=True)
    chapter = sub.add_parser("chapter")
    chapter.add_argument("--root", required=True)
    chapter.add_argument("--chapter", required=True)
    chapter.add_argument("--status", choices=("pending", "in_progress", "completed", "failed"), required=True)
    next_chapter = sub.add_parser("next-chapter")
    next_chapter.add_argument("--root", required=True)
    record_debt = sub.add_parser("record-debt")
    record_debt.add_argument("--root", required=True)
    record_debt.add_argument(
        "--from", dest="from_path", default=None,
        help="qc_debt.json 路径；默认 <root>/data/qc_debt.json",
    )
    args = parser.parse_args()
    try:
        config = load_config(Path(args.config).resolve())
        root = Path(args.root).resolve()
        if args.command == "init":
            path = state_path(root)
            if path.exists() and not args.force:
                print(f"✗ 状态文件已存在：{path}", file=sys.stderr)
                return 2
            state = initial_state(args.mode, config)
            save_state(root, state)
            _print_state(state, "initialized")
            return 0
        state = load_state(root)
        if args.command == "status":
            _print_state(state, "status")
            return 0
        if args.command == "next-chapter":
            _print_state(state, "next_chapter")
            return 0
        if args.command == "register-chapters":
            updated = register_chapters(state, args.chapter)
            action = "chapters_registered"
        elif args.command == "chapter":
            if args.status == "completed":
                drafts = list((root / "report").glob(f"_draft_{args.chapter}_*.md"))
                if not any(draft.with_suffix(".meta.json").exists() for draft in drafts):
                    raise ValueError(
                        f"章节 {args.chapter} 缺少配对的 .md 与 .meta.json，不能标记 completed"
                    )
            max_attempts = int(config.get("budgets", {}).get("max_chapter_attempts", 0)) or None
            updated = update_chapter_status(
                state, args.chapter, args.status, max_attempts=max_attempts
            )
            action = f"chapter_{args.status}"
        elif args.command == "advance":
            updated, action = advance_state(state, config, confirmed=args.confirmed)
        elif args.command == "record-debt":
            from_path = (
                Path(args.from_path).resolve() if args.from_path
                else root / "data" / "qc_debt.json"
            )
            data = json.loads(from_path.read_text(encoding="utf-8"))
            summary = data.get("summary", {}) or {}
            updated = json.loads(json.dumps(state, ensure_ascii=False))
            updated["completeness_debt"] = {
                "warnings": int(summary.get("warnings", 0)),
                "errors": int(summary.get("errors", 0)),
                "by_category": summary.get("by_category", {}) or {},
                "core_passed": bool(data.get("core_passed")),
                "source": str(from_path),
                "at": now_iso(),
            }
            updated["updated_at"] = now_iso()
            action = "debt_recorded"
        else:
            updated, action = record_external_failure(
                state, config, args.source, args.reason, args.alternative_url
            )
        if updated is not state:
            save_state(root, updated)
        _print_state(updated, action)
        if action == "needs_confirmation":
            return 3
        if action in {"chapters_not_registered", "chapters_incomplete"}:
            return 4
        return 0
    except (OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
        print(f"✗ workflow 状态处理失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
