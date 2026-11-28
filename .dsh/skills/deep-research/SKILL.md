---
name: deep-research
description: 在已打开的 research-agent 项目中检索、核验证据并生成带图表的研究报告和决策简报。
---

从用户打开的 research-agent 仓库根目录读取 CLAUDE.md、references/report_delivery.md 和 .claude/commands/deep-research.md，按其中的阶段、确认点、工具和文件契约执行。请核实当前工作区有 tools/scaffold.py 和 uv.lock，使用 README 的锁定依赖安装方式。从仓库运行脚本，课题写入 projects/。缺少项目文件时提示打开完整仓库。

把宿主的提问、检索、命令和文件能力映射到对应操作。支持委派时使用章节研究员；仅有单个执行者时逐章执行同一研究卡、登记来源并落盘草稿。依 .claude/agents/report-editor.md 约束编辑过程，使用冻结材料。无人值守时沿用启动约定；模式需要人工确认时保存进度，等待确认。缺少联网、执行或文件权限时说明具体受影响的活动及产物。完成前运行严格 QC，报告验收结果。
