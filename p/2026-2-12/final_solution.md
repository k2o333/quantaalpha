# Stock Loop 模式智能增量下载方案 - 最终整合版

**版本**: v2.0  
**日期**: 2026-02-12  
**状态**: 已整合评估建议

---

## 一、方案概述

### 1.1 目标

在 `--update --interface <接口> --ts_code <股票代码>` 指令执行时：

| 场景 | 行为 |
|------|------|
| 该股票完全无数据 | 全历史下载 |
| 该股票有数据但不完整 | 检测缺口，仅下载缺失的日期段 |
| 该股票数据完整 | 跳过，不调用 API |

### 1.2 设计原则

基于对 `cm.md` 和 `cm2.md` 评估报告的分析，采用以下原则：

1. **扩展现有模块**：不新增独立模块，在 `CoverageManager` 中扩展功能
2. **最小侵入性**：复用现有配置结构，新增可选字段
3. **向后兼容**：默认行为不变，需显式配置才启用新功能
4. **适配现有接口**：使用 Polars 的 `filter()` 方法替代不支持的 `filters` 参数

### 1.3 与原方案对比

| 对比项 | 原方案 (complete_solution.md) | 本方案 |
|--------|------------------------------|--------|
| 新增模块 | `StockLoopPlanner` | 无，扩展 `CoverageManager` |
| 配置结构 | 新增 `date_params` 块 | 复用 `duplicate_detection` |
| 接口兼容性 | 使用不存在的 `filters` 参数 | 读取后用 Polars 过滤 |
| 修改范围 | 3个文件 | 2个文件 |

---

## 二、核心实现

### 2.1 扩展 CoverageManager

在 `/home/quan/testdata/aspipe_v4/app4/core/coverage_manager.py` 中添加以下方法：

```python
# ============================================================================
# 股票级别日期缺口检测（新增功能）
# ============================================================================

def get_stock_existing_dates(
    self,
    interface_name: str,
    ts_code: str,
    date_column: str = 'trade_date'
) -> Set[str]:
    """
    获取指定股票已存在的所有日期
    
    Args:
        interface_name: 接口名称
        ts_code: 股票代码
        date_column: 日期列名
        
    Returns:
        已存在的日期集合（YYYYMMDD格式）
    """
    cache_key = f"{interface_name}:{ts_code}:dates"
    
    # 检查缓存
    with self._cache_lock:
        if cache_key in self._cache:
            return self._cache[cache_key]
    
    try:
        # 读取接口数据（包含 ts_code 和日期列）
        df = self.storage_manager.read_interface_data(
            interface_name,
            columns=[date_column, 'ts_code']
        )
        
        if df.is_empty():
            return set()
        
        # 使用 Polars 过滤指定股票（适配现有接口）
        import polars as pl
        filtered = df.filter(pl.col('ts_code') == ts_code)
        
        if filtered.is_empty():
            return set()
        
        # 提取并格式化日期
        dates = set()
        for date_val in filtered[date_column]:
            formatted = format_date(date_val)
            if formatted:
                dates.add(formatted)
        
        # 缓存结果
        with self._cache_lock:
            self._cache[cache_key] = dates
        
        logger.debug(f"[{interface_name}/{ts_code}] 已有 {len(dates)} 天数据")
        return dates
        
    except Exception as e:
        logger.warning(f"获取 {interface_name}/{ts_code} 的现有日期失败: {e}")
        return set()


def detect_stock_date_gaps(
    self,
    interface_name: str,
    ts_code: str,
    start_date: str,
    end_date: str,
    date_column: str = 'trade_date',
    min_gap_days: int = 1
) -> List[Tuple[str, str]]:
    """
    检测指定股票在日期范围内的缺口
    
    Args:
        interface_name: 接口名称
        ts_code: 股票代码
        start_date: 起始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)
        date_column: 日期列名
        min_gap_days: 最小缺口天数
        
    Returns:
        缺失的日期段列表 [(start, end), ...]
    """
    logger.info(f"检测缺口: {interface_name}/{ts_code} ({start_date} ~ {end_date})")
    
    # 1. 获取已有日期
    existing_dates = self.get_stock_existing_dates(
        interface_name, ts_code, date_column
    )
    
    # 2. 如果没有数据，返回完整范围
    if not existing_dates:
        logger.info(f"[{ts_code}] 无现有数据，需要完整下载")
        return [(start_date, end_date)]
    
    # 3. 获取交易日历
    if self.downloader:
        trade_calendar = self.downloader.get_trade_calendar(start_date, end_date)
    else:
        logger.warning("Downloader not available for trade calendar")
        return [(start_date, end_date)]
    
    if not trade_calendar:
        logger.warning(f"未获取到交易日历")
        return [(start_date, end_date)]
    
    # 4. 计算期望交易日
    trade_days = [
        d['cal_date'] for d in trade_calendar 
        if d.get('is_open', 0) == 1 and 
           start_date <= d['cal_date'] <= end_date
    ]
    
    # 5. 找出缺失的交易日
    missing_days = [d for d in trade_days if d not in existing_dates]
    
    if not missing_days:
        logger.info(f"[{ts_code}] 数据已完整覆盖")
        return []
    
    logger.info(f"[{ts_code}] 缺失 {len(missing_days)} 个交易日")
    
    # 6. 合并为连续区间
    gaps = self._merge_dates_to_ranges(missing_days, min_gap_days)
    
    # 7. 输出缺口详情
    for i, (gap_start, gap_end) in enumerate(gaps):
        logger.info(f"  [{i+1}] {gap_start} ~ {gap_end}")
    
    return gaps


def _merge_dates_to_ranges(
    self, 
    dates: List[str], 
    min_gap_days: int = 1
) -> List[Tuple[str, str]]:
    """
    将日期列表合并为连续区间
    
    Args:
        dates: 日期列表（已排序）
        min_gap_days: 最小缺口天数
        
    Returns:
        区间列表 [(start, end), ...]
    """
    if not dates:
        return []
    
    sorted_dates = sorted(dates)
    ranges = []
    range_start = sorted_dates[0]
    range_end = sorted_dates[0]
    
    for i in range(1, len(sorted_dates)):
        curr = sorted_dates[i]
        prev = sorted_dates[i-1]
        
        # 判断是否连续（允许周末间隔，最多3天）
        from datetime import datetime
        curr_dt = datetime.strptime(curr, '%Y%m%d')
        prev_dt = datetime.strptime(prev, '%Y%m%d')
        
        if (curr_dt - prev_dt).days <= 3:
            range_end = curr
        else:
            # 保存当前区间（如果满足最小天数）
            if self._days_between(range_start, range_end) >= min_gap_days:
                ranges.append((range_start, range_end))
            range_start = curr
            range_end = curr
    
    # 保存最后一个区间
    if self._days_between(range_start, range_end) >= min_gap_days:
        ranges.append((range_start, range_end))
    
    return ranges


def _days_between(self, start_date: str, end_date: str) -> int:
    """计算两个日期之间的天数（包含首尾）"""
    from datetime import datetime
    start = datetime.strptime(start_date, '%Y%m%d')
    end = datetime.strptime(end_date, '%Y%m%d')
    return (end - start).days + 1
```

