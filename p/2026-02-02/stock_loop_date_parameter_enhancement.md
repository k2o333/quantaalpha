# stock_loop 模式日期参数增强方案

## 需求背景

当前 `stock_loop` 模式在处理日期参数时存在以下问题：
1. 接口支持 `start_date` 和 `end_date` 参数时，main.py 的命令行参数会被忽略
2. 接口使用其他日期锚定参数（如 `period`、`ann_date`、`trade_date`）时，无法利用命令行日期范围进行遍历

## 需求整理

### 场景 1：接口直接支持 start_date/end_date 参数
- **条件**：接口的 YAML 配置中定义了 `start_date` 和 `end_date` 两个 parameter
- **行为**：main.py 的 `--start_date` 和 `--end_date` 命令行参数直接透传给接口
- **处理方式**：保持现有的参数传递逻辑

### 场景 2：接口使用其他日期锚定参数（period/ann_date/trade_date 等）
- **条件**：
  1. 接口的 YAML 配置没有（或作废了）`start_date` 和 `end_date` 参数
  2. 配置了其他日期参数，如 `period`、`ann_date`、`trade_date` 等
  3. 这些参数在 YAML 中被标注为**日期锚定参数**
- **行为**：
  - 根据 main.py 的 `--start_date` 和 `--end_date` 确定总日期范围
  - 在该范围内，按照 `window_size_days` 进行时间窗口遍历
  - 每个窗口使用日期锚定参数进行请求
- **处理方式**：
  - 需要在 YAML 中增加日期锚定参数的标识（如 `is_date_anchor: true`）
  - 需要在代码中实现窗口遍历逻辑，将时间范围转换为多个锚定参数的请求

---

## 技术方案

### 1. YAML 配置扩展

在接口配置的 `parameters` 节点中增加 `is_date_anchor` 标识：

```yaml
parameters:
  start_date:
    description: 报告期开始日期 YYYYMMDD
    required: false
    type: string
    is_date_anchor: false  # 默认值，可省略
  end_date:
    description: 报告期结束日期 YYYYMMDD
    required: false
    type: string
    is_date_anchor: false  # 默认值，可省略
  period:
    description: 报告期 YYYYMMDD
    required: false
    type: string
    is_date_anchor: true   # 标识为日期锚定参数
  ann_date:
    description: 公告日期 YYYYMMDD
    required: false
    type: string
    is_date_anchor: true   # 标识为日期锚定参数
```

**规则**：
- `is_date_anchor: true` 表示该参数用于遍历日期范围
- 一个接口只能有**一个**日期锚定参数（如果有多个，需在验证时抛出警告）
- `start_date` 和 `end_date` 默认 `is_date_anchor: false`（用于范围过滤，不是遍历锚点）

### 2. 核心代码修改

#### 2.1 `app4/main.py` 修改

**位置**：`main.py:648-658`（stock_loop 模式处理逻辑）

**修改前**：
```python
if pagination_config.get('enabled', False) and pagination_config.get('mode') == 'stock_loop':
    logger.info(f"Using stock_loop mode for {interface_name}")
    
    # [修正] stock_loop 模式：不传递日期参数，让接口返回全历史
    params = {}
    if args.ts_code:
        params['ts_code'] = args.ts_code
    logger.info(f"Using stock_loop mode for {interface_name}, fetching full history")
```

