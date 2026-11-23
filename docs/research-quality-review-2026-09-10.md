# research-agent：产出质量调研与优化记录

调研日期：2026-09-10。基线提交：`b5e714072995a9c393cba08d887c35a6d735d0ee`。

本轮完成了仓库检查、GitHub 相关项目检索、官方实现与研究方法对照、代码修复和回归验证。主要结论是：项目已有多宿主入口、六阶段状态机、证据 ID、受限编辑和严格 QC，当前最值得补强的是证据计数的可信性，以及研究过程能否留下可复核记录。无需为了增加功能而更换整个框架。

## 调研范围与取舍

通过 agent-reach 的 GitHub CLI 搜索相关仓库，再阅读官方 README、关键实现及论文；使用 Exa 和网页搜索补充评估方法。检索热度只用于发现候选，不作为质量排名。下表区分借鉴机制与本轮实施范围，未运行这些项目的完整系统，也没有验证它们自报的排行榜成绩。

| 项目/官方材料 | 查看的机制 | 对本项目的取舍 |
|---|---|---|
| [Stanford STORM](https://github.com/stanford-oval/storm) | 写作前检索、视角驱动提问、先研究再生成大纲 | 在研究卡明确适用视角和问题验收条件；沿用既有动态大纲，不照搬百科式文章结构 |
| [LangChain Open Deep Research](https://github.com/langchain-ai/open_deep_research) / [研究提示词](https://github.com/langchain-ai/open_deep_research/blob/main/src/open_deep_research/prompts.py) | 每轮检索评估信息缺口、逐步收窄查询、设定停止条件；压缩研究材料时保留出处 | 新增可审计检索结果记录，补研按核心问题排序；沿用现有熔断，不硬套其搜索次数 |
| [GPT Researcher](https://github.com/assafelovic/gpt-researcher) | 规划、资料抓取、来源跟踪、汇总成报告 | 保留本项目已有的阶段分离，强化证据到原文的关联，暂不引入新运行时 |
| [dzhng/deep-research](https://github.com/dzhng/deep-research) / [检索实现](https://github.com/dzhng/deep-research/blob/main/src/deep-research.ts) | 迭代维护 learnings、follow-up questions、visited URLs，按深度与广度展开 | 将未回答问题与检索新进展显式记录；单纯保存访问 URL 不足以证明引用支撑 |
| [Jina node-DeepResearch](https://github.com/jina-ai/node-DeepResearch) | 搜索、阅读、推理循环与预算约束；项目定位偏答案检索 | 借鉴缺口驱动和预算意识，长报告仍由当前章节与编辑流程负责 |
| [Alibaba Tongyi DeepResearch](https://github.com/Alibaba-NLP/DeepResearch) | ReAct 与 IterResearch 的 Heavy 推理路径 | 作为更换底层研究模型的候选方向；本轮不引入模型部署、训练或推理基础设施 |
| [DeepResearch Bench](https://github.com/Ayanami0730/deep_research_bench) / [论文](https://arxiv.org/abs/2506.11763) | RACE 评估报告质量，FACT 验证声明与来源支撑并统计有效引用 | 把结构覆盖与事实正确性分开表述；建立可复核诊断，不冒充官方 RACE/FACT 成绩 |
| [DeepResearch Bench II](https://github.com/SawyerCooper/DeepResearchBench2) | 基于专家报告的细粒度要求，分信息召回、分析和表达评价 | 研究前明确问题及验收条件；正式语义评估仍需固定题目和人工审查的要求清单 |
| [ReportBench](https://github.com/ByteDance-BandAI/ReportBench) | URL 规范化去重，回取引用原文并寻找支撑片段 | 修复同文来源重复计数，新增证据级原文短摘录和定位；本轮不将登记的摘录宣称为已核验 |
| [Anthropic：研究系统工程实践](https://www.anthropic.com/engineering/multi-agent-research-system) | 明确研究任务边界、预算、上下文交接与评估 | 改进研究者与总编辑的交接协议，保持现有宿主调度机制 |
| [Anthropic：Agent 评估方法](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | 组合不同评估手段，区分执行轨迹和最终结果 | 用确定性回归验证漏洞，再用人工/语义评审判断报告效果；不混淆两种成绩 |
| [Parsing and Evaluating Source Attribution in LLM Deep Research](https://arxiv.org/html/2605.06635) | 将链接可用性、内容相关性、事实核验拆成不同维度 | 修正项目中有关 Wayback 的过度推断；归档存在不证明论断，归档缺失不证明伪造 |

外部经验支持优化方向，但不构成本项目已经提高事实准确率的实验证据。社交渠道的登录/连接状态不完整，本轮没有把社区舆论作为技术结论依据。

## 发现并修复的问题

### 1. 同一篇材料能被算成两份独立来源

原实现优先使用填写的 `independence_group` 或机构名。两个记录即使指向同一个网页，只要分组名不同，就可能达到“双独立来源”阈值。数值与结论的证据矩阵因此可能高估支撑强度。

新实现把生产者分组、规范化 URL、经确认的 `origin_url` 关联起来，按连接后的来源组计数。跟踪参数、DOI/arXiv 别名继续沿用既有规范化逻辑。相同原文及登记的转载不再因机构名变化获得额外计数；高等级来源数也按独立组计数。

实现：`tools/source_identity.py`、`tools/aggregate_meta.py`、`tools/qc.py`。

边界：未登记的转载关系仍需研究者识别。共用论文托管域的独立研究，需要填写真实生产者/分组；不能单靠托管域精确判断独立性。

### 2. 来源清单能代替支撑证据

原数值检查把声明的 `source_ids` 与支撑证据来源合并计数。把第二来源列入清单，即使它没有支持这句话，甚至只提供反对意见，也可能通过。

新检查只沿 `supporting_evidence_ids → source_ids` 计算支撑。章节及声明中同一 evidence ID 同时位于支持和反对列表时给出复核警告，要求说明不同作用或拆分片段。历史产物抽查显示，有些材料同时支持条件性结论并说明其限制；因此不把双重角色直接判为错误，不自动删除反方证据。

### 3. 最终 QC 没有重验完整的章节关系

最终 QC 现在复用聚合器校验，拒绝空章节数组、错误的 ID 数组和悬空引用等结构问题。不能通过跳过聚合器或后改元数据轻易绕过。诊断遇到无效输入时写 `invalid_metadata`，覆盖之前的成功记录，避免读到陈旧成绩。

### 4. 提示词要求反向验证，但缺少可检查的过程记录

新增兼容 schema v2 的可选字段：

- `research_questions`：从研究卡保留问题、回答状态、证据 ID 和缺口。
- `search_log`：实际查询、用途、结果、来源 ID 及简短结果说明。
- `data_points[].provenance`：每个支撑来源的短摘录、原文位置和访问日期。
- `sources[].origin_url`：经确认的转载原始出处。

终检自动输出 `data/quality_scorecard.json`，包含五项覆盖指标及具体补研建议。无记录不计满分；受阻查询不计作完成反向检查；真实查询未发现新反证可如实记录。旧 v2 缺少新字段时给 advisory，不要求批量重写历史报告。

协议与三个宿主入口、研究者、总编辑、研究卡和 README 已同步。新增功能仅使用标准库，不增加模型或服务依赖。填写方法见 [研究质量协议](../references/research_quality.md)。

### 5. 链接归档与事实真实性混淆

原文档将“伪造 URL 没有归档”写成可以依赖的识别依据。这不足以支撑真假判断：合法网页可能从未被归档，归档查询也可能失败。已修正 README、项目约定、调度说明和工具注释；链接失败仍沿用 advisory 策略，具体事实须核对原文。

## 验证结果

基线完整测试：81 项通过。修改后完整测试：100 项通过，新增 19 项回归测试；包含本地 Playwright 导出测试和六阶段流程测试。首次沙箱运行因 macOS 浏览器启动权限失败，在允许本地浏览器启动的环境重新执行后通过。未改变测试断言来掩盖该环境问题。

从基线提交加载旧版校验函数，使用同一组合成样本进行前后对照：

| 合成回归样本 | 修改前 | 修改后 |
|---|---|---|
| 同一 URL，使用不同分组并附跟踪参数 | 放行 | 拦截 |
| 第二来源只列在清单，没有支撑证据 | 放行 | 拦截 |
| 第二来源只提供反对证据 | 放行 | 拦截 |
| 同一 evidence ID 同时支持与反对结论 | 静默放行 | 给出复核警告，保留反方证据 |
| 正常的两份独立支撑证据 | 放行 | 放行 |

对照原始结果见 [回归结果 JSON](quality-regression-comparison.json)。这些结果证明已修复的校验行为，不是实际报告质量提高百分比。

## 现有产物兼容性抽查

只读检查 `projects/*/data/chapter_meta.json`，共找到 15 份元数据。基线与修改后均有 12 份通过聚合结构校验，没有新增结构校验不通过的课题；另外 3 份在基线中已不通过，本轮未修改历史产物。通过校验的材料共含 98 章、1,214 条证据，均尚未登记本轮新增的结构化问题计划或 `provenance` 字段。这只说明新格式尚未使用，不能据此断言以前没有做过检索或保存过其他形式的原文记录。

检查发现 40 处证据双重角色标注，已作为需要解释的警告；抽样阅读表明其中包含用于支持条件性结论及说明限制的材料，所以没有采取自动删除反证或统一阻断的处理。原始汇总见 [历史产物检查结果](quality-history-audit.json)。本次兼容性检查不等于这些历史报告已通过完整严格 QC 或语义事实核验；独立来源计数的修正仍可能要求部分报告补充实际支撑证据。

## 后续评估重点

建议下一步用少量固定真实研究题做版本盲评：固定问题、数据截止日期和预算，分别评估核心问题回答完整度、引用实际支撑、口径与反证保留、分析深度、建议可执行性。优先逐条审查核心结论，不能只比较字数、来源数或本轮新增覆盖指标。

本轮没有运行付费 LLM 裁判、官方全量 benchmark 或完整的前后报告生成实验。因此不能声称事实正确率、整体写作质量或榜单分数已经提高了某个百分比。现已提供能够减少确定性漏洞、暴露研究缺口的代码与协议，以及后续验证需要的原文关联记录。
