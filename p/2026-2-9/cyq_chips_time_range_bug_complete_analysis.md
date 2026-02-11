# cyq_chips time_range 配置失效问题 - 完整分析报告

## 执行摘要

本文档详细分析了 `cyq_chips` 接口的 `time_range` 配置失效问题。核心发现是：**单股票下载和多股票下载在处理 `time_range` 配置时存在根本差异**，原因是 `app4/main.py` 中硬编码的 `_stock_full_history` 参数绕过了 `PaginationComposer`，导致 `time_range` 配置在多股票下载模式下完全失效。

## 问题现象

### 问题描述

在执行以下命令时：
```bash
/root/miniforge3/envs/get/bin/python app4/main.py --interface cyq_chips
```

即使 `app4/config/interfaces/cyq_chips.yaml` 中配置了：
```yaml
pagination:
  enabled: true
  mode: stock_loop
  time_range:
    enabled: true
    window: 10d
    stop_on_empty: 90
```

系统仍然以"单请求全历史"模式下载数据，**不会**按 10 天窗口分割请求。

### 日志证据

**问题日志（多股票下载）**:
```
2026-02-10 20:45:25,977 - __main__ - INFO - Non-update mode: fetching full history per stock for cyq_chips (single request per stock)
2026-02-10 20:45:26,065 - core.downloader - INFO - Downloading data for stock 300506.SZ, params: {'_stock_full_history': True, 'ts_code': '300506.SZ', 'start_date': '20160324'}
```

**正常日志（单股票下载）**:
```
INFO - Using stock_loop mode for cyq_chips
INFO - Downloading data for stock 000001.SZ, params: {'ts_code': '000001.SZ', 'start_date': '20240101', 'end_date': '20240110', '_time_window': ('20240101', '20240110')}
```

**关键差异**: 多股票下载时日志显示 `'_stock_full_history': True` 且没有时间窗口参数。

## 根本原因分析

### 问题代码位置

**文件**: `app4/main.py`  
**行号**: 981 (非更新模式) 和 376 (更新模式)

### 问题代码逻辑

```python
# app4/main.py:981 (非更新模式)
if not user_provided_dates and not args.ts_code:
    params = {'_stock_full_history': True}  # ❌ 问题所在
    logger.info(f"Non-update mode: fetching full history per stock for {interface_name} (single request per stock)")

# app4/main.py:376 (更新模式)
elif interface_name == 'disclosure_date' and not user_provided_dates and not args.ts_code:
    params = {'_stock_full_history': True}  # ❌ 同样问题
    logger.info(f"Fetching full history per stock for {interface_name} (single request per stock)")
```

### 执行路径详解

当执行 `python app4/main.py --interface cyq_chips` 时：

1. **参数设置**: `user_provided_dates = False`, `args.ts_code = None`
2. **问题代码**: `params = {'_stock_full_history': True}`
3. **传递给**: `PaginationExecutor.execute(base_params)`
4. **执行判断** (`app4/core/pagination_executor.py:73-85`):
```python
if base_params.get('_date_anchor_param') and self._is_stock_loop_enabled(...):
    # ...
elif base_params.get('_stock_full_history') and self._is_stock_loop_enabled(...):
    # ✅ 进入此分支！
    stock_list = context.stock_list or []
    params_list = []
    for stock in stock_list:
        p = {'ts_code': ts_code, '_stock_info': stock}
        params_list.append(p)
    # ❌ 关键: 不调用 PaginationComposer.compose()
else:
    composer = PaginationComposer(context)
    params_list = list(composer.compose(base_params))  # 被绕过
```

5. **结果**: `time_range` 配置被完全忽略

## 单股票 vs 多股票行为对比

### 执行流程差异

#### 单股票下载 (`--ts_code 000001.SZ`)