**修改后**：
```python
if pagination_config.get('enabled', False) and pagination_config.get('mode') == 'stock_loop':
    logger.info(f"Using stock_loop mode for {interface_name}")
    
    # [增强] 检查接口是否支持 start_date/end_date 参数
    parameter_config = interface_config.get('parameters', {})
    has_start_end = 'start_date' in parameter_config and 'end_date' in parameter_config
    
    # 检查是否有日期锚定参数
    date_anchor_param = None
    for param_name, param_def in parameter_config.items():
        if param_def.get('is_date_anchor', False):
            if date_anchor_param:
                logger.warning(f"Multiple date anchor parameters found for {interface_name}: {date_anchor_param}, {param_name}. Using first: {date_anchor_param}")
            else:
                date_anchor_param = param_name
    
    if has_start_end:
        # 场景 1：接口支持 start_date/end_date，直接透传命令行参数
        params = {
            'start_date': args.start_date,
            'end_date': args.end_date
        }
        if args.ts_code:
            params['ts_code'] = args.ts_code
        logger.info(f"Using start_date/end_date for {interface_name}: {args.start_date} - {args.end_date}")
    elif date_anchor_param:
        # 场景 2：接口使用日期锚定参数，传递范围供遍历
        params = {
            'start_date': args.start_date,
            'end_date': args.end_date,
            '_date_anchor_param': date_anchor_param  # 内部标记，用于分页执行器
        }
        if args.ts_code:
            params['ts_code'] = args.ts_code
        logger.info(f"Using date anchor parameter '{date_anchor_param}' for {interface_name}: {args.start_date} - {args.end_date}")
    else:
        # 原有逻辑：没有日期参数，获取全历史
        params = {}
        if args.ts_code:
            params['ts_code'] = args.ts_code
        logger.info(f"Using stock_loop mode for {interface_name}, fetching full history (no date parameters)")
```

#### 2.2 `app4/core/pagination.py` 修改

**位置**：`app4/core/pagination.py:368-390`（`generate_stock_params` 方法）

**新增方法**：在 `ParameterGenerator` 类中增加日期锚定参数遍历方法

```python
def generate_stock_date_anchor_params(
    self,
    base_params: Dict[str, Any],
    existing_stocks_checker: Optional[Callable[[str, str], bool]] = None
) -> Iterator[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    生成股票循环+日期锚定参数遍历
    
    场景：接口使用 period/ann_date/trade_date 等日期锚定参数，
         需要在命令行指定的日期范围内按窗口遍历
    
    Args:
        base_params: 基础参数（包含 start_date, end_date, _date_anchor_param）
        existing_stocks_checker: 可选的回调函数，用于检查股票数据是否存在
    
    Yields:
        (参数, 股票信息) 元组，参数包含日期锚定参数的当前窗口值
    """
    if not self.context.stock_list:
        logger.error("Stock list not provided for stock loop pagination")
        return
    
    # 提取日期范围和锚定参数
    start_date = base_params.get('start_date')
    end_date = base_params.get('end_date')
    date_anchor_param = base_params.get('_date_anchor_param')
    
    if not start_date or not end_date or not date_anchor_param:
        logger.error(f"Missing required params: start_date={start_date}, end_date={end_date}, date_anchor_param={date_anchor_param}")
        return
    
    # 获取窗口大小
    window_size = self.context.pagination_config.get('window_size_days', 365)
    
    # 获取交易日历
    trade_calendar = self.context.trade_calendar or []
    
    if not trade_calendar:
        logger.warning(f"No trade calendar provided, using daily date generation")
        # 如果没有交易日历，使用简单的日期遍历
        from datetime import datetime, timedelta
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')
        current = start_dt
        date_points = []
        while current <= end_dt:
            date_points.append(current.strftime('%Y%m%d'))
            current += timedelta(days=window_size)
    else:
        # 使用交易日历生成日期点
        trade_days = [
            day for day in trade_calendar
            if day.get('is_open', 0) == 1 and
               start_date <= day['cal_date'] <= end_date
        ]
        trade_days.sort(key=lambda x: x['cal_date'])
        
        # 按窗口大小分割
        date_points = []
        for i in range(0, len(trade_days), window_size):
            window = trade_days[i:i + window_size]
            if window:
                # 根据锚定参数类型选择窗口的结束日期
                date_points.append(window[-1]['cal_date'])
    
    logger.info(f"Generated {len(date_points)} date points for anchor parameter '{date_anchor_param}'")
    
    # 为每只股票生成日期锚定参数遍历
    for stock in self.context.stock_list:
        ts_code = stock['ts_code']
        
        # 前置去重检查
        if not self.context.force_download and existing_stocks_checker:
            if existing_stocks_checker(self.context.interface_name, ts_code):
                logger.debug(f"Skipping stock {ts_code} (data exists)")
                continue
        
        # 为每个日期点生成参数
        for date_point in date_points:
            stock_params = base_params.copy()
            stock_params['ts_code'] = ts_code
            
            # 移除内部标记和日期范围参数
            stock_params.pop('_date_anchor_param', None)
            stock_params.pop('start_date', None)
            stock_params.pop('end_date', None)
            
            # 设置日期锚定参数
            stock_params[date_anchor_param] = date_point
            
            yield stock_params, stock
```

