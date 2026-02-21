# Type B 报告期缺口检测 - 进一步优化方案

## 一、现状

### 当前实现

Type B 接口（报告期接口）已实现基于连续性的分组查询：

```
第一次下载: 20240101 ~ 20240630
  → 获取报告期: 20231231, 20240331
  → 存储: 2 条记录

第二次下载: 20230101 ~ 20241231
  → 缺失报告期: ['20230331', '20230630', '20230930', '20240630', '20240930', '20241231']
  → 连续性分组: 2 个范围
    - 范围查询: 20230101 ~ 20230930
    - 范围查询: 20240401 ~ 20241231
  → 去重: removed=1
```

### 当前代码位置

- 文件: `app4/core/coverage_manager.py`
- 方法: `_detect_report_period_gaps` (行 1007)
- 分组方法: `_merge_periods_to_ranges` (行 1267)

---

## 二、问题

### 问题描述

当前实现只考虑了**缺失报告期之间的连续性**，但**没有考虑已存在报告期作为断点**。

### 问题示例

```
已存在报告期: 20231231, 20240331
缺失报告期:   20230331, 20230630, 20230930, 20240630, 20240930, 20241231

当前分组结果:
  组1: 20230331 ~ 20230930 (连续)
  组2: 20240630 ~ 20241231 (连续)

生成的查询:
  查询1: start_date=20230101, end_date=20230930
  查询2: start_date=20240401, end_date=20241231
```

### 问题分析

**查询1 的问题：**
```
查询范围: 20230101 ~ 20230930
API 返回: 20230331, 20230630, 20230930, 20231231
                                        ↑
                              这个已经存在了！
```

API 的 `start_date + end_date` 范围查询会返回区间内**所有报告期**，包括：
- 20230331, 20230630, 20230930（缺失，需要下载）
- 20231231（已存在，不需要下载）

**结果：** 仍然会下载已存在的 20231231，依赖去重机制过滤。

### 影响范围

| 接口 | removed 数量 | 原因 |
|------|-------------|------|
| income_vip | 1 | 查询范围包含已存在的 20231231 |
| balancesheet_vip | 2 | 查询范围包含已存在的报告期 |
| cashflow_vip | 1 | 同上 |
| 其他 Type B 接口 | 类似 | 同上 |

---

## 三、方案

### 方案目标

**完全避免重复下载**，实现 `removed=0`。

### 核心思路

将**已存在的报告期作为断点**，查询范围精确限制在两个断点之间。

### 方案详解

#### 1. 识别断点

```
已存在报告期（断点）: 20231231, 20240331
缺失报告期: 20230331, 20230630, 20230930, 20240630, 20240930, 20241231
```

#### 2. 按断点分组

```
断点将时间轴分成区间:

区间1: < 20231231
  缺失: 20230331, 20230630, 20230930
  
区间2: 20231231 ~ 20240331
  缺失: 无
  
区间3: > 20240331
  缺失: 20240630, 20240930, 20241231
```

#### 3. 精确查询范围

关键：**查询的 end_date 应该是断点的前一个季度，而不是缺失报告期的最后一个**

```
组1缺失: 20230331, 20230630, 20230930
  下一个断点: 20231231
  断点前一季度: 20230930
  查询范围: 20230101 ~ 20230930  ✓ 正好到缺失的最后一个

组2缺失: 20240630, 20240930, 20241231
  上一个断点: 20240331
  断点后一季度: 20240630
  查询范围: 20240401 ~ 20241231  ✓ 从缺失的第一个开始
```

#### 4. 特殊情况处理

**情况A：缺失报告期紧邻断点**

```
已存在: 20240331
缺失: 20240630, 20240930

断点 20240331 的下一季度是 20240630，正好是缺失的第一个
查询范围: 20240401 ~ 20240930  ✓ 不包含 20240331
```

**情况B：缺失报告期跨越断点**

```
已存在: 20230630
缺失: 20230331, 20230930, 20231231

分组:
  组1: 20230331 (断点前)
  组2: 20230930, 20231231 (断点后)

查询1: 20230101 ~ 20230331  ✓ 不包含 20230630
查询2: 20230701 ~ 20231231  ✓ 不包含 20230630
```

### 代码实现

#### 新增方法: `_merge_periods_to_ranges_with_breakpoints`

