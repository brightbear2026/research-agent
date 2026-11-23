"""研究过程诊断：只衡量可审计的记录覆盖，不将元数据分数冒充事实正确率。"""
from __future__ import annotations

from datetime import date
from typing import Any


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_quality_metadata(chapter: dict) -> list[str]:
    """可选 v2 扩展：旧章节可缺省；填写后必须类型正确且引用闭环。"""
    errors: list[str] = []
    sources = {s.get("source_id") for s in chapter.get("sources", []) if isinstance(s, dict)}
    evidence = {e.get("evidence_id") for e in chapter.get("data_points", []) if isinstance(e, dict)}

    def records(owner: dict, key: str, path: str) -> list[dict]:
        value = owner.get(key, [])
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            errors.append(f"{path}: 必须是对象数组")
            return []
        return value

    def refs(owner: dict, key: str, allowed: set, path: str) -> list[str]:
        value = owner.get(key)
        if not isinstance(value, list) or any(not _text(item) for item in value):
            errors.append(f"{path}.{key}: 必须是非空字符串组成的数组")
            return []
        if len(set(value)) != len(value) or any(item not in allowed for item in value):
            errors.append(f"{path}.{key}: 引用不存在或重复的 ID")
        return value

    questions = records(chapter, "research_questions", "research_questions")
    question_ids: set[str] = set()
    for i, question in enumerate(questions):
        path = f"research_questions[{i}]"
        qid = question.get("question_id")
        if not _text(qid) or qid in question_ids:
            errors.append(f"{path}.question_id: 缺失或重复")
        else:
            question_ids.add(qid)
        if not _text(question.get("question")):
            errors.append(f"{path}.question: 不得为空")
        if question.get("status") not in ("answered", "partial", "unanswered"):
            errors.append(f"{path}.status: 必须为 answered/partial/unanswered")
        linked = refs(question, "evidence_ids", evidence, path)
        if question.get("status") in ("answered", "partial") and not linked:
            errors.append(f"{path}: 已回答或部分回答必须关联 evidence_ids")
        if question.get("status") != "answered" and not _text(question.get("gap_reason")):
            errors.append(f"{path}.gap_reason: 未完全回答须说明缺口")

    for i, entry in enumerate(records(chapter, "search_log", "search_log")):
        path = f"search_log[{i}]"
        if not _text(entry.get("question_id")) or entry["question_id"] not in question_ids:
            errors.append(f"{path}.question_id: 引用不存在的研究问题")
        for key in ("query", "reason"):
            if not _text(entry.get(key)):
                errors.append(f"{path}.{key}: 不得为空")
        if entry.get("intent") not in ("support", "counter", "background"):
            errors.append(f"{path}.intent: 必须为 support/counter/background")
        if entry.get("outcome") not in ("new_evidence", "no_new_evidence", "blocked"):
            errors.append(f"{path}.outcome: 必须为 new_evidence/no_new_evidence/blocked")
        linked = refs(entry, "source_ids", sources, path)
        if entry.get("outcome") == "new_evidence" and not linked:
            errors.append(f"{path}: new_evidence 必须关联 source_ids")

    # 检索任务规划（阶段三编译进大纲的类型化任务；借鉴 paper-orchestra 三类检索：
    # explore=章节探索 / refute=反方与局限检索 / pin=必引原文定向锁定）
    task_ids: set[str] = set()
    for i, entry in enumerate(records(chapter, "search_tasks", "search_tasks")):
        path = f"search_tasks[{i}]"
        tid = entry.get("task_id")
        if not _text(tid) or tid in task_ids:
            errors.append(f"{path}.task_id: 缺失或重复")
        else:
            task_ids.add(tid)
        if not _text(entry.get("focus")):
            errors.append(f"{path}.focus: 不得为空")
        if entry.get("type") not in ("explore", "refute", "pin"):
            errors.append(f"{path}.type: 必须为 explore/refute/pin")
        if entry.get("status") not in ("planned", "done", "partial", "open"):
            errors.append(f"{path}.status: 必须为 planned/done/partial/open")
        if entry.get("status") == "done" and not _text(entry.get("result")):
            errors.append(f"{path}.result: 已完成须一句话记录结果（找到什么 / 确认没有）")
        refs(entry, "evidence_ids", evidence, path)
        linked_sources = refs(entry, "source_ids", sources, path)
        if entry.get("type") == "pin" and entry.get("status") == "done" and not linked_sources:
            errors.append(f"{path}: pin（必引原文）完成后必须关联 source_ids")

    # P0/P1 优先级（可选）：标 P0 = 研究者承诺该结论必须有一级/权威来源背书
    for i, claim in enumerate(chapter.get("claims", [])):
        if not isinstance(claim, dict):
            continue
        priority = claim.get("priority")
        if priority is not None and priority not in ("P0", "P1"):
            errors.append(f"claims[{i}].priority: 必须为 P0/P1")
    conclusion = chapter.get("chapter_conclusion")
    if isinstance(conclusion, dict):
        cc_priority = conclusion.get("priority")
        if cc_priority is not None and cc_priority not in ("P0", "P1"):
            errors.append("chapter_conclusion.priority: 必须为 P0/P1")

    for i, point in enumerate(chapter.get("data_points", [])):
        if not isinstance(point, dict):
            continue
        seen: set[str] = set()
        for j, item in enumerate(records(point, "provenance", f"data_points[{i}].provenance")):
            path = f"data_points[{i}].provenance[{j}]"
            sid = item.get("source_id")
            if not _text(sid) or sid not in point.get("source_ids", []) or sid in seen:
                errors.append(f"{path}.source_id: 必须唯一且属于本条证据的 source_ids")
            else:
                seen.add(sid)
            for key in ("locator", "excerpt"):
                if not _text(item.get(key)):
                    errors.append(f"{path}.{key}: 不得为空")
            try:
                raw_date = item.get("access_date")
                if not isinstance(raw_date, str) or date.fromisoformat(raw_date).isoformat() != raw_date:
                    raise ValueError
            except (TypeError, ValueError):
                errors.append(f"{path}.access_date: 必须为有效 YYYY-MM-DD 日期")
    return errors


