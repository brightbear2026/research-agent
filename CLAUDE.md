# 研究代理项目约定（research-agent）

本仓库是一个面向 **Claude Code、Codex/ChatGPT Work 与 Hermes/Agent-Skills harness** 的多入口深度研究代理：Claude Code 以 `/deep-research <课题>` 触发，Codex/ChatGPT Work 以 `$deep-research-work` 触发，Hermes/兼容 harness 读取根目录 `SKILL.md`；三者共享同一六阶段状态机、schema v2、聚合与 QC 工具。最终在 `projects/<课题slug>/` 落地 Markdown + HTML 报告与证据矩阵——**每个课题一个独立 slug 文件夹，互不覆盖**。领域定位：**科技/产业**。

本仓库的来源分层和 QC 阈值按科技/产业研究设计，不默认适用于医疗诊断、治疗建议、法律意见、诉讼策略或个人投资建议。若用户把这些高风险主题放入范围，必须明确提示领域边界，并另行采用相应专业标准、最新法规/指南与合格专家复核；不得把本项目的“QC 通过”表述为专业意见。


启动时按 [交付与跨章综合协议](references/report_delivery.md) 约定读者、决策、输出形态和篇幅。阶段四收齐草稿后，按协议先做跨章综合，再组装和冻结声明。

## 阶段一的需求澄清

三个宿主都在生成研究问题和关键词之前执行本节。先提取用户原话和本次提供的材料，识别谁会用成果、用来做什么。学习类课题可以用“读者最终要能解释或完成什么”描述用途。如果连研究对象都无法辨认，先取得题目再创建课题目录。

**判断是否值得问。** 试着给模糊之处写出两种合理解释。如果选择会改变研究对象、比较方案、所需证据或交付用途，就值得澄清。材料里已有答案的直接采用。能靠检索回答的事实列入研究任务。用户已经写清任务时，简短复述并开始拆题。

| 模式 | 如何处理影响方向的歧义 |
|---|---|
| `regular` | 在启动阶段内先问最上游的取舍。每轮只问当前可以决定的事，给出建议选项和理由，等用户回答再问依赖它的问题。用户委托判断或要求按现有信息推进时，把所选口径记作工作假设。剩余问题可以通过研究回答时结束访谈，按已有启动检查点确认。 |
| `plan` | 先按明确标注的假设完成初调和大纲，把待定选择、建议及其对大纲的影响带到唯一的大纲确认点。用户纠正时，同步修订需求和计划，再结束计划模式。 |
| `execution` | 已有题目就采用现有信息和可解释的默认口径直接推进。把影响结论适用范围的假设写入启动记录，并在交付时披露。 |

**记录与使用。** 在 `sources/stage1_kickoff.md` 开头写“研究需求”，列出目标读者与用途、必答问题、范围与排除项、验收依据。验收依据要说明什么材料或解释足以回答问题。分别标明用户已给定的条件、Agent 采用的假设和待研究的事实。后续的 ≥15 个研究问题由 Agent 自行展开。编写大纲时逐项核对必答问题，每章写明承接哪一项，研究卡沿用对应的验收依据。到交付时，给出每项问题的回答位置或证据缺口。恢复已有课题时沿用已记录的决定，旧课题可从已有启动记录和大纲继续。

