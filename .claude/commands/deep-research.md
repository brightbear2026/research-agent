---
description: 围绕课题执行六阶段深度研究，产出 Markdown+HTML 双格式报告与证据矩阵
argument-hint: <研究课题> [depth=快速|标准|深度]
---

你现在是「深度研究」流程的**调度方（orchestrator）**。课题为：**$ARGUMENTS**（若为空，先用 AskUserQuestion 向用户索要课题、背景、目标读者、研究范围与重点关注问题）。

严格遵循本仓库 `CLAUDE.md` 的全部约定（红线、来源分层、行内标签、引用、目录契约）。不要一次性生成最终报告——按下面 **6 阶段** 推进，阶段一/二/三结束用 `AskUserQuestion` 暂停确认。

## 0. 解析与初始化
- **每个课题独立启动，不前置参考 `projects/` 下其他课题的历史报告/产出**。新课题从课题本身的研究问题与关键词出发；既有课题报告仅作交付归档，不作为新课题的背景输入。除非用户明确要求引用某既有课题结论，否则不读取其他课题目录。
- 从参数解析 `depth`（默认「标准」）。规则：
  - 快速：3–5 个核心论证章节，正文约 1–2 万字，每结论 ≥1 一级来源，截图按需。
  - 标准：5–8 个论证章节，正文约 2–4 万字，每结论 ≥2 一级来源，关键页强制截图。
  - 深度：6–10 个论证章节，正文原则上不超过 6 万字，标准要求 + 每章反向验证多轮 + 全量截图。
- **项目目录名 = `projects/<课题slug>`**（如「AI Agent 安全」→ `projects/ai-agent-security`；slug 用课题英文/拼音短名、kebab-case）。**每个课题一个独立 slug 文件夹，绝不复用旧目录**，从源头避免覆盖上一课题。
- 运行 `uv run python tools/scaffold.py projects/<课题slug>` 建骨架。若该目录已存在且非空，scaffold 会**拒绝**（需换 slug；或加 `--force`——会先把旧目录备份为 `<slug>-backup-<时间>`，不直接清空）。
- 用 `TaskCreate` 建立阶段一~六的任务，逐个 `in_progress`/`completed`。

## 阶段一 · 研究启动（先调研再设计大纲）
产出（写入 `sources/stage1_kickoff.md`）：
1. 课题定义与边界（研究对象、不研究什么、时间/地域/分析层级范围）。
2. **概念分解与辨析（关键，不可跳）**：若课题标题含多个概念（如「A 与 B」），必须把每个概念作为**对等概念**独立定义，并辨析它们的关系（包含/交叉/因果/层级）+ 一张概念关系图。**这些定义须作为 Ch1「§概念定义与辨析」节写进报告正文**（不只停在过程文档）——这是最常被漏掉的环节。
3. **术语表 `data/glossary.md`**（用 Write 创建）：列出全部核心术语（中英、定义、与相邻概念的区别），作为全报告统一口径；Phase 4 每个 researcher 须先读。
4. **≥15 个研究问题**，按类划分（定义/历史/现状/数据/技术/企业/人物观点/竞争/应用/风险/趋势/战略）。
5. 中英文关键词矩阵（中/英/学术/企业/政策/数据/反方/争议/年份/地域）。
6. 搜索策略与预期资料类型、研究风险。
→ **检查点**：用 `AskUserQuestion` 让用户确认/调整**概念辨析**、边界与问题集。

## 阶段二 · 广泛调研
围绕课题在「学术论文/关键人物/头部企业/政策标准/市场数据/案例」6 维做广泛搜索（中英关键词各多组，含反方词）。产出（写入 `sources/stage2_survey.md`）：
- 论文清单、关键人物清单、头部企业清单、政策/标准清单、数据来源清单、案例清单（含成功与失败）。
- 初步重要发现、争议点、资料缺口（同步填 `evidence/research_gaps.md`）。
- 关键论文/人物/企业尽量读一手原文（WebFetch）。
→ **检查点**：`AskUserQuestion` 确认调研覆盖面与重点。

