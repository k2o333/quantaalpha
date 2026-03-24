# T01: 三合一调度架构设计

**Slice:** S08
**Milestone:** M004

## Goal
定义 MiningOrchestrator 类接口，设计数据监控/温故/知新三个子模块的交互流程，输出完整架构设计文档。

## Must-Haves

### Truths
- `MiningOrchestrator` 类接口定义完整
- 三合一流程图和状态机定义清晰
- 模块间依赖关系明确

### Artifacts
- `quantaalpha/continuous/orchestrator.py` — 调度器接口定义
- `quantaalpha/continuous/__init__.py` — 模块初始化
- 架构设计文档

### Key Links
- 依赖 S02 的 `select_revalidation_candidates()`
- 依赖 S05 的状态机
- 依赖 S06 的向量检索

## Steps
1. 创建 `continuous/` 目录。
2. 定义 `MiningOrchestrator` 接口:
   ```python
   class MiningOrchestrator(Protocol):
       def start(self) -> None: ...
       def stop(self) -> None: ...
       def trigger_mining(self) -> None: ...
       def trigger_revalidation(self) -> None: ...
   ```
3. 设计三合一流程:
   - 数据监控: 监听 app4 数据更新 → 触发因子回测
   - 温故: 定时调用 select_revalidation_candidates() → 回测 → 更新状态
   - 知新: RAG 检索 → LLM 生成 → 回测 → 入库
4. 定义状态机和调度策略接口。
5. 用 `py_compile` 验证语法。
6. 编写架构设计文档（Markdown 格式）。

## Context
- 上游来源: `docs/drafts/mining/factor_mining_requirements.md §F.3.1`
- 本 slice 为设计文档 slice，不涉及运行时代码实现
