# S05: 因子生命周期状态机 — UAT

**Milestone:** M004
**Written:** 2026-03-24

## UAT Type

- **UAT mode:** Contract (unit tests + syntax verification)
- **Why this mode is sufficient:** 状态机逻辑是纯函数，适合通过单元测试验证，无需运行时环境

## Preconditions

- Python 3.13+ 环境
- quantaalpha 包可导入（可从 quantaalpha/ 目录或通过 symlink）

## Smoke Test

```bash
cd third_party/quantaalpha
python -m py_compile quantaalpha/factors/status_rules.py
python -m pytest tests/test_status_transition.py -v
```

**Expected:** 编译成功，6/6 测试通过

---

## Test Cases

### 1. pending_validation → active (成功 + 高稳定性)

**Steps:**
1. 创建初始 entry（无 evaluation）
2. 调用 `update_factor_status(entry, {"status": "success", "summary": {"stability_score": 0.6}})`
3. 检查 `result["evaluation"]["status"]`

**Expected:** `status == "active"`

```python
entry = {"factor_id": "test1"}
result = update_factor_status(entry, {
    "status": "success",
    "summary": {"stability_score": 0.6}
})
assert result["evaluation"]["status"] == "active"
```

---

### 2. pending_validation → degraded (成功 + 低稳定性)

**Steps:**
1. 创建初始 entry（无 evaluation）
2. 调用 `update_factor_status(entry, {"status": "success", "summary": {"stability_score": 0.29}})`
3. 检查 `result["evaluation"]["status"]`

**Expected:** `status == "degraded"`

```python
entry = {"factor_id": "test2"}
result = update_factor_status(entry, {
    "status": "success",
    "summary": {"stability_score": 0.29}
})
assert result["evaluation"]["status"] == "degraded"
```

---

### 3. active → stale (30 天未验证)

**Steps:**
1. 创建 active 状态的 entry，`last_validated` 为 31 天前
2. 调用 `update_factor_status(entry, None, now=datetime(2026, 3, 19))`
3. 检查 `result["evaluation"]["status"]`

**Expected:** `status == "stale"`

```python
now = datetime(2026, 3, 19)
entry = {
    "factor_id": "test3",
    "evaluation": {
        "status": "active",
        "last_validated": (now - timedelta(days=31)).isoformat(),
        "stability_score": 0.6
    }
}
result = update_factor_status(entry, None, now=now)
assert result["evaluation"]["status"] == "stale"
```

---

### 4. active → degraded (验证失败)

**Steps:**
1. 创建 active 状态的 entry
2. 调用 `update_factor_status(entry, {"status": "failure", "summary": {}})`
3. 检查 `result["evaluation"]["status"]`

**Expected:** `status == "degraded"`

```python
entry = {
    "factor_id": "test4",
    "evaluation": {"status": "active", "consecutive_failures": 0}
}
result = update_factor_status(entry, {
    "status": "failure",
    "summary": {}
})
assert result["evaluation"]["status"] == "degraded"
```

---

### 5. degraded → active (稳定性恢复)

**Steps:**
1. 创建 degraded 状态的 entry（stability_score=0.2）
2. 调用 `update_factor_status(entry, {"status": "success", "summary": {"stability_score": 0.7}})`
3. 检查 `result["evaluation"]["status"]` 和 `consecutive_failures`

**Expected:** `status == "active"`, `consecutive_failures == 0`

```python
entry = {
    "factor_id": "test5",
    "evaluation": {
        "status": "degraded",
        "stability_score": 0.2,
        "consecutive_failures": 1
    }
}
result = update_factor_status(entry, {
    "status": "success",
    "summary": {"stability_score": 0.7}
})
assert result["evaluation"]["status"] == "active"
assert result["evaluation"]["consecutive_failures"] == 0
```

---

### 6. degraded → deprecated (连续失败 3 次)

**Steps:**
1. 创建 degraded 状态的 entry，`consecutive_failures=2`
2. 调用 `update_factor_status(entry, {"status": "failure", "summary": {}})`
3. 检查 `result["evaluation"]["status"]` 和 `consecutive_failures`

**Expected:** `status == "deprecated"`, `consecutive_failures == 3`

```python
entry = {
    "factor_id": "test6",
    "evaluation": {
        "status": "degraded",
        "stability_score": 0.1,
        "consecutive_failures": 2
    }
}
result = update_factor_status(entry, {
    "status": "failure",
    "summary": {}
})
assert result["evaluation"]["status"] == "deprecated"
assert result["evaluation"]["consecutive_failures"] == 3
```

---

## Edge Cases

### EC1: 稳定性边界值 (0.5)

**Steps:**
1. `stability_score = 0.5` 时验证
2. 检查是否为 active

**Expected:** `status == "active"`（阈值是 >= 0.5）

### EC2: 稳定性边界值 (0.3)

**Steps:**
1. `stability_score = 0.3` 时验证
2. 检查是否为 degraded

**Expected:** `status == "degraded"`（阈值是 < 0.3）

### EC3: 无效的 last_validated 格式

**Steps:**
1. 创建 entry，`last_validated` 为无效格式
2. 调用 `update_factor_status(entry, None)`
3. 检查不抛异常

**Expected:** 无异常，正常处理

---

## Failure Signals

- **语法错误:** `python -m py_compile` 失败
- **测试失败:** `pytest tests/test_status_transition.py` 任意 FAIL
- **类型错误:** status 不在预期枚举值中
- **状态不变:** 验证后 status 未按预期转换

---

## Not Proven By This UAT

- 实际运行时与因子库的完整集成（需因子库有真实数据）
- 并发更新状态的安全性
- 长期 stale 因子的自动归档
- 因子库持久化到磁盘的完整性

---

## Notes for Tester

1. **运行所有测试:** `pytest tests/test_status_transition.py -v`
2. **单独测试函数:** `pytest tests/test_status_transition.py::TestStatusTransition::test_active_to_stale -v`
3. **调试状态转换:** 在 `update_factor_status()` 中添加 print 语句
4. **检查默认值:** `DEFAULT_FACTOR_STATUS_CONFIG` 中的阈值

---

## Run Commands

```bash
# 语法检查
cd third_party/quantaalpha
python -m py_compile quantaalpha/factors/status_rules.py

# 运行所有状态转换测试
python -m pytest tests/test_status_transition.py -v

# 运行特定测试
python -m pytest tests/test_status_transition.py::TestStatusTransition::test_active_to_stale -v

# 运行 S02 相关测试（验证集成）
python -m pytest tests/test_status_transition.py tests/test_revalidation_candidates.py -v
```
