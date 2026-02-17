# Type B 报告期缺口检测 - API 参数问题分析

## 一、问题发现

### 背景

在分析 `outputb` 目录的测试输出时，发现文档 [Type_B报告期缺口检测进一步优化方案.md](./Type_B报告期缺口检测进一步优化方案.md) 第 56 行的假设与实际 API 行为不一致。

### 文档假设（错误）

```
查询范围: 20230101 ~ 20230930
API 返回: 20230331, 20230630, 20230930, 20231231
                                        ↑
                              这个已经存在了！
```

文档假设：`start_date=20230101, end_date=20230930` 会返回报告期 20231231。

### 实际日志验证

从 `income_vip_2_output.txt` 可以看到：

```
范围查询: 20230101 ~ 20230930
Downloaded 5 records for income_vip
Deduplication completed: input=5, output=5, removed=0
```

**removed=0 说明 API 没有返回已存在的 20231231**，因为 20231231 > 20230930。

---

## 二、Tushare API 参数说明

### 官方文档定义

根据 Tushare Pro 官方文档（https://tushare.pro/document/2?doc_id=33）：

| 参数 | 类型 | 必选 | 描述 |
|-----|------|-----|------|
| ts_code | str | Y | 股票代码 |
| ann_date | str | N | 公告日期（YYYYMMDD格式） |
| f_ann_date | str | N | 实际公告日期 |
| **start_date** | str | N | **公告日开始日期** |
| **end_date** | str | N | **公告日结束日期** |
| period | str | N | 报告期(每个季度最后一天的日期，如20171231表示年报) |

### 关键发现

**`start_date` 和 `end_date` 是按公告日期（ann_date）过滤，不是按报告期（end_date）过滤！**

---

## 三、问题分析

### 3.1 API 行为与预期不一致

| 查询参数 | 预期行为（错误假设） | 实际行为 |
|---------|-------------------|---------|
| `start_date=20240101, end_date=20240630` | 返回报告期在 2024Q1-Q2 的数据 | 返回 **ann_date** 在 2024-01-01 ~ 2024-06-30 的数据，包括 20231231 年报（因为年报通常在 4 月公告） |
| `start_date=20230101, end_date=20230930` | 返回报告期在 2023Q1-Q3 的数据 | 返回 **ann_date** 在 2023-01-01 ~ 2023-09-30 的数据，**不会**返回 20231231（因为 2023 年报在 2024 年 4 月公告） |

### 3.2 实际日志验证

#### 第一次下载

```
参数: start_date=20240101, end_date=20240630
返回: 2 records
存储: income_vip_20231231_20240331_...parquet
```

**分析**：返回了 20231231 和 20240331 两个报告期的数据，因为：
- 2023 年报（报告期 20231231）的公告日期通常在 2024 年 4 月
- 2024 一季报（报告期 20240331）的公告日期通常在 2024 年 4 月

#### 第二次下载

```
查询1: start_date=20230101, end_date=20230930
返回: 5 records, removed=0

查询2: start_date=20240401, end_date=20241231
返回: 3 records, removed=1
```

**分析**：
- 查询1 没有返回 20231231，因为 2023 年报的公告日期不在 2023-01-01 ~ 2023-09-30 范围内
- 查询2 返回了重复数据，因为公告日期在 2024-04-01 ~ 2024-12-31 范围内的数据可能与第一次下载重叠

### 3.3 公告日期与报告期的关系

| 报告期 | 典型公告日期范围 | 说明 |
|-------|-----------------|------|
| 20231231（年报） | 2024-01-01 ~ 2024-04-30 | 年报通常在次年 1-4 月公告 |
| 20240331（一季报） | 2024-04-01 ~ 2024-04-30 | 一季报通常在 4 月公告 |
| 20240630（半年报） | 2024-07-01 ~ 2024-08-31 | 半年报通常在 7-8 月公告 |
| 20240930（三季报） | 2024-10-01 ~ 2024-10-31 | 三季报通常在 10 月公告 |

---

## 四、影响范围

### 4.1 当前实现的问题

当前缺口检测逻辑假设 `start_date`/`end_date` 是报告期范围：

