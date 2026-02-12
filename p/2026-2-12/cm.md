# Stock Loop 模式智能增量下载方案 - 修改建议

## 一、核心问题总结

经过对 `complete_solution.md` 方案与 `app4/` 现有代码的深度对比分析，发现以下关键兼容性问题：

| 问题类型 | 严重程度 | 影响范围 |
|---------|---------|---------|
| 职责重叠 | 高 | 架构层面 |
| 配置体系冲突 | 高 | 40+ 配置文件 |
| 接口不兼容 | 中 | StorageManager |
| 分页模式不匹配 | 中 | 大部分高频接口 |

---

## 二、详细问题分析

### 2.1 职责重叠问题

**方案提议的 `StockLoopPlanner` 类功能：**
- `_get_existing_dates_for_stock()` - 获取单只股票已有日期
- `_detect_date_gaps()` - 检测日期缺口
- `_plan_date_range_mode()` - 生成下载计划

**现有架构已具备的功能：**

| 现有模块 | 已有功能 | 与方案重叠度 |
|---------|---------|-------------|
| `CoverageManager` | `_check_stock_existence()` - 股票存在性检查 | 60% |
| `DateCalculator` | `calculate_update_range()` - 日期范围计算 | 70% |
| `PaginationComposer` | `_apply_stock_loop()` - 股票循环处理 | 50% |
| `PaginationExecutor` | 执行分页请求、覆盖率跳过逻辑 | 40% |

**建议**：不新增 `StockLoopPlanner`，而是在现有 `CoverageManager` 中扩展功能。

---

### 2.2 配置体系冲突

**方案提议的新配置格式：**
```yaml
# 需要新增 date_params 字段
date_params:
  mode: "date_range"
  data_date_column: "trade_date"
  input_mapping:
    start_date: "start_date"
  default_start_date: "20000101"
  lookback_days: 7
```

**现有配置格式：**
```yaml
# daily_basic.yaml 现有配置
duplicate_detection:
  enabled: true
  date_column: "trade_date"  # 已有日期列配置
  threshold: 0.95

parameters:
  start_date:
    type: string
    required: false
  end_date:
    type: string
    required: false
```

**问题**：
1. 需要修改 40+ 个接口配置文件
2. `data_date_column` 与 `duplicate_detection.date_column` 语义重复
3. `mode` 字段与 `pagination.mode` 容易混淆

**建议**：复用现有配置字段，不新增 `date_params` 块。

---

### 2.3 接口不兼容问题

**方案代码中的调用：**
```python
# stock_loop_planner.py 第 448-453 行
df = self.coverage_manager.storage_manager.read_interface_data(
    interface_name,
    filters={'ts_code': ts_code},  # ❌ 不支持 filters 参数
    columns=[date_column]
)
```

**现有 StorageManager 接口：**
```python
# storage.py 实际接口
def read_interface_data(
    self,
    interface_name: str,
    columns: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> pl.DataFrame:
    # 不支持 filters 参数！
```

**建议**：扩展 `StorageManager.read_interface_data()` 支持 `filters` 参数，或使用 Polars 的 `filter()` 方法在读取后过滤。

---

### 2.4 分页模式不匹配

**现有接口分页模式分布：**

| 接口 | 现有模式 | 方案目标模式 | 兼容性 |
|-----|---------|-------------|--------|
| `daily_basic` | `reverse_date_range` | `stock_loop` | ❌ 冲突 |
| `moneyflow` | `reverse_date_range` | `stock_loop` | ❌ 冲突 |
| `income_vip` | `stock_loop` | `stock_loop` | ✅ 兼容 |
| `disclosure_date` | `stock_loop` + `is_date_anchor` | `date_anchor` | ⚠️ 部分兼容 |

**问题**：方案核心功能（股票级缺口检测）仅对 `stock_loop` 模式有效，而高频接口使用 `reverse_date_range`。

**建议**：
1. 优先为 `stock_loop` 模式接口实现股票级增量
2. `reverse_date_range` 接口继续使用现有的日期范围覆盖率检测

---

## 三、具体修改建议

### 3.1 方案一：最小侵入式扩展（推荐）

**思路**：在现有架构上扩展，不新增核心模块。

#### 步骤 1：扩展 CoverageManager

在 `app4/core/coverage_manager.py` 中添加：