```
main()
  ↓
args.ts_code 存在 → params = {'ts_code': '000001.SZ'}
  ↓
_prepare_stock_list() → 过滤为单股票
  ↓
run_concurrent_stock_download(1个任务)
  ↓
download_single_stock(params={'ts_code': '000001.SZ'})
  ↓
PaginationExecutor.execute()
  ↓
检查:
  - _date_anchor_param? No
  - _stock_full_history? No  ✓
  ↓
PaginationComposer.compose(base_params)  ✓ 调用
  ↓
执行顺序:
  1. _apply_time_range()  ✓ (如果 enabled)
  2. _apply_stock_loop()  ✓
  ↓
生成: N个窗口 × 1股票 = N个参数
```

#### 多股票下载 (`--interface cyq_chips`)

```
main()
  ↓
args.ts_code 不存在 + user_provided_dates 不存在
  ↓
❌ params = {'_stock_full_history': True}
  ↓
_prepare_stock_list() → 全部股票 (5479只)
  ↓
run_concurrent_stock_download(5479个任务)
  ↓
download_single_stock(params={'_stock_full_history': True, 'ts_code': '000001.SZ'})
  ↓
PaginationExecutor.execute()
  ↓
检查:
  - _date_anchor_param? No
  - _stock_full_history? Yes  ✗
  ↓
**绕过** PaginationComposer.compose()  ✗
  ↓
直接生成: 1请求 × 5479股票 = 5479个参数
```

### 关键差异点

| 对比维度 | 单股票下载 | 多股票下载 |
|---------|-----------|-----------|
| **是否设置 `_stock_full_history`** | ❌ 否 | ✅ 是 |
| **是否调用 PaginationComposer** | ✅ 是 | ❌ 否 |
| **time_range 是否生效** | ✅ 生效 | ❌ 失效 |
| **参数生成逻辑** | 时间→股票 | 仅股票 |
| **请求次数 (30天/10天窗口)** | 3 次 | 5479 次 |
| **单次请求数据量** | 小 (10天) | 大 (全历史) |

### 参数生成数量对比

**假设**: 日期范围 = 30天, window = 10d, 股票数 = 5479

| 场景 | PaginationComposer? | 参数计算公式 | 参数数量 | API 请求次数 |
|------|---------------------|--------------|----------|--------------|
| 单股票 | ✅ 是 | N窗口 × 1股票 | 3 × 1 = **3** | **3** |
| 多股票 | ❌ 否 | 1请求 × 5479股票 | 1 × 5479 = **5479** | **5479** |

**差异**: 多股票模式下请求次数是单股票的 **1826 倍** (5479/3)!

### 日志对比

#### 单股票下载日志（time_range 生效）
```
INFO - Using stock_loop mode for cyq_chips
INFO - Starting concurrent download for cyq_chips with 1 stocks
INFO - Downloading data for stock 000001.SZ, params: {'ts_code': '000001.SZ', 'start_date': '20240101', 'end_date': '20240110', '_time_window': ('20240101', '20240110')}
INFO - Downloading data for stock 000001.SZ, params: {'ts_code': '000001.SZ', 'start_date': '20240111', 'end_date': '20240120', '_time_window': ('20240111', '20240120')}
INFO - Downloading data for stock 000001.SZ, params: {'ts_code': '000001.SZ', 'start_date': '20240121', 'end_date': '20240131', '_time_window': ('20240121', '20240131')}
```

#### 多股票下载日志（time_range 失效）
```
INFO - Using stock_loop mode for cyq_chips
INFO - Non-update mode: fetching full history per stock for cyq_chips (single request per stock)  # ❌ 关键提示
INFO - Starting concurrent download for cyq_chips with 5479 stocks
INFO - Downloading data for stock 300506.SZ, params: {'_stock_full_history': True, 'ts_code': '300506.SZ', 'start_date': '20160324'}  # ❌ 没有时间窗口
INFO - Downloading data for stock 002539.SZ, params: {'_stock_full_history': True, 'ts_code': '002539.SZ', 'start_date': '20110118'}
...
```

### 代码调用栈对比

#### 单股票调用栈
```python
download_single_stock()
  ↓
PaginationExecutor.execute(base_params={'ts_code': '000001.SZ'})
  ↓
# 进入 else 分支
composer = PaginationComposer(context)
params_list = list(composer.compose(base_params))  # ✅ 调用
  ↓
compose()
  ↓
_apply_time_range(params_stream)  # ✅ 执行
_apply_stock_loop(params_stream)   # ✅ 执行
```

