# S01: 跨周期验证通过标准

**Goal:** 在回测流程中添加因子跨周期验证的自动判定标准，使系统能根据 IC/Rank IC 阈值和最少通过周期数自动判断因子是否有效。
**Demo:** 回测完成后，系统自动输出因子是否满足跨周期验证标准的判定结果。

## Must-Haves
- `backtest.yaml` 的 `multi_period_validation` 新增 `require_all_pass`, `pass_criteria.min_ic`, `pass_criteria.min_rank_ic`, `pass_criteria.min_periods_pass` 配置项
- `validation_judge.py` 新模块实现 `evaluate_multi_period_results()` 函数
- 判定逻辑: 遍历各周期回测结果，对比 IC/Rank IC 阈值，统计通过周期数
- 单元测试覆盖: 全通过、部分通过、全失败三种场景

## Proof Level
- This slice proves: **contract**
- Real runtime required: no (mock 回测结果)
- Human/UAT required: no

## Verification
- `python -m py_compile quantaalpha/backtest/validation_judge.py`
- `pytest quantaalpha/tests/test_validation_judge.py -v`
- `grep "pass_criteria" quantaalpha/factors/prompts/backtest.yaml` returns >= 3 matches
- **Diagnostic/Failure-path check**: 验证 evaluate_multi_period_results() 对空输入、缺失指标的处理

## Tasks

- [x] **T01: 扩展 backtest.yaml 配置 + 创建 validation_judge.py** `est:30m`
  - Why: 配置和判定逻辑是核心交付物
  - Files: `quantaalpha/factors/prompts/backtest.yaml`, `quantaalpha/backtest/validation_judge.py`
  - Do: 在 backtest.yaml 的 multi_period_validation 下新增 require_all_pass, pass_criteria 配置段；创建 validation_judge.py 实现 evaluate_multi_period_results()
  - Verify: py_compile 通过, grep 配置项
  - Done when: 配置段存在，判定函数可调用

- [x] **T02: 单元测试 + 集成到回测结果聚合** `est:20m`
  - Why: 验证判定逻辑正确性并接入实际流程
  - Files: `quantaalpha/tests/test_validation_judge.py`, 回测结果聚合模块
  - Do: 编写测试用例覆盖三种场景；在回测结果聚合时调用 evaluate_multi_period_results()
  - Verify: pytest 通过，聚合逻辑包含判定调用
  - Done when: 10+ 测试通过，回测结果包含判定输出

## Files Likely Touched
- `quantaalpha/factors/prompts/backtest.yaml` (modify)
- `quantaalpha/backtest/validation_judge.py` (new)
- `quantaalpha/tests/test_validation_judge.py` (new)

## Observability / Diagnostics

### Runtime Signals
- `evaluate_multi_period_results()` returns `EvaluationResult` dataclass with structured fields:
  - `overall_pass` (bool): Final pass/fail judgment
  - `passing_periods` / `failing_periods` (list): Period names by judgment
  - `period_judgments` (list): Per-period details including `reason` field explaining pass/fail

### Inspection Surfaces
- `format_evaluation_result()`: Human-readable string output
- `period_judgments[].reason`: Textual explanation (e.g., "IC (0.0150) <= threshold (0.0200)")

### Failure Visibility
- Missing IC/Rank IC: Treated as failure with reason "IC/Rank IC not available"
- Non-success status: Treated as failure with reason "Period status is '{status}'"
- Empty periods: Returns overall_pass=False, total_periods=0

### Redaction Constraints
- No sensitive data exposure in judgment output
- Only period names and numeric thresholds logged

---
estimated_steps: 8
estimated_files: 3