```python
def get_stock_existing_dates(
    self,
    interface_name: str,
    ts_code: str,
    date_column: str = 'trade_date'
) -> set:
    """
    获取指定股票已存在的所有日期
    
    新增方法，支持股票级别的日期缺口检测
    """
    try:
        # 读取数据后过滤（适配现有接口）
        df = self.storage_manager.read_interface_data(
            interface_name,
            columns=[date_column, 'ts_code']
        )
        
        if df.is_empty():
            return set()
        
        # 按股票代码过滤
        filtered = df.filter(pl.col('ts_code') == ts_code)
        if filtered.is_empty():
            return set()
        
        dates = set()
        for date_val in filtered[date_column]:
            formatted = format_date(date_val)
            if formatted:
                dates.add(formatted)
        
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
    date_column: str = 'trade_date'
) -> List[tuple]:
    """
    检测指定股票在日期范围内的缺口
    
    Returns:
        List[tuple]: 缺失的日期段列表 [(start, end), ...]
    """
    existing_dates = self.get_stock_existing_dates(
        interface_name, ts_code, date_column
    )
    
    # 获取交易日历
    trade_calendar = self.downloader.get_trade_calendar(start_date, end_date)
    if not trade_calendar:
        return [(start_date, end_date)]
    
    trade_days = [
        d['cal_date'] for d in trade_calendar 
        if d.get('is_open', 0) == 1
    ]
    
    # 找出缺失的交易日
    missing_days = [d for d in trade_days if d not in existing_dates]
    
    if not missing_days:
        return []
    
    # 合并为连续区间
    return self._merge_to_ranges(missing_days)

def _merge_to_ranges(self, dates: List[str]) -> List[tuple]:
    """将日期列表合并为连续区间"""
    if not dates:
        return []
    
    sorted_dates = sorted(dates)
    ranges = []
    range_start = sorted_dates[0]
    range_end = sorted_dates[0]
    
    for i in range(1, len(sorted_dates)):
        curr = sorted_dates[i]
        prev = sorted_dates[i-1]
        
        # 判断是否连续（允许周末间隔）
        curr_dt = datetime.strptime(curr, '%Y%m%d')
        prev_dt = datetime.strptime(prev, '%Y%m%d')
        
        if (curr_dt - prev_dt).days <= 3:
            range_end = curr
        else:
            ranges.append((range_start, range_end))
            range_start = curr
            range_end = curr
    
    ranges.append((range_start, range_end))
    return ranges
```

#### 步骤 2：扩展配置支持（可选字段）

在接口配置中添加可选字段，复用现有结构：

```yaml
# daily_basic.yaml 修改示例
duplicate_detection:
  enabled: true
  date_column: "trade_date"
  threshold: 0.95
  # 新增可选字段
  stock_level_detection: true  # 启用股票级别检测
  lookback_days: 7             # 回溯天数

pagination:
  enabled: true
  mode: stock_loop  # 或保持 reverse_date_range
  skip_existing_stocks: true   # 新增：跳过已有数据的股票
```

#### 步骤 3：修改 PaginationComposer

在 `app4/core/pagination.py` 的 `_apply_stock_loop()` 方法中集成：

```python
def _apply_stock_loop(self, params_stream: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
    """应用股票循环维度 - 增强版"""
    stock_list = self.context.stock_list
    if not stock_list:
        logger.error("Stock list not provided")
        return
    
    skip_existing = self.config.get('stock_loop', {}).get('skip_existing', False)
    stock_level_detection = self.interface_config.get('duplicate_detection', {}).get('stock_level_detection', False)
    
    for params in params_stream:
        for stock in stock_list:
            ts_code = stock.get('ts_code')
            if not ts_code:
                continue
            
            # 股票级别缺口检测
            if stock_level_detection and self.context.coverage_manager and not self.context.force_download:
                date_column = self.interface_config.get('duplicate_detection', {}).get('date_column', 'trade_date')
                gaps = self.context.coverage_manager.detect_stock_date_gaps(
                    self.interface_config.get('api_name'),
                    ts_code,
                    params.get('start_date', '20000101'),
                    params.get('end_date', datetime.now().strftime('%Y%m%d')),
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
                    yield gap_params
            else:
                # 原有逻辑
                if skip_existing and not self.context.force_download:
                    if self._stock_data_exists(ts_code):
                        continue
                
                stock_params = params.copy()
                stock_params['ts_code'] = ts_code
                stock_params['_stock_info'] = stock
                yield stock_params
```

---

### 3.2 方案二：独立模块（备选）

如果坚持使用独立模块，建议：

1. **重命名模块**：`stock_loop_planner.py` → `incremental_planner.py`，明确其作为增量下载策略的角色

2. **修改依赖方式**：作为 `CoverageManager` 的策略组件，而非独立调用：
   ```python
   # 在 CoverageManager 中
   def __init__(self, ...):
       self.incremental_planner = IncrementalPlanner(self, config_loader)
   ```

3. **配置字段复用**：使用现有配置字段，不新增 `date_params`：
   ```yaml
   # 复用 duplicate_detection 配置
   duplicate_detection:
     enabled: true
     date_column: "trade_date"
     mode: "date_range"  # 新增：参数模式
   ```

---

## 四、实施优先级建议

| 优先级 | 任务 | 工作量 | 风险 |
|-------|-----|-------|-----|
| P0 | 扩展 `CoverageManager` 添加 `get_stock_existing_dates()` | 2h | 低 |
| P0 | 扩展 `CoverageManager` 添加 `detect_stock_date_gaps()` | 3h | 低 |
| P1 | 修改 `PaginationComposer._apply_stock_loop()` 集成缺口检测 | 4h | 中 |
| P2 | 为 `stock_loop` 模式接口添加 `stock_level_detection` 配置 | 1h/接口 | 低 |
| P3 | 扩展 `StorageManager` 支持 `filters` 参数（可选优化） | 3h | 中 |

**预计总工作量**：方案一约 15-20 小时，方案二约 25-30 小时。

---

## 五、总结

1. **不推荐直接应用原方案**：与现有架构存在较多冲突，增加维护负担

2. **推荐方案一**：在现有 `CoverageManager` 和 `PaginationComposer` 基础上扩展，保持架构一致性

3. **配置设计建议**：复用 `duplicate_detection` 配置块，新增 `stock_level_detection` 和 `lookback_days` 字段

4. **实施路径**：先实现核心方法，再逐步为各接口启用功能