#### 多股票调用栈
```python
download_single_stock()
  ↓
PaginationExecutor.execute(base_params={'_stock_full_history': True, 'ts_code': '000001.SZ'})
  ↓
# 进入 _stock_full_history 分支
# 直接返回 params_list
# ❌ 不调用 PaginationComposer
```

## 影响范围

### 受影响的接口

所有满足以下条件的接口：
- `pagination.mode: stock_loop`
- `time_range.enabled: true` (配置正确)
- 用户未提供 `--start_date`/`--end_date` 参数
- 用户未指定 `--ts_code` 参数

### 受影响的功能

1. **time_range.window**: 窗口分割失效
2. **time_range.stop_on_empty**: 提前停止逻辑失效
3. **性能**: 单次请求数据量过大，易超时
4. **内存**: 处理大批量数据，内存占用高
5. **稳定性**: 大请求失败率高

## 修复方案

### 配置驱动方案（推荐）

**修改文件**: `app4/core/pagination_executor.py`

**修改位置**: 第77-85行

#### 方案描述
在 `pagination` 配置中增加新参数 `skip_time_range_in_full_history`，允许用户控制 `_stock_full_history` 是否跳过 `time_range` 配置。

**优点**:
- 向后兼容：默认 `true`（跳过 time_range），保持现有行为
- 灵活配置：可以在 YAML 中控制行为，无需修改代码
- 统一逻辑：main.py 不需要修改，逻辑集中在 PaginationExecutor

#### 修改代码

```python
# 修改前 (pagination_executor.py:77-85)
elif base_params.get('_stock_full_history') and self._is_stock_loop_enabled(context.interface_config):
    stock_list = context.stock_list or []
    params_list = []
    for stock in stock_list:
        ts_code = stock.get('ts_code')
        if not ts_code:
            continue
        p = {'ts_code': ts_code, '_stock_info': stock}
        params_list.append(p)

# 修改后
elif base_params.get('_stock_full_history') and self._is_stock_loop_enabled(context.interface_config):
    # 检查配置：是否跳过 time_range
    pagination_config = context.interface_config.get('pagination', {})
    skip_time_range = pagination_config.get('skip_time_range_in_full_history', True)

    if not skip_time_range:
        # 不跳过 time_range：调用 PaginationComposer 处理窗口
        composer = PaginationComposer(context)
        cleaned_params = {k: v for k, v in base_params.items() if k != '_stock_full_history'}
        params_list = list(composer.compose(cleaned_params))
    else:
        # 跳过 time_range：默认行为（向后兼容）
        stock_list = context.stock_list or []
        params_list = []
        for stock in stock_list:
            ts_code = stock.get('ts_code')
            if not ts_code:
                continue
            p = {'ts_code': ts_code, '_stock_info': stock}
            params_list.append(p)
```

### 配置文件示例

#### 方案A：启用 time_range（新行为）

```yaml
# app4/config/interfaces/cyq_chips.yaml
pagination:
  enabled: true
  mode: stock_loop
  skip_time_range_in_full_history: false  # ✅ 不跳过 time_range
  time_range:
    enabled: true
    window: 10d
    stop_on_empty: 90
```

**行为**: 即使设置了 `_stock_full_history`，仍然按 10 天窗口分割请求

#### 方案B：跳过 time_range（默认行为，向后兼容）

```yaml
# app4/config/interfaces/cyq_chips.yaml
pagination:
  enabled: true
  mode: stock_loop
  skip_time_range_in_full_history: true   # ✅ 跳过 time_range（默认）
  time_range:
    enabled: true
    window: 10d
    stop_on_empty: 90
```

**行为**: 如果设置了 `_stock_full_history`，则跳过 time_range，直接全历史下载

#### 方案C：不设置参数（完全向后兼容）

```yaml
# app4/config/interfaces/cyq_chips.yaml
pagination:
  enabled: true
  mode: stock_loop
  time_range:
    enabled: true
    window: 10d
```

**行为**: 默认 `skip_time_range_in_full_history: true`，保持现有行为

