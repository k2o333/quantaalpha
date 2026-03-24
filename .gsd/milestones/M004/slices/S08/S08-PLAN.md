# S08: 24H 调度中心设计

**Goal:** 设计完整的三合一调度中心架构（数据监控 + 温故 + 知新），确定技术选型，定义模块接口。
**Demo:** 架构设计文档完成，模块间接口契约定义清晰，技术选型有理有据。

## Must-Haves
- `orchestrator.py` 定义 `MiningOrchestrator` 类接口（调度入口）
- `scheduler.py` 定义调度策略接口: `DataMonitorTrigger`, `RevalidationScheduler`, `MiningScheduler`
- 技术选型文档: 向量库（ChromaDB）、任务调度（APScheduler vs Celery）、进程管理（Supervisor vs systemd）评估
- 三合一流程定义:
  1. 数据监控: 监听 app4 数据更新 → 触发因子回测
  2. 温故: 定时调用 select_revalidation_candidates() → 回测 → 更新状态
  3. 知新: RAG 检索 → LLM 生成 → 回测 → 入库
- 异常处理和故障恢复策略设计
- 模块间接口契约定义文档

## Proof Level
- This slice proves: **design document** (不涉及运行时代码)
- Real runtime required: no
- Human/UAT required: yes (设计评审)

## Verification
- 设计文档完整性检查
- 接口定义 py_compile 通过
- 技术选型文档包含 pros/cons 对比

## Tasks

- [x] **T01: 三合一调度架构设计** `est:40m`
  - Why: 架构设计是后续实现的基础
  - Files: `quantaalpha/continuous/orchestrator.py` (接口定义), 设计文档
  - Do: 定义 MiningOrchestrator 接口；设计数据监控/温故/知新三个子模块的交互流程；定义状态机和调度策略
  - Verify: 接口定义 py_compile 通过
  - Done when: 三合一流程图和接口定义完整

- [x] **T02: 技术选型评估** `est:30m`
  - Why: 不同技术栈对实现难度和运维成本影响重大
  - Files: 设计文档
  - Do: 评估 APScheduler/Celery/Prefect (任务调度)、Supervisor/systemd (进程管理)、Loguru+Grafana (日志监控)、YAML+Pydantic (配置管理) 的 pros/cons
  - Verify: 文档包含对比表
  - Done when: 每个模块的推荐方案及理由记录完成

- [x] **T03: 模块间接口契约定义** `est:25m`
  - Why: 契约是各模块独立实现的前提
  - Files: `quantaalpha/continuous/scheduler.py` (接口定义)
  - Do: 定义 DataMonitorTrigger / RevalidationScheduler / MiningScheduler 接口；定义事件分发格式；定义与 FactorLibraryManager、ProviderPool、VectorStore 的集成点
  - Verify: py_compile 通过
  - Done when: 所有接口可 import 且无循环依赖

## Files Likely Touched
- `quantaalpha/continuous/orchestrator.py` (new — 接口定义)
- `quantaalpha/continuous/scheduler.py` (new — 接口定义)
- `quantaalpha/continuous/__init__.py` (new)
- 设计文档 (new)

---
estimated_steps: 12
estimated_files: 4