## 阶段三 · 论证地图与正式大纲（基于调研，非预设）
先产出 `sources/stage3_argument_map.yaml`：研究问题、一句话答案、总论点、3–7 个核心分论点、分论点依赖关系、所需正反证据、承载章节与决策含义。再据此产出三级大纲 `sources/stage3_outline.md`。**不默认套用固定 13 章**；历史、人物、政策、企业等材料只有在支撑核心论点时才独立成章，否则放进最相关章节或证据附件。每章列出：读者问题、一句话结论、在总论证中的作用、依赖/交给相邻章节的问题、目标字数、所需正反证据、预期图表与截图。大纲必须是调研结果，不是预设答案的包装。
→ **检查点**：`AskUserQuestion` 确认大纲。

## 阶段四 · 分章深研（派 researcher 子代理）
对每一章：
1. 先写「研究卡」（可基于 `templates/research_card.md`）。
2. 用 **Agent 工具派发 `researcher` 子代理**执行该章（独立维度可多条并行；单消息内放多个 Agent 调用以并发）。**每个 researcher 的 prompt 必须前置：「先读 `data/glossary.md`，全文术语定义以此为准，不得自行另造或漂移」**，并告知本章涉及的术语条目。子代理同时产出 `report/_draft_<chNN>_<slug>.md`（只含读者正文）与同名 `.meta.json`（数据点、截图、争议、缺口）。正文使用内联源标签 `[[SRC|...]]`（见 researcher 契约）。**截图须在草稿正文支撑处用 `![简述](images/FIG-NNN.png)` 内联（fig_id 全局唯一、按出现顺序续编），不得在草稿末尾或单设「截图」节集中罗列**（详见 researcher 契约）。
3. 收齐所有章节草稿。

## 阶段五 · 确定性组装 + 总编辑
1. 运行 `uv run python tools/merge.py <项目名> --require-meta ...`，把所有草稿中的源标签按 URL 去重并分配全局 `[n]`，生成 `data/citations.csv`、`data/chapter_meta.json` 与 `report/_assembled_report.md`。合并器兼容 Markdown 表格中的 `[[SRC\|...]]`，并剔除旧格式草稿的生产过程章节。
2. 读取各章 `.meta.json`，把数据点汇总进 `data/source_data.csv`，截图写入 `data/screenshot_manifest.csv`，核心结论/争议写入 evidence 矩阵；不要从读者正文反向解析这些内部数据。
3. 派发 `report-editor` 总编辑代理。它读取组装稿、argument map、大纲和术语表，只做重组、压缩、去重和语言编辑，**不得搜索或新增事实、数字、来源、案例与引用编号**，输出 `report/research_report.md`。
4. 总编辑必须保留各章草稿里已内联的图片在其支撑论断附近，不得把图片集中移到附录或报告末尾。
5. 运行：
   `uv run python tools/qc.py --root <项目名> --report <项目名>/report/research_report.md --citation-baseline <项目名>/report/_assembled_report.md --skip-links --depth <档位>`
   修复残留源标签、生产过程文字、超长句段、重复结构和引用问题。

## 阶段六 · 交付
1. `uv run python tools/screenshot.py <项目名>/data/screenshot_manifest.csv --root <项目名>` 生成真实截图与 `figures.csv`（失败页自动落占位，禁止伪造）。
2. `uv run python tools/render_html.py <项目名>/report/research_report.md --root <项目名>` 生成自包含 HTML。
3. `uv run python tools/evidence.py --root <项目名>` 汇总证据库。
4. `uv run python tools/qc.py --root <项目名> --citation-baseline <项目名>/report/_assembled_report.md --depth <档位> --strict`（含链接与可读性检查）做终检；非 0 退出则修订直至通过。严格模式下占位截图、未登记图、引用元数据缺失、残留内部文字和严重可读性问题都会阻止交付。
5. 写 `<项目名>/README.md`（课题、文件结构、阅读方式、数据截止、截图说明、研究限制、更新方式）。
6. 最终交付：MD + HTML + evidence 矩阵 + 截图目录；向用户汇报路径与 qc 结果。

## 始终遵守
- 不编造；无法确认就写「暂未找到可靠公开来源」。
- 每个重要事实有来源、每个数据有口径、每个人物观点有原始出处、企业方案优先官方材料、截图真实可溯源。
- 主动搜反方观点；区分事实/观点/推测/研究判断。
- 截图、链接、引用闭环以 `qc.py` 全绿为准。
