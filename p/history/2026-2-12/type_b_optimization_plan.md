# 类型 B（报告期接口）增量下载优化方案

**文档版本**: v1.0  
**日期**: 2026-02-12  
**作者**: Claude Code  
**状态**: 待实施

---

## 一、问题描述

### 1.1 当前实现的问题

**类型 B 接口**（如 `income_vip`, `balancesheet_vip`, `cashflow_vip` 等）当前的增量下载逻辑存在以下问题：

```python
# 当前代码 (coverage_manager.py: _detect_report_period_gaps)
def _detect_report_period_gaps(...):
    existing_dates = self.get_stock_existing_dates(...)
    expected_periods = self._generate_report_periods(start_date, end_date)
    
    if not existing_dates:
        return [{'ts_code': ts_code, 'start_date': start_date, 'end_date': end_date}]
    
    missing_periods = [p for p in expected_periods if p not in existing_dates]
    
    if not missing_periods:
        return []
    
    # ❌ 问题：即使只缺失部分报告期，仍返回完整范围
    return [{'ts_code': ts_code, 'start_date': start_date, 'end_date': end_date}]
```

### 1.2 实际影响

**测试案例**（income_vip 接口）：

| 步骤 | 操作 | 日期范围 | 已有数据 | 缺失数据 | 实际查询范围 | API 返回 |
|------|------|---------|---------|---------|-------------|---------|
| 1 | 第一次下载 | 2024Q1 | 无 | 20240331 | 20240101-20240331 | 1 条 |
| 2 | 第二次下载 | 2024Q1-Q2 | 20240331 | 20240630 | 20240101-20240630 | 2 条 |

**问题分析**：
- 第二次下载时，系统检测到缺失 1 个报告期（20240630）
- 但仍然查询了完整的 **2024Q1-Q2** 范围
- API 返回了 2 条数据（Q1+Q2），其中 Q1 数据已存在
- 虽然最终存储时通过去重避免了重复，但浪费了：
  - **API 调用次数**（可能触发限流）
  - **网络带宽**（传输重复数据）
  - **处理时间**（重复数据的解析和去重）

---

## 二、优化方案

### 2.1 核心思路

将类型 B 的查询方式从 **范围查询** 改为 **精确报告期查询**：

**优化前**：
```python
{'ts_code': '000001.SZ', 'start_date': '20240101', 'end_date': '20240630'}
# 查询 6 个月的完整范围
```

**优化后**：
```python
# 只查询缺失的报告期
{'ts_code': '000001.SZ', 'start_date': '20240401', 'end_date': '20240630'}
# 或者更精确：
{'ts_code': '000001.SZ', 'period': '20240630'}  # 单次查询
```

### 2.2 优化策略

对于类型 B 接口，支持两种查询模式：

| 场景 | 策略 | 参数示例 |
|------|------|---------|
| **缺失少量报告期**（≤3 个） | 逐个精确查询 | `{'period': '20240630'}` |
| **缺失大量报告期**（>3 个） | 范围查询（保持现状） | `{'start_date': '20240101', 'end_date': '20240630'}` |

---

## 三、实现细节

### 3.1 修改 `_detect_report_period_gaps` 方法

```python
def _detect_report_period_gaps(
    self,
    interface_name: str,
    ts_code: str,
    start_date: str,
    end_date: str,
    date_column: str
) -> List[Dict[str, Any]]:
    """
    类型 B：报告期缺口检测（优化版）
    
    适用于：income_vip, balancesheet_vip, cashflow_vip 等
    
    优化策略：
    1. 如果缺失报告期数量 ≤ 3，生成精确查询任务
    2. 如果缺失报告期数量 > 3，使用范围查询（保持现状）
    """
    logger.info(f"[{interface_name}/{ts_code}] 报告期缺口检测 ({start_date} ~ {end_date})")
    
    existing_dates = self.get_stock_existing_dates(interface_name, ts_code, date_column)
    expected_periods = self._generate_report_periods(start_date, end_date)
    
    if not existing_dates:
        logger.info(f"[{ts_code}] 无现有数据，需要下载 {len(expected_periods)} 个报告期")
        return [{'ts_code': ts_code, 'start_date': start_date, 'end_date': end_date}]
    
    missing_periods = [p for p in expected_periods if p not in existing_dates]
    
    if not missing_periods:
        logger.info(f"[{ts_code}] 报告期数据已完整")
        return []
    
    logger.info(f"[{ts_code}] 缺失 {len(missing_periods)} 个报告期: {missing_periods}")
    
    # ✅ 优化：根据缺失数量选择查询策略
    MAX_PRECISE_QUERIES = 3  # 最多 3 个精确查询
    
    if len(missing_periods) <= MAX_PRECISE_QUERIES:
        # 策略 1：精确查询每个缺失的报告期
        # 根据 date_column 选择参数名
        if date_column == 'end_date':
            # 使用 end_date 作为查询参数
            return [
                {
                    'ts_code': ts_code,
                    'start_date': p,  # 报告期开始日期
                    'end_date': p     # 报告期结束日期（同一天）
                }
                for p in missing_periods
            ]
        elif date_column == 'period':
            # 使用 period 作为查询参数
            return [
                {
                    'ts_code': ts_code,
                    'period': p
                }
                for p in missing_periods
            ]
        else:
            # 默认使用范围查询
            pass
    
    # 策略 2：范围查询（缺失较多时，减少 API 调用次数）
    # 计算最小覆盖范围
    min_period = min(missing_periods)
    max_period = max(missing_periods)
    
    return [{
        'ts_code': ts_code,
        'start_date': min_period,
        'end_date': max_period
    }]
```

