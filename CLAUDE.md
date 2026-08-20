# 研究代理项目约定（research-agent）

本仓库是一个面向 **Claude Code、Codex/ChatGPT Work 与 Hermes/Agent-Skills harness** 的多入口深度研究代理：Claude Code 以 `/deep-research <课题>` 触发，Codex/ChatGPT Work 以 `$deep-research-work` 触发，Hermes/兼容 harness 读取根目录 `SKILL.md`；三者共享同一六阶段状态机、schema v2、聚合与 QC 工具。最终在 `projects/<课题slug>/` 落地 Markdown + HTML 报告与证据矩阵——**每个课题一个独立 slug 文件夹，互不覆盖**。领域定位：**科技/产业**。

本仓库的来源分层和 QC 阈值按科技/产业研究设计，不默认适用于医疗诊断、治疗建议、法律意见、诉讼策略或个人投资建议。若用户把这些高风险主题放入范围，必须明确提示领域边界，并另行采用相应专业标准、最新法规/指南与合格专家复核；不得把本项目的“QC 通过”表述为专业意见。

## 不可违反的红线
- **不编造**：论文、作者、人物发言、数据、公司方案、市场规模、URL、截图、政策、产品能力、访谈、页码、日期——一律不得虚构。
- 无法确认的信息必须写明「**暂未找到可靠公开来源**」，不得用标题或二手转述臆造内容。
- 截图必须来自 **Playwright 真实捕获**（`tools/screenshot.py`），失败则落占位符 + 索引，**禁止用 AI 图/拼接/base64 冒充原始截图**。
- 区分 **事实 / 人物观点 / 机构观点 / 行业共识 / 争议 / 研究判断 / 推测**，不得把观点写成事实、把推测包装成定论。

## 来源可信度分层（详见 `references/source_rubric.md`）
| 等级 | 来源类型 | 工具映射（科技/产业） |
|---|---|---|
| A 一级·原始 | 企业官网、年报财报、白皮书、产品文档、标准原文、政府政策、专利、原始演讲/访谈 | WebFetch / web_reader 抓官方 URL |
| B 二级·权威研究 | 智库、行业协会、具名券商/投行研报、分析师、高校、国际机构报告 | WebSearch + WebFetch |
| C 三级·专业媒体 | 主流财经/科技/行业媒体深度报道 | WebSearch |
| D 四级·一般内容 | 自媒体、聚合站、论坛、匿名社媒、营销软文 | **仅作线索**，不得作关键结论唯一依据 |

关键结论不得只依赖 C/D 级来源。

### 券商研报作为研究输入
- 将券商/投行研报纳入广泛调研和分章深研，重点用于产业链拆解、盈利预测、市场一致预期、估值假设与专家线索。完整、具名、可追溯且披露方法的研报通常为 B 级；转载摘要/截图为 C 级，来源不明的研报聚合为 D 级线索。
- 评级、目标价、盈利预测、市场空间测算等必须标 `【机构观点·券商名称·发布日期】`，不得写成事实。研报转引的财报、政策、标准和数据库，应尽量回溯原始来源并另行登记，不能把二手数据当作 A 级。
- 同一研报的官网版、平台版和转载版只算一个来源；同一券商研究所默认使用同一 `independence_group`。关键事实/数值仍须用原始来源或另一独立机构交叉验证。
- 在 chapter meta 的来源对象中标 `source_type=broker_report`，并尽量记录 `authors`、`report_type`、`covered_entity_or_industry`、`page_or_location`、`forecast_horizon`、`key_assumptions`、`conflict_disclosure` 与访问限制。交付时由聚合器生成 `data/broker_report_list.csv`。
- 不绕过登录、验证码、付费墙或授权控制，不传播未授权全文。完整规则见 `references/source_rubric.md`。

## 交叉验证
一级数值类结论（市场规模/收入/用户/份额/融资/排名）须 **≥2 独立来源**。来源冲突时：列出各数据 + 口径 + 时间 + 机构，进 `evidence/controversy_matrix.csv`，给**条件性结论**，不得简单二选一。正文【事实】段中的数值声明同样适用此规则——单一 C/D 级来源支撑的数值会被 `qc.py` 标记为 advisory（写入 `data/qc_debt.json`），建议补独立第二来源或改标【推测】。

## 行内标签（Markdown 与 HTML 共用，渲染器识别）
- `【事实】` 客观事实（须有来源）
- `【观点·姓名·机构·YYYY-MM-DD】` 人物观点（须有原始出处）
- `【机构观点·机构·日期】` 机构观点
- `【争议】` 存在分歧
- `【研究判断】` 基于证据的综合判断
- `【推测】` 尚未充分证据支持的假设

