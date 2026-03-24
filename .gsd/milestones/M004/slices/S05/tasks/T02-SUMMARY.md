---
id: T02
parent: S05
milestone: M004
status: completed
verification_result: passed
completed_at: 2026-03-24
blocker_discovered: false
provides:
  - library.py integration with status machine
  - test_status_transition.py (6 passing tests)
requires:
  - T01: update_factor_status() function
affects:
  - S08: status machine for scheduling triggers
key_files:
  - third_party/quantaalpha/quantaalpha/factors/library.py
  - third_party/quantaalpha/tests/test_status_transition.py
key_decisions:
  - Audit trail on status change via _append_audit_entry()
  - persist=True default for auto-persistence
patterns_established:
  - Status change triggers audit trail
  - Config passthrough to update_factor_status
observability_surfaces:
  - _append_audit_entry() with trigger="apply_validation_result"
  - factor data persisted to disk on status change
---

# T02: 集成到 library.py + 单元测试

**Status:** Completed

## Intended Outcome

- 状态机接入因子库并有回归测试保护

## What Was Built

### Integration in library.py

`apply_validation_result()` 方法（第 520-554 行）集成了状态机：

```python
def apply_validation_result(
    self,
    factor_entry: dict[str, Any],
    validation_result: dict[str, Any],
    *,
    now: datetime | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    previous_entry = self.get_factor(...) or self._normalize_factor_entry(factor_entry)
    previous_status = previous_entry.get("evaluation", {}).get("status")
    updated = update_factor_status(...)
    
    if persist:
        # Persist to data store
        self.data["factors"][factor_id] = updated
        
        # Audit trail on status change
        if previous_status != new_status:
            self._append_audit_entry(
                trigger="apply_validation_result",
                ...
            )
        self._save()
    return updated
```

### Test Coverage

`tests/test_status_transition.py` 包含 6 个测试用例：

| Test | Coverage |
|------|----------|
| `test_default_thresholds_match_plan` | 阈值配置正确性 |
| `test_active_to_stale` | 30 天未验证 → stale |
| `test_active_to_degraded_low_stability` | 稳定性降至 0.29 → degraded |
| `test_degraded_to_active_boundary` | 稳定性恢复至 0.51 → active |
| `test_degraded_to_deprecated` | 连续失败 3 次 → deprecated |
| `test_degraded_to_active_high_stability` | 高稳定性恢复 → active |

## Verification Evidence

| Command | Exit Code | Verdict | Duration |
|---------|-----------|---------|----------|
| `pytest tests/test_status_transition.py -v` | 0 | 6/6 PASS | 0.04s |
| `pytest tests/test_status_transition.py tests/test_revalidation_candidates.py -v` | 0 | 21/21 PASS | 0.47s |

## Diagnostics

- 检查审计追踪: `manager.get_audit_trail(trigger="apply_validation_result")`
- 检查因子状态: `manager.get_factor(factor_id)["evaluation"]["status"]`
- 检查连续失败: `manager.get_factor(factor_id)["evaluation"]["consecutive_failures"]`