```python
# coverage_manager.py 中的逻辑
quarter_start_map = {
    "0331": "0101",
    "0630": "0401",
    "0930": "0701",
    "1231": "1001",
}

for range_start, range_end in period_ranges:
    start_year = range_start[:4]
    start_q = quarter_start_map.get(range_start[4:], "0101")
    task_start = f"{start_year}{start_q}"
    tasks.append({"ts_code": ts_code, "start_date": task_start, "end_date": range_end})
```

这个逻辑将缺失报告期转换为日期范围，但 API 实际上是按公告日期过滤，不是按报告期过滤。

### 4.2 可能的问题场景

1. **漏下载数据**：某些报告期的公告日期可能不在预期的日期范围内
2. **重复下载**：不同日期范围的查询可能返回相同报告期的数据
3. **数据不完整**：依赖去重机制过滤，但可能遗漏某些数据

---

## 五、解决方案：基于公告日期规律的优化方案

### 5.1 核心思路

```
缺失检测：基于报告期（end_date）
下载参数：基于放宽后的公告日期范围（ann_date）
公告日期重合：使用并集合并查询
```

### 5.2 报告期与公告日期的映射关系

#### 基础映射（法定期限）

| 报告期类型 | 报告期后缀 | 法定公告期限 | 基础公告日期范围 |
|-----------|-----------|-------------|-----------------|
| 年报 | 1231 | 次年4月30日前 | 次年01-01 ~ 次年04-30 |
| 一季报 | 0331 | 4月30日前 | 04-01 ~ 04-30 |
| 半年报 | 0630 | 8月31日前 | 07-01 ~ 08-31 |
| 三季报 | 0930 | 10月31日前 | 10-01 ~ 10-31 |

#### 放宽后的映射（考虑延迟公告）

| 报告期类型 | 放宽公告日期范围 | 放宽幅度 |
|-----------|-----------------|---------|
| 年报 | 次年01-01 ~ 次年05-30 | +30天 |
| 一季报 | 04-01 ~ 05-30 | +30天 |
| 半年报 | 07-01 ~ 09-30 | +30天 |
| 三季报 | 10-01 ~ 11-30 | +30天 |

### 5.3 公告日期范围重合分析

#### 重合情况

| 报告期组合 | 公告日期范围 | 重合区间 |
|-----------|-------------|---------|
| 年报(20231231) + 一季报(20240331) | 2024-01-01~05-15 与 2024-04-01~05-15 | **2024-04-01 ~ 2024-05-15** |
| 半年报(20240630) + 三季报(20240930) | 2024-07-01~09-15 与 2024-10-01~11-15 | 无重合 |
| 年报(20231231) + 半年报(20240630) | 2024-01-01~05-15 与 2024-07-01~09-15 | 无重合 |

**关键发现**：年报和次年一季报的公告日期范围有重合！

### 5.4 实现方案

#### 步骤1：缺失检测（基于报告期）

```python
def detect_missing_periods(existing_periods, expected_periods):
    return [p for p in expected_periods if p not in existing_periods]
```

#### 步骤2：报告期转公告日期范围

```python
def period_to_ann_date_range(period: str, buffer_days: int = 30) -> tuple:
    """
    将报告期转换为放宽后的公告日期范围
    
    Args:
        period: 报告期，如 "20231231"
        buffer_days: 放宽天数，可配置，默认30天
    
    Returns:
        (start_date, end_date) 公告日期范围
    """
    year = int(period[:4])
    suffix = period[4:]
    
    # 放宽后的公告日期范围
    range_map = {
        "0331": (f"{year}0401", f"{year}0530"),   # 一季报
        "0630": (f"{year}0701", f"{year}0930"),   # 半年报
        "0930": (f"{year}1001", f"{year}1130"),   # 三季报
        "1231": (f"{year+1}0101", f"{year+1}0530"), # 年报（次年公告）
    }
    
    return range_map.get(suffix)
```

#### 步骤3：合并重合的公告日期范围