### 配置参数说明

#### `skip_time_range_in_full_history`

**类型**: `boolean`  
**默认值**: `true`（向后兼容）  
**作用**: 控制当 `_stock_full_history=True` 时是否跳过 `time_range` 配置

| 值 | 行为 | 适用场景 |
|----|------|---------|
| `true` | 跳过 time_range，直接全历史下载 | 快速全量下载、接口不支持日期分割 |
| `false` | 不跳过 time_range，按窗口分割 | 稳定下载、避免大请求超时 |

### 向后兼容性

**默认行为（不修改配置）**:
- `skip_time_range_in_full_history` 未设置 → 默认为 `true`
- 行为与当前一致：`_stock_full_history` 跳过 `time_range`
- 现有接口无需修改配置

**启用新功能**:
- 在 YAML 中显式设置 `skip_time_range_in_full_history: false`
- 即可启用 time_range 分割，即使使用 `_stock_full_history`

## 配置文件要求

### 正确的 cyq_chips.yaml

#### 场景1：启用 time_range 分割（推荐新配置）

```yaml
api_name: cyq_chips
description: 每日筹码分布
name: cyq_chips

pagination:
  enabled: true
  mode: stock_loop
  skip_time_range_in_full_history: false  # ✅ 关键：不跳过 time_range
  time_range:
    enabled: true
    window: 10d        # 10天窗口
    stop_on_empty: 90  # 连续90天无数据停止
  stock_loop:
    enabled: true

parameters:
  ts_code:
    description: 股票代码
    required: true
    type: string
  start_date:
    description: 开始日期 YYYYMMDD
    required: false
    type: string
  end_date:
    description: 结束日期 YYYYMMDD
    required: false
    type: string

permissions:
  min_points: 120
  rate_limit: 60
```

#### 场景2：保持向后兼容（跳过 time_range）

```yaml
api_name: cyq_chips
description: 每日筹码分布
name: cyq_chips

pagination:
  enabled: true
  mode: stock_loop
  skip_time_range_in_full_history: true   # ✅ 跳过 time_range（默认）
  time_range:
    enabled: true
    window: 10d
    stop_on_empty: 90
  stock_loop:
    enabled: true

# ... 其他配置 ...
```

#### 场景3：最小配置（使用默认值）

```yaml
api_name: cyq_chips
description: 每日筹码分布
name: cyq_chips

pagination:
  enabled: true
  mode: stock_loop
  time_range:
    enabled: true
    window: 10d
    stop_on_empty: 90

# ... 其他配置 ...
# 效果: skip_time_range_in_full_history 默认为 true
```

### 配置检查清单

#### 基础配置
- [ ] `pagination.enabled: true`
- [ ] `pagination.mode: stock_loop`
- [ ] `pagination.time_range.enabled: true`
- [ ] `pagination.time_range.window` 已配置（如 `10d`）

#### 关键新配置
- [ ] `pagination.skip_time_range_in_full_history: false`  ⚠️ 设置为 `false` 以启用 time_range
- [ ] `pagination.stock_loop.enabled: true`  ⚠️ 推荐显式设置

#### 配置建议
| 场景 | skip_time_range_in_full_history | 行为 | 推荐 |
|------|----------------------------------|------|------|
| 新接口/追求稳定 | `false` | 按窗口分割 | ✅ 推荐 |
| 现有接口/追求速度 | `true` (或不设置) | 全历史下载 | 保持默认 |
| 测试 | `false` + 小窗口 | 快速验证 | 测试用 |

## 验证与测试

### 测试1: 验证配置生效（skip_time_range_in_full_history=false）

**步骤1: 配置 YAML**

```yaml
# app4/config/interfaces/cyq_chips.yaml
pagination:
  enabled: true
  mode: stock_loop
  skip_time_range_in_full_history: false  # ✅ 关键配置
  time_range:
    enabled: true
    window: 10d
    stop_on_empty: 90
```

**步骤2: 执行命令**
```bash
python app4/main.py --interface cyq_chips --start-date 20240101 --end-date 20240131
```

