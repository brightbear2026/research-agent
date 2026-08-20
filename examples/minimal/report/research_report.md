---
title: "research-agent 最小实现审计样例"
created_date: "2026-08-11"
data_cutoff_date: "2026-08-11"
language: "zh-CN"
---

# 第 1 章 模式控制是否来自统一实现

## 本章结论

【事实】仓库配置定义了常规、计划和执行三种模式；三者共享同一组六阶段名称，但确认点与停止位置不同。[1]

## 直接证据

【事实】`workflow_modes.yaml` 把确认点、停止阶段、公开来源访问策略和失败预算集中在一份配置中。[1] `workflow_policy.py` 读取该配置，持久化当前阶段、确认次数、外部失败、资料缺口和逐章进度。[2]

## 解释与限制

【研究判断】这说明三种模式不是只存在于 README 的文字约定中。该样例只验证仓库内的确定性控制层，不验证 Claude Code、Codex 或外部网站在所有运行环境中的可用性。

## 对决策的含义

评审模式行为时，应优先检查配置、状态文件和状态机测试；仅比较两个入口的提示词不足以证明它们实际一致。

## 参考文献

1. research-agent，《workflow_modes.yaml》，GitHub，2026-08-11。[链接](https://github.com/brightbear2026/research-agent/blob/main/config/workflow_modes.yaml)
2. research-agent，《workflow_policy.py》，GitHub，2026-08-11。[链接](https://github.com/brightbear2026/research-agent/blob/main/tools/workflow_policy.py)