def _metric(covered: int, total: int) -> dict:
    return {"covered": int(covered), "total": total, "ratio": round(covered / total, 4) if total else None}


def build_quality_scorecard(chapters: list[dict]) -> dict:
    """输入须已通过章节校验。比例按总体分子/分母统计，缺数据不会得到满分。"""
    findings: list[dict] = []
    rows: list[dict] = []
    for chapter in chapters:
        cid = chapter["chapter_id"]
        evidence = {e["evidence_id"]: e for e in chapter["data_points"]}
        questions = chapter.get("research_questions", [])
        searches = chapter.get("search_log", [])
        counter_questions = {s["question_id"] for s in searches if s["intent"] == "counter" and s["outcome"] != "blocked"}

        def finding(code: str, target: str, action: str) -> None:
            findings.append({"chapter_id": cid, "code": code, "target_id": target, "action": action})

        if not questions:
            finding("question_plan_missing", cid, "从研究卡登记核心问题，不能用已写出的结论倒推覆盖率。")
        for q in questions:
            if q["status"] != "answered":
                finding("question_gap", q["question_id"], "补充能回答该问题的证据，或在报告中披露：" + q["gap_reason"])
            if q["question_id"] not in counter_questions:
                finding("counter_search_missing", q["question_id"], "检索反例、不同口径或失败案例；如未找到，记录查询和结果，勿虚构反证。")

        located = 0
        for eid, point in evidence.items():
            recorded = {p["source_id"] for p in point.get("provenance", [])}
            if set(point["source_ids"]).issubset(recorded):
                located += 1
            else:
                finding("provenance_missing", eid, "为每个支撑来源补充原文短摘录、页码/章节位置和访问日期。")

        tasks = chapter.get("search_tasks", [])
        done_tasks = [t for t in tasks if t.get("status") == "done"]
        refute_tasks = [t for t in tasks if t.get("type") == "refute"]
        refute_done = [t for t in refute_tasks if t.get("status") == "done"]
        for task in tasks:
            if task.get("status") == "done":
                continue
            if task.get("type") == "refute":
                finding("refute_task_open", task.get("task_id", "?"),
                        "完成反方检索并在 result 记录结论；确实无反证也要记录查询与结果，勿虚构反证。")
            elif task.get("type") == "pin":
                finding("pin_task_open", task.get("task_id", "?"),
                        "完成必引原文的定向锁定（回到提出方法/数据集/指标的一手文献），或说明找不到的原因。")
            else:
                finding("search_task_open", task.get("task_id", "?"),
                        "完成检索任务，或降级为 open 并说明缺口原因。")

        source_map = {s.get("source_id"): s for s in chapter.get("sources", []) if isinstance(s, dict)}

        def ab_backed(item: dict) -> bool:
            sids: list[str] = []
            for eid in item.get("supporting_evidence_ids", []):
                point = evidence.get(eid) or {}
                sids.extend(point.get("source_ids", []) or [])
            return any((source_map.get(sid) or {}).get("tier") in {"A", "B"} for sid in sids)

        conclusion = chapter.get("chapter_conclusion") or {}
        p0_items = [c for c in chapter["claims"] if c.get("priority") == "P0"]
        if conclusion.get("priority") == "P0":
            p0_items.append(conclusion)
        for item in p0_items:
            if not ab_backed(item):
                finding("p0_weak_support", item.get("claim_id", "?"),
                        "P0 声明缺少 A/B 级来源背书；补一级/权威来源，或降级为 P1 并说明。")

        supported = 0
        for claim in chapter["claims"]:
            if claim["supporting_evidence_ids"]:
                supported += 1
            else:
                finding("claim_support_missing", claim["claim_id"], "补充支撑证据，或明确标注为尚未证实的假设并说明限制。")
        metrics = {
            "question_plan_coverage": _metric(bool(questions), 1),
            "claim_support_coverage": _metric(supported, len(chapter["claims"])),
            "evidence_provenance_coverage": _metric(located, len(evidence)),
            "question_answer_coverage": _metric(sum(q["status"] == "answered" for q in questions), len(questions)),
            "counter_search_coverage": _metric(len(counter_questions), len(questions)),
            "search_task_completion": _metric(len(done_tasks), len(tasks)),
            "refute_task_coverage": _metric(len(refute_done), len(refute_tasks)),
            "p0_ab_support_coverage": _metric(sum(1 for item in p0_items if ab_backed(item)), len(p0_items)),
        }
        rows.append({"chapter_id": cid, "metrics": metrics})

    totals = {}
    if rows:
        for name in rows[0]["metrics"]:
            totals[name] = _metric(
                sum(row["metrics"][name]["covered"] for row in rows),
                sum(row["metrics"][name]["total"] for row in rows),
            )
    return {
        "schema_version": 1,
        "evaluation_kind": "metadata_coverage_not_factual_accuracy",
        "limitations": [
            "仅校验登记结构与覆盖，不自动验证摘录真伪、引用蕴含或正文是否完整回答问题。",
            "研究问题和检索日志由研究者登记，须结合原始记录复核；缺少记录的比例为 null。",
            "P0 优先级由研究者自行标注，工具不判断其是否'核心'，只核验其 A/B 来源背书。",
            "不生成综合质量分，不替代人工评审或 DeepResearch Bench 等语义评估。",
        ],
        "metrics": totals, "chapters": rows, "findings": findings,
    }
