# T01: 扩展 backtest.yaml 配置 + 创建 validation_judge.py

**Slice:** S01
**Milestone:** M004

## Goal
为多周期回测增加 `pass_criteria` 配置与独立判定函数，使系统可以自动判断跨周期验证是否通过。

## Must-Haves

### Truths
- `multi_period_validation` 配置中存在 `require_all_pass` 和 `pass_criteria` 字段
- `evaluate_multi_period_results()` 可根据 IC / Rank IC / 通过周期数返回结构化判定结果
- 缺失字段或空结果时函数表现可预期，不抛出隐式异常

### Artifacts
- `third_party/quantaalpha/quantaalpha/factors/prompts/backtest.yaml` — 多周期验证配置增强
- `third_party/quantaalpha/quantaalpha/backtest/validation_judge.py` — 判定函数模块

### Key Links
- `backtest.yaml` → `validation_judge.py` 通过统一的 `pass_criteria` 键名对齐
- 后续结果聚合模块可直接调用 `evaluate_multi_period_results()`

## Steps
1. 阅读 M003 S03 已落地的多周期配置，确认当前 `backtest.yaml` 结构与字段命名。
2. 在 `backtest.yaml` 的 `multi_period_validation` 下补充 `require_all_pass` 与 `pass_criteria`。
3. 创建 `validation_judge.py`，定义输入数据结构和 `evaluate_multi_period_results()`。
4. 为缺失指标、空 periods、部分通过、全部通过等场景补充防御性处理。
5. 用 `py_compile` 验证新模块语法。

## Context
- 上游来源是 `docs/drafts/mining/factor_mining_requirements.md §C.3.1`
- M003 S03 已实现多周期区间配置，但未形成统一的通过标准自动判定
- 该任务只建立配置与判定能力，不负责把结果写回因子库

## Expected Output
- `third_party/quantaalpha/configs/backtest.yaml` — 修改，增加 `require_all_pass` 和 `pass_criteria` 配置
- `third_party/quantaalpha/quantaalpha/backtest/validation_judge.py` — 新建，实现 `evaluate_multi_period_results()` 函数

## Observability Impact
- 函数返回 `EvaluationResult` dataclass，包含 `overall_pass`、`passing_periods`、`failing_periods`
- `period_judgments` 列表包含每周期详细判定原因 (reason 字段)
- 缺失指标时返回可预期的失败结果，不抛出异常
- `format_evaluation_result()` 提供人类可读的输出格式
