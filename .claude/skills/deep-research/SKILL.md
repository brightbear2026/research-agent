---
name: deep-research
description: 围绕任意课题执行六阶段深度研究（调研→证据库→大纲→分章深研→双格式交付），产出 Markdown+HTML 报告与证据矩阵，严守不编造/来源分层/真实截图。
---

# deep-research 技能

本技能是「深度研究」流程的入口。**推荐用 `/deep-research <课题> [depth=快速|标准|深度] [mode=regular|plan|execution]` 触发**。三模式由 `workflow_policy.py` 状态机统一控制：常规模式确认三次，计划模式仅大纲后确认并停止，执行模式仓库流程零确认。

## 何时使用
用户要求就某课题做系统、广泛、深入、可验证的研究，并产出双格式报告时。

## 流程（六阶段，确认点由状态机决定）
1. **启动**：课题定义/边界、≥15 研究问题、中英文关键词矩阵、搜索策略 → 检查点。
2. **广泛调研**：论文/人物/头部企业/政策标准/市场数据/案例六维搜索 + 证据库脚手架 + 发现/争议/缺口 → 检查点。
3. **大纲**：基于调研生成三级大纲（每章目标/问题/证据/图表/截图/结论）→ 检查点。
4. **分章深研**：每章写研究卡，**派 `researcher` 子代理**执行（独立维度并行）。
5. **组装与总编辑**：源标签 `[[SRC|...]]` 去重→分配 `[n]`→写 `data/citations.csv` 与 `_assembled_report.md`；由 `report-editor` 基于 argument map 压缩、去重、重组为 `research_report.md`。
6. **交付**：`screenshot.py`（真实截图）→ `render_html.py` → `evidence.py` → `qc.py --strict`（含链接、引用、截图与可读性）终检 → README。

## 红线（见 CLAUDE.md）
不编造任何来源/数据/观点/截图；无法确认写「暂未找到可靠公开来源」；区分事实/观点/判断；关键数值 ≥2 独立来源；截图必须真实（失败落占位，禁止伪造）；引用/链接/截图以 `qc.py` 全绿为准。

## 完整执行细则
见 `.claude/commands/deep-research.md`（canonical）。工具用法见 `CLAUDE.md`。