**预期日志**:
```
INFO - Using stock_loop mode for cyq_chips
INFO - Starting concurrent download for cyq_chips with 5479 stocks
INFO - Submitting batch of 100 tasks
INFO - Downloading data for stock 300506.SZ, params: {'_stock_full_history': True, 'ts_code': '300506.SZ', 'start_date': '20160324', 'end_date': '20160333', '_time_window': ('20160324', '20160333')}
INFO - Downloading data for stock 300506.SZ, params: {'_stock_full_history': True, 'ts_code': '300506.SZ', 'start_date': '20160403', 'end_date': '20160413', '_time_window': ('20160403', '20160413')}
...
```

**关键验证点**:
- ✅ 日志中出现 `_time_window` 标记
- ✅ 请求按 10 天窗口分割（多个请求 per 股票）
- ✅ 即使参数中有 `_stock_full_history`，仍然分割

**统计验证**:
```bash
# 统计日志中的 "Downloading data" 行数
grep "Downloading data for stock" app4.log | wc -l
# 预期: 5479 股票 × N个窗口（取决于上市时间）
# 示例: 如果平均 10 年 ≈ 2500 交易日 / 10 天 = 250 窗口
# 则: 5479 × 250 = 1,369,750 次
```

### 测试2: 验证跳过配置（skip_time_range_in_full_history=true）

**步骤1: 配置 YAML**

```yaml
# app4/config/interfaces/cyq_chips.yaml
pagination:
  enabled: true
  mode: stock_loop
  skip_time_range_in_full_history: true   # ✅ 跳过 time_range
  time_range:
    enabled: true
    window: 10d
    stop_on_empty: 90
```

**步骤2: 执行命令**
```bash
python app4/main.py --interface cyq_chips
```

**预期日志**:
```
INFO - Using stock_loop mode for cyq_chips
INFO - Non-update mode: fetching full history per stock for cyq_chips (single request per stock)
INFO - Starting concurrent download for cyq_chips with 5479 stocks
INFO - Submitting batch of 100 tasks
INFO - Downloading data for stock 300506.SZ, params: {'_stock_full_history': True, 'ts_code': '300506.SZ', 'start_date': '20160324'}
...
```

**关键验证点**:
- ✅ 日志中出现 `"_stock_full_history": True`
- ✅ 日志中没有 `_time_window` 标记
- ✅ 每个股票只有 1 个请求（全历史）

**统计验证**:
```bash
grep "Downloading data for stock" app4.log | wc -l
# 预期: 5479 次（每个股票 1 次）
```

### 测试3: 验证向后兼容（不设置参数）

**步骤1: 配置 YAML（不设置新参数）**

```yaml
# app4/config/interfaces/cyq_chips.yaml
pagination:
  enabled: true
  mode: stock_loop
  time_range:
    enabled: true
    window: 10d
    stop_on_empty: 90
```

**步骤2: 执行命令**
```bash
python app4/main.py --interface cyq_chips
```

**预期行为**:
- 与 **测试2** 相同（skip_time_range_in_full_history 默认为 true）
- 向后兼容：现有配置无需修改

### 测试4: 验证 stop_on_empty（仅当 skip=false 时生效）

**步骤1: 配置 YAML**

```yaml
# app4/config/interfaces/cyq_chips.yaml
pagination:
  enabled: true
  mode: stock_loop
  skip_time_range_in_full_history: false  # ✅ 启用 time_range
  time_range:
    enabled: true
    window: 10d
    stop_on_empty: 5  # ✅ 设置为 5 天方便测试
```

**步骤2: 执行命令**
```bash
python app4/main.py --interface cyq_chips --ts-code 000001.SZ --start-date 20200101
```

**预期**: 如果某只股票早期数据不存在，应在连续 5 天无数据后停止

### 测试5: 验证覆盖率管理器

**步骤1: 配置 YAML**

```yaml
# app4/config/interfaces/cyq_chips.yaml
pagination:
  enabled: true
  mode: stock_loop
  skip_time_range_in_full_history: false  # ✅ 启用 time_range
  time_range:
    enabled: true
    window: 10d
```

