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
- **领域定位**：科技/产业（Web 为主 + 企业官网/财报/白皮书/标准/政策/券商与投行研报）。
- **截图**：Playwright 真实捕获（失败落占位，绝不伪造）。
- **解释性结构图**：优先使用可选的 **Diagram Design** 插件；保留可追溯 HTML 源并导出 PNG，插件不可用时降级为 Mermaid。

### 项目亮点

- **Claude Code 与 Codex/ChatGPT Work 双入口**：两个入口调用同一套状态机和确定性工具，避免行为漂移。
- **三种执行模式**：常规模式保留阶段确认；计划模式只产出计划；执行模式在仓库流程内连续运行到交付。
- **机器可执行六阶段状态机**：模式、阶段、确认次数、停止条件和失败预算写入 `.research-workflow.json`，不只依赖提示词约定。
- **逐章断点续跑 + 子代理熔断**：阶段四登记 `chapter_progress`，中断后跳过已完成且产物配对有效的章节，从首个未完成章节继续；`researcher` 连续 3 轮检索无新进展即返回（不自循环空转），章节重派达 `max_chapter_attempts`（默认 3）后被拒绝再派，防止卡死章节无限烧 token。
- **schema v2 证据语义**：声明、证据和来源使用稳定 ID 关联；数值必须保留单位、统计时间、地区或适用范围。
- **禁止循环证据**：章节结论不能复制为自身支撑证据，重要结论必须追溯到真实 evidence ID 和 source ID。
- **声明账本与编辑审计**：总编辑可以改写表达，但新增数字、日期、实体、因果关系、确定性升级或删除限制条件会被 QC 拦截。
- **安全、真实的网页与 PDF 捕获**：限制输出目录、文件大小、PDF 页数、图片像素、重试次数和总时间；不隐藏自动化，不绕过登录、验证码、付费墙或 WAF。
- **可审查交付物**：同时生成规范 Markdown、HTML、数据表、证据矩阵、争议矩阵、来源清单和资料缺口清单。
- **券商研报正式入库**：广泛调研主动覆盖券商/投行研报；章节元数据保留分析师、预测期、关键假设、评级/目标价与利益冲突，聚合为 `data/broker_report_list.csv`。预测作为机构观点，底层事实回溯原始来源。
- **两段式 QC 交付门禁**：核心检查（引用闭环、事实标签同段引用、独立来源、截图、漂移审计、可读性、内容禁忌）`exit 0` 即可交付；死链、链接警告、来源时效、段落级数值来源等 advisory 项不阻断，写入 `data/qc_debt.json` 异步收尾。**死链永不阻断**——伪造 URL 无 Wayback 归档会在清单显眼标红，真实但反爬/失效的来源由 Wayback 存档佐证。新增段落级数值来源（单 C/D 级来源支撑的【事实】数值）与快变领域来源时效校验。

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
- `【事实】` 所在段落必须就近出现 `[n]`；禁用「众所周知 / 毫无疑问 / 必将 / 彻底改变 / 颠覆一切 / 市场前景无限 / 具有重大意义」。结构图用 Mermaid，禁止手画 ASCII/Unicode 框线图；英文直接引语最多 25 词，超出部分改为转述。

### 适用领域边界

默认规则针对科技/产业研究。医疗诊断与治疗、法律意见与诉讼策略、个人投资建议等高风险主题需要另行采用相应专业标准、最新法规/指南和合格专家复核；本项目的“QC 通过”不构成医疗、法律或投资专业意见。

### 环境要求