例如，用户说“研究国内 MCP Gateway 市场”，若用途不明，可以先问“谁会拿这份研究做什么决定？如果是产品立项，我建议比较独立采购与现有平台扩展，两条路线需要不同的采购和部署证据。”若用户回答“已经确定内置，只想评估首期功能”，就围绕首期范围拆题。客户究竟买了什么，由 Agent 查采购文件或案例。研究结论仍由证据决定。提问方法参考 [grill-me 的上游实现](https://github.com/mattpocock/skills/tree/main/skills/productivity/grilling)。

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
研究过程的具体记录与补研规则见 `references/research_quality.md`；新研究在分章前读取并执行。每章登记核心问题、检索结果及证据原文位置，终检生成 `data/quality_scorecard.json`。该文件衡量记录覆盖，不能当作事实正确率。

一级数值类结论（市场规模/收入/用户/份额/融资/排名）须 **≥2 独立来源**。来源冲突时：列出各数据 + 口径 + 时间 + 机构，进 `evidence/controversy_matrix.csv`，给**条件性结论**，不得简单二选一。正文【事实】段中的数值声明同样适用此规则——单一 C/D 级来源支撑的数值会被 `qc.py` 标记为 advisory（写入 `data/qc_debt.json`），建议补独立第二来源或改标【推测】。

**文献存在性验证**：交付前对 `data/paper_list.csv` 运行 `tools/paper_enrich.py`（有 DOI/arXiv ID 走确定性端点，否则按标题查 Crossref，可选 Semantic Scholar）。`not_found ≠ 编造实锤`——未被学术索引收录的中文文献、白皮书、厂商报告都会落入 not_found；验证结果只作 advisory 进 `qc_debt.json`，由人工核对收尾，永不阻断交付。**检索任务类型化**：阶段三把各章检索编译为 `explore / refute / pin` 三类任务登记进章节元数据 `search_tasks`，反方检索从自觉变成有覆盖账本的任务；核心结论可自标 `priority: P0`，P0 声明必须有 A/B 级来源背书（终检强制）。引用覆盖率是过程指标，**不设硬性引用配额**，不得为凑数引用低质来源。

独立性只统计 `supporting_evidence_ids` 实际关联的来源；声明的 `source_ids` 清单或反方证据不补足支持数。同一规范化 URL 即使登记了不同机构/分组也只计一次；已确认转载的来源填写 `origin_url`，与原文及相同生产者合并。无法识别生产者、域名或原文的来源不贡献独立计数。

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
- **分析与证据呈现**：比较章先按读者的决策维度对齐来源，写出差异、反证和适用条件。正文就近展示分析图表和需要辨认细节的证据局部；仅供复核的已采集原图用普通链接（相对报告目录，如 `[查看完整截图](../images/FIG-005.png)`）。普通资料用来源引用。执行细则见 `templates/research_card.md`。
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
- 快速：3–5 个核心论证章节；重要结论 ≥1 个 A/B 级来源，数值声明仍须 ≥2 个独立来源；截图按需。
- 标准：5–8 个论证章节；重要结论 ≥2 个独立来源且至少含 A/B 级；需读者辨认原文、图表或界面时采集关键区块。
- 深度：6–10 个论证章节；标准要求 + 每章多轮反向验证 + 关键原始材料按需留档。
默认篇幅为提示。简报也须有实质解释、来源及证据；明确约定的字符边界由 QC 校验。

## 运行工具（统一前缀 `uv run python tools/xxx.py`）
- `scaffold.py <项目名>`：建交付目录树 + 空索引。
- `workflow_policy.py`：统一三模式、六阶段、逐章进度、有限重试与断点续跑。
- `aggregate_meta.py`：校验 schema v2、证据引用关系与数据限定字段，备份后原子聚合。
- `claim_ledger.py`：冻结编辑前事实锚点并审计数字、日期、实体、因果、确定性和限制条件漂移。
- `screenshot.py <manifest.csv>`：真实截图（`full`/`viewport`/`element` 区块/`pdf` 指定页）+ 写 `figures.csv`。
- `diagram_assets.py <diagram_manifest.csv>`：校验 Diagram Design 静态 HTML，导出 PNG，并合并写 `figures.csv`。
- `render_html.py <md> <out.html>`：渲染自包含 HTML。
- `evidence.py`：生成证据/争议矩阵 + 资料缺口。
- `qc.py --root <项目名> [--strict]`：链接、引用、截图、格式与可读性质检；最终交付必须使用 `--strict`。核心检查 `exit 0` 即可交付；死链/链接警告/来源时效/段落级数值来源/文献存在性等 advisory 项不阻断，写入 `data/qc_debt.json`（再用 `workflow_policy.py record-debt` 记入状态机）异步收尾。死链永不阻断——失效链接记录在 debt 清单中；有无归档不能判定来源真伪或引用是否有效。
- `paper_enrich.py --root <项目名>`：验证 `paper_list.csv` 文献存在性并回填规范元数据（Crossref/arXiv/S2），产出 `data/paper_list_enriched.csv` 与 `data/paper_verification.json`，供 `qc.py` 生成 advisory。
- `check_env.py`：从已安装 Playwright 包读取所需 Chromium build，并检查浏览器是否存在。
- `charts.py`：生成图表到 `images/`。

## 默认与禁忌
- 报告语言：**中文**叙事；英文来源保留**简短原文**引用（不超过合理篇幅，避免版权风险）。
- **模型分级**（宿主支持子代理选模型时）：阶段二广泛调研等检索密集型子代理可用轻量模型，阶段四分章深研与总编辑保持主力模型——检索候选发现对推理深度要求低，写作与证据研判不掉档。
- 所有「目前/当前/最新」等须标**明确日期**；标注**数据截止日期**与**访问日期**。
- 禁用无证据套话：「众所周知 / 毫无疑问 / 必将 / 彻底改变 / 颠覆一切 / 市场前景无限 / 具有重大意义」。
- **新课题独立调研，不前置参考 `projects/` 下其他课题的历史报告**：每次 `/deep-research` 从课题本身的研究问题/关键词出发；既有课题报告仅作交付归档，不作为新课题的背景输入（除非用户明确要求引用）。
