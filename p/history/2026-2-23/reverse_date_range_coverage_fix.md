# reverse_date_range 模式覆盖率检测修复方案

## 问题描述

`reverse_date_range` 模式的接口（如 `block_trade`）在增量更新时，重复下载已存在的数据，无法正确跳过。

### 问题现象

```bash
# 第一次运行
python app4/main.py --update --interface block_trade --start_date 20260115 --end_date 20260201
# Downloaded 2243 条记录
# Found 603 duplicate records
# 最终写入 1640 条

# 第二次运行（相同日期范围）
python app4/main.py --update --interface block_trade --start_date 20260115 --end_date 20260201
# 又 Downloaded 2243 条记录  ← 没有跳过！
# Deduplication: input=1640, output=0, removed=1640
# All records already exist, skipping save
```

## 根本原因分析（经调试确认）

### 问题发现过程

通过添加调试日志，发现以下关键信息：

```
[Coverage] Window dates applied: 20260130 ~ 20260130 for block_trade
No existing data found for block_trade in range 20260130-20260130
```

**窗口日期已正确传递**，但 `read_interface_data` 返回了空数据！

### 真正的问题：storage.py 文件名解析错误

问题在 `storage.py` 的 `read_interface_data` 方法中的文件名过滤逻辑。

#### 文件名格式

```
{interface_name}_{start_date}_{end_date}_{timestamp}_{uuid}.parquet
```

例如：`block_trade_20260115_20260130_1771906674329_26598015.parquet`

#### 解析逻辑错误

```python
# storage.py 第 393-405 行
parts = f.split('_')
if len(parts) >= 4 and start_date and end_date:
    # 假设 parts[1] 是 min_date, parts[2] 是 max_date
    f_min, f_max = parts[1], parts[2]
    if f_min != "nodate":
        if f_max < start_date or f_min > end_date:
            continue
```

#### 实际解析结果

```
文件名: block_trade_20260115_20260130_1771906674329_26598015.parquet

parts = ['block', 'trade', '20260115', '20260130', '1771906674329', '26598015.parquet']

错误解析:
  f_min = parts[1] = 'trade'      ← 应该是 '20260115'
  f_max = parts[2] = '20260115'   ← 应该是 '20260130'

正确解析应该是:
  f_min = '20260115' (真正的 start_date)
  f_max = '20260130' (真正的 end_date)
```

#### 导致的后果

```python
# 查询 20260130 的数据时
if f_max < start_date:  # "20260115" < "20260130" → True
    continue  # 跳过该文件！

# 所有文件都被跳过，返回空数据
# 覆盖率检查认为没有数据，不跳过下载
```

### 为什么 cyq_perf 能正确去重？

`cyq_perf` 配置了 `is_date_anchor: true`，但其数据文件名同样包含下划线（`cyq_perf_xxx.parquet`）。理论上也应该受此问题影响。

可能的原因：
1. `cyq_perf` 的数据文件名格式不同
2. 或者之前测试时数据文件名格式不同

## 影响范围

**所有接口名称包含下划线的接口都会受影响**，例如：
- `block_trade`
- `cyq_perf`
- `daily_basic`
- `moneyflow_ind_dc`
- `moneyflow_ind_ths`
- `moneyflow_mkt_dc`
- `moneyflow_cnt_ths`
- `moneyflow_ths`
- `stk_managers`
- `stock_basic`
- `share_float`
- `stk_holdertrade`

以及更多。

## 修复方案

### 方案：修改 storage.py 的文件名解析逻辑

#### 修改位置

`app4/core/storage.py` 第 385-410 行

#### 修改前

```python
for f in all_files:
    if not f.endswith('.parquet'): continue

    # 简单过滤：如果提供了日期范围，且文件名包含日期信息，则进行过滤
    # 文件名格式: name_start_end_ts_uuid.parquet
    parts = f.split('_')
    if len(parts) >= 4 and start_date and end_date:
        # 这是一个简化的过滤逻辑，实际可能需要更健壮的解析
        # 假设 parts[1] 是 min_date, parts[2] 是 max_date
        f_min, f_max = parts[1], parts[2]
        if f_min != "nodate":
            # 检查范围重叠
            if f_max < start_date or f_min > end_date:
                continue

    files_to_read.append(os.path.join(dir_path, f))
```

#### 修改后

```python
for f in all_files:
    if not f.endswith('.parquet'): continue

    # 简单过滤：如果提供了日期范围，且文件名包含日期信息，则进行过滤
    # 文件名格式: {interface_name}_{start_date}_{end_date}_{timestamp}_{uuid}.parquet
    # 注意：interface_name 可能包含下划线，所以需要从后往前解析
    
    if start_date and end_date:
        # 从文件名中提取日期范围
        # 格式: xxx_YYYYMMDD_YYYYMMDD_ts_uuid.parquet
        # 使用正则表达式匹配日期模式
        import re
        # 匹配两个连续的8位数字（日期格式）
        date_pattern = r'_(\d{8})_(\d{8})_'
        match = re.search(date_pattern, f)
        if match:
            f_min, f_max = match.group(1), match.group(2)
            # 检查范围重叠
            if f_max < start_date or f_min > end_date:
                continue

    files_to_read.append(os.path.join(dir_path, f))
```

#### 关键改动

1. **使用正则表达式解析日期**：避免接口名称中下划线的干扰
2. **匹配模式**：`_(\d{8})_(\d{8})_` 匹配两个连续的8位数字日期
3. **向后兼容**：如果文件名不匹配日期模式，仍然会读取文件

## 验证步骤

### 1. 修复 storage.py 后测试

```bash
# 第一次运行
python app4/main.py --update --interface block_trade --start_date 20260115 --end_date 20260201

# 第二次运行（应该跳过所有已存在的日期）
python app4/main.py --update --interface block_trade --start_date 20260115 --end_date 20260201

# 预期：第二次运行应该跳过所有窗口
```

### 2. 调试日志验证

```bash
python app4/main.py --update --interface block_trade --start_date 20260115 --end_date 20260201 --log-level DEBUG 2>&1 | grep -i "coverage\|existing"
```

预期看到类似：
```
[Coverage] Window dates applied: 20260130 ~ 20260130 for block_trade
Coverage for block_trade (20260130-20260130): 100.00% (1/1)
Skipping request due to coverage check
```

## 补充说明

### 为什么之前的修复没有生效？

之前修改了 `pagination_executor.py` 正确传递窗口日期，但 `storage.py` 的文件名解析错误导致读取不到数据，所以覆盖率检查始终返回"无数据"。

### 为什么之前认为 pagination_executor.py 有问题？

最初分析时，发现 `_time_window` 被 `clean_params` 过滤掉了。这确实是一个逻辑问题，但不是导致重复下载的直接原因。直接原因是 `storage.py` 的文件名解析错误。

### 两个修复都需要吗？

**是的**，两个修复都是必要的：

1. **pagination_executor.py 修复**：确保传递正确的窗口日期给覆盖率检查
2. **storage.py 修复**：确保能正确读取已有数据

只有两个修复都完成，覆盖率检查才能正常工作。

## 相关文件

- `app4/core/storage.py` - **主要问题**：文件名解析错误
- `app4/core/pagination_executor.py` - 次要问题：窗口日期传递（已修复）
- `app4/core/coverage_manager.py` - 覆盖率检查逻辑
- `app4/core/pagination.py` - 分页参数生成，`_time_window` 的来源