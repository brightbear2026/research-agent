# 研究代理项目约定（research-agent）

本仓库是一个 **Claude Code 原生深度研究代理**：以 `/deep-research <课题>` 触发，按 6 阶段执行「调研→证据库→大纲→分章深研→双格式交付」，最终在 `projects/<课题slug>/`（如 `projects/ai-agent-security`）落地 Markdown + HTML 报告与证据矩阵——**每个课题一个独立 slug 文件夹，互不覆盖**。领域定位：**科技/产业**。

## 不可违反的红线
- **不编造**：论文、作者、人物发言、数据、公司方案、市场规模、URL、截图、政策、产品能力、访谈、页码、日期——一律不得虚构。
- 无法确认的信息必须写明「**暂未找到可靠公开来源**」，不得用标题或二手转述臆造内容。
- 截图必须来自 **Playwright 真实捕获**（`tools/screenshot.py`），失败则落占位符 + 索引，**禁止用 AI 图/拼接/base64 冒充原始截图**。
- 区分 **事实 / 人物观点 / 机构观点 / 行业共识 / 争议 / 研究判断 / 推测**，不得把观点写成事实、把推测包装成定论。

## 来源可信度分层（详见 `references/source_rubric.md`）
| 等级 | 来源类型 | 工具映射（科技/产业） |
|---|---|---|
| A 一级·原始 | 企业官网、年报财报、白皮书、产品文档、标准原文、政府政策、专利、原始演讲/访谈 | WebFetch / web_reader 抓官方 URL |
| B 二级·权威研究 | 智库、行业协会、分析师、高校、国际机构报告 | WebSearch + WebFetch |
| C 三级·专业媒体 | 主流财经/科技/行业媒体深度报道 | WebSearch |
| D 四级·一般内容 | 自媒体、聚合站、论坛、匿名社媒、营销软文 | **仅作线索**，不得作关键结论唯一依据 |

关键结论不得只依赖 C/D 级来源。

## 交叉验证
一级数值类结论（市场规模/收入/用户/份额/融资/排名）须 **≥2 独立来源**。来源冲突时：列出各数据 + 口径 + 时间 + 机构，进 `evidence/controversy_matrix.csv`，给**条件性结论**，不得简单二选一。

## 行内标签（Markdown 与 HTML 共用，渲染器识别）
- `【事实】` 客观事实（须有来源）
- `【观点·姓名·机构·YYYY-MM-DD】` 人物观点（须有原始出处）
- `【机构观点·机构·日期】` 机构观点
- `【争议】` 存在分歧
- `【研究判断】` 基于证据的综合判断
- `【推测】` 尚未充分证据支持的假设

## 引用与单一事实源
- 正文用 `[n]` 编号引用，每个 `[n]` 必须在 `data/citations.csv` 中登记（作者/标题/出版物/日期/DOI/原始链接/访问日期/页码）。
- **Markdown 为规范叙事（canonical）**，HTML 由 `tools/render_html.py` 从 Markdown + 旁路索引（`data/citations.csv`、`figures.csv`、`tables.csv`）派生，禁止两版分别手写。
- 自制图表标题统一标「数据来源：根据公开资料整理/计算」，不得冒充机构原图。

## 交付目录契约（由 `tools/scaffold.py` 生成）
```
projects/<课题slug>/
├── README.md
├── report/{research_report.md, research_report.html}
├── images/FIG-###.png
├── data/{citations.csv, figures.csv, tables.csv, source_data.csv, company_comparison.csv, paper_list.csv, source_index.csv, screenshot_manifest.csv}
├── evidence/{evidence_matrix.csv, controversy_matrix.csv, research_gaps.md}
└── sources/{bibliography.md, source_index.md}
```

## 深度旋钮
Skill 接收 `depth=快速|标准|深度`（默认「标准」）：
- 快速：核心 5–7 章，每结论 ≥1 一级来源，截图按需。
- 标准：完整 12–13 章，每结论 ≥2 一级来源，关键页强制截图。
- 深度：标准 + 每章多轮反向验证 + 全量截图。

## 运行工具（统一前缀 `uv run python tools/xxx.py`）
- `scaffold.py <项目名>`：建交付目录树 + 空索引。
- `screenshot.py <manifest.csv>`：真实截图（`full`/`viewport`/`element` 区块/`pdf` 指定页）+ 写 `figures.csv`。
- `render_html.py <md> <out.html>`：渲染自包含 HTML。
- `evidence.py`：生成证据/争议矩阵 + 资料缺口。
- `qc.py <项目名>`：链接/引用/截图/表格/格式质检。
- `charts.py`：生成图表到 `images/`。

## 默认与禁忌
- 报告语言：**中文**叙事；英文来源保留**简短原文**引用（不超过合理篇幅，避免版权风险）。
- 所有「目前/当前/最新」等须标**明确日期**；标注**数据截止日期**与**访问日期**。
- 禁用无证据套话：「众所周知 / 毫无疑问 / 必将 / 彻底改变 / 颠覆一切 / 市场前景无限 / 具有重大意义」。