**步骤2: 第一次运行（下载数据）**
```bash
python app4/main.py --interface cyq_chips --ts-code 000001.SZ --start-date 20240101 --end-date 20240131
```

**步骤3: 第二次运行（验证跳过）**
```bash
python app4/main.py --interface cyq_chips --ts-code 000001.SZ --start-date 20240101 --end-date 20240131
```

**预期**: 应跳过已下载的数据，显示 `Skipping stock ... (already exists)`

## 性能影响评估

### 配置 skip_time_range_in_full_history=true（默认，向后兼容）

**请求次数**: 5479 次（全历史，单请求 per 股票）  
**单次请求数据量**: 大（可能 10,000+ 条记录）  
**内存占用**: 高（批量处理大数据）  
**失败风险**: 高（大请求易超时）  
**API 配额消耗**: 5479 积分  

**适用场景**: 快速全量下载、接口不支持日期分割、网络稳定

### 配置 skip_time_range_in_full_history=false（新配置）

**请求次数**: 5479 × N 窗口 =  **~1,369,750 次**  （假设：平均上市 10 年 ≈ 2500 交易日 / 10 天窗口）  
**单次请求数据量**: 小（约 2000-3000 条记录）  
**内存占用**: 低（流式处理小批量）  
**失败风险**: 低（小请求稳定）  
**API 配额消耗**: ~1,369,750 积分 ⚠️  

**适用场景**: 稳定下载、避免大请求超时、数据完整性要求高

### 优化建议

#### 1. **配合覆盖率管理器**（必须，两种配置都需要）
```yaml
# 确保 coverage_manager 启用
coverage_manager:
  enabled: true
  strategy: stock
```
**效果**: 跳过已下载数据，减少无效请求

#### 2. **调整窗口大小**（当 skip=false 时）
```yaml
# 根据数据密度调整
time_range:
  window: 30d  # 从 10d 改为 30d，减少请求次数 66%
```
**效果**: 平衡请求次数和稳定性

#### 3. **使用增量更新模式**（推荐）
```bash
# 只下载缺失数据
python app4/main.py --update --interface cyq_chips
```
**效果**: 首次全量后，后续只补增量

#### 4. **分批下载**（当 skip=false 时）
```bash
# 降低并发数，避免配额耗尽
python app4/main.py --interface cyq_chips --concurrency 2
```
**效果**: 降低瞬时请求压力

### 配置选择建议

| 场景 | skip_time_range_in_full_history | window | 理由 |
|------|----------------------------------|--------|------|
| **首次全量** | `true` (默认) | 不设置 | 快速下载，减少请求次数 |
| **日常更新** | `false` | `30d` | 稳定，增量小 |
| **接口不稳定** | `false` | `10d` | 小请求更可靠 |
| **积分充足** | `false` | `10d` | 追求数据完整性 |
| **积分紧张** | `true` | 不设置 | 节省积分 |

## 相关文件

### 核心文件（新方案）
1. `app4/core/pagination_executor.py:77-85` - 新增配置检查逻辑
2. `app4/config/interfaces/cyq_chips.yaml` - 新增 `skip_time_range_in_full_history` 配置
3. `app4/core/pagination.py:78` - `time_range` 启用检查
4. `app4/core/pagination.py:82` - `stock_loop` 启用检查

### 相关文件（旧方案，无需修改）
- `app4/main.py:981` - 设置 `_stock_full_history`（保持原样）
- `app4/main.py:376` - 设置 `_stock_full_history`（保持原样）
- `app4/core/downloader.py:468` - 下载日志输出
- `app4/core/scheduler.py` - 任务调度
- `app4/core/coverage_manager.py` - 覆盖率管理

### 配置加载相关
- `app4/core/config_loader.py` - 配置加载和验证
- `app4/core/schema_manager.py` - 配置模式验证（如需添加新参数验证）

## 备份与回滚

### 修改前备份

```bash
# 备份 pagination_executor.py（唯一需要修改的文件）
cp app4/core/pagination_executor.py app4/core/pagination_executor.py.backup.$(date +%Y%m%d_%H%M%S)

# 备份配置文件（以防需要回退配置）
cp app4/config/interfaces/cyq_chips.yaml app4/config/interfaces/cyq_chips.yaml.backup
```

