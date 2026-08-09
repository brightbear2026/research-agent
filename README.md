<div align="center">

# research-agent · 深度研究代理 / Deep Research Agent

**Claude Code + Codex/ChatGPT Work · 证据驱动 · Playwright 真实截图**

**Claude Code + Codex/ChatGPT Work · Evidence-driven · Real Playwright screenshots**

[中文](#中文) ｜ [English](#english)

</div>

---

## 中文

一个同时支持 **Claude Code 与 Codex/ChatGPT Work** 的证据驱动深度研究代理。通过统一状态机执行六阶段流程，产出 **Markdown + HTML** 报告、证据矩阵、数据表与资料缺口清单，严守：**不编造、来源分层、交叉验证、声明—证据可追溯、真实截图**。

- **双入口**：Claude Code 命令与 Codex/ChatGPT Work 技能共用同一状态机、schema v2、聚合器和 QC。
- **领域定位**：科技/产业（Web 为主 + 企业官网/财报/白皮书/标准/政策）。
- **截图**：Playwright 真实捕获（失败落占位，绝不伪造）。

### 项目亮点

- **Claude Code 与 Codex/ChatGPT Work 双入口**：两个入口调用同一套状态机和确定性工具，避免行为漂移。
- **三种执行模式**：常规模式保留阶段确认；计划模式只产出计划；执行模式在仓库流程内连续运行到交付。
- **机器可执行六阶段状态机**：模式、阶段、确认次数、停止条件和失败预算写入 `.research-workflow.json`，不只依赖提示词约定。
- **schema v2 证据语义**：声明、证据和来源使用稳定 ID 关联；数值必须保留单位、统计时间、地区或适用范围。
- **禁止循环证据**：章节结论不能复制为自身支撑证据，重要结论必须追溯到真实 evidence ID 和 source ID。
- **声明账本与编辑审计**：总编辑可以改写表达，但新增数字、日期、实体、因果关系、确定性升级或删除限制条件会被 QC 拦截。
- **安全、真实的网页与 PDF 捕获**：限制输出目录、文件大小、PDF 页数、图片像素、重试次数和总时间；不隐藏自动化，不绕过登录、验证码、付费墙或 WAF。
- **可审查交付物**：同时生成规范 Markdown、HTML、数据表、证据矩阵、争议矩阵、来源清单和资料缺口清单。

### 三种运行模式（mode）

| 模式 | 参数 | 仓库内确认点 | 执行范围 | 适用场景 |
|---|---|---:|---|---|
| 常规模式 | `mode=regular` | 3 次：启动、广泛调研、大纲 | 完成六阶段 | 希望逐步校准范围、资料覆盖和大纲 |
| 计划模式 | `mode=plan` | 1 次：大纲完成后 | 确认计划后停止，不写正式报告 | 只需要研究方案、问题树、来源策略和正式大纲 |
| 执行模式 | `mode=execution` | 0 次 | 连续执行六阶段并尝试完成交付 | 目标和范围明确，希望减少仓库流程等待 |

“执行模式零确认”仅指本仓库不主动设置内容检查点。系统权限审批、登录、验证码、付费墙和网站访问控制仍然有效；访问失败会在有限重试后转为资料缺口，不会被绕过或无限重试。

### 核心红线

- **不编造**：论文、作者、人物发言、数据、公司方案、市场规模、URL、截图、政策、产品能力、访谈、页码、日期——一律不得虚构。
- 无法确认的信息必须写明「**暂未找到可靠公开来源**」，不得用标题或二手转述臆造内容。
- 截图必须来自 **Playwright 真实捕获**；失败则落明确标注的占位符，**禁止用 AI 图/拼接冒充原始截图**。
- 区分 **事实 / 人物观点 / 机构观点 / 行业共识 / 争议 / 研究判断 / 推测**。
- 关键数值类结论须 **≥2 独立来源**交叉验证；来源冲突时列口径/时间/机构，给**条件性结论**，不二选一。

### 环境要求

- **Python ≥ 3.13**
- **[uv](https://docs.astral.sh/uv/)**（依赖管理）
- **[Claude Code](https://docs.claude.com/en/docs/claude-code/overview)**（CLI 已挂载 WebSearch / WebFetch 等 Web 工具）
- **Codex/ChatGPT Work**（可选，通过 `.codex/skills/deep-research-work` 入口使用）
- **Playwright Chromium**（截图用，首次自动安装）

### 安装

```bash
# 1) 克隆并安装依赖
git clone https://github.com/brightbear2026/research-agent.git
cd research-agent
uv sync
uv run playwright install chromium   # 首次需要，约下载 ~150MB

```

### Claude Code 使用方法

在 Claude Code 中打开仓库目录，使用 `/deep-research`：

```text
# 常规模式（默认）
/deep-research AI Agent 评测体系 depth=标准 mode=regular

# 只生成研究计划与正式大纲，确认后停止
/deep-research AI Agent 评测体系 depth=标准 mode=plan

# 仓库流程不设置内容确认点，连续运行到交付
/deep-research AI Agent 评测体系 depth=深度 mode=execution
```

Claude Code 的完整调度规则位于 `.claude/commands/deep-research.md`；分章研究和总编辑分别由 `.claude/agents/researcher.md`、`.claude/agents/report-editor.md` 约束。

### Codex / ChatGPT Work 使用方法

仓库内置技能 `.codex/skills/deep-research-work/`。在 Codex 或支持工作区技能的 ChatGPT Work 中打开本仓库，然后在对话中显式调用：

```text
使用 $deep-research-work，研究“AI Agent 评测体系”，depth=标准，mode=regular。

使用 $deep-research-work，为“企业 Agent 安全治理”制定研究计划，depth=深度，mode=plan。

使用 $deep-research-work，完整研究“推理算力基础设施”，depth=深度，mode=execution。
```

Codex/ChatGPT Work 会读取同一份 `CLAUDE.md`、`config/workflow_modes.yaml` 和确定性工具。技能入口不会复制或维护另一套研究规则。

运行中的状态保存在课题目录的 `.research-workflow.json`。需要检查状态时可运行：

```bash
uv run python tools/workflow_policy.py status --root projects/my-topic
```

所有产出均落在独立的 `projects/<topic-slug>/`，不会覆盖其他课题。

### 深度旋钮（depth）

| 取值 | 章节数 | 每个结论来源 | 截图 |
|---|---|---|---|
| `快速` | 3–5 个论证章节，约 1–2 万字 | ≥1 一级来源 | 按需 |
| `标准`（默认） | 5–8 个论证章节，约 2–4 万字 | ≥2 一级来源 | 关键页强制 |
| `深度` | 6–10 个论证章节，原则上 ≤6 万字 | 多轮交叉 | 全量 |

### 六阶段流程

流程由 `config/workflow_modes.yaml` 和 `tools/workflow_policy.py` 控制。`regular` 在前三阶段分别确认，`plan` 仅在大纲后确认并停止，`execution` 不设置仓库内确认点；所有模式都受外部访问控制和有限重试预算约束。

1. **启动**：课题定义/边界、≥15 个研究问题、中英文关键词矩阵 → 检查点
2. **广泛调研**：论文/人物/头部企业/政策标准/数据/案例 6 张清单 → 检查点
3. **论证地图与大纲**：先确定总论点、分论点和依赖关系，再生成动态大纲 → 检查点
4. **分章深研**：每章写「研究卡」，并行派发 `researcher`；读者正文与 `.meta.json` 分离
5. **组装与总编辑**：schema v2 与证据关系校验 → 生成声明账本 → 标签去重 → `_assembled_report.md` → 总编辑压缩、去重、重组 → 事实漂移审计
6. **交付**：截图 → 渲染 HTML → 证据矩阵 → `qc.py --strict`（含可读性）→ README

### 目录结构

```
.claude/
├── agents/{researcher,report-editor}.md # 研究执行 + 受限总编辑
├── commands/deep-research.md       # L2 调度方（六阶段 + 检查点 + 合并协议，canonical）
├── skills/deep-research/SKILL.md   # 技能入口（可发现摘要）
└── settings.json                   # 工具命令权限白名单
.codex/skills/deep-research-work/   # Codex/ChatGPT Work 技能入口
config/workflow_modes.yaml          # 三模式、六阶段、确认点与资源预算
CLAUDE.md                           # 项目约定（红线/来源分层/标签/引用/目录契约）
references/source_rubric.md         # 来源可信度 A/B/C/D 分级表
templates/                          # 报告骨架、HTML 模板、元数据、研究卡、截图清单
tools/                              # 状态机、迁移、聚合、声明账本、截图、渲染与 QC
```

### 工具一览（统一前缀 `uv run python tools/xxx.py`）

```bash
# 建交付目录树 + 空索引
uv run python tools/scaffold.py projects/my-topic

# 旧版 chapter_meta 无损迁移（输出 .v2.json，不覆盖原文件）
uv run python tools/migrate_chapter_meta.py projects/my-topic/data/chapter_meta.json

# 组装章节，生成 citations、chapter_meta、_assembled_report 和 claim_ledger
uv run python tools/merge.py projects/my-topic --require-meta --title "报告标题"

# 先校验 schema v2 和证据关系，再备份并聚合旁路 CSV
uv run python tools/aggregate_meta.py --root projects/my-topic --dry-run
uv run python tools/aggregate_meta.py --root projects/my-topic --force

# Playwright 真实截图（读 manifest，写 figures.csv）
uv run python tools/screenshot.py projects/my-topic/data/screenshot_manifest.csv \
  --root projects/my-topic --deadline-seconds 600

# Markdown → 自包含 HTML（带目录导航/深色模式/打印样式/引用锚点）
uv run python tools/render_html.py projects/my-topic/report/research_report.md --root projects/my-topic

# 生成证据/争议矩阵 + 资料缺口
uv run python tools/evidence.py --root projects/my-topic

# 终检：引用闭环 + 链接 + 截图 + 可读性 + 编辑引用审计
uv run python tools/qc.py --root projects/my-topic --strict \
  --citation-baseline projects/my-topic/report/_assembled_report.md \
  --claim-ledger projects/my-topic/data/claim_ledger.json

# 自制图表（标题自动标注「数据来源：根据公开资料整理/计算」）
uv run python tools/charts.py bar --data <csv> --x <col> --y <col> --out images/FIG-005.png --title "..." --source "..."
```

### 行内标签（Markdown 与 HTML 共用）

| 标签 | 含义 |
|---|---|
| `【事实】` | 客观事实（须有来源） |
| `【观点·姓名·机构·YYYY-MM-DD】` | 人物观点（须有原始出处） |
| `【机构观点·机构·日期】` | 机构观点 |
| `【争议】` | 存在分歧 |
| `【研究判断】` | 基于证据的综合判断 |
| `【推测】` | 尚未充分证据支持的假设 |

### 来源可信度分层

| 等级 | 来源类型 | 工具映射 |
|---|---|---|
| **A 一级·原始** | 企业官网、年报财报、白皮书、产品文档、标准原文、政府政策、专利、原始演讲/访谈 | WebFetch / web_reader 抓官方 URL |
| **B 二级·权威研究** | 智库、行业协会、分析师、高校、国际机构报告 | WebSearch + WebFetch |
| **C 三级·专业媒体** | 主流财经/科技/行业媒体深度报道 | WebSearch |
| **D 四级·一般内容** | 自媒体、聚合站、论坛、匿名社媒、营销软文 | **仅作线索**，不作关键结论唯一依据 |

### 单一事实源（双格式一致性）

- `report/_assembled_report.md` 是确定性组装稿；`report/research_report.md` 是经受限总编辑处理后的规范终稿（canonical）。
- 引用 `[n]`、图片、表格从 `data/{citations,figures,tables}.csv` 派生。
- HTML 由 `render_html.py` 从 Markdown + 旁路索引生成，**禁止两版分别手写**。
- `qc.py --strict` 校验：引用闭环、图片、链接、内部材料、可读性，以及总编辑是否新增数字/日期/实体、升级确定性或因果关系、删除限制条件。

### 交付目录契约（由 `scaffold.py` 生成）

```
projects/my-topic/
├── README.md
├── report/{_assembled_report.md, research_report.md, research_report.html}
├── images/FIG-###.png
├── data/{citations, figures, tables, source_data, company_comparison,
│        paper_list, source_index, screenshot_manifest}.csv,
│        {chapter_meta, claim_ledger}.json
├── evidence/{evidence_matrix, controversy_matrix}.csv, research_gaps.md
└── sources/{bibliography, source_index}.md
```

### 研究限制

- 截图只能写入项目 `images/`；PDF 下载限制字节数、页数、像素和总时间。429/部分 5xx 仅有限退避重试，登录、验证码、付费墙和 WAF 分别记录，不尝试绕过。
- 外部页面无法抓取时，截图落占位、记录失败原因和替代来源，正文标「暂未找到可靠公开来源」，不臆造。
- 一手原文优先；二手来源仅作线索，关键结论不依赖 C/D 级来源。
- 数据截止与访问日期以报告 frontmatter 与 `citations.csv` 为准。
- Playwright 浏览器版本须与 Python 包版本匹配（包 `1.62.0` ↔ build `1234`）；不匹配时报「Executable doesn't exist」，重跑 `uv run playwright install chromium` 即可。

---

## English

A reusable, evidence-driven research agent for **Claude Code and Codex/ChatGPT Work**. Both entry points share one executable six-phase state machine, schema v2, deterministic aggregation, claim-ledger editing audit, and strict QC. It delivers **Markdown + HTML** reports, evidence matrices, data tables, and disclosed research gaps.

- **Dual entry points**: Claude Code commands and a Codex/ChatGPT Work skill share the same workflow implementation.
- **Domain**: Tech/Industry (Web-first + corporate sites / filings / whitepapers / standards / policy).
- **Screenshots**: Playwright real capture (failures get an explicit placeholder, never faked).

### Highlights

- **Two entry points, one implementation**: Claude Code and Codex/ChatGPT Work use the same state machine, schema, aggregation, and QC tools.
- **Three workflow modes**: regular checkpoints, plan-only delivery, or continuous execution.
- **Executable six-phase policy**: phase, confirmation count, stop conditions, failures, and retry budgets are persisted instead of living only in prompts.
- **Evidence semantics with schema v2**: stable claim, evidence, and source IDs; numeric evidence retains unit, statistical time, and region or scope.
- **No circular evidence**: conclusion text cannot serve as its own support.
- **Claim-ledger editing audit**: blocks new numbers, dates, entities, causal claims, certainty escalation, and loss of limitations.
- **Bounded, compliant capture**: real browser/PDF capture with path, size, page, pixel, retry, and deadline limits; no access-control bypass.
- **Reviewable deliverables**: Markdown, HTML, evidence and controversy matrices, data tables, source indexes, screenshots, and research gaps.

### Workflow Modes

| Mode | Parameter | Repository checkpoints | Stops at | Best for |
|---|---|---:|---|---|
| Regular | `mode=regular` | 3: kickoff, survey, outline | Final delivery | Iterative scope and outline review |
| Plan | `mode=plan` | 1: after outline | Confirmed plan; no formal report execution | Research strategy and outline only |
| Execution | `mode=execution` | 0 | Final delivery attempt | A clear brief with minimal workflow pauses |

Zero checkpoints in execution mode applies only to repository-defined content confirmations. System permissions, authentication, CAPTCHA, paywalls, and site controls still apply. Failed sources are retried within finite budgets, then disclosed as research gaps.

### Core Red Lines

- **No fabrication**: papers, authors, quotes, figures, company plans, market sizes, URLs, screenshots, policies, product capabilities, interviews, page numbers, dates — none may be invented.
- Unverifiable information must read "**暂未找到可靠公开来源**" (no reliable public source found) — never dress up a headline or second-hand paraphrase as content.
- Screenshots must come from **real Playwright capture**; on failure an explicitly-labeled placeholder is written — **no AI images, no splicing, no fake originals**.
- Clearly distinguish **fact / personal opinion / institutional view / industry consensus / dispute / research judgment / speculation**.
- Key numeric conclusions require **≥2 independent sources**; on conflict, list caliber/time/institution and give a **conditional conclusion** — never pick one and hide the other.

### Requirements

- **Python ≥ 3.13**
- **[uv](https://docs.astral.sh/uv/)** (dependency management)
- **[Claude Code](https://docs.claude.com/en/docs/claude-code/overview)** (CLI with WebSearch / WebFetch and other Web tools mounted)
- **Codex/ChatGPT Work** (optional, via `.codex/skills/deep-research-work`)
- **Playwright Chromium** (for screenshots; installed on first run)

### Install

```bash
# 1) Clone and install
git clone https://github.com/brightbear2026/research-agent.git
cd research-agent
uv sync
uv run playwright install chromium   # first run only, ~150MB download

```

### Use with Claude Code

Open this repository in Claude Code and run:

```text
/deep-research AI agent evaluation depth=标准 mode=regular
/deep-research AI agent evaluation depth=标准 mode=plan
/deep-research AI agent evaluation depth=深度 mode=execution
```

The canonical command workflow is `.claude/commands/deep-research.md`. Per-chapter research and constrained editing are defined in `.claude/agents/`.

### Use with Codex / ChatGPT Work

Open the repository as the workspace and explicitly invoke the bundled skill:

```text
Use $deep-research-work to research “AI agent evaluation”, depth=标准, mode=regular.
Use $deep-research-work to plan research on “enterprise agent security”, depth=深度, mode=plan.
Use $deep-research-work to fully research “inference infrastructure”, depth=深度, mode=execution.
```

The skill is located at `.codex/skills/deep-research-work/` and delegates to the same `CLAUDE.md`, `config/workflow_modes.yaml`, and deterministic tools as Claude Code.

Inspect a running workflow with:

```bash
uv run python tools/workflow_policy.py status --root projects/my-topic
```

Each run writes to its own `projects/<topic-slug>/` directory.

### Depth Knob

| Value | Chapters | Sources per conclusion | Screenshots |
|---|---|---|---|
| `fast` (`快速`) | 3–5 argument chapters, ~10–20k Chinese chars | ≥1 primary | as needed |
| `standard` (`标准`, default) | 5–8 argument chapters, ~20–40k Chinese chars | ≥2 primary | key pages forced |
| `deep` (`深度`) | 6–10 argument chapters, normally ≤60k Chinese chars | multi-round cross-check | full |

### Six-Phase Pipeline

1. **Kickoff**: scope/boundaries, ≥15 research questions, bilingual keyword matrix → checkpoint
2. **Broad survey**: 6 lists (papers / people / leading companies / policy & standards / data / cases) → checkpoint
3. **Argument map + outline**: define thesis, claims, dependencies and evidence before the dynamic outline → checkpoint
4. **Per-chapter research**: dispatch `researcher` subagents; keep reader-facing Markdown separate from `.meta.json`
5. **Assemble + edit**: dedupe source tags → `_assembled_report.md` → constrained editor compresses and restructures the final narrative
6. **Deliver**: screenshots → render HTML → evidence matrix → strict QC including readability → README

### Directory Layout

```
.claude/
├── agents/{researcher,report-editor}.md # research worker + constrained final editor
├── commands/deep-research.md       # L2 orchestrator (6 phases + checkpoints + merge protocol; canonical)
├── skills/deep-research/SKILL.md   # Skill entry (discoverable summary)
└── settings.json                   # allowed tool commands
.codex/skills/deep-research-work/   # Codex/ChatGPT Work skill entry
config/workflow_modes.yaml          # modes, phases, checkpoints, budgets
CLAUDE.md                           # Project conventions (red lines / tiers / tags / citations / layout)
references/source_rubric.md         # A/B/C/D source credibility rubric
templates/                          # report skeleton, HTML template, metadata, research card, screenshot manifest
tools/                              # workflow, migration, aggregation, ledger, capture, rendering, and QC
```

### Tools (common prefix `uv run python tools/xxx.py`)

```bash
# Scaffold the delivery tree + empty indexes
uv run python tools/scaffold.py projects/my-topic

# Deterministic assembly (also writes chapter_meta and claim_ledger)
uv run python tools/merge.py projects/my-topic --require-meta --title "Report title"

# Validate schema/evidence relations, then back up and aggregate sidecar CSVs
uv run python tools/aggregate_meta.py --root projects/my-topic --dry-run
uv run python tools/aggregate_meta.py --root projects/my-topic --force

# Playwright real screenshots (reads manifest, writes figures.csv)
uv run python tools/screenshot.py projects/my-topic/data/screenshot_manifest.csv \
  --root projects/my-topic --deadline-seconds 600

# Markdown → self-contained HTML (nav / dark mode / print styles / citation anchors)
uv run python tools/render_html.py projects/my-topic/report/research_report.md --root projects/my-topic

# Build evidence/controversy matrices + research gaps
uv run python tools/evidence.py --root projects/my-topic

# Final gate: citations + links + figures + readability + editor citation audit
uv run python tools/qc.py --root projects/my-topic --strict \
  --citation-baseline projects/my-topic/report/_assembled_report.md \
  --claim-ledger projects/my-topic/data/claim_ledger.json

# Self-made charts (auto-appends "Source: compiled/calculated from public data")
uv run python tools/charts.py bar --data <csv> --x <col> --y <col> --out images/FIG-005.png --title "..." --source "..."
```

### Inline Tags (shared by Markdown and HTML)

| Tag | Meaning |
|---|---|
| `【事实】` | Objective fact (needs a source) |
| `【观点·name·org·YYYY-MM-DD】` | Personal opinion (needs original source) |
| `【机构观点·org·date】` | Institutional view |
| `【争议】` | Dispute |
| `【研究判断】` | Evidence-based judgment |
| `【推测】` | Speculation (insufficient evidence) |

### Source Credibility Tiers

| Tier | Source type | Tool mapping |
|---|---|---|
| **A · Primary** | Corporate sites, annual/financial reports, whitepapers, product docs, standards, government policy, patents, original talks/interviews | WebFetch / web_reader on official URLs |
| **B · Authoritative** | Think tanks, industry associations, analysts, universities, international bodies | WebSearch + WebFetch |
| **C · Professional media** | Major business/tech/industry deep reporting | WebSearch |
| **D · General** | Self-media, aggregators, forums, anonymous social, marketing | **Lead only** — never the sole basis for a key conclusion |

### Single Source of Truth (dual-format consistency)

- `report/_assembled_report.md` is the deterministic assembly; `report/research_report.md` is the constrained editor's canonical final narrative.
- Citations `[n]`, figures, and tables derive from `data/{citations,figures,tables}.csv`.
- HTML is generated by `render_html.py` from Markdown + sidecar indexes — **never hand-author both versions**.
- `qc.py --strict` verifies citation closure, figures, links, leaked process material, length/sentence/paragraph limits, and that editing introduced no new citation IDs.

### Delivery Tree (created by `scaffold.py`)

```
projects/my-topic/
├── README.md
├── report/{_assembled_report.md, research_report.md, research_report.html}
├── images/FIG-###.png
├── data/{citations, figures, tables, source_data, company_comparison,
│        paper_list, source_index, screenshot_manifest}.csv,
│        {chapter_meta, claim_ledger}.json
├── evidence/{evidence_matrix, controversy_matrix}.csv, research_gaps.md
└── sources/{bibliography, source_index}.md
```

### Known Limitations

- On paywalled / JS-blocked pages, the screenshot falls back to a placeholder and the body reads "no reliable public source found" — nothing is fabricated.
- Primary sources are preferred; secondary sources are leads only and never the sole basis for a key conclusion.
- Data cutoff and access dates follow the report frontmatter and `citations.csv`.
- The Playwright browser build must match the Python package version (package `1.62.0` ↔ build `1234`); a mismatch reports "Executable doesn't exist" — just re-run `uv run playwright install chromium`.

---

<div align="center">

<sub>Claude Code: <code>/deep-research</code> · Codex/ChatGPT Work: <code>$deep-research-work</code></sub>

</div>
