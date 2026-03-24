# T01: 准备测试环境

**Slice:** S04  
**Milestone:** M001  

## Goal
确认项目运行因子挖掘所需的各项依赖、环境变量及数据是完备的。

## Must-Haves

### Truths
- 可以成功导入 `quantaalpha`
- `APIBackend` 或是 LLM proxy 的环境变量已正确设置并在可用状态

### Artifacts
- 无新代码产物，纯环境和检查项

### Key Links
- 测试环境 -> quantaalpha 核心库调用

## Steps
1. 检查环境变量中是否配置了模型 API KEY（如 `OPENAI_API_KEY`，`LITELLM_KEY` 等）。
2. 确认 `data/` 目录下存在因子挖掘所需的预处理数据（Parquet档）。
3. 如需激活特定 conda 环境则激活之。

## Context
- 因子挖掘修复主要是针对由异常响应导致的工作流挂起，需要具备触发提议的条件。