### 快速回滚

#### 方案1：恢复代码备份
```bash
# 恢复备份
mv app4/core/pagination_executor.py.backup.20240210_224500 app4/core/pagination_executor.py
```

#### 方案2：修改配置（无需回滚代码）
```yaml
# 将 skip_time_range_in_full_history 改为 true
pagination:
  skip_time_range_in_full_history: true  # 改为 true，恢复旧行为
```

#### 方案3：手动撤销代码修改
```python
# 在 pagination_executor.py 中
# 删除或注释掉新增的配置检查逻辑
# 保留原始的 _stock_full_history 分支
```

## 常见问题

### Q1: 为什么单股票下载正常，多股票下载失效？

**A**: 单股票下载时 `args.ts_code` 存在，不会设置 `_stock_full_history`，因此会调用 `PaginationComposer`。多股票下载时 `args.ts_code` 为 `None`，代码设置 `_stock_full_history`，而默认配置 `skip_time_range_in_full_history: true` 导致跳过 `time_range`。

### Q2: 新配置 `skip_time_range_in_full_history` 的作用是什么？

**A**: 控制当 `_stock_full_history=True` 时是否跳过 `time_range` 配置。`true`（默认）跳过，保持向后兼容；`false` 不跳过，启用时间窗口分割。

### Q3: 修改后 API 请求次数会增加多少？

**A**: 取决于配置：
- `skip=true`（默认）：5479 次（不增加）
- `skip=false` + `window=10d`：约 1,369,750 次（增加 250 倍）

### Q4: 如何平衡请求次数和数据稳定性？

**A**: 配置建议：
1. `skip_time_range_in_full_history: false`（启用分割）
2. `window: 30d`（增大窗口，减少请求次数）
3. 启用覆盖率管理器（跳过已下载）

### Q5: 如何验证配置生效？

**A**: 查看日志：
- `skip=false`：应看到 `_time_window` 标记
- `skip=true`：应看到 `_stock_full_history: True`

### Q6: 需要修改 main.py 吗？

**A**: **不需要**。新方案只在 `pagination_executor.py` 中增加配置检查逻辑，`main.py` 保持原样。

## 总结

### 核心结论（新方案）

1. **问题根源**: `_stock_full_history` 参数绕过 `PaginationComposer`，导致 `time_range` 配置失效
2. **根本原因**: 没有机制让 `_stock_full_history` 和 `time_range` 共存
3. **新方案**: 在 `pagination_executor.py` 中增加配置检查，让 `time_range` 控制 `_stock_full_history` 的行为
4. **配置驱动**: 通过 `skip_time_range_in_full_history` 参数控制是否跳过时间窗口
5. **向后兼容**: 默认 `true`（跳过），保持现有行为，无需修改现有接口

### 修复方案对比

| 方案 | 修改文件 | 向后兼容 | 灵活性 | 推荐度 |
|------|---------|---------|--------|--------|
| **旧方案1**: 移除 `_stock_full_history` | `main.py` | ❌ 不兼容 | ❌ 低 | ❌ 不推荐 |
| **旧方案2**: 增加 time_range 判断 | `main.py` | ⚠️ 部分兼容 | ⚠️ 中 | ⚠️ 一般 |
| **新方案**: 配置驱动 | `pagination_executor.py` | ✅ 完全兼容 | ✅ 高 | ✅ **强烈推荐** |

### 配置行为矩阵

| skip_time_range_in_full_history | _stock_full_history | time_range.enabled | 行为 | 请求次数 |
|----------------------------------|---------------------|-------------------|------|---------|
| `true` (默认) | ✅ 设置 | ✅ true | **跳过 time_range** (向后兼容) | 5479 |
| `true` (默认) | ✅ 设置 | ❌ false | 跳过 time_range | 5479 |
| `false` | ✅ 设置 | ✅ true | **启用 time_range** (新功能) | 5479×N |
| `false` | ✅ 设置 | ❌ false | 不分割（time_range 未启用） | 5479 |
| 不适用 | ❌ 未设置 | ✅ true | 正常分割（单股票模式） | N |
| 不适用 | ❌ 未设置 | ❌ false | 不分割 | 1 |

