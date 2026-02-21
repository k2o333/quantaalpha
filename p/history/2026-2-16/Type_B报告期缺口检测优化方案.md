# Type B 报告期缺口检测优化方案

## 一、问题描述

### 现象

Type B 接口（如 `income_vip`, `balancesheet_vip`）在第二次下载更大日期范围时，会重复下载已存在的报告期数据。

### 复现场景

```
第一次下载: 20240101 ~ 20240630
  → 获取报告期: 20231231, 20240331
  → 存储: 2 条记录

第二次下载: 20230101 ~ 20241231
  → 缺口检测: 缺失 6 个报告期 ['20230331', '20230630', '20230930', '20240630', '20240930', '20241231']
  → 正确排除了已存在的 20240331
  → 但使用范围查询: 20230101 ~ 20241231
  → API 返回: 10 条记录（包含已存在的 20240331）
  → 去重后: 8 条记录（removed=2）
```

### 问题日志

```
[000001.SZ] 缺失 6 个报告期: ['20230331', '20230630', '20230930', '20240630', '20240930', '20241231']
[000001.SZ] 使用范围查询策略（6 个缺失报告期 > 3）
  - 最小覆盖范围: 20230101 ~ 20241231
Downloaded 10 records for income_vip
Deduplication completed for income_vip: input=10, output=8, removed=2
```

---

## 二、问题诊断

### 根本原因

当前代码在缺失报告期数量 > 3 时，使用**单一范围查询**覆盖所有缺失报告期：

```python
# 文件: coverage_manager.py, 行 970-985
if len(missing_periods) <= MAX_PRECISE_QUERIES:
    # 精确查询：每个报告期单独请求
    return [{'ts_code': ts_code, 'start_date': period_start, 'end_date': period} for period in missing_periods]
else:
    # 范围查询：一个请求覆盖全部
    min_period = min(missing_periods)  # 20230331
    max_period = max(missing_periods)  # 20241231
    return [{'ts_code': ts_code, 'start_date': min_start, 'end_date': max_period}]
```

### 问题分析

当缺失报告期之间存在"断层"（已存在的报告期）时：

```
缺失报告期: 20230331, 20230630, 20230930, [断层: 20240331已存在], 20240630, 20240930, 20241231
                              ↑─────────────────────────────────────↑
                              范围查询会包含这个已存在的报告期
```

API 的 `start_date + end_date` 范围查询会返回区间内**所有报告期**的数据，无法排除特定报告期。

### 影响范围

| 接口类型 | 是否受影响 | 说明 |
|---------|-----------|------|
| Type A (交易日历) | 否 | 使用 `_merge_dates_to_ranges` 按连续性分组 |
| Type B (报告期) | **是** | 未按连续性分组，直接用整体范围 |
| Type C (日期锚定) | 否 | 每个锚点单独查询 |

---

## 三、解决方案

### 方案概述

参考 Type A 的实现，将缺失报告期按**连续性分组**，每组生成一个范围查询，跳过已存在的报告期。

### 优化后效果

```
缺失报告期: 20230331, 20230630, 20230930, [20240331已存在], 20240630, 20240930, 20241231

分组结果:
  组1: 20230331 ~ 20230930 (连续3个)
  组2: 20240630 ~ 20241231 (连续3个)

生成任务:
  {'ts_code': '000001.SZ', 'start_date': '20230101', 'end_date': '20230930'}
  {'ts_code': '000001.SZ', 'start_date': '20240401', 'end_date': '20241231'}
```

### 代码修改

#### 1. 新增方法: `_merge_periods_to_ranges`