#### 2.3 `app4/core/pagination_executor.py` 修改

**位置**：`app4/core/pagination_executor.py:193-240`（`execute_stock_loop_pagination` 方法）

**修改逻辑**：
在 `execute_stock_loop_pagination` 方法中，检测是否有 `_date_anchor_param` 标记，如果有则使用新的日期锚定参数遍历方法。

```python
def execute_stock_loop_pagination(self, interface_config: Dict[str, Any],
                                 params: Dict[str, Any],
                                 context: PaginationContext,
                                 make_request_callback: Callable,
                                 get_stock_list_callback: Callable,
                                 coverage_manager: Optional[Any] = None,
                                 force_download: bool = False) -> List[Dict[str, Any]]:
    """执行股票循环分页，支持日期锚定参数遍历"""
    # 获取股票列表
    logger.info("正在获取股票列表...")
    stock_list = get_stock_list_callback()

    if not stock_list:
        logger.error("Failed to get stock list for stock loop pagination")
        return []

    # 更新上下文
    context.stock_list = stock_list

    # 创建参数生成器
    param_gen = ParameterGenerator(context)

    # 确定并发数
    interface_name = interface_config['name']
    if interface_name in ['fina_audit', 'forecast_vip', 'express_vip', 'disclosure_date']:
        max_workers = 1
    elif interface_name in ['top10_holders', 'top10_floatholders', 'pledge_detail', 'dividend']:
        max_workers = 2
    else:
        max_workers = 4

    all_data = []

    # [新增] 检查是否有日期锚定参数标记
    if '_date_anchor_param' in params:
        logger.info(f"Using date anchor parameter: {params['_date_anchor_param']}")
        
        # 使用日期锚定参数遍历
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            
            for stock_params, stock_info in param_gen.generate_stock_date_anchor_params(
                params,
                existing_stocks_checker=lambda name, code: self._is_stock_data_exists(name, code, coverage_manager)
            ):
                future = executor.submit(
                    make_request_callback,
                    interface_config,
                    stock_params
                )
                futures[future] = (stock_info['ts_code'], stock_params)
            
            for future in as_completed(futures):
                ts_code, stock_params = futures[future]
                try:
                    data = future.result()
                    if data:
                        all_data.extend(data)
                        logger.info(f"Downloaded {len(data)} records for {ts_code}")
                except Exception as e:
                    logger.error(f"Error downloading stock {ts_code}: {e}")
    else:
        # [原有逻辑] 普通股票循环
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            
            for stock_params, stock_info in param_gen.generate_stock_params(
                params,
                existing_stocks_checker=lambda name, code: self._is_stock_data_exists(name, code, coverage_manager)
            ):
                future = executor.submit(
                    make_request_callback,
                    interface_config,
                    stock_params
                )
                futures[future] = (stock_info['ts_code'], stock_params)
            
            for future in as_completed(futures):
                ts_code, stock_params = futures[future]
                try:
                    data = future.result()
                    if data:
                        all_data.extend(data)
                        logger.info(f"Downloaded {len(data)} records for {ts_code}")
                except Exception as e:
                    logger.error(f"Error downloading stock {ts_code}: {e}")

    return all_data
```

