# T03: 模块间接口契约定义

**Slice:** S08
**Milestone:** M004

## Goal
定义 DataMonitorTrigger / RevalidationScheduler / MiningScheduler 接口，以及与 FactorLibraryManager、ProviderPool、VectorStore 的集成点。

## Must-Haves

### Truths
- 所有子模块接口有明确签名
- 事件分发格式定义
- 无循环依赖

### Artifacts
- `quantaalpha/continuous/scheduler.py` — 调度器接口定义

### Key Links
- 依赖 T01 的 Orchestrator 接口
- 依赖 T02 的技术选型结论

## Steps
1. 创建 `scheduler.py`。
2. 定义触发器接口:
   ```python
   class DataMonitorTrigger(Protocol):
       def start_watching(self) -> None: ...
       def on_data_update(self, event: DataUpdateEvent) -> None: ...
   ```
3. 定义调度器接口:
   ```python
   class RevalidationScheduler(Protocol):
       def schedule_revalidation(self, factor_ids: List[str]) -> None: ...
       def on_revalidation_complete(self, result: ValidationResult) -> None: ...
   ```
4. 定义事件格式:
   ```python
   @dataclass
   class DataUpdateEvent:
       source: str
       timestamp: datetime
       records_updated: int
   ```
5. 定义与现有模块的集成点:
   - FactorLibraryManager: 读写因子
   - ProviderPool: 调用 LLM
   - VectorStore: RAG 检索
6. 用 `py_compile` 验证无循环导入。

## Context
- 本任务依赖 T01 和 T02 完成
- 接口设计应考虑未来实现灵活性