### 2.2 修改 PaginationComposer

在 `/home/quan/testdata/aspipe_v4/app4/core/pagination.py` 中修改 `_apply_stock_loop` 方法：

```python
def _apply_stock_loop(self, params_stream: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
    """
    应用股票循环维度 - 增强版（支持股票级别缺口检测）
    
    Args:
        params_stream: 参数流
        
    Yields:
        应用股票循环后的参数
    """
    stock_list = self.context.stock_list
    if not stock_list:
        logger.error("Stock list not provided")
        return
    
    # 获取配置
    stock_loop_config = self.config.get('stock_loop', {})
    skip_existing = stock_loop_config.get('skip_existing', False)
    
    # 新增：股票级别缺口检测配置
    detection_config = self.interface_config.get('duplicate_detection', {})
    stock_level_detection = detection_config.get('stock_level_detection', False)
    date_column = detection_config.get('date_column', 'trade_date')
    
    parameter_config = self.interface_config.get('parameters', {})
    
    for params in params_stream:
        for stock in stock_list:
            ts_code = stock.get('ts_code')
            if not ts_code:
                continue
            
            # === 新增：股票级别缺口检测 ===
            if stock_level_detection and self.context.coverage_manager and not self.context.force_download:
                # 获取日期范围
                start_date = params.get('start_date', '20000101')
                end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))
                
                # 检测缺口
                gaps = self.context.coverage_manager.detect_stock_date_gaps(
                    self.interface_config.get('api_name', ''),
                    ts_code,
                    start_date,
                    end_date,
                    date_column
                )
                
                if not gaps:
                    logger.debug(f"Skipping {ts_code}, data already complete")
                    continue
                
                # 为每个缺口生成参数
                for gap_start, gap_end in gaps:
                    gap_params = params.copy()
                    gap_params['ts_code'] = ts_code
                    gap_params['start_date'] = gap_start
                    gap_params['end_date'] = gap_end
                    gap_params['_stock_info'] = stock
                    gap_params['_gap_fill'] = True  # 标记为缺口填充
                    yield gap_params
                
                continue
            
            # === 原有逻辑：简单跳过 ===
            if skip_existing and not self.context.force_download:
                if self._stock_data_exists(ts_code):
                    continue
            
            stock_params = params.copy()
            stock_params['ts_code'] = ts_code
            stock_params['_stock_info'] = stock
            yield stock_params
```

