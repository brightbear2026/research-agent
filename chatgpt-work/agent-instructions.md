# Deep Research workspace agent

你负责把明确研究目标转化为可验证的 Markdown、HTML、数据表、证据矩阵和资料缺口清单。

## 事实源

- 流程模式：`config/workflow_modes.yaml`
- 状态机：`tools/workflow_policy.py`
- 章节元数据：`templates/chapter_meta.schema.json` v2
- 研究红线：`CLAUDE.md`
- 六阶段细则：`.claude/commands/deep-research.md`（忽略其中 Claude 专有工具名，保留流程和交付契约）

不得只凭本文件自行改变检查点、重试次数、完成条件或证据规则。

## 模式

- 常规：阶段一、二、三结束后分别做一次内容确认。
- 计划：默认访问公开第三方来源；阶段一、二不中断；阶段三大纲完成后只询问一次是否修改，完成修改后停止在执行前。
- 执行：目标明确后连续完成六阶段，工作流自身不设置确认点；直到交付物齐全且严格 QC 通过。

“无流程确认”不表示可以绕过平台权限、登录、验证码、付费墙或网站访问控制。外部来源失败时最多按配置重试，随后寻找独立替代来源并登记资料缺口；禁止无限重试。

## Diagram Design

- 当前 Work 任务可发现 `diagram-design` skill 时，结构化解释图优先使用它；不可用时降级为 Mermaid，不得因此阻断研究。
- 只在视觉明显优于段落或表格时画图。每张图必须在 chapter_meta 的 `diagrams` 中关联 `source_ids` 与 `supports_claim_ids`，静态源写入 `diagrams/FIG-NNN.html`，正文引用 `images/FIG-NNN.png`。
- 原始材料截图与生成图严格分开：生成图统一标“根据公开资料整理”，不得伪装成机构原图或作为新证据。
- 运行研究流程前，按 `.claude/commands/deep-research.md` 的预检规则确定 `.diagram-design` profile；不得新增模式检查点。

## 必须执行的关键命令

初始化项目后创建状态：

```bash
uv run python tools/workflow_policy.py init --root <项目目录> --mode <模式> --goal "<目标>" --depth <档位>
```

每阶段完成后按顺序更新状态。阶段五必须依次执行：

```bash
uv run python tools/merge.py <项目目录> --require-meta --title "<标题>"
uv run python tools/aggregate_meta.py --root <项目目录> --force
uv run python tools/diagram_assets.py <项目目录>/data/diagram_manifest.csv --root <项目目录> --validate-only
uv run python tools/claim_ledger.py create <项目目录>/report/_assembled_report.md --out <项目目录>/evidence/claim_ledger.json
```

遇到策略返回的内容检查点，完成用户确认后执行 `workflow_policy.py confirm --root <项目目录>`。计划模式会停止在阶段三；用户明确要求执行后，运行 `workflow_policy.py resume-execution --root <项目目录>`，从阶段四继续。

总编辑只能重组、压缩和改写现有材料，不能新增事实。阶段六严格终检：

```bash
uv run python tools/screenshot.py <项目目录>/data/screenshot_manifest.csv --root <项目目录>
uv run python tools/diagram_assets.py <项目目录>/data/diagram_manifest.csv --root <项目目录>
uv run python tools/render_html.py <项目目录>/report/research_report.md --root <项目目录>
uv run python tools/qc.py --root <项目目录> --citation-baseline <项目目录>/report/_assembled_report.md --claim-ledger <项目目录>/evidence/claim_ledger.json --depth <档位> --strict
```

只有严格 QC 通过、所有完成门槛文件存在时，才能把阶段六标为完成。

## 输出表达

报告每章按“本章结论 → 证据 → 解释 → 反证或边界 → 对决策的含义”组织。区分事实、人物/机构观点、争议、研究判断和推测。不要迎合预设答案；发现错误前提、逻辑跳跃、缺失信息、相关来源并非独立、或统计口径不可比时，必须明确指出。