- **Python ≥ 3.13**
- **[uv](https://docs.astral.sh/uv/)**（依赖管理）
- **[Claude Code](https://docs.claude.com/en/docs/claude-code/overview)**（CLI 已挂载 WebSearch / WebFetch 等 Web 工具）
- **Codex/ChatGPT Work**（可选，通过 `.codex/skills/deep-research-work` 入口使用）
- **Playwright Chromium**（截图用，首次自动安装）
- **[Diagram Design](https://github.com/cathrynlavery/diagram-design)**（可选但推荐；用于编辑级结构图）

### 安装

```bash
# 1) 克隆并安装依赖
git clone https://github.com/brightbear2026/research-agent.git
cd research-agent
uv sync
uv run playwright install chromium   # 首次需要，约下载 ~150MB
uv run python tools/check_env.py      # 自动读取当前包所需的 Chromium build

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

阶段四中断后可查看下一章；已完成章节不会重复执行：

```bash
uv run python tools/workflow_policy.py next-chapter --root projects/my-topic
```

所有产出均落在独立的 `projects/<topic-slug>/`，不会覆盖其他课题。

ChatGPT Work 使用 `chatgpt-work/agent-instructions.md` 作为工作区代理指令。它不会自动读取 `.claude/`，因此两个入口都以 `config/workflow_modes.yaml` 为模式事实源。

### 自治模式

| 模式 | 流程确认 | 停止位置 |
|---|---|---|
| 常规 | 阶段一、二、三各确认一次 | 六阶段交付 |
| 计划 | 大纲后只确认一次是否修改 | 阶段三，等待另行执行 |
| 执行 | 仓库流程不设置确认点 | 交付物齐全且严格 QC 通过 |

公开第三方来源在计划/执行模式下默认访问，但不绕过权限、登录、验证码、付费墙或网站访问控制。

### 深度旋钮（depth）

| 取值 | 章节数 | 每个结论来源 | 截图 |
|---|---|---|---|
| `快速` | 3–5 个论证章节，约 1–2 万字 | 重要结论 ≥1；数值声明仍须 ≥2 个独立来源 | 按需 |
| `标准`（默认） | 5–8 个论证章节，约 2–4 万字 | 重要结论 ≥2 个独立来源，且至少含 A/B 级 | 关键页强制 |
| `深度` | 6–10 个论证章节，原则上 ≤6 万字 | 标准要求 + 每章多轮交叉与反向验证 | 全量 |

严格 QC 的最低正文完整度为快速 4,000、标准 10,000、深度 18,000 个去空白字符；这是防止占位稿通过的下限，不替代上表的目标篇幅和内容质量要求。

### 六阶段流程

流程由 `config/workflow_modes.yaml` 和 `tools/workflow_policy.py` 控制。`regular` 在前三阶段分别确认，`plan` 仅在大纲后确认并停止，`execution` 不设置仓库内确认点；所有模式都受外部访问控制和有限重试预算约束。

1. **启动**：课题定义/边界、≥15 个研究问题、中英文关键词矩阵 → 检查点
2. **广泛调研**：论文/人物/头部企业/政策标准/数据/券商与投行研报/案例 7 张清单 → 检查点
3. **论证地图与大纲**：先确定总论点、分论点和依赖关系，再生成动态大纲 → 检查点
4. **分章深研**：登记逐章状态，按研究卡派发 `researcher`；读者正文与 `.meta.json` 分离，中断后从首个未完成章节恢复
5. **组装与总编辑**：schema v2 与证据关系校验 → 生成声明账本 → 标签去重 → `_assembled_report.md` → 总编辑压缩、去重、重组 → 事实漂移审计
6. **交付**：截图 → 渲染 HTML → 证据矩阵 → `qc.py --strict`（核心检查 `exit 0` 即可交付；死链/时效/数值来源等 advisory 项写 `data/qc_debt.json`，不阻断）→ `workflow_policy.py record-debt` → README

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
examples/minimal/                   # 可公开审查的最小交付样例
```

### 工具一览（统一前缀 `uv run python tools/xxx.py`）

```bash
# 建交付目录树 + 空索引
uv run python tools/scaffold.py projects/my-topic

# 检查 Python、Playwright 包与当前 Chromium build
uv run python tools/check_env.py

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

# Markdown → 单文件 HTML（Diagram Design 使用本地 PNG；降级 Mermaid 依赖 CDN）
uv run python tools/render_html.py projects/my-topic/report/research_report.md --root projects/my-topic

# 生成证据/争议矩阵 + 资料缺口
uv run python tools/evidence.py --root projects/my-topic

# 终检（两段式）：核心检查 exit 0 即可交付；死链/时效/数值来源等 advisory 项写 data/qc_debt.json，不阻断
uv run python tools/qc.py --root projects/my-topic --strict \
  --citation-baseline projects/my-topic/report/_assembled_report.md \
  --claim-ledger projects/my-topic/data/claim_ledger.json

# 把 qc_debt.json 摘要记入状态机（completeness_debt），供交付交接
uv run python tools/workflow_policy.py record-debt --root projects/my-topic

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
| **B 二级·权威研究** | 智库、行业协会、完整具名券商/投行研报、分析师、高校、国际机构报告 | WebSearch + WebFetch |
| **C 三级·专业媒体** | 主流财经/科技/行业媒体深度报道 | WebSearch |
| **D 四级·一般内容** | 自媒体、聚合站、论坛、匿名社媒、营销软文 | **仅作线索**，不作关键结论唯一依据 |

### 单一事实源（双格式一致性）

- `report/_assembled_report.md` 是确定性组装稿；`report/research_report.md` 是经受限总编辑处理后的规范终稿（canonical）。
- 引用 `[n]`、图片、表格从 `data/{citations,figures,tables}.csv` 派生。
- HTML 由 `render_html.py` 从 Markdown + 旁路索引生成，**禁止两版分别手写**。
- `qc.py --strict` 是两段式门禁：核心检查（引用闭环、事实标签同段引用、独立来源数量、图片、内容禁忌、英文直接引语长度、分档最低完整度与可读性、总编辑是否新增数字/日期/实体、升级确定性或因果关系、删除限制条件）须 `exit 0` 才可交付；死链、链接警告、快变领域来源时效、段落级数值来源等 advisory 项写入 `data/qc_debt.json`，不阻断。死链永不阻断——伪造 URL 无 Wayback 归档会在清单显眼标红。最低完整度用于拦截占位稿，不是鼓励重复或凑字数。

### 交付目录契约（由 `scaffold.py` 生成）

```
projects/my-topic/
├── README.md
├── report/{_assembled_report.md, research_report.md, research_report.html}
├── images/FIG-###.png
├── diagrams/FIG-###.html
├── data/{citations, figures, tables, source_data, company_comparison,
│        paper_list, broker_report_list, source_index, screenshot_manifest}.csv,
│        {chapter_meta, claim_ledger}.json
├── evidence/{evidence_matrix, controversy_matrix}.csv, research_gaps.md
└── sources/{bibliography, source_index}.md
```

### 研究限制

- 截图只能写入项目 `images/`；PDF 下载限制字节数、页数、像素和总时间。429/部分 5xx 仅有限退避重试，登录、验证码、付费墙和 WAF 分别记录，不尝试绕过。
- 外部页面无法抓取时，截图落占位、记录失败原因和替代来源，正文标「暂未找到可靠公开来源」，不臆造。
- 一手原文优先；二手来源仅作线索，关键结论不依赖 C/D 级来源。
- 券商研报中的评级、目标价与预测属于机构观点；同一报告的转载不重复计数，底层事实尽量回溯原始来源，访问受限内容不绕过权限或传播全文。
- 数据截止与访问日期以报告 frontmatter 与 `citations.csv` 为准。
- Playwright 固定为与驱动二进制耦合的版本；`tools/check_env.py` 会从当前安装包的 `browsers.json` 自动读取所需 Chromium build，不在文档中硬编码映射。不匹配时重跑 `uv run playwright install chromium`。

### 样例、测试与许可证

- [最小公开交付样例](examples/minimal/README.md)展示报告、引用、证据矩阵和资料缺口。
- GitHub Actions 对锁定依赖、环境映射和完整单元测试做持续集成检查。
- 项目采用 [MIT License](LICENSE)。

---

## English

A reusable, evidence-driven research agent for **Claude Code and Codex/ChatGPT Work**. Both entry points share one executable six-phase state machine, schema v2, deterministic aggregation, claim-ledger editing audit, and strict QC. It delivers **Markdown + HTML** reports, evidence matrices, data tables, and disclosed research gaps.

- **Dual entry points**: Claude Code commands and a Codex/ChatGPT Work skill share the same workflow implementation.
- **Domain**: Tech/Industry (Web-first + corporate sites / filings / whitepapers / standards / policy / broker research).
- **Screenshots**: Playwright real capture (failures get an explicit placeholder, never faked).
- **Explanatory diagrams**: optional Diagram Design integration keeps editable HTML sources, exports audited PNGs, and falls back to Mermaid when unavailable.

### Highlights

- **Two entry points, one implementation**: Claude Code and Codex/ChatGPT Work use the same state machine, schema, aggregation, and QC tools.
- **Three workflow modes**: regular checkpoints, plan-only delivery, or continuous execution.
- **Executable six-phase policy**: phase, confirmation count, stop conditions, failures, and retry budgets are persisted instead of living only in prompts.
- **Per-chapter resume + subagent fuse**: phase-four progress survives interruptions and skips completed chapters with valid paired artifacts. A `researcher` returns after 3 consecutive rounds with no new verifiable source (no self-looping); chapters that hit `max_chapter_attempts` (default 3) are refused re-dispatch.
- **Evidence semantics with schema v2**: stable claim, evidence, and source IDs; numeric evidence retains unit, statistical time, and region or scope.
- **No circular evidence**: conclusion text cannot serve as its own support.
- **Claim-ledger editing audit**: blocks new numbers, dates, entities, causal claims, certainty escalation, and loss of limitations.
- **Bounded, compliant capture**: real browser/PDF capture with path, size, page, pixel, retry, and deadline limits; no access-control bypass.
- **Reviewable deliverables**: Markdown, HTML, evidence and controversy matrices, data tables, source indexes, screenshots, and research gaps.
- **Broker research as a first-class input**: the survey actively covers sell-side reports; chapter metadata preserves analysts, forecast horizons, assumptions, ratings/targets, disclosures, and access limits, then aggregates used reports into `data/broker_report_list.csv`. Forecasts remain institutional views and underlying facts are traced to primary sources.
- **Two-phase delivery gate**: core checks (`exit 0`) make the report deliverable; advisory items (dead links, link warnings, source freshness, paragraph-level numeric sourcing) are written to a structured `data/qc_debt.json` for async cleanup. Dead links never block delivery — a fabricated URL has no Wayback archive and surfaces red in the debt manifest. Core gates still include local citations for fact paragraphs, independent-source checks, banned-phrase and box-diagram checks, a 25-word English quotation limit, and minimum completeness floors that block stub reports.

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
- A paragraph tagged `【事实】` must contain a local `[n]` citation. Promotional certainty phrases and hand-drawn ASCII/Unicode box diagrams are blocked; English direct quotations are limited to 25 words.

### Domain Boundary

The default rubric is designed for technology and industry research. Medical diagnosis or treatment, legal advice or litigation strategy, and personal investment advice require domain-specific current standards and qualified expert review. Passing this repository's QC is not professional medical, legal, or investment advice.

### Requirements

- **Python ≥ 3.13**
- **[uv](https://docs.astral.sh/uv/)** (dependency management)
- **[Claude Code](https://docs.claude.com/en/docs/claude-code/overview)** (CLI with WebSearch / WebFetch and other Web tools mounted)
- **Codex/ChatGPT Work** (optional, via `.codex/skills/deep-research-work`)
- **Playwright Chromium** (for screenshots; installed on first run)
- **[Diagram Design](https://github.com/cathrynlavery/diagram-design)** (optional, recommended for editorial diagrams)

### Install

```bash
# 1) Clone and install
git clone https://github.com/brightbear2026/research-agent.git
cd research-agent
uv sync
uv run playwright install chromium   # first run only, ~150MB download
uv run python tools/check_env.py      # resolves the required browser build dynamically

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
uv run python tools/workflow_policy.py next-chapter --root projects/my-topic
```

Each run writes to its own `projects/<topic-slug>/` directory.

### Depth Knob

| Value | Chapters | Sources per conclusion | Screenshots |
|---|---|---|---|
| `fast` (`快速`) | 3–5 argument chapters, ~10–20k Chinese chars | ≥1 for key conclusions; numeric claims still need ≥2 independent sources | as needed |
| `standard` (`标准`, default) | 5–8 argument chapters, ~20–40k Chinese chars | ≥2 independent sources for key conclusions, including at least one A/B source | key pages forced |
| `deep` (`深度`) | 6–10 argument chapters, normally ≤60k Chinese chars | standard requirements plus multi-round cross-checking and counter-evidence review | full |

Strict QC uses minimum non-whitespace completeness floors of 4,000 / 10,000 / 18,000 characters for fast / standard / deep. These floors reject stubs; they do not replace the target ranges or evidence-quality requirements above.

### Six-Phase Pipeline

1. **Kickoff**: scope/boundaries, ≥15 research questions, bilingual keyword matrix → checkpoint
2. **Broad survey**: 7 lists (papers / people / leading companies / policy & standards / data / broker research / cases) → checkpoint
3. **Argument map + outline**: define thesis, claims, dependencies and evidence before the dynamic outline → checkpoint
4. **Per-chapter research**: persist chapter status, dispatch `researcher` workers, keep Markdown separate from `.meta.json`, and resume at the first incomplete chapter
5. **Assemble + edit**: dedupe source tags → `_assembled_report.md` → constrained editor compresses and restructures the final narrative
6. **Deliver**: screenshots → render HTML → evidence matrix → strict QC (core checks `exit 0` = deliverable; dead links / freshness / paragraph-level numeric sourcing and other advisory items are written to `data/qc_debt.json`, never blocking) → `workflow_policy.py record-debt` → README

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
examples/minimal/                   # small public deliverable example
```

### Tools (common prefix `uv run python tools/xxx.py`)

```bash
# Scaffold the delivery tree + empty indexes
uv run python tools/scaffold.py projects/my-topic

# Check Python, Playwright package, and the required Chromium build
uv run python tools/check_env.py

# Deterministic assembly (also writes chapter_meta and claim_ledger)
uv run python tools/merge.py projects/my-topic --require-meta --title "Report title"

# Validate schema/evidence relations, then back up and aggregate sidecar CSVs
uv run python tools/aggregate_meta.py --root projects/my-topic --dry-run
uv run python tools/aggregate_meta.py --root projects/my-topic --force

# Playwright real screenshots (reads manifest, writes figures.csv)
uv run python tools/screenshot.py projects/my-topic/data/screenshot_manifest.csv \
  --root projects/my-topic --deadline-seconds 600

# Validate Diagram Design HTML; omit --validate-only during delivery to export PNGs
uv run python tools/diagram_assets.py projects/my-topic/data/diagram_manifest.csv \
  --root projects/my-topic --validate-only

# Markdown → single-file HTML (Diagram Design uses local PNGs; Mermaid fallback uses CDN)
uv run python tools/render_html.py projects/my-topic/report/research_report.md --root projects/my-topic

# Build evidence/controversy matrices + research gaps
uv run python tools/evidence.py --root projects/my-topic

# Final gate (two-phase): citations + evidence independence + content rules + figures + editing audit.
# Core checks exit 0 = deliverable; advisory items (dead links / freshness / numeric sourcing) -> data/qc_debt.json (never blocking).
uv run python tools/qc.py --root projects/my-topic --strict \
  --citation-baseline projects/my-topic/report/_assembled_report.md \
  --claim-ledger projects/my-topic/data/claim_ledger.json

# Record advisory debt into the state machine after delivery
uv run python tools/workflow_policy.py record-debt --root projects/my-topic

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
| **B · Authoritative** | Think tanks, industry associations, complete attributable broker/investment-bank research, analysts, universities, international bodies | WebSearch + WebFetch |
| **C · Professional media** | Major business/tech/industry deep reporting | WebSearch |
| **D · General** | Self-media, aggregators, forums, anonymous social, marketing | **Lead only** — never the sole basis for a key conclusion |

### Single Source of Truth (dual-format consistency)

- `report/_assembled_report.md` is the deterministic assembly; `report/research_report.md` is the constrained editor's canonical final narrative.
- Citations `[n]`, figures, and tables derive from `data/{citations,figures,tables}.csv`.
- HTML is generated by `render_html.py` from Markdown + sidecar indexes — **never hand-author both versions**.
- `qc.py --strict` is a two-phase gate: core checks (citation closure, local citations for fact paragraphs, independent support, figures, prohibited content, quotation length, minimum completeness, readability, factual drift after editing) must `exit 0` to deliver; advisory items (dead links, link warnings, source freshness for fast-moving domains, paragraph-level numeric sourcing) are written to `data/qc_debt.json` and never block. Dead links never block — fabricated URLs have no Wayback archive and surface red in the debt manifest. Completeness floors block stubs; they are not targets for repetitive padding.

### Delivery Tree (created by `scaffold.py`)

```
projects/my-topic/
├── README.md
├── report/{_assembled_report.md, research_report.md, research_report.html}
├── images/FIG-###.png
├── diagrams/FIG-###.html
├── data/{citations, figures, tables, source_data, company_comparison,
│        paper_list, broker_report_list, source_index, screenshot_manifest}.csv,
│        {chapter_meta, claim_ledger}.json
├── evidence/{evidence_matrix, controversy_matrix}.csv, research_gaps.md
└── sources/{bibliography, source_index}.md
```

### Known Limitations

- On paywalled / JS-blocked pages, the screenshot falls back to a placeholder and the body reads "no reliable public source found" — nothing is fabricated.
- Primary sources are preferred; secondary sources are leads only and never the sole basis for a key conclusion.
- Broker ratings, price targets, and forecasts are institutional views; syndicated copies count once, underlying facts should be traced to primary sources, and access controls or full-report copyrights are not bypassed.
- Data cutoff and access dates follow the report frontmatter and `citations.csv`.
- Playwright is pinned because its driver and browser binary are coupled. `tools/check_env.py` reads the required Chromium build from the installed package instead of hardcoding the mapping in this README. Re-run `uv run playwright install chromium` on mismatch.

### Example, CI, and License

- See the [minimal public deliverable](examples/minimal/README.md).
- GitHub Actions verifies locked dependencies, the package/browser mapping, and the full unit-test suite.
- Licensed under the [MIT License](LICENSE).

---

<div align="center">

<sub>Claude Code: <code>/deep-research</code> · Codex/ChatGPT Work: <code>$deep-research-work</code></sub>

</div>