### 3. 配置验证

在 `app4/core/config_loader.py` 中增加配置验证逻辑：

```python
def _validate_date_anchor_parameters(self, interface_config: Dict[str, Any]) -> bool:
    """
    验证日期锚定参数配置
    
    规则：
    1. 一个接口只能有一个日期锚定参数
    2. 日期锚定参数不能是 start_date 或 end_date
    """
    parameter_config = interface_config.get('parameters', {})
    date_anchor_params = []
    
    for param_name, param_def in parameter_config.items():
        if param_def.get('is_date_anchor', False):
            if param_name in ['start_date', 'end_date']:
                logger.error(f"Invalid date anchor parameter '{param_name}' in interface {interface_config.get('name')}: start_date and end_date cannot be date anchors")
                return False
            date_anchor_params.append(param_name)
    
    if len(date_anchor_params) > 1:
        logger.warning(f"Multiple date anchor parameters found in interface {interface_config.get('name')}: {date_anchor_params}. Only the first one will be used")
    
    return True
```

在 `validate_config` 方法中调用此验证。

---

## 日期锚定参数类型处理

不同的日期锚定参数需要不同的遍历策略：

| 参数类型 | 遍历策略 | 示例 |
|---------|---------|------|
| `period` | 季度末日期 | 20230331, 20230630, 20230930, 20231231 |
| `ann_date` | 交易日历或固定间隔 | 根据窗口大小遍历交易日历 |
| `trade_date` | 交易日历 | 遍历每个交易日 |
| `end_date` | 交易日历 | 与 ann_date 类似 |

### 实现方式

在 `generate_stock_date_anchor_params` 方法中，根据 `date_anchor_param` 的类型选择遍历策略：

```python
def _generate_date_points_by_type(self, start_date: str, end_date: str, 
                                  anchor_param: str, window_size: int) -> List[str]:
    """
    根据日期锚定参数类型生成日期点
    
    Args:
        start_date: 开始日期
        end_date: 结束日期
        anchor_param: 锚定参数名称
        window_size: 窗口大小
    
    Returns:
        日期点列表
    """
    from datetime import datetime, timedelta
    
    if anchor_param == 'period':
        # 季度末日期
        return generate_quarter_end_dates(start_date, end_date)
    elif anchor_param in ['ann_date', 'end_date']:
        # 按窗口大小遍历交易日历
        if self.context.trade_calendar:
            trade_days = [
                day for day in self.context.trade_calendar
                if day.get('is_open', 0) == 1 and
                   start_date <= day['cal_date'] <= end_date
            ]
            trade_days.sort(key=lambda x: x['cal_date'])
            date_points = []
            for i in range(0, len(trade_days), window_size):
                window = trade_days[i:i + window_size]
                if window:
                    date_points.append(window[-1]['cal_date'])
            return date_points
        else:
            # 退化为简单的日期遍历
            start_dt = datetime.strptime(start_date, '%Y%m%d')
            end_dt = datetime.strptime(end_date, '%Y%m%d')
            current = start_dt
            date_points = []
            while current <= end_dt:
                date_points.append(current.strftime('%Y%m%d'))
                current += timedelta(days=window_size)
            return date_points
    elif anchor_param == 'trade_date':
        # 每个交易日
        if self.context.trade_calendar:
            return [
                day['cal_date'] for day in self.context.trade_calendar
                if day.get('is_open', 0) == 1 and
                   start_date <= day['cal_date'] <= end_date
            ]
        else:
            # 退化为每日遍历
            start_dt = datetime.strptime(start_date, '%Y%m%d')
            end_dt = datetime.strptime(end_date, '%Y%m%d')
            current = start_dt
            date_points = []
            while current <= end_dt:
                date_points.append(current.strftime('%Y%m%d'))
                current += timedelta(days=1)
            return date_points
    else:
        # 默认使用窗口遍历
        return self._generate_date_points_by_type(start_date, end_date, 'ann_date', window_size)
```

