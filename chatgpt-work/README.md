# ChatGPT Work 适配说明

本目录提供可复制到 ChatGPT Work 工作区代理的指令，不假设 ChatGPT Work 会自动读取 `.claude/`。

## 使用方式

1. 把仓库作为工作区文件或连接的代码仓库提供给 ChatGPT Work。
2. 将 `agent-instructions.md` 设为工作区代理指令。
3. 输入明确目标，并指定 `mode=常规|计划|执行`、`depth=快速|标准|深度`。
4. 代理必须把 `config/workflow_modes.yaml` 和 `tools/workflow_policy.py` 作为模式事实源。
5. 若工作区可用 Diagram Design 插件，在新任务中启用它；若不可用，代理会按规则降级为 Mermaid，不影响证据研究和交付。

平台自身的权限、登录或连接器授权提示不属于本仓库的流程确认，不能由模式配置绕过。

## 推荐输入

```text
目标：研究……，为……提供决策依据。
范围：时间……；地域……；不包含……。
读者：……。
mode=执行
depth=标准
```

计划模式只产出到阶段三，并在大纲完成后询问一次是否修改；不会自动进入正式执行。用户确认执行后，代理用 `workflow_policy.py resume-execution` 从阶段四继续，不重复前三阶段。
