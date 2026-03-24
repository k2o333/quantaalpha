# T02: 集成到 library.py + 单元测试

**Slice:** S05
**Milestone:** M004

## Goal
将状态机逻辑接入 `apply_validation_result()`，在验证结果更新时自动触发状态转换，并编写完整的单元测试。

## Must-Haves

### Truths
- `apply_validation_result()` 调用 `determine_lifecycle_status()` 更新因子状态
- 所有状态转换路径有对应测试覆盖
- 测试覆盖 12+ 场景

### Artifacts
- `third_party/quantaalpha/quantaalpha/factors/library.py` — 状态机集成
- `third_party/quantaalpha/tests/test_factor_lifecycle.py` — 完整测试套件

### Key Links
- 依赖 S05/T01 完成的状态机函数
- S08 调度中心会调用状态转换逻辑

## Steps
1. 阅读 `library.py` 的 `apply_validation_result()` 方法。
2. 在验证结果更新后调用 `determine_lifecycle_status(period_results)`。
3. 将返回的状态写入 `evaluation.lifecycle_status` 字段。
4. 创建 `test_factor_lifecycle.py`，测试:
   - 所有周期通过 → stable_active
   - 大部分周期通过 → seasonal
   - 少数周期通过 → degraded
   - 全部失败 → archived
   - degraded → stable_active 恢复
   - archived → stable_active 重新激活
   - invalid period_results 处理
   - 状态转换边界条件
5. 运行 pytest，确认 12+ 测试通过。

## Context
- 本任务依赖 T01 完成的状态机函数
- 状态转换触发时机: 每次 `apply_validation_result()` 被调用
