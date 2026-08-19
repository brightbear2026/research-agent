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
2. **广泛调研**：论文/人物/头部企业/政策标准/市场数据/券商与投行研报/案例七维搜索 + 证据库脚手架 + 发现/争议/缺口 → 检查点。
3. **大纲**：基于调研生成三级大纲（每章目标/问题/证据/图表/截图/结论）→ 检查点。
4. **分章深研**：登记逐章状态，每章写研究卡并派 `researcher` 执行；完成时校验 `.md`/`.meta.json` 配对，中断后从首个未完成章节继续。
5. **组装与总编辑**：源标签 `[[SRC|...]]` 去重→分配 `[n]`→写 `data/citations.csv` 与 `_assembled_report.md`；由 `report-editor` 基于 argument map 压缩、去重、重组为 `research_report.md`。
6. **交付**：`screenshot.py`（真实截图）→ `render_html.py` → `evidence.py` → `qc.py --strict`（含事实就近引用、独立来源、内容禁忌、最低完整度、截图与事实漂移）终检 → `workflow_policy.py record-debt` → README。**两段式交付**：核心检查 `exit 0` 即可交付；死链/链接警告/来源时效/段落级数值来源等 advisory 项写入 `data/qc_debt.json` 作为已跟踪技术债，不阻断交付。

## 红线（见 CLAUDE.md）
不编造任何来源/数据/观点/截图；无法确认写「暂未找到可靠公开来源」；区分事实/观点/判断；关键数值 ≥2 独立来源；截图必须真实（失败落占位，禁止伪造）；引用闭环、截图、漂移审计、可读性等核心检查以 `qc.py` `exit 0` 为准，advisory 项（死链等）入 `qc_debt.json` 异步收尾、不阻断交付。

## 完整执行细则
见 `.claude/commands/deep-research.md`（canonical）。工具用法见 `CLAUDE.md`。