---

## 三、配置设计

### 3.1 配置字段说明

复用现有 `duplicate_detection` 配置块，新增可选字段：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `stock_level_detection` | bool | false | 是否启用股票级别缺口检测 |
| `date_column` | string | 'trade_date' | 数据中的日期字段名 |
| `lookback_days` | int | 7 | 回溯天数（处理数据延迟） |

### 3.2 配置示例

#### 日线数据接口

```yaml
# daily_basic.yaml
api_name: daily_basic
description: 每日指标

duplicate_detection:
  enabled: true
  date_column: "trade_date"        # 已有字段
  threshold: 0.95
  # 新增字段
  stock_level_detection: true      # 启用股票级别检测
  lookback_days: 7                 # 回溯天数

pagination:
  enabled: true
  mode: stock_loop                 # 需要是 stock_loop 模式
  stock_loop:
    skip_existing: false           # 使用新的缺口检测替代简单跳过
```

#### 财报数据接口

```yaml
# income_vip.yaml
api_name: income_vip
description: 利润表(VIP)

duplicate_detection:
  enabled: true
  date_column: "end_date"          # 财报使用 end_date
  key_columns: [ts_code, end_date]
  # 新增字段
  stock_level_detection: true
  lookback_days: 0                 # 财报不需要回溯

pagination:
  enabled: true
  mode: stock_loop
```

#### 不启用新功能的接口

```yaml
# moneyflow.yaml（保持原有行为）
api_name: moneyflow
description: 个股资金流向

duplicate_detection:
  enabled: true
  date_column: "trade_date"
  # 不添加 stock_level_detection，保持原有行为

pagination:
  enabled: true
  mode: stock_loop
  stock_loop:
    skip_existing: true            # 使用原有的简单跳过逻辑
```

---

## 四、执行流程

### 4.1 流程图

```
用户执行: python app4/main.py --update --interface daily_basic --ts_code 000001.SZ

    │
    ▼
┌─────────────────────────────┐
│ 1. 加载接口配置              │
│    - stock_level_detection? │
│    - date_column?           │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ 2. PaginationComposer       │
│    ._apply_stock_loop()     │
└─────────────────────────────┘
    │
    ├── stock_level_detection=true ──────────────────┐
    │                                                │
    │   ┌────────────────────────────────────────────▼
    │   │ 3. CoverageManager.detect_stock_date_gaps()│
    │   │    - 读取该股票已有日期                     │
    │   │    - 获取交易日历                          │
    │   │    - 计算缺失日期段                        │
    │   └────────────────────────────────────────────┤
    │                                                │
    │   ┌────────────────────────────────────────────▼
    │   │ 4. 生成下载任务                            │
    │   │    - 无数据 → [(start, end)]              │
    │   │    - 有缺口 → [(gap1_start, gap1_end), …] │
    │   │    - 完整 → [] (跳过)                      │
    │   └────────────────────────────────────────────┤
    │                                                │
    │   ┌────────────────────────────────────────────▼
    │   │ 5. 执行下载                                │
    │   │    - 仅下载缺失的日期段                    │
    │   └────────────────────────────────────────────┘
    │
    └── stock_level_detection=false ──────► 原有逻辑
                                              - skip_existing 简单跳过
```

### 4.2 日志示例

**场景 1：完全无数据**
```
[daily_basic/000001.SZ] 检测缺口: daily_basic/000001.SZ (20000101 ~ 20260212)
[daily_basic/000001.SZ] 无现有数据，需要完整下载
[daily_basic/000001.SZ] 下载: start_date=20000101, end_date=20260212
```

**场景 2：有缺口**
```
[daily_basic/000001.SZ] 检测缺口: daily_basic/000001.SZ (20250101 ~ 20260212)
[daily_basic/000001.SZ] 已有 45 天数据
[daily_basic/000001.SZ] 缺失 15 个交易日
[daily_basic/000001.SZ]   [1] 20250115 ~ 20250120
[daily_basic/000001.SZ]   [2] 20250201 ~ 20260212
[daily_basic/000001.SZ] 下载缺口: start_date=20250115, end_date=20250120
[daily_basic/000001.SZ] 下载缺口: start_date=20250201, end_date=20260212
```

**场景 3：数据完整**
```
[daily_basic/000001.SZ] 检测缺口: daily_basic/000001.SZ (20250101 ~ 20260212)
[daily_basic/000001.SZ] 已有 50 天数据
[daily_basic/000001.SZ] 数据已完整覆盖
[daily_basic/000001.SZ] Skipping 000001.SZ, data already complete
```

