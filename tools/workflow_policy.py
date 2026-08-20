#!/usr/bin/env python3
"""统一的研究模式与六阶段状态机。

该模块是 Claude Code、ChatGPT Work 和命令行入口共同依赖的流程事实源。
它只取消仓库自身的流程确认，不会也不能绕过系统权限、登录、验证码或付费墙。

用法：
  uv run python tools/workflow_policy.py describe --mode 计划
  uv run python tools/workflow_policy.py init --root projects/topic --mode 执行 --goal "..."
  uv run python tools/workflow_policy.py complete-stage --root projects/topic --stage 1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "workflow_modes.yaml"
STATE_REL = Path("data/workflow_state.json")


class WorkflowPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class ModeDecision:
    mode: str
    completed_stage: int
    checkpoint_required: bool
    should_stop: bool
    next_stage: int | None


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("modes"), dict):
        raise WorkflowPolicyError(f"无效模式配置: {path}")
    return raw


def normalize_mode(value: str, config: dict[str, Any] | None = None) -> str:
    config = config or load_config()
    candidate = value.strip().lower()
    for canonical, policy in config["modes"].items():
        aliases = {str(x).strip().lower() for x in policy.get("aliases", [])}
        aliases.add(canonical.lower())
        if candidate in aliases:
            return canonical
    allowed = ", ".join(config["modes"])
    raise WorkflowPolicyError(f"未知模式 {value!r}；可用模式: {allowed}")


def policy_for(mode: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_config()
    return config["modes"][normalize_mode(mode, config)]


def decision(mode: str, completed_stage: int, config: dict[str, Any] | None = None) -> ModeDecision:
    config = config or load_config()
    canonical = normalize_mode(mode, config)
    stages = [int(x) for x in config.get("common", {}).get("stages", [])]
    if completed_stage not in stages:
        raise WorkflowPolicyError(f"阶段必须是 {stages} 之一")
    policy = config["modes"][canonical]
    checkpoint = completed_stage in {int(x) for x in policy.get("checkpoints_after", [])}
    stop_after = policy.get("stop_after_stage")
    should_stop = stop_after is not None and completed_stage >= int(stop_after)
    next_stage = None if should_stop or completed_stage == stages[-1] else completed_stage + 1
    return ModeDecision(canonical, completed_stage, checkpoint, should_stop, next_stage)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def init_state(root: Path, mode: str, goal: str, depth: str) -> Path:
    canonical = normalize_mode(mode)
    if not goal.strip():
        raise WorkflowPolicyError("目标不能为空")
    state = {
        "schema_version": 1,
        "mode": canonical,
        "goal": goal.strip(),
        "depth": depth,
        "completed_stage": 0,
        "status": "running",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "external_gaps": [],
    }
    state_path = root.resolve() / STATE_REL
    _atomic_write_json(state_path, state)
    return state_path


def complete_stage(root: Path, stage: int) -> tuple[Path, ModeDecision]:
    root = root.resolve()
    state_path = root / STATE_REL
    if not state_path.exists():
        raise WorkflowPolicyError(f"找不到流程状态: {state_path}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("status") != "running":
        raise WorkflowPolicyError(f"当前状态为 {state.get('status')}，不能继续阶段；先确认或切换到执行模式")
    expected = int(state.get("completed_stage", 0)) + 1
    if stage != expected:
        raise WorkflowPolicyError(f"阶段必须顺序完成；当前应完成阶段 {expected}，收到 {stage}")
    if stage == 6:
        missing = completion_gate_errors(root)
        if missing:
            raise WorkflowPolicyError("阶段六完成门槛未满足: " + "; ".join(missing))
    result = decision(str(state["mode"]), stage)
    state["completed_stage"] = stage
    state["status"] = "completed" if stage == 6 else (
        "awaiting_confirmation" if result.checkpoint_required else "running"
    )
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _atomic_write_json(state_path, state)
    return state_path, result


def completion_gate_errors(root: Path, config: dict[str, Any] | None = None) -> list[str]:
    config = config or load_config()
    errors: list[str] = []
    for gate in config.get("common", {}).get("completion_gates", []):
        if gate == "qc_strict_passed":
            result_path = root / "data/qc_strict_result.json"
            if not result_path.exists():
                errors.append("缺少 data/qc_strict_result.json")
                continue
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                errors.append("data/qc_strict_result.json 无效")
                continue
            if result.get("passed") is not True:
                errors.append("严格 QC 未通过")
                continue
            artifacts = result.get("artifacts_sha256", {})
            if "report/research_report.md" not in artifacts:
                errors.append("严格 QC 记录缺少报告摘要")
            for rel, expected_hash in artifacts.items():
                artifact = root / rel
                if not artifact.exists() or not artifact.is_file():
                    errors.append(f"严格 QC 后文件缺失: {rel}")
                    continue
                digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
                if digest != expected_hash:
                    errors.append(f"严格 QC 后文件发生变化: {rel}")
        else:
            path = root / str(gate)
            if not path.exists() or (path.is_file() and path.stat().st_size == 0):
                errors.append(f"缺少交付物 {gate}")
    return errors


def confirm_checkpoint(root: Path) -> Path:
    state_path = root.resolve() / STATE_REL
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("status") != "awaiting_confirmation":
        raise WorkflowPolicyError("当前没有等待确认的检查点")
    if state.get("mode") == "plan" and int(state.get("completed_stage", 0)) == 3:
        state["status"] = "stopped_for_plan"
    else:
        state["status"] = "running"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _atomic_write_json(state_path, state)
    return state_path


def resume_execution(root: Path) -> Path:
    """把已完成阶段三的计划切换为执行模式，不重复前三阶段。"""
    state_path = root.resolve() / STATE_REL
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("mode") != "plan" or state.get("status") != "stopped_for_plan" or int(state.get("completed_stage", 0)) != 3:
        raise WorkflowPolicyError("只有已确认并停止在阶段三的计划模式可以继续执行")
    state["mode"] = "execute"
    state["status"] = "running"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _atomic_write_json(state_path, state)
    return state_path


def main() -> int:
    parser = argparse.ArgumentParser(description="研究流程模式状态机")
    sub = parser.add_subparsers(dest="command", required=True)
    describe = sub.add_parser("describe")
    describe.add_argument("--mode", required=True)
    init = sub.add_parser("init")
    init.add_argument("--root", required=True)
    init.add_argument("--mode", required=True)
    init.add_argument("--goal", required=True)
    init.add_argument("--depth", choices=["快速", "标准", "深度"], default="标准")
    complete = sub.add_parser("complete-stage")
    complete.add_argument("--root", required=True)
    complete.add_argument("--stage", required=True, type=int)
    confirm = sub.add_parser("confirm")
    confirm.add_argument("--root", required=True)
    resume = sub.add_parser("resume-execution")
    resume.add_argument("--root", required=True)
    args = parser.parse_args()

    try:
        if args.command == "describe":
            config = load_config()
            canonical = normalize_mode(args.mode, config)
            print(json.dumps({
                "mode": canonical,
                "policy": config["modes"][canonical],
                "common": config["common"],
            }, ensure_ascii=False, indent=2))
        elif args.command == "init":
            print(f"✓ 流程状态已创建: {init_state(Path(args.root), args.mode, args.goal, args.depth)}")
        elif args.command == "complete-stage":
            path, result = complete_stage(Path(args.root), args.stage)
            print(json.dumps({"state": str(path), **result.__dict__}, ensure_ascii=False, indent=2))
        elif args.command == "confirm":
            print(f"✓ 检查点已确认: {confirm_checkpoint(Path(args.root))}")
        else:
            print(f"✓ 已从计划切换为执行模式: {resume_execution(Path(args.root))}")
    except (WorkflowPolicyError, json.JSONDecodeError, OSError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