---

## 向后兼容性

### 兼容性保证

1. **未配置 `is_date_anchor` 的接口**：保持原有行为（全历史下载）
2. **只配置了 `start_date`/`end_date` 的接口**：使用场景 1 的逻辑（透传命令行参数）
3. **配置了 `is_date_anchor: true` 的接口**：使用场景 2 的逻辑（日期锚定遍历）

### 迁移建议

对于现有接口，如果需要使用日期锚定功能：
1. 在 YAML 配置中为日期参数添加 `is_date_anchor: true`
2. 确保 `window_size_days` 配置合理
3. 测试验证功能是否符合预期

---

## 测试计划

### 单元测试

1. **配置验证测试**：测试 `is_date_anchor` 配置的验证逻辑
2. **参数生成测试**：测试 `generate_stock_date_anchor_params` 方法的各种场景
3. **日期点生成测试**：测试不同类型锚定参数的日期点生成逻辑

### 集成测试

1. **场景 1 测试**：配置了 `start_date`/`end_date` 的接口
2. **场景 2 测试**：配置了 `is_date_anchor: true` 的接口（period/ann_date/trade_date）
3. **兼容性测试**：未配置日期参数的接口（原有行为）

### 测试用例示例

```python
# 测试场景 1
def test_stock_loop_with_start_end_date():
    # 接口配置了 start_date 和 end_date
    # 命令行参数 --start_date 20230101 --end_date 20231231
    # 验证参数正确透传
    pass

# 测试场景 2 - period
def test_stock_loop_with_period_anchor():
    # 接口配置了 period 且 is_date_anchor: true
    # 命令行参数 --start_date 20230101 --end_date 20231231
    # 验证按季度末日期遍历
    pass

# 测试场景 2 - ann_date
def test_stock_loop_with_ann_date_anchor():
    # 接口配置了 ann_date 且 is_date_anchor: true
    # 命令行参数 --start_date 20230101 --end_date 20231231
    # 验证按窗口大小遍历
    pass

# 测试兼容性
def test_stock_loop_backward_compatibility():
    # 接口未配置日期参数
    # 验证原有行为（全历史下载）
    pass
```

---

## 实施步骤

1. **Phase 1: YAML 配置扩展**
   - 在接口配置中添加 `is_date_anchor` 字段
   - 更新配置验证逻辑

2. **Phase 2: 核心代码修改**
   - 修改 `main.py` 的 stock_loop 模式处理逻辑
   - 在 `pagination.py` 中添加 `generate_stock_date_anchor_params` 方法
   - 修改 `pagination_executor.py` 的 `execute_stock_loop_pagination` 方法

3. **Phase 3: 日期点生成逻辑**
   - 实现不同类型锚定参数的日期点生成策略
   - 添加交易日历支持

4. **Phase 4: 测试与验证**
   - 编写单元测试
   - 编写集成测试
   - 验证向后兼容性

5. **Phase 5: 文档更新**
   - 更新接口配置文档
   - 更新使用说明

---

## 风险与注意事项

1. **性能风险**：日期锚定遍历可能产生大量请求，需要合理配置 `window_size_days`
2. **API 限制**：注意 TuShare API 的频率限制，避免触发限流
3. **数据一致性**：确保日期锚定遍历不会导致数据重复或遗漏
4. **配置错误**：错误的 `is_date_anchor` 配置可能导致意外行为，需要严格的配置验证

---

## 总结

本方案通过引入 `is_date_anchor` 配置标识，实现了 stock_loop 模式下对日期参数的灵活处理：

- **场景 1**：接口支持 `start_date`/`end_date`，直接透传命令行参数
- **场景 2**：接口使用日期锚定参数，在命令行日期范围内按窗口遍历
- **向后兼容**：未配置日期参数的接口保持原有行为

方案设计保持了代码的清晰性和可维护性，同时提供了灵活的配置能力。