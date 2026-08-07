---
description: 围绕课题执行六阶段深度研究，产出 Markdown+HTML 双格式报告与证据矩阵
argument-hint: <研究课题> [depth=快速|标准|深度]
---

你现在是「深度研究」流程的**调度方（orchestrator）**。课题为：**$ARGUMENTS**（若为空，先用 AskUserQuestion 向用户索要课题、背景、目标读者、研究范围与重点关注问题）。

严格遵循本仓库 `CLAUDE.md` 的全部约定（红线、来源分层、行内标签、引用、目录契约）。不要一次性生成最终报告——按下面 **6 阶段** 推进，阶段一/二/三结束用 `AskUserQuestion` 暂停确认。

## 0. 解析与初始化
- 从参数解析 `depth`（默认「标准」）。规则：
  - 快速：5–7 章，每结论 ≥1 一级来源，截图按需。
  - 标准：12–13 章，每结论 ≥2 一级来源，关键页强制截图。
  - 深度：标准 + 每章反向验证多轮 + 全量截图。
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

## 阶段三 · 正式大纲（基于调研，非预设）
产出三级大纲 `sources/stage3_outline.md`，覆盖规范建议的 13 章结构（按课题裁剪）。每章列出：目标、核心问题、所需证据、预期图表、预期截图、预期结论。**大纲必须是调研结果，不是预设答案的包装。**
→ **检查点**：`AskUserQuestion` 确认大纲。

## 阶段四 · 分章深研（派 researcher 子代理）
对每一章：
1. 先写「研究卡」（可基于 `templates/research_card.md`）。
2. 用 **Agent 工具派发 `researcher` 子代理**执行该章（独立维度可多条并行；单消息内放多个 Agent 调用以并发）。**每个 researcher 的 prompt 必须前置：「先读 `data/glossary.md`，全文术语定义以此为准，不得自行另造或漂移」**，并告知本章涉及的术语条目。子代理产出 `report/_draft_<chNN>_<slug>.md`，使用内联源标签 `[[SRC|...]]`（见 researcher 契约）。
3. 收齐所有章节草稿。

## 阶段五 · 合并与初稿（你亲自做合并，保证编号一致）
1. 读取全部 `report/_draft_*.md`。
2. **源标签 → 引用编号**：按 url 去重所有 `[[SRC|...]]` 标签，依首次出现顺序分配全局 `[1][2]…`；生成 `data/citations.csv`（字段：id/type/author_org/title/publication_site/publish_date/doi_or_id/url/access_date/page_or_location/tier）。
3. 把草稿中每个 `[[SRC|...]]` 替换为对应 `[n]`（同源复用同一编号）。
4. 组装 `report/research_report.md`：YAML frontmatter（基于 `templates/metadata.yaml`，填真实日期）+ 目录 + 各章正文 + 附录 + 参考文献（占位，由渲染器生成）。
5. 把各章「数据小表」汇总进 `data/source_data.csv`；论文进 `data/paper_list.csv`；企业对比进 `data/company_comparison.csv`；主来源进 `data/source_index.csv`。
6. 把需截图项写进 `data/screenshot_manifest.csv`。
7. 把核心结论/争议分别进 `evidence/evidence_matrix.csv`、`evidence/controversy_matrix.csv`。
8. 运行 `uv run python tools/qc.py --root <项目名> --skip-links`，按报错修订（补登记/补来源/修标签）。可迭代多轮。

## 阶段六 · 交付
1. `uv run python tools/screenshot.py <项目名>/data/screenshot_manifest.csv --root <项目名>` 生成真实截图与 `figures.csv`（失败页自动落占位，禁止伪造）。
2. `uv run python tools/render_html.py <项目名>/report/research_report.md --root <项目名>` 生成自包含 HTML。
3. `uv run python tools/evidence.py --root <项目名>` 汇总证据库。
4. `uv run python tools/qc.py --root <项目名>`（含链接检查）做终检；非 0 退出则修订直至通过（死链/未登记引用/缺失图必须修）。
5. 写 `<项目名>/README.md`（课题、文件结构、阅读方式、数据截止、截图说明、研究限制、更新方式）。
6. 最终交付：MD + HTML + evidence 矩阵 + 截图目录；向用户汇报路径与 qc 结果。

## 始终遵守
- 不编造；无法确认就写「暂未找到可靠公开来源」。
- 每个重要事实有来源、每个数据有口径、每个人物观点有原始出处、企业方案优先官方材料、截图真实可溯源。
- 主动搜反方观点；区分事实/观点/推测/研究判断。
- 截图、链接、引用闭环以 `qc.py` 全绿为准。
