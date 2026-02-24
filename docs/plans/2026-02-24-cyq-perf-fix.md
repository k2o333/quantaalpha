# cyq_perf Non-Trading Day Filter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the cyq_perf interface to filter out non-trading days when using date anchor pagination, preventing requests for days with no data.

**Architecture:** Modify the `_apply_date_anchor_range` method in pagination.py to use trading calendar data instead of all calendar days, with a fallback to calendar days if trading calendar is unavailable.

**Tech Stack:** Python, Polars, TuShare API integration

---

### Task 1: Create the implementation plan document

**Files:**
- Create: `docs/plans/2026-02-24-cyq-perf-fix.md`

**Step 1:** Create the plan document

This step was completed as part of creating the overall plan.

### Task 2: Write the failing test for non-trading day filtering

**Files:**
- Create: `test/test_date_anchor_pagination.py`

**Step 1:** Write the failing test

This was completed with a test that verifies date anchor pagination filters out non-trading days.

**Step 2:** Run test to verify it passes
Run: `pytest test/test_date_anchor_pagination.py::test_date_anchor_pagination_filters_non_trading_days -v`
Expected: PASS

### Task 3: Implement the fix in pagination.py

**Files:**
- Modify: `app4/core/pagination.py:256`

**Step 1:** Update the `_apply_date_anchor_range` method to use trading days instead of all calendar days

This was completed by replacing:
```python
anchor_values = self._generate_daily_dates(start_date, end_date)
```

With:
```python
# 生成每日日期锚定值 - 修复：使用交易日历过滤非交易日
anchor_values = [d["cal_date"] for d in self._get_trade_days(start_date, end_date)]
if not anchor_values:
    anchor_values = self._generate_daily_dates(start_date, end_date)  # 降级处理
```

### Task 4: Verify the fix with comprehensive testing

**Files:**
- Test: `app4/core/pagination.py`
- Test: `test/test_date_anchor_pagination.py`

**Step 1:** Validate that the fix only includes trading days

The fix has been validated with both trading day filtering and fallback behavior tests.

**Step 2:** Run additional validation tests

All tests pass successfully, confirming that the fix works as intended.

### Task 5: Commit the changes

**Files:**
- `app4/core/pagination.py`
- `test/test_date_anchor_pagination.py`
- `docs/plans/2026-02-24-cyq-perf-fix.md`

**Step 1:** Add and commit the changes

```bash
git add app4/core/pagination.py test/test_date_anchor_pagination.py docs/plans/2026-02-24-cyq-perf-fix.md
git commit -m "fix: filter non-trading days in date anchor pagination for cyq_perf
- Update _apply_date_anchor_range to use trading calendar instead of all calendar days
- Add fallback to calendar days when no trade calendar is available
- Add test to verify non-trading days are filtered out
- This prevents unnecessary requests for days with no data (e.g. weekends/holidays)"
```