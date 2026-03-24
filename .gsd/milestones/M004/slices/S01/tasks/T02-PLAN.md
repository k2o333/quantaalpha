# T02: 单元测试 + 集成到回测结果聚合

**Slice:** S01
**Milestone:** M004

## Goal
验证跨周期判定逻辑并将其接入现有回测结果聚合流程，确保回测输出携带可消费的判定结论。

## Must-Haves

### Truths
- 针对全部通过、部分通过、全部失败、缺失指标的测试全部覆盖
- 回测结果聚合链路能调用 `evaluate_multi_period_results()`
- 聚合结果中保留原始 period 结果与最终判定，不丢失已有字段

### Artifacts
- `third_party/quantaalpha/tests/test_validation_judge.py` — 判定逻辑测试
- 回测结果聚合模块 — 接入自动判定结果

### Key Links
- 聚合模块 → `validation_judge.py` 通过显式 import 接入
- 测试用例 → `pass_criteria` 字段命名与 `backtest.yaml` 保持一致

## Steps
1. 写出 `test_validation_judge.py`，覆盖 pass/fail/partial/empty 四类核心场景。
2. 运行测试并确认在 T01 完成前会暴露缺失实现或行为不匹配。
3. 修改回测结果聚合模块，调用 `evaluate_multi_period_results()`。
4. 重新运行目标测试，确认判定逻辑与聚合输出一致。
5. 补充必要的边界测试，避免未来配置字段变动造成隐式回归。

## Context
- 本任务依赖 S01/T01 已创建 `validation_judge.py`
- 只要求把自动判定嵌入回测结果输出，不要求实现生命周期状态流转
- 生命周期判断留给 M004 S05 处理
