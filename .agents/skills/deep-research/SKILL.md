---
name: deep-research
description: 在已打开的 research-agent 仓库中执行有证据支撑的深度研究，交付研究报告或决策简报（Markdown、HTML、分析图、证据矩阵）。供从项目 .agents/skills/ 发现技能的宿主（Codex、DSH 等）使用。
---

本入口只负责被发现和启动。流程、工具与文件契约全部在仓库共享部分维护：从仓库根目录读取 CLAUDE.md、references/report_delivery.md 和 .claude/commands/deep-research.md，按其中的阶段、确认点、工具和文件契约执行，不要凭记忆复述流程，也不要另建一套规则。

先核实当前工作区是完整仓库（存在 tools/scaffold.py 与 uv.lock），按 README 的锁定依赖方式安装。课题写入 projects/<slug>/，不要复用其他课题的输出。

把宿主的提问、检索、命令执行和文件能力映射到对应操作。支持委派时按章分派研究员；只有单个执行者时逐章执行同一研究卡并落盘草稿。编辑遵守 .claude/agents/report-editor.md，只使用冻结材料。无人值守时沿用启动约定；需要人工确认的模式下保存进度等待确认。缺少联网、执行或文件权限时，说明受影响的活动和产物。完成前运行严格 QC 并报告验收结果。
