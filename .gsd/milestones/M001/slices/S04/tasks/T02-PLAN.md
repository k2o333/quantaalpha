# T02: 执行因子挖掘验证

**Slice:** S04  
**Milestone:** M001  

## Goal
实际运行一次包含 `factor_construct` 步骤的因子挖掘流程，并收集运行日志。

## Must-Haves

### Truths
- `factor_construct` 被调度并实际与 LLM 产生交互
- 流程执行期间若遭遇 LLM 空响应，重试限制能够生效

### Artifacts
- 无新增代码文件，产出执行日志

### Key Links
- `proposal.py` 中新修改的重试逻辑能够被覆盖

## Steps
1. 使用命令行运行因子挖掘主入口脚本。
2. 将标准输出与标准错误重定向到日志文件中保存，或者在终端直接观察。
3. 等待至少一次因子提议周期完成或失败。

## Context
- 之前 M001 的 Bug 主要在 factor proposal 环节发生。