```python
def merge_ann_date_ranges(missing_periods: List[str]) -> List[tuple]:
    """
    将缺失报告期转换为公告日期范围，并合并重合的范围
    
    Args:
        missing_periods: 缺失的报告期列表
    
    Returns:
        合并后的公告日期范围列表 [(start_date, end_date, covered_periods), ...]
    """
    # 1. 每个报告期转换为公告日期范围
    period_ranges = []
    for period in missing_periods:
        ann_range = period_to_ann_date_range(period)
        if ann_range:
            period_ranges.append((ann_range[0], ann_range[1], [period]))
    
    # 2. 按开始日期排序
    period_ranges.sort(key=lambda x: x[0])
    
    # 3. 合并重合的范围
    merged = []
    for start, end, periods in period_ranges:
        if merged and start <= merged[-1][1]:
            # 有重合，合并
            prev_start, prev_end, prev_periods = merged[-1]
            merged[-1] = (
                prev_start,
                max(prev_end, end),
                prev_periods + periods
            )
        else:
            merged.append((start, end, periods))
    
    return merged
```

#### 步骤4：生成下载任务

```python
def generate_download_tasks(ts_code: str, missing_periods: List[str]) -> List[dict]:
    """
    生成下载任务
    
    Args:
        ts_code: 股票代码
        missing_periods: 缺失的报告期列表
    
    Returns:
        下载任务列表
    """
    merged_ranges = merge_ann_date_ranges(missing_periods)
    
    tasks = []
    for start_date, end_date, covered_periods in merged_ranges:
        tasks.append({
            "ts_code": ts_code,
            "start_date": start_date,
            "end_date": end_date,
            "_expected_periods": covered_periods,  # 用于日志和验证
        })
    
    return tasks
```

### 5.5 示例演示

#### 输入

```
缺失报告期: ['20231231', '20240331', '20240630', '20240930']
```

#### 步骤1：转换为公告日期范围

```
20231231 → 20240101 ~ 20240530 (年报)
20240331 → 20240401 ~ 20240530 (一季报)
20240630 → 20240701 ~ 20240930 (半年报)
20240930 → 20241001 ~ 20241130 (三季报)
```

#### 步骤2：合并重合范围

```
范围1: 20240101 ~ 20240530 (年报)
范围2: 20240401 ~ 20240530 (一季报) ← 与范围1重合
范围3: 20240701 ~ 20240930 (半年报)
范围4: 20241001 ~ 20241130 (三季报)

合并后:
  查询1: 20240101 ~ 20240530 → 覆盖 [20231231, 20240331]
  查询2: 20240701 ~ 20240930 → 覆盖 [20240630]
  查询3: 20241001 ~ 20241130 → 覆盖 [20240930]
```

#### 输出

```python
[
    {"ts_code": "000001.SZ", "start_date": "20240101", "end_date": "20240530", "_expected_periods": ["20231231", "20240331"]},
    {"ts_code": "000001.SZ", "start_date": "20240701", "end_date": "20240930", "_expected_periods": ["20240630"]},
    {"ts_code": "000001.SZ", "start_date": "20241001", "end_date": "20241130", "_expected_periods": ["20240930"]},
]
```

### 5.6 方案优势

| 维度 | 说明 |
|-----|------|
| 精确性 | 缺失检测基于报告期，不会遗漏 |
| 效率 | 公告日期范围合并，减少 API 调用次数 |
| 容错性 | 放宽公告日期范围，覆盖延迟公告情况 |
| 可验证 | 每个查询记录预期覆盖的报告期，便于验证 |

### 5.7 注意事项

1. **去重机制仍需保留**：由于放宽了公告日期范围，可能返回额外数据，需要去重
2. **边界情况**：跨年报告期需要特别注意年份计算
3. **延迟公告**：极端延迟情况（如超过 30 天）可能需要额外处理

---

## 六、结论

1. **文档假设错误**：API 的 `start_date`/`end_date` 是按公告日期过滤，不是按报告期过滤
2. **解决方案**：
   - 缺失检测基于报告期（end_date）
   - 下载参数使用放宽后的公告日期范围
   - 合并重合的公告日期范围，减少 API 调用
3. **核心改进**：年报和一季报公告日期重合时，使用并集合并为一次查询

---

## 七、相关文件

| 文件 | 说明 |
|-----|------|
| [Type_B报告期缺口检测进一步优化方案.md](./Type_B报告期缺口检测进一步优化方案.md) | 原优化方案文档 |
| `p/interface4/outputb/income_vip_1_output.txt` | 第一次下载日志 |
| `p/interface4/outputb/income_vip_2_output.txt` | 第二次下载日志 |
| `app4/core/coverage_manager.py` | 缺口检测核心代码 |
| `app4/config/interfaces/income_vip.yaml` | income_vip 接口配置 |

---

文档日期: 2026-02-17