### 3.2 处理多个 Gap Task 的下载逻辑

在 `downloader.py` 中，当 `gap_tasks` 包含多个任务时，需要循环下载：

```python
# 已有实现（在 _download_single_stock 方法中）
if gap_tasks:
    logger.info(f"Downloading {len(gap_tasks)} gap tasks for stock {stock['ts_code']}")
    all_stock_data = []
    
    for gap_task in gap_tasks:
        task_params = stock_params.copy()
        task_params.update(gap_task)
        
        # ... 下载逻辑 ...
        task_data = executor.execute(...)
        if task_data:
            all_stock_data.extend(task_data)
    
    stock_data = all_stock_data
```

**该逻辑已实现**，无需额外修改。

---

## 四、预期效果

### 4.1 优化前后对比

**场景**：已下载 2024Q1 数据，现在需要下载 2024Q2 数据

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| **查询范围** | 2024Q1-Q2（6个月） | 2024Q2（3个月） | ↓ 50% |
| **API 返回数据量** | 2 条（Q1+Q2） | 1 条（Q2） | ↓ 50% |
| **网络传输** | 2 条数据 | 1 条数据 | ↓ 50% |
| **去重处理** | 需要 | 不需要 | ↓ 100% |
| **API 调用次数** | 1 次 | 1 次 | - |

### 4.2 更大场景的优化

**场景**：已下载 2020-2023 年共 16 个季度数据，现在需要下载 2024Q1 数据

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| **查询范围** | 2020Q1-2024Q1（17个季度） | 2024Q1（1个季度） | ↓ 94% |
| **API 返回数据量** | 17 条 | 1 条 | ↓ 94% |

### 4.3 边界情况处理

| 场景 | 处理方式 | 说明 |
|------|---------|------|
| **缺失 1-3 个报告期** | 精确查询每个缺失期 | 最优策略 |
| **缺失 4+ 个报告期** | 范围查询最小覆盖区间 | 减少 API 调用次数 |
| **全部缺失** | 范围查询整个区间 | 保持现状 |
| **全部存在** | 跳过下载 | 已有逻辑 |

---

## 五、实施步骤

### Step 1: 修改 `coverage_manager.py`

```bash
# 文件路径
/home/quan/testdata/aspipe_v4/app4/core/coverage_manager.py

# 修改方法
_detect_report_period_gaps()
```

### Step 2: 添加配置参数（可选）

可以在接口配置中添加参数，控制精确查询的阈值：

```yaml
# app4/config/interfaces/income_vip.yaml
duplicate_detection:
  enabled: true
  date_column: "end_date"
  stock_level_detection: true
  max_precise_queries: 3  # 最多 3 个精确查询，超过则使用范围查询
```

### Step 3: 测试验证

```bash
# 测试场景 1：缺失 1 个报告期
cd /home/quan/testdata/aspipe_v4
python app4/main.py --update --interface income_vip \
  --ts_code 000001.SZ --start_date 20240101 --end_date 20240331

python app4/main.py --update --interface income_vip \
  --ts_code 000001.SZ --start_date 20240101 --end_date 20240630

# 验证：第二次应该只查询 2024Q2 范围（或更精确的范围）
```

---

## 六、风险评估

### 6.1 潜在问题

| 问题 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| API 不支持单日期查询 | 低 | 高 | 测试验证每个接口 |
| 多任务下载增加延迟 | 中 | 低 | 限制最大精确查询数 |
| 代码复杂度增加 | 中 | 低 | 详细注释和测试 |

### 6.2 兼容性

- ✅ **向后兼容**：优化不改变接口，仅调整查询参数
- ✅ **配置兼容**：新增配置参数有默认值
- ✅ **数据兼容**：返回数据格式不变

---

## 七、总结

### 优化价值

1. **减少 API 调用负载**：避免传输重复数据
2. **提升下载速度**：减少网络传输和处理时间
3. **降低限流风险**：减少不必要的 API 调用
4. **精确控制**：只获取真正需要的数据

### 建议优先级

**高优先级**：建议尽快实施，特别是对于高频下载的场景（如每日增量更新）。

### 后续优化

1. 可以根据实际 API 性能数据调整 `MAX_PRECISE_QUERIES` 阈值
2. 可以添加缓存策略，避免重复检测缺口
3. 可以支持异步并行下载多个缺口任务

---

**文档结束**