---

## 五、集成步骤

### 步骤 1：修改 CoverageManager

编辑 `/home/quan/testdata/aspipe_v4/app4/core/coverage_manager.py`：

1. 在文件末尾添加三个新方法：
   - `get_stock_existing_dates()`
   - `detect_stock_date_gaps()`
   - `_merge_dates_to_ranges()`

### 步骤 2：修改 PaginationComposer

编辑 `/home/quan/testdata/aspipe_v4/app4/core/pagination.py`：

1. 在 `_apply_stock_loop()` 方法中添加股票级别缺口检测逻辑
2. 添加 `datetime` 导入（如果尚未导入）

### 步骤 3：配置接口

为需要启用股票级别检测的接口添加配置：

```yaml
duplicate_detection:
  stock_level_detection: true
  date_column: "trade_date"  # 或 end_date
```

**建议优先配置的接口**：
1. `income_vip` - 利润表
2. `balancesheet_vip` - 资产负债表
3. `cashflow_vip` - 现金流量表
4. `disclosure_date` - 披露日期

---

## 六、测试验证

### 6.1 单元测试

```python
# test_stock_level_detection.py

def test_get_stock_existing_dates():
    """测试获取股票已有日期"""
    # 准备测试数据
    # ...
    
    dates = coverage_manager.get_stock_existing_dates(
        'daily_basic', '000001.SZ', 'trade_date'
    )
    
    assert isinstance(dates, set)
    assert all(len(d) == 8 for d in dates)  # YYYYMMDD 格式


def test_detect_stock_date_gaps():
    """测试缺口检测"""
    # 场景1：无数据
    gaps = coverage_manager.detect_stock_date_gaps(
        'daily_basic', 'NEW_STOCK.SZ', '20250101', '20250131'
    )
    assert gaps == [('20250101', '20250131')]
    
    # 场景2：有缺口
    # ...
    
    # 场景3：数据完整
    # ...
```

### 6.2 集成测试

```bash
# 测试全历史下载
/root/miniforge3/envs/get/bin/python app4/main.py \
    --update --interface income_vip --ts_code 000001.SZ

# 测试增量下载（再次运行）
/root/miniforge3/envs/get/bin/python app4/main.py \
    --update --interface income_vip --ts_code 000001.SZ

# 测试跳过（数据完整时）
/root/miniforge3/envs/get/bin/python app4/main.py \
    --update --interface income_vip --ts_code 000001.SZ
```

---

## 七、注意事项

### 7.1 适用范围

| 分页模式 | 是否适用 | 说明 |
|---------|---------|------|
| `stock_loop` | ✅ 适用 | 本方案主要目标 |
| `reverse_date_range` | ❌ 不适用 | 使用现有的日期范围覆盖率检测 |
| `period_range` | ⚠️ 部分适用 | 需要调整日期生成逻辑 |
| `date_anchor` | ⚠️ 部分适用 | 需要调整锚点遍历逻辑 |

### 7.2 性能考虑

1. **缓存策略**：股票日期查询结果会缓存，避免重复读取
2. **批量读取**：一次性读取接口所有数据，在内存中过滤
3. **缺口合并**：将多个小缺口合并为连续段，减少 API 调用次数

### 7.3 回滚方案

如果出现问题，可以：

1. **临时禁用**：删除接口配置中的 `stock_level_detection` 字段
2. **完全回滚**：恢复 `coverage_manager.py` 和 `pagination.py` 的备份

---

## 八、总结

### 8.1 方案优势

| 优势 | 说明 |
|------|------|
| **最小侵入** | 仅修改 2 个文件，不新增模块 |
| **向后兼容** | 默认行为不变，需显式配置才启用 |
| **配置复用** | 复用现有 `duplicate_detection` 配置 |
| **接口适配** | 使用 Polars 过滤，适配现有接口 |

### 8.2 与评估建议的对应

| 评估建议 | 本方案实现 |
|---------|-----------|
| 扩展 CoverageManager | ✅ 添加 3 个新方法 |
| 不新增独立模块 | ✅ 无新模块 |
| 复用现有配置 | ✅ 复用 duplicate_detection |
| 适配 StorageManager 接口 | ✅ 使用 Polars filter() |
| 优先 stock_loop 模式 | ✅ 仅对 stock_loop 生效 |

### 8.3 预期收益

1. **减少 API 调用**：仅下载缺失的日期段
2. **提高数据完整性**：精确检测日期级缺口
3. **降低维护成本**：复用现有架构，减少代码复杂度