## 引用与单一事实源
- 正文用 `[n]` 编号引用，每个 `[n]` 必须在 `data/citations.csv` 中登记（作者/标题/出版物/日期/DOI/原始链接/访问日期/页码）。
- **Markdown 为规范叙事（canonical）**：`report/_assembled_report.md` 是确定性组装稿，经 `report-editor` 只做压缩、去重和重组后生成 `report/research_report.md` 终稿；HTML 再由 `tools/render_html.py` 从终稿 + 旁路索引派生，禁止两版分别手写。
- 自制图表标题统一标「数据来源：根据公开资料整理/计算」，不得冒充机构原图。
- **截图/自制图表内联到所支撑的章节正文**：在相关论断处用 Markdown 图片语法 `![简述](images/FIG-NNN.png)` 单独成段展示；**不得在附录或报告末尾集中罗列图片**。`data/figures.csv` 仅作旁路索引（供 caption、`qc.py` 校验），不是展示位置。
- **结构化关系图优先 Diagram Design，Mermaid 为降级路径**：仅当视觉明显优于段落/表格时生成结构图。宿主可发现 `diagram-design` skill 时，输出可审查的 `diagrams/FIG-NNN.html`，再由 `tools/diagram_assets.py` 校验并导出 `images/FIG-NNN.png`；不可发现时用 Mermaid。生成图只是“根据公开资料整理”的解释性资产，不是证据或机构原始截图，必须在 chapter meta 的 `diagrams` 中关联 `source_ids` 与 `supports_claim_ids`。**禁止手画 ASCII 框线图**。

## 交付目录契约（由 `tools/scaffold.py` 生成）
```
projects/<课题slug>/
├── README.md
├── report/{_assembled_report.md, research_report.md, research_report.html}
├── images/FIG-###.png
├── diagrams/FIG-###.html
├── data/{citations.csv, figures.csv, tables.csv, source_data.csv, company_comparison.csv, paper_list.csv, broker_report_list.csv, source_index.csv, screenshot_manifest.csv, diagram_manifest.csv, glossary.md, chapter_meta.json}
├── evidence/{evidence_matrix.csv, controversy_matrix.csv, research_gaps.md}
└── sources/{bibliography.md, source_index.md}
```

## 深度旋钮
Skill 接收 `depth=快速|标准|深度`（默认「标准」）：
- 快速：3–5 个核心论证章节，正文约 1–2 万字；重要结论 ≥1 个 A/B 级来源，数值声明仍须 ≥2 个独立来源；截图按需。
- 标准：5–8 个论证章节，正文约 2–4 万字；重要结论 ≥2 个独立来源且至少含 A/B 级；关键页强制截图。
- 深度：6–10 个论证章节，正文原则上不超过 6 万字；标准要求 + 每章多轮反向验证 + 全量截图。
- 严格 QC 的最低正文完整度为快速 4,000、标准 10,000、深度 18,000 个去空白字符，仅用于拦截占位稿，不得以重复文字凑数。

## 运行工具（统一前缀 `uv run python tools/xxx.py`）
- `scaffold.py <项目名>`：建交付目录树 + 空索引。
- `workflow_policy.py`：统一三模式、六阶段、逐章进度、有限重试与断点续跑。
- `aggregate_meta.py`：校验 schema v2、证据引用关系与数据限定字段，备份后原子聚合。
- `claim_ledger.py`：冻结编辑前事实锚点并审计数字、日期、实体、因果、确定性和限制条件漂移。
- `screenshot.py <manifest.csv>`：真实截图（`full`/`viewport`/`element` 区块/`pdf` 指定页）+ 写 `figures.csv`。
- `diagram_assets.py <diagram_manifest.csv>`：校验 Diagram Design 静态 HTML，导出 PNG，并合并写 `figures.csv`。
- `render_html.py <md> <out.html>`：渲染自包含 HTML。
- `evidence.py`：生成证据/争议矩阵 + 资料缺口。
- `qc.py --root <项目名> [--strict]`：链接、引用、截图、格式与可读性质检；最终交付必须使用 `--strict`。核心检查 `exit 0` 即可交付；死链/链接警告/来源时效/段落级数值来源等 advisory 项不阻断，写入 `data/qc_debt.json`（再用 `workflow_policy.py record-debt` 记入状态机）异步收尾。死链永不阻断——伪造 URL 无 Wayback 归档会在 debt 清单显眼标红。
- `check_env.py`：从已安装 Playwright 包读取所需 Chromium build，并检查浏览器是否存在。
- `charts.py`：生成图表到 `images/`。

## 默认与禁忌
- 报告语言：**中文**叙事；英文来源保留**简短原文**引用（不超过合理篇幅，避免版权风险）。
- 所有「目前/当前/最新」等须标**明确日期**；标注**数据截止日期**与**访问日期**。
- 禁用无证据套话：「众所周知 / 毫无疑问 / 必将 / 彻底改变 / 颠覆一切 / 市场前景无限 / 具有重大意义」。
- **新课题独立调研，不前置参考 `projects/` 下其他课题的历史报告**：每次 `/deep-research` 从课题本身的研究问题/关键词出发；既有课题报告仅作交付归档，不作为新课题的背景输入（除非用户明确要求引用）。
