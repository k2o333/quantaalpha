# Iterate 2.3: 质量门控与状态流转回归测试

Status: planned
Priority: P0
Depends-on: 2026-03-15-iterate2-02-failed-factor-debug-filter.md

---

## 一、目标

补齐 V2 设计里最关键的“可信度防线”测试，确保以下行为有稳定回归保护：

- planning 数据边界约束
- 质量门控拦截坏因子
- 多周期结果参与状态更新
- `revalidate` 语义修改后不破坏状态流转

这个迭代以测试为主，必要时允许少量代码重构来提升可测性。

---

## 二、范围

包含：

- 新增测试文件
- 提炼可测试辅助函数
- 补齐状态流转与门控坏样本 fixtures

不包含：

- 调度脚本
- 审计日志
- 文件锁

### 2.1 Downstream Consumer

- 状态流转规则最终由 `FactorLibraryManager.apply_validation_result()` 消费
- 质量门控结果最终影响是否进入高成本 backtest

### 2.2 Failure Semantics

- 坏样本应被明确挡在质量门控前段，而不是等到后面失败
- 阈值变更如果影响状态流转，测试必须第一时间失败

### 2.3 Caller Contract

- 规则调用方：helper 或规则函数返回值必须能稳定表达真实边界
- 流程调用方：质量门控结果必须足以阻止后续高成本步骤
- reviewer：应能从测试直接看出“规则是否阻止了后续流程”

### 2.4 What Does Not Count As Done

- 只按当前实现重拼 report 结构不算回归保护
- 只断言 `False` / `None`，不说明具体规则原因，不算合格测试
- 需要保护真实规则边界，而不是只保护 helper 当前写法

---

## 三、代码落点

- `third_party/quantaalpha/tests/test_continuous_factor_features.py`
- 建议新增：
  - `third_party/quantaalpha/tests/test_status_transition.py`
  - `third_party/quantaalpha/tests/test_planning_constraints.py`
  - `third_party/quantaalpha/tests/test_quality_gate.py`
- 可能需要小幅调整：
  - `third_party/quantaalpha/quantaalpha/factors/status_rules.py`
  - `third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py`
  - `third_party/quantaalpha/quantaalpha/backtest/validation.py`

---

## 四、开发方案

### 4.1 测试拆分

把当前偏“混合式”的 `test_continuous_factor_features.py` 拆成更明确的主题测试：

- `test_planning_constraints.py`
- `test_quality_gate.py`
- `test_status_transition.py`

保留原文件作为兼容 smoke test，也可以逐步瘦身。

### 4.2 质量门控坏样本用例

至少覆盖：

- NaN 比例过高
- inf 比例存在
- 常数列
- 有效样本占比过低

每个用例都要检查：

- 是否被 gate 拦截
- 返回原因是否明确
- 不会继续进入高成本 backtest

### 4.3 状态流转回归

至少覆盖：

- `pending_validation -> active`
- `active -> degraded`
- `active -> stale`
- `degraded -> deprecated`

并固定默认阈值断言：

- `active_stability_threshold = 0.5`
- `degraded_stability_threshold = 0.3`
- `stale_threshold_days = 30`

### 4.4 planning 边界约束

如果 planning 约束逻辑已有关键常量或 helper，应直接对 helper 做测试，不建议依赖整条 LLM 链路。

至少覆盖：

- 明显越界方向被拦截
- 合法价量方向可通过
- 错误提示包含被拦截原因

---

## 五、测试方案

### 5.1 自动化测试命令

```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m unittest -q third_party/quantaalpha.tests.test_continuous_factor_features
/root/miniforge3/envs/mining/bin/python -m unittest -q third_party/quantaalpha.tests.test_status_transition
/root/miniforge3/envs/mining/bin/python -m unittest -q third_party/quantaalpha.tests.test_planning_constraints
/root/miniforge3/envs/mining/bin/python -m unittest -q third_party/quantaalpha.tests.test_quality_gate
```

### 5.2 回归测试要求

- 新增测试不能依赖真实外部 LLM
- 尽量使用 stub module 和最小 fixture
- 失败断言必须能定位到具体规则，而不是只看 `False`

### 5.3 手工验收

抽查 1 个坏因子样本和 1 个正常样本：

- 坏样本应在 gate 被挡下
- 正常样本应仍能继续进入后续流程

### 5.4 Required Boundary Test

至少包含：

- 1 个坏样本证明不会进入高成本 backtest
- 1 组状态阈值断言，覆盖 `active / degraded / stale / deprecated`

### 5.5 Disproof Command

```bash
cd /home/quan/testdata/aspipe_v4
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_status_transition.py third_party/quantaalpha/tests/test_planning_constraints.py third_party/quantaalpha/tests/test_quality_gate.py -q
```

### 5.6 Primary Evidence / Secondary Evidence

Primary evidence:

- 至少 1 个测试证明坏样本会阻止后续高成本步骤
- 至少 1 组阈值断言覆盖真实状态流转边界

Secondary evidence:

- 仅针对 helper 的形状测试
- 仅验证 report 或消息文本的测试
- 不影响后续流程的局部布尔值测试

---

## 六、验收标准

1. 关键稳定性约束均有自动化测试保护
2. 状态流转阈值在测试中被显式断言
3. 坏样本不会再轻易穿透质量门控
4. planning 越界方向有可复现测试
5. 测试执行不依赖外部服务
6. 至少有一个测试直接证明 gate 会阻止后续高成本步骤

### 6.1 Move Blockers / Move-to-Tested Conditions

出现以下任一情况，文档不得移到 `tested`：

- 只证明 helper 当前实现，不证明真实规则边界
- 坏样本会失败，但仍可能进入后续高成本步骤
- 阈值变更无法通过测试立即暴露

仅当以下条件同时满足时，才允许移到 `tested`：

- `Disproof Command` 已执行
- `Primary Evidence` 已满足
- 关键规则边界已通过测试固定

---

## 七、交付产物

- 新增 2 到 3 个主题测试文件
- 质量门控坏样本 fixtures
- 必要的小幅可测性重构
