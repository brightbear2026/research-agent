<div align="center">

# research-agent · 深度研究代理 / Deep Research Agent

**Claude Code 原生 · 科技/产业 · Playwright 真实截图**
**Claude Code-native · Tech/Industry · Playwright real screenshots**

[中文](#中文) ｜ [English](#english)

</div>

---

## 中文

把「深度课题研究与双格式报告生成」规范做成一个可复用的 **Claude Code 研究代理**。以 `/deep-research <课题>` 触发，按 **6 阶段**（调研 → 证据库 → 大纲 → 分章深研 → 双格式交付）产出 **Markdown + HTML** 报告与证据矩阵，严守：**不编造、来源分层、交叉验证、区分事实/观点/判断、真实可溯源截图**。

- **实现形态**：Claude Code 原生（自定义 agent + 分阶段命令 + 辅助 Python 脚本）。
- **领域定位**：科技/产业（Web 为主 + 企业官网/财报/白皮书/标准/政策）。
- **截图**：Playwright 真实捕获（失败落占位，绝不伪造）。

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
- **Playwright Chromium**（截图用，首次自动安装）

### 快速开始

```bash
# 1) 克隆并安装依赖
git clone https://github.com/brightbear2026/research-agent.git
cd research-agent
uv sync
uv run playwright install chromium   # 首次需要，约下载 ~150MB

# 2) 在 Claude Code 内打开本目录后触发研究
#    （在 Claude Code 会话中运行）
/deep-research <你的课题> depth=标准
```

产出落在 `projects/my-topic/`（可改名）。

### 深度旋钮（depth）

| 取值 | 章节数 | 每个结论来源 | 截图 |
|---|---|---|---|
| `快速` | 核心 5–7 章 | ≥1 一级来源 | 按需 |
| `标准`（默认） | 完整 12–13 章 | ≥2 一级来源 | 关键页强制 |
| `深度` | 标准 + 反向验证 | 多轮交叉 | 全量 |

### 六阶段流程

1. **启动**：课题定义/边界、≥15 个研究问题、中英文关键词矩阵 → 检查点
2. **广泛调研**：论文/人物/头部企业/政策标准/数据/案例 6 张清单 → 检查点
3. **大纲**：基于调研（非预设）生成三级大纲 → 检查点
4. **分章深研**：每章写「研究卡」，并行派发 `researcher` 子代理
5. **合并**：标签去重 → 全局 `[n]` 引用 → 写 `citations.csv` → 组装报告
6. **交付**：截图 → 渲染 HTML → 证据矩阵 → `qc.py` 质检全绿 → README

### 目录结构

```
.claude/
├── agents/researcher.md            # L1 研究员子代理（检索/验证/写作执行体）
├── commands/deep-research.md       # L2 调度方（六阶段 + 检查点 + 合并协议，canonical）
├── skills/deep-research/SKILL.md   # 技能入口（可发现摘要）
└── settings.json                   # 工具命令权限白名单
CLAUDE.md                           # 项目约定（红线/来源分层/标签/引用/目录契约）
references/source_rubric.md         # 来源可信度 A/B/C/D 分级表
templates/                          # 报告骨架、HTML 模板、元数据、研究卡、截图清单
tools/                              # 确定性工具（scaffold/screenshot/render_html/evidence/qc/charts）
```

### 工具一览（统一前缀 `uv run python tools/xxx.py`）

```bash
# 建交付目录树 + 空索引
uv run python tools/scaffold.py projects/my-topic

# Playwright 真实截图（读 manifest，写 figures.csv）
uv run python tools/screenshot.py projects/my-topic/data/screenshot_manifest.csv --root projects/my-topic

# Markdown → 自包含 HTML（带目录导航/深色模式/打印样式/引用锚点）
uv run python tools/render_html.py projects/my-topic/report/research_report.md --root projects/my-topic

# 生成证据/争议矩阵 + 资料缺口
uv run python tools/evidence.py --root projects/my-topic

# 质检：引用闭环 + 链接活性 + 截图对应（退出码 0 才算交付）
uv run python tools/qc.py --root projects/my-topic

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

- `report/research_report.md` 为规范叙事（canonical）。
- 引用 `[n]`、图片、表格从 `data/{citations,figures,tables}.csv` 派生。
- HTML 由 `render_html.py` 从 Markdown + 旁路索引生成，**禁止两版分别手写**。
- `qc.py` 校验：正文 `[n]` ↔ citations.csv 闭环、图片对应真实文件、链接活性。

### 交付目录契约（由 `scaffold.py` 生成）

```
projects/my-topic/
├── README.md
├── report/{research_report.md, research_report.html}
├── images/FIG-###.png
├── data/{citations, figures, tables, source_data, company_comparison,
│        paper_list, source_index, screenshot_manifest}.csv
├── evidence/{evidence_matrix, controversy_matrix}.csv, research_gaps.md
└── sources/{bibliography, source_index}.md
```

### 研究限制

- 付费墙 / JS 拦截页面无法抓取时，截图落占位、正文标「暂未找到可靠公开来源」，不臆造。
- 一手原文优先；二手来源仅作线索，关键结论不依赖 C/D 级来源。
- 数据截止与访问日期以报告 frontmatter 与 `citations.csv` 为准。
- Playwright 浏览器版本须与 Python 包版本匹配（包 `1.62.0` ↔ build `1234`）；不匹配时报「Executable doesn't exist」，重跑 `uv run playwright install chromium` 即可。

---

## English

A reusable **Claude Code research agent** that operationalizes a "deep research + dual-format report" specification. Triggered by `/deep-research <topic>`, it runs a **6-phase pipeline** (research → evidence base → outline → per-chapter deep research → dual-format delivery) and produces **Markdown + HTML** reports with an evidence matrix — while strictly enforcing: **no fabrication, source tiering, cross-validation, fact/opinion/judgment distinction, and real traceable screenshots**.

- **Form**: Claude Code-native (custom agent + staged command + helper Python scripts).
- **Domain**: Tech/Industry (Web-first + corporate sites / filings / whitepapers / standards / policy).
- **Screenshots**: Playwright real capture (failures get an explicit placeholder, never faked).

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
- **Playwright Chromium** (for screenshots; installed on first run)

### Quick Start

```bash
# 1) Clone and install
git clone https://github.com/brightbear2026/research-agent.git
cd research-agent
uv sync
uv run playwright install chromium   # first run only, ~150MB download

# 2) Trigger research inside Claude Code
#    (run within a Claude Code session in this directory)
/deep-research <your topic> depth=standard
```

Output lands in `projects/my-topic/` (renameable).

### Depth Knob

| Value | Chapters | Sources per conclusion | Screenshots |
|---|---|---|---|
| `fast` (`快速`) | 5–7 core | ≥1 primary | as needed |
| `standard` (`标准`, default) | full 12–13 | ≥2 primary | key pages forced |
| `deep` (`深度`) | standard + adversarial verification | multi-round cross-check | full |

### Six-Phase Pipeline

1. **Kickoff**: scope/boundaries, ≥15 research questions, bilingual keyword matrix → checkpoint
2. **Broad survey**: 6 lists (papers / people / leading companies / policy & standards / data / cases) → checkpoint
3. **Outline**: three-level outline derived from research (not preset) → checkpoint
4. **Per-chapter deep research**: write a "research card" per chapter, dispatch `researcher` subagents in parallel
5. **Merge**: dedupe source tags → global `[n]` citations → write `citations.csv` → assemble report
6. **Deliver**: screenshots → render HTML → evidence matrix → `qc.py` all-green → README

### Directory Layout

```
.claude/
├── agents/researcher.md            # L1 researcher subagent (search/verify/write worker)
├── commands/deep-research.md       # L2 orchestrator (6 phases + checkpoints + merge protocol; canonical)
├── skills/deep-research/SKILL.md   # Skill entry (discoverable summary)
└── settings.json                   # allowed tool commands
CLAUDE.md                           # Project conventions (red lines / tiers / tags / citations / layout)
references/source_rubric.md         # A/B/C/D source credibility rubric
templates/                          # report skeleton, HTML template, metadata, research card, screenshot manifest
tools/                              # deterministic tools (scaffold/screenshot/render_html/evidence/qc/charts)
```

### Tools (common prefix `uv run python tools/xxx.py`)

```bash
# Scaffold the delivery tree + empty indexes
uv run python tools/scaffold.py projects/my-topic

# Playwright real screenshots (reads manifest, writes figures.csv)
uv run python tools/screenshot.py projects/my-topic/data/screenshot_manifest.csv --root projects/my-topic

# Markdown → self-contained HTML (nav / dark mode / print styles / citation anchors)
uv run python tools/render_html.py projects/my-topic/report/research_report.md --root projects/my-topic

# Build evidence/controversy matrices + research gaps
uv run python tools/evidence.py --root projects/my-topic

# Quality check: citation closure + link liveness + screenshot correspondence (exit 0 = deliverable)
uv run python tools/qc.py --root projects/my-topic

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

- `report/research_report.md` is the canonical narrative.
- Citations `[n]`, figures, and tables derive from `data/{citations,figures,tables}.csv`.
- HTML is generated by `render_html.py` from Markdown + sidecar indexes — **never hand-author both versions**.
- `qc.py` verifies: in-text `[n]` ↔ citations.csv closure, figure ↔ real file correspondence, link liveness.

### Delivery Tree (created by `scaffold.py`)

```
projects/my-topic/
├── README.md
├── report/{research_report.md, research_report.html}
├── images/FIG-###.png
├── data/{citations, figures, tables, source_data, company_comparison,
│        paper_list, source_index, screenshot_manifest}.csv
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

<sub>Built with Claude Code · 触发 <code>/deep-research</code></sub>

</div>
