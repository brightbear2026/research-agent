# 研究卡 · 第 N 章 《章节名》

> 每章分章深研前先填写本卡，再派 researcher 子 agent 执行。

- **本章目标**：
- **本章核心问题**（3–6 个）：
  1.
- **已有资料**：
- **缺失资料**：
- **需补充搜索的关键词**（中/英/学术/企业/政策/数据/反方/争议/年份/地域）：
- **需验证的数据**：
- **需查找的人物观点**：
- **需查找的企业方案**：
- **需制作的图表**：
- **需截取的原始材料**（登记到 `data/screenshot_manifest.csv`，由调度方 Phase 6 统一执行 `screenshot.py`）：
  - **对象类型清单**（按需勾选；优先一级来源；每张须支持某条具体结论）：
    - [ ] 标准/框架原文页（OWASP / MITRE ATLAS / NIST AI RMF / ISO 42001 / MAESTRO / TC260…）
    - [ ] 标准全文 PDF 指定页（`capture=pdf`，`selector` 填页码如 `1` / `1-3` / `2,4`）
    - [ ] 核心论文 arXiv 摘要页，或 PDF 中实验结果图所在页
    - [ ] 基准/排行榜实时页（AgentDojo / LMSYS Arena / HarmBench —— 须标访问日期）
    - [ ] CVE/漏洞披露页（NVD 详情 / GitHub Security Advisory / 厂商 PSIRT）
    - [ ] 厂商/产品官方页（含 GitHub 仓库指标页：star/license/活跃度）
    - [ ] 机构原创图表/象限（Gartner 魔力象限 / Forrester Wave / 信通院评估表）
    - [ ] 法规/政策原文页，或备案查询结果页
    - [ ] 财报/IR 数字页（市场/融资数值的一级来源）
  - **截取模式**：`full`=整页 ｜ `viewport`=视口 ｜ `element`=按 CSS selector 截区块（更聚焦、省体积，优先用于大页里的关键表/图）｜ `pdf`=PDF 指定页（多页自动纵向拼接）。
  - **不截**：搜索结果页、转载/二手、付费墙内打不开的（→ 落占位）、纯数字（进 `source_data.csv`）、自制图（`charts.py`）。
  - 每条登记：`fig_id / url / capture / selector / supports_conclusion / is_primary_source`。
- **预期结论**：

---

## 研究产出（执行后回填）

### 本章事实
<!-- 【事实】标注，附 [n] 引用 -->

### 本章数据
<!-- 登记到 data/source_data.csv -->

### 本章人物观点
<!-- 【观点·姓名·机构·日期】+ 原始出处 [n] -->

### 本章公司方案

### 本章案例
<!-- 背景/原问题/方案/实施/资源/结果/验证/局限/可复制/不可复制 -->

### 本章争议
<!-- 登记 controversy_matrix.csv -->

### 本章分析

### 本章结论
<!-- 含：结论/主要证据/反对证据/适用条件/时间范围/置信度(高|中高|中|中低|低)/决策影响 -->

### 引用来源
<!-- [n] → data/citations.csv -->

### 待补充内容