```python
def _merge_periods_to_ranges(self, periods: List[str]) -> List[tuple]:
    """
    将缺失报告期按连续性分组
    
    报告期连续性判断:
    - 同年相邻季度: 0331→0630, 0630→0930, 0930→1231
    - 跨年连续: 1231→次年0331
    """
    if not periods:
        return []
    
    sorted_periods = sorted(periods)
    ranges = []
    group_start = sorted_periods[0]
    group_end = sorted_periods[0]
    
    quarter_order = {'0331': 1, '0630': 2, '0930': 3, '1231': 4}
    
    for i in range(1, len(sorted_periods)):
        curr = sorted_periods[i]
        prev = sorted_periods[i-1]
        
        curr_year = curr[:4]
        prev_year = prev[:4]
        curr_q = quarter_order[curr[4:]]
        prev_q = quarter_order[prev[4:]]
        
        is_continuous = (
            (curr_year == prev_year and curr_q == prev_q + 1) or
            (int(curr_year) == int(prev_year) + 1 and curr_q == 1 and prev_q == 4)
        )
        
        if is_continuous:
            group_end = curr
        else:
            ranges.append((group_start, group_end))
            group_start = curr
            group_end = curr
    
    ranges.append((group_start, group_end))
    return ranges
```

#### 2. 修改方法: `_detect_report_period_gaps`

```python
def _detect_report_period_gaps(self, interface_name, ts_code, start_date, end_date,
                               date_column, user_provided_dates, stock_info):
    # ... 前面代码不变 ...
    
    missing_periods = [p for p in expected_periods if p not in existing_dates]
    
    if not missing_periods:
        logger.info(f"[{ts_code}] 报告期数据已完整")
        return []
    
    logger.info(f"[{ts_code}] 缺失 {len(missing_periods)} 个报告期: {missing_periods}")
    
    quarter_start_map = {
        '0331': '0101', '0630': '0401', '0930': '0701', '1231': '1001'
    }
    
    # 使用连续性分组替代单一范围查询
    period_ranges = self._merge_periods_to_ranges(missing_periods)
    
    logger.info(f"[{ts_code}] 报告期分组结果: {len(period_ranges)} 个范围")
    
    tasks = []
    for range_start, range_end in period_ranges:
        start_year = range_start[:4]
        start_q = quarter_start_map[range_start[4:]]
        task_start = f"{start_year}{start_q}"
        
        tasks.append({
            'ts_code': ts_code,
            'start_date': task_start,
            'end_date': range_end
        })
        logger.info(f"  - 范围查询: {task_start} ~ {range_end}")
    
    return tasks
```

---

## 四、方案对比

| 维度 | 当前实现 | 优化方案 |
|-----|---------|---------|
| 重复下载 | 有（依赖去重） | 无 |
| API 调用次数 | 1 次 | N 次（N = 连续组数） |
| 数据传输量 | 可能冗余 | 精确 |
| 代码复杂度 | 简单 | 略增 |

### 典型场景对比

```
场景: 缺失 6 个报告期，中间有 1 个已存在

当前实现:
  - API 调用: 1 次
  - 下载数据: 包含已存在的报告期
  - 去重: removed=2

优化方案:
  - API 调用: 2 次
  - 下载数据: 精确，无重复
  - 去重: removed=0
```

---

## 五、实施建议

### 优先级

**中等优先级**

- 当前实现依赖存储层去重，不会导致数据重复
- 但会产生不必要的网络传输和 API 数据返回

### 实施步骤

1. 在 `coverage_manager.py` 中添加 `_merge_periods_to_ranges` 方法
2. 修改 `_detect_report_period_gaps` 方法使用新的分组逻辑
3. 添加单元测试验证连续性判断逻辑
4. 进行集成测试验证实际下载效果

### 测试用例

```python
def test_merge_periods_to_ranges():
    # 测试连续报告期
    periods = ['20230331', '20230630', '20230930']
    assert _merge_periods_to_ranges(periods) == [('20230331', '20230930')]
    
    # 测试有断层的报告期
    periods = ['20230331', '20230630', '20230930', '20240630', '20240930']
    assert _merge_periods_to_ranges(periods) == [
        ('20230331', '20230930'),
        ('20240630', '20240930')
    ]
    
    # 测试跨年连续
    periods = ['20230930', '20231231', '20240331']
    assert _merge_periods_to_ranges(periods) == [('20230930', '20240331')]
```

---

## 六、相关文件

| 文件 | 说明 |
|-----|------|
| `app4/core/coverage_manager.py` | 缺口检测核心代码 |
| `app4/core/coverage_manager.py#L871` | `_detect_report_period_gaps` 方法 |
| `app4/core/coverage_manager.py#L1114` | `_merge_dates_to_ranges` 方法（Type A 参考） |
