# Deep Research 多宿主适配备忘

2026-11-27 讨论记录。Claude Code 和 Codex 是同事安装使用的首要环境，Hermes 纳入现有入口的回归范围，WorkBuddy 和 DSH 纳入扩展目标。本文记录设计方向，各宿主的完整支持状态以实测为准。

## 安装与维护

- 共用一份研究流程、模板、脚本和质量规则。需求澄清、检索取证、章节归纳、绘图、综合编辑和导出等后续功能优先在共享部分维护。
- 各宿主入口负责发现和启动研究流程，并将提问、文件操作、命令执行、联网或任务委派映射到该宿主的能力。缺少并行委派时，验证顺序执行能否交付相同成果。
- 区分随项目分发的内容、需要单独安装的依赖，以及需要用户配置的凭据或权限。安装检查应指出缺项、受影响的具体产物和补齐方法。

| 宿主 | 要保留或验证的入口 |
| --- | --- |
| Claude Code | 保留现有 deep-research 入口，验证干净环境安装和启动 |
| Codex | 保留 deep-research-work，验证技能发现、脚本执行与资源路径 |
| Hermes | 保留仓库已有的 SKILL.md 入口，验证澄清、委派和编辑流程 |
| WorkBuddy | 验证本地技能导入、资源随包加载、文件和命令权限 |
| DSH | 暂按 DeepSeek Harness 规划，核实产品及技能发现机制，分别验证交互和无人值守场景 |

## 验收口径

在各宿主的干净环境安装，用同一份小型研究任务验证需求澄清、来源检索、证据定位、分析图、终稿和导出。记录宿主版本、依赖、执行方式、实际生成的产物和未通过项。只通过技能发现或安装检查的宿主，仍需继续验证完整流程。

## v2.3.0-beta.1 候选入口

Claude Code 和 Hermes 继续使用 README 所列入口。Codex 在保留 `.codex/skills/deep-research-work/` 的同时，新增 `.agents/skills/deep-research/SKILL.md`，放在官方项目级发现目录下；该入口是薄入口，只负责被发现和启动，流程仍指向仓库共享规则。DSH 在本轮按 DeepSeek Harness 测试，其技能发现同样读取项目 `.agents/skills/`；打包候选入口暂保留 `.dsh/skills/deep-research/SKILL.md`，与 `.agents` 入口同源，待客户端实测后二选一。WorkBuddy 本地模式选择本仓库为工作区，在“添加技能 → 上传技能”中导入同一入口打成的 ZIP。可在仓库根运行 `python3 -m zipfile -c deep-research-entry.zip .dsh/skills/deep-research/SKILL.md`。包仅含调度入口，工具和模板来自同事已经打开的完整仓库。以上入口均待客户端实际导入、执行和交付验收。

参考 [DeepSeek Harness 技能发现目录](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/skills.md) 与 [WorkBuddy 技能导入说明](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)。