### 关键改进

**旧方案**: 行为由代码硬编码决定，无法灵活配置  
**新方案**: 行为由 YAML 配置文件控制，灵活可配置

### 配置选择建议

| 使用场景 | skip_time_range_in_full_history | window | 理由 |
|---------|----------------------------------|--------|------|
| **现有接口** | `true` (不设置) | 不设置 | 保持默认，无需修改 |
| **新接口** | `false` | `30d` | 启用分割，稳定可靠 |
| **接口不稳定** | `false` | `10d` | 小窗口，降低失败率 |
| **追求速度** | `true` | 不设置 | 减少请求次数 |
| **追求完整** | `false` | `10d` | 小批量，易重试 |

### 实施步骤

#### 第一步：修改代码（一次性）
```bash
# 备份文件
cp app4/core/pagination_executor.py app4/core/pagination_executor.py.backup

# 修改 pagination_executor.py:77-85
# 添加 skip_time_range_in_full_history 配置检查逻辑
```

#### 第二步：配置接口（按需）
```yaml
# 对新接口或需要稳定的接口
pagination:
  skip_time_range_in_full_history: false
  time_range:
    enabled: true
    window: 30d
```

#### 第三步：验证测试
```bash
# 测试1: 验证 time_range 生效
python app4/main.py --interface cyq_chips --ts-code 000001.SZ --start-date 20240101 --end-date 20240131
# 检查日志: 应出现 _time_window 标记

# 测试2: 验证跳过配置
# 修改 YAML: skip_time_range_in_full_history: true
python app4/main.py --interface cyq_chips --ts-code 000001.SZ
# 检查日志: 不应出现 _time_window 标记
```

#### 第四步：监控与优化
- 监控 API 配额消耗
- 根据接口稳定性调整 `window` 大小
- 配合覆盖率管理器避免重复下载

### 风险与应对

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|---------|
| 配置错误 | 中 | 中 | 提供配置检查清单，增加日志提示 |
| 请求次数激增 | 低 | 高 | 默认 `skip=true`，需手动启用；配合覆盖率管理器 |
| API 配额耗尽 | 低 | 高 | 监控配额，增大 window，分批下载 |
| 向后兼容性问题 | 极低 | 高 | 默认保持旧行为，无需修改现有配置 |

### 关键建议

1. **立即实施**: 修改 `pagination_executor.py`，添加配置检查逻辑（简单、安全）
2. **按需配置**: 对新接口设置 `skip_time_range_in_full_history: false`
3. **保持默认**: 现有接口无需修改配置，保持向后兼容
4. **监控日志**: 验证 `_time_window` 标记是否出现，确认配置生效
5. **优化窗口**: 根据数据量和接口稳定性调整 `window` 大小（推荐 30d）
6. **启用覆盖率**: 必须配合覆盖率管理器，避免重复下载

### 长期收益

- ✅ **配置驱动**: 无需修改代码，通过 YAML 控制行为
- ✅ **向后兼容**: 默认保持旧行为，平滑过渡
- ✅ **灵活可控**: 不同接口可以有不同的配置
- ✅ **易于维护**: 集中管理，减少硬编码
- ✅ **可观测性**: 日志明确显示配置效果

---

**文档版本**: 2.0（新方案）  
**创建日期**: 2026-02-10  
**更新日期**: 2026-02-10  
**相关 Issue**: cyq_chips time_range 配置失效  
**修复状态**: 待实施（新方案）  
**优先级**: 高  
**影响范围**: 所有使用 stock_loop + time_range 的接口  
**向后兼容性**: ✅ 完全兼容（默认配置保持旧行为）

---

**文档版本**: 1.0  
**创建日期**: 2026-02-10  
**相关 Issue**: cyq_chips time_range 配置失效  
**修复状态**: 待修复  
**优先级**: 高  
**影响范围**: 所有使用 stock_loop + time_range 的接口