```python
def _merge_periods_to_ranges_with_breakpoints(
    self, missing_periods: List[str], existing_periods: List[str]
) -> List[tuple]:
    """
    将缺失报告期按连续性分组，以已存在的报告期为断点
    
    Args:
        missing_periods: 缺失的报告期列表
        existing_periods: 已存在的报告期列表（作为断点）
    
    Returns:
        连续报告期的范围列表，每个元素为 (range_start, range_end)
    """
    if not missing_periods:
        return []
    
    if not existing_periods:
        return self._merge_periods_to_ranges(missing_periods)
    
    sorted_missing = sorted(missing_periods)
    sorted_existing = sorted(existing_periods)
    
    quarter_order = {"0331": 1, "0630": 2, "0930": 3, "1231": 4}
    
    def get_prev_quarter(period):
        """获取前一个季度"""
        year = int(period[:4])
        q = quarter_order.get(period[4:], 0)
        if q == 1:
            return f"{year - 1}1231"
        elif q == 2:
            return f"{year}0331"
        elif q == 3:
            return f"{year}0630"
        elif q == 4:
            return f"{year}0930"
        return None
    
    def get_next_quarter(period):
        """获取后一个季度"""
        year = int(period[:4])
        q = quarter_order.get(period[4:], 0)
        if q == 1:
            return f"{year}0630"
        elif q == 2:
            return f"{year}0930"
        elif q == 3:
            return f"{year}1231"
        elif q == 4:
            return f"{year + 1}0331"
        return None
    
    def is_continuous(prev, curr):
        """判断两个报告期是否连续"""
        curr_year = curr[:4]
        prev_year = prev[:4]
        curr_q = quarter_order.get(curr[4:], 0)
        prev_q = quarter_order.get(prev[4:], 0)
        
        return (curr_year == prev_year and curr_q == prev_q + 1) or (
            int(curr_year) == int(prev_year) + 1 and curr_q == 1 and prev_q == 4
        )
    
    def has_breakpoint_between(prev, curr):
        """判断两个缺失报告期之间是否有断点"""
        for bp in sorted_existing:
            if prev < bp < curr:
                return True
        return False
    
    ranges = []
    i = 0
    while i < len(sorted_missing):
        group_start = sorted_missing[i]
        group_end = sorted_missing[i]
        
        j = i + 1
        while j < len(sorted_missing):
            curr = sorted_missing[j]
            prev = sorted_missing[j - 1]
            
            if is_continuous(prev, curr) and not has_breakpoint_between(prev, curr):
                group_end = curr
                j += 1
            else:
                break
        
        ranges.append((group_start, group_end))
        i = j
    
    return ranges
```

#### 修改 `_detect_report_period_gaps`

```python
# 原代码
period_ranges = self._merge_periods_to_ranges(missing_periods)

# 修改为
period_ranges = self._merge_periods_to_ranges_with_breakpoints(
    missing_periods, existing_dates
)
```

### 效果对比

| 维度 | 当前实现 | 优化方案 |
|-----|---------|---------|
| removed 数量 | 1-2 | 0 |
| API 调用次数 | N 次 | N 次（相同） |
| 数据传输量 | 有冗余 | 精确 |
| 代码复杂度 | 中等 | 略增 |

### 测试用例

```python
def test_merge_with_breakpoints():
    # 测试1：有断点的分组
    missing = ['20230331', '20230630', '20230930', '20240630', '20240930', '20241231']
    existing = ['20231231', '20240331']
    result = _merge_periods_to_ranges_with_breakpoints(missing, existing)
    assert result == [
        ('20230331', '20230930'),
        ('20240630', '20241231')
    ]
    
    # 测试2：断点在缺失报告期中间
    missing = ['20230331', '20230930', '20231231']
    existing = ['20230630']
    result = _merge_periods_to_ranges_with_breakpoints(missing, existing)
    assert result == [
        ('20230331', '20230331'),
        ('20230930', '20231231')
    ]
    
    # 测试3：无断点
    missing = ['20230331', '20230630', '20230930']
    existing = []
    result = _merge_periods_to_ranges_with_breakpoints(missing, existing)
    assert result == [('20230331', '20230930')]
```

---

## 四、实施建议

### 优先级

**高优先级**

- 当前实现依赖去重机制，虽然不会导致数据重复，但会产生不必要的网络传输
- 对于大数据量场景，减少 API 返回数据量可以显著提升性能

### 实施步骤

1. 在 `coverage_manager.py` 中添加 `_merge_periods_to_ranges_with_breakpoints` 方法
2. 修改 `_detect_report_period_gaps` 方法调用新方法
3. 添加单元测试验证断点分组逻辑
4. 运行 `test_type_b_interfaces.sh` 验证 removed=0

### 验证方法

```bash
# 运行测试脚本
/home/quan/testdata/aspipe_v4/p/interface4/test_type_b_interfaces.sh

# 检查输出日志，确认 removed=0
grep "removed=" /home/quan/testdata/aspipe_v4/p/interface4/outputb/*_2_output.txt
```

---

## 五、相关文件

| 文件 | 说明 |
|-----|------|
| `app4/core/coverage_manager.py` | 缺口检测核心代码 |
| `p/2026-2-16/Type_B报告期缺口检测优化方案.md` | 第一阶段优化方案 |
| `p/2026-2-16/Type_B报告期缺口检测修复说明.txt` | 第一阶段修复说明 |
| `p/interface4/test_type_b_interfaces.sh` | Type B 接口测试脚本 |

---

文档日期: 2026-02-17
