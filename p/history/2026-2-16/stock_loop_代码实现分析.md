# Stock Loop 模式代码实现分析

**日期**: 2026-02-16  
**目的**: 分析现有代码如何实现三种接口类型（A/B/C）的 8 种场景行为

---

## 一、核心组件架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         main.py                                  │
│  - 解析命令行参数，设置 user_provided_dates 标记                   │
│  - 调用 ParamsBuilder.build() 构建初始参数                       │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ParamsBuilder                                 │
│  - _detect_scenario(): 检测下载场景类型                          │
│  - build_params_list(): 为每只股票生成初始参数（未检测缺口）       │
│  - 创建 DownloadContext（传递 user_provided_dates）              │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PaginationComposer                            │
│  - compose(): 组合分页维度（time_range → stock_loop → offset）   │
│  - _apply_stock_loop(): 遍历股票列表，调用缺口检测               │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CoverageManager                               │
│  - detect_stock_gaps(): 统一缺口检测入口                         │
│  - _determine_gap_mode(): 判断接口类型 (A/B/C/D)                 │
│  - 根据已有数据生成具体的缺口下载任务                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、完整执行流程

```
main.py
  │
  ├─→ ParamsBuilder.build() 
  │     └─→ 检测场景类型（DATE_RANGE/DATE_ANCHOR/FULL_HISTORY）
  │     └─→ 构建初始参数（start_date, end_date, ts_code）
  │
  ├─→ ParamsBuilder.build_params_list()
  │     └─→ 为每只股票生成一个初始参数（还未检测缺口）
  │     └─→ 创建 DownloadContext（包含 user_provided_dates）
  │
  └─→ run_concurrent_stock_download()
        │
        └─→ downloader.download(interface_name, params)
              │
              └─→ _execute_pagination()
                    │
                    └─→ PaginationComposer.compose()
                          │
                          ├─→ _apply_time_range() (如果启用)
                          │
                          └─→ _apply_stock_loop()  ← 缺口检测在这里！
                                │
                                └─→ CoverageManager.detect_stock_gaps()
                                      │
                                      └─→ 根据已有数据生成缺口任务
```

---

## 三、各阶段职责说明

| 阶段 | 组件 | 职责 | 输入 | 输出 |
|------|------|------|------|------|
| **参数构建** | ParamsBuilder | 决定"怎么查" | 用户参数 + 接口配置 | 场景类型 + 初始参数范围 |
| **分页组合** | PaginationComposer | 组合分页维度 | 初始参数 + 股票列表 | 参数流（迭代器） |
| **缺口检测** | CoverageManager | 决定"查什么" | 已有数据 + 日期范围 | 具体的缺口任务列表 |

**设计要点**：
- **ParamsBuilder** 不查询已有数据，只根据接口配置判断场景类型
- **CoverageManager** 在分页执行阶段才被调用，查询已有数据并生成缺口任务
- 这样设计避免了在参数构建阶段频繁读取存储，提高了效率

---

## 四、场景检测逻辑

**文件**: [params_builder.py](file:///home/quan/testdata/aspipe_v4/app4/core/params_builder.py#L107-L139)

```python
def _detect_scenario(self, ts_code, user_provided_dates, start_date, end_date):
    # 1. 检查是否是 stock_loop 模式
    is_stock_loop = (
        self.pagination_config.get('enabled', False) and
        self.pagination_config.get('mode') == 'stock_loop'
    )
    if not is_stock_loop:
        return DownloadScenario.DIRECT

    # 2. 检查是否有 start_date + end_date 参数（Type A/B）
    has_start_end = 'start_date' in self.parameter_config and 'end_date' in self.parameter_config

    # 3. 检查是否有日期锚定参数（Type C）
    date_anchor_param = self._find_date_anchor_param()

    # Type A/B 接口：有 start_date + end_date 参数
    if has_start_end:
        return DownloadScenario.STOCK_LOOP_DATE_RANGE

    # Type C 接口：有日期锚定参数
    if date_anchor_param:
        if not user_provided_dates:
            return DownloadScenario.STOCK_LOOP_FULL_HISTORY  # 全历史模式
        return DownloadScenario.STOCK_LOOP_DATE_ANCHOR  # 按锚点遍历模式

    return DownloadScenario.STOCK_LOOP_FULL_HISTORY
```

---

## 五、接口类型判断

**文件**: [coverage_manager.py](file:///home/quan/testdata/aspipe_v4/app4/core/coverage_manager.py#L758-L793)

```python
def _determine_gap_mode(self, interface_config):
    parameters = interface_config.get('parameters', {})
    detection_config = interface_config.get('duplicate_detection', {})
    date_column = detection_config.get('date_column', 'trade_date')

    # 1. 有 is_date_anchor=true → 类型 C
    if any(p.get('is_date_anchor', False) for p in parameters.values()):
        return 'date_anchor'

    # 2. 有 start_date + end_date 参数 → 类型 A 或 B（根据 date_column 区分）
    if 'start_date' in parameters and 'end_date' in parameters:
        return 'trade_date' if date_column == 'trade_date' else 'report_period'

    # 3. 无任何日期参数 → 类型 D
    has_date_param = any(p in parameters for p in ['start_date', 'end_date', 'trade_date', 'period', 'ann_date'])
    if not has_date_param:
        return 'no_date_filter'

    # 4. 其他情况
    return 'trade_date' if date_column == 'trade_date' else 'report_period'
```

---

## 六、Type A（交易日历接口）实现

### 6.1 适用接口

`cyq_chips`, `moneyflow_dc`, `stk_factor_pro`

### 6.2 配置特征

```yaml
# cyq_chips.yaml
duplicate_detection:
  date_column: "trade_date"  # 关键标识
parameters:
  start_date: {...}
  end_date: {...}
```

### 6.3 缺口检测实现

**文件**: [coverage_manager.py](file:///home/quan/testdata/aspipe_v4/app4/core/coverage_manager.py#L795-L862)

```python
def _detect_trade_date_gaps(self, interface_name, ts_code, start_date, end_date, 
                            date_column, user_provided_dates, stock_info):
    existing_dates = self.get_stock_existing_dates(interface_name, ts_code, date_column)

    # 场景 1 & 5: 无已有数据
    if not existing_dates:
        if user_provided_dates:
            # 场景 5: 用户提供了日期 → 按指定范围下载
            return [{'ts_code': ts_code, 'start_date': start_date, 'end_date': end_date}]
        else:
            # 场景 1: 用户未提供日期 → 只传 ts_code，获取全历史
            return [{'ts_code': ts_code}]

    # 场景 2, 3, 4, 6, 7, 8: 有已有数据
    trade_days = get_trade_calendar(start_date, end_date)

    if not user_provided_dates:
        # 场景 2, 4: 用户未提供日期 → 只检测现有数据之后的缺失日期
        max_existing_date = max(existing_dates)
        trade_days = [d for d in trade_days if d > max_existing_date]

    # 检测缺失的交易日
    missing_days = [d for d in trade_days if d not in existing_dates]
    ranges = self._merge_dates_to_ranges(missing_days)

    return [{'ts_code': ts_code, 'start_date': r[0], 'end_date': r[1]} for r in ranges]
```

### 6.4 八种场景行为对照

| 场景 | 用户提供日期 | ts_code | 已有数据 | 代码执行路径 |
|------|-------------|---------|---------|-------------|
| 1 | ❌ | ✅ | ❌ | `return [{'ts_code': ts_code}]` |
| 2 | ❌ | ✅ | ✅ | 检测 `max_existing_date` 之后的缺失日期 |
| 3 | ❌ | ❌ | ❌ | 触发所有股票轮询，每只股票执行场景 1 |
| 4 | ❌ | ❌ | ✅ | 触发所有股票轮询，每只股票执行场景 2 |
| 5 | ✅ | ✅ | ❌ | `return [{'ts_code': ts_code, 'start_date': ..., 'end_date': ...}]` |
| 6 | ✅ | ✅ | ✅ | 检测指定范围内的缺失日期 |
| 7 | ✅ | ❌ | ❌ | 触发所有股票轮询，每只股票执行场景 5 |
| 8 | ✅ | ❌ | ✅ | 触发所有股票轮询，每只股票执行场景 6 |

---

## 七、Type B（报告期接口）实现

### 7.1 适用接口

`income_vip`, `balancesheet_vip`, `cashflow_vip`, `fina_indicator_vip`, `fina_audit`, `fina_mainbz_vip`, `forecast_vip`, `top10_floatholders`

### 7.2 配置特征

```yaml
# income_vip.yaml
duplicate_detection:
  date_column: "end_date"  # 关键标识（不是 trade_date）
parameters:
  start_date:
    is_date_anchor: false  # 明确标识为范围参数
  end_date:
    is_date_anchor: false
```

### 7.3 缺口检测实现

**文件**: [coverage_manager.py](file:///home/quan/testdata/aspipe_v4/app4/core/coverage_manager.py#L864-L956)

```python
def _detect_report_period_gaps(self, interface_name, ts_code, start_date, end_date,
                               date_column, user_provided_dates, stock_info):
    existing_dates = self.get_stock_existing_dates(interface_name, ts_code, date_column)
    expected_periods = self._generate_report_periods(start_date, end_date)  # 0331, 0630, 0930, 1231

    # 场景 1 & 5: 无已有数据
    if not existing_dates:
        if user_provided_dates:
            return [{'ts_code': ts_code, 'start_date': start_date, 'end_date': end_date}]
        else:
            return [{'ts_code': ts_code}]

    # 场景 2, 4: 用户未提供日期 → 只检测现有数据之后的缺失报告期
    if not user_provided_dates and existing_dates:
        max_existing_date = max(existing_dates)
        expected_periods = [p for p in expected_periods if p > max_existing_date]

    missing_periods = [p for p in expected_periods if p not in existing_dates]

    # 优化策略：缺失少则精确查询，缺失多则范围查询
    MAX_PRECISE_QUERIES = 3
    if len(missing_periods) <= MAX_PRECISE_QUERIES:
        # 精确查询每个缺失的报告期
        return [{'ts_code': ts_code, 'start_date': period_start, 'end_date': period} 
                for period in missing_periods]
    else:
        # 范围查询（最小覆盖区间）
        return [{'ts_code': ts_code, 'start_date': min_start, 'end_date': max_period}]
```

### 7.4 报告期生成逻辑

```python
def _generate_report_periods(self, start_date, end_date):
    periods = []
    quarter_ends = ['0331', '0630', '0930', '1231']
    for year in range(start_year - 1, end_year + 2):
        for qe in quarter_ends:
            period = f"{year}{qe}"
            if start_date <= period <= end_date:
                periods.append(period)
    return sorted(periods)
```

### 7.5 八种场景行为对照

| 场景 | 用户提供日期 | ts_code | 已有数据 | 代码执行路径 |
|------|-------------|---------|---------|-------------|
| 1 | ❌ | ✅ | ❌ | `return [{'ts_code': ts_code}]` |
| 2 | ❌ | ✅ | ✅ | 检测 `max_existing_date` 之后的缺失报告期 |
| 3 | ❌ | ❌ | ❌ | 触发所有股票轮询，每只股票执行场景 1 |
| 4 | ❌ | ❌ | ✅ | 触发所有股票轮询，每只股票执行场景 2 |
| 5 | ✅ | ✅ | ❌ | `return [{'ts_code': ts_code, 'start_date': ..., 'end_date': ...}]` |
| 6 | ✅ | ✅ | ✅ | 检测指定范围内的缺失报告期 |
| 7 | ✅ | ❌ | ❌ | 触发所有股票轮询，每只股票执行场景 5 |
| 8 | ✅ | ❌ | ✅ | 触发所有股票轮询，每只股票执行场景 6 |

---

## 八、Type C（日期锚定接口）实现

### 8.1 适用接口

`disclosure_date`, `top10_holders`, `dividend`, `pledge_stat`, `stk_rewards`

### 8.2 配置特征

```yaml
# disclosure_date.yaml
parameters:
  end_date:
    is_date_anchor: true  # 关键标识
```

### 8.3 场景检测逻辑

**文件**: [params_builder.py](file:///home/quan/testdata/aspipe_v4/app4/core/params_builder.py#L107-L139)

```python
if date_anchor_param:
    if not user_provided_dates:
        return DownloadScenario.STOCK_LOOP_FULL_HISTORY  # 全历史模式
    return DownloadScenario.STOCK_LOOP_DATE_ANCHOR  # 按锚点遍历模式
```

### 8.4 缺口检测实现

**文件**: [coverage_manager.py](file:///home/quan/testdata/aspipe_v4/app4/core/coverage_manager.py#L958-L1027)

```python
def _detect_date_anchor_gaps(self, interface_name, ts_code, start_date, end_date,
                             date_column, interface_config, user_provided_dates, stock_info):
    # 找到锚定参数名（如 end_date, period, ann_date）
    anchor_param = self._find_anchor_param(interface_config)
    existing_dates = self.get_stock_existing_dates(interface_name, ts_code, date_column)

    # 场景 1 & 5: 无已有数据
    if not existing_dates:
        if user_provided_dates:
            # 场景 5: 生成日期区间内的所有锚点值，逐个查询
            anchor_values = self._generate_anchor_values(start_date, end_date, anchor_param)
            return [{'ts_code': ts_code, anchor_param: anchor} for anchor in anchor_values]
        else:
            # 场景 1: 只传 ts_code，获取全历史
            return [{'ts_code': ts_code}]

    # 场景 2, 4: 用户未提供日期 → 检测现有数据之后的缺失锚点
    if not user_provided_dates:
        max_existing_date = max(existing_dates)
        anchor_values = self._generate_anchor_values(max_existing_date, end_date, anchor_param)
        missing_anchors = [a for a in anchor_values if a > max_existing_date]
    else:
        # 场景 6, 8: 用户提供了日期 → 生成区间内锚点，跳过已有的
        anchor_values = self._generate_anchor_values(start_date, end_date, anchor_param)
        missing_anchors = [a for a in anchor_values if a not in existing_dates]

    # Type C 特点：每个缺失锚点生成一个独立查询任务
    return [{'ts_code': ts_code, anchor_param: anchor} for anchor in missing_anchors]
```

### 8.5 八种场景行为对照

| 场景 | 用户提供日期 | ts_code | 已有数据 | 代码执行路径 |
|------|-------------|---------|---------|-------------|
| 1 | ❌ | ✅ | ❌ | `return [{'ts_code': ts_code}]` |
| 2 | ❌ | ✅ | ✅ | 检测 `max_existing_date` 之后的缺失锚点 |
| 3 | ❌ | ❌ | ❌ | 触发所有股票轮询，每只股票执行场景 1 |
| 4 | ❌ | ❌ | ✅ | 触发所有股票轮询，每只股票执行场景 2 |
| 5 | ✅ | ✅ | ❌ | 生成区间内所有锚点值，逐个查询 |
| 6 | ✅ | ✅ | ✅ | 生成区间内锚点，跳过已有的，下载缺失的 |
| 7 | ✅ | ❌ | ❌ | 触发所有股票轮询，每只股票执行场景 5 |
| 8 | ✅ | ❌ | ✅ | 触发所有股票轮询，每只股票执行场景 6 |

---

## 九、股票轮询执行流程

**文件**: [pagination.py](file:///home/quan/testdata/aspipe_v4/app4/core/pagination.py#L164-L220)

```python
def _apply_stock_loop(self, params_stream):
    stock_list = self.context.stock_list
    stock_level_detection = detection_config.get('stock_level_detection', False)

    for params in params_stream:
        for stock in stock_list:
            ts_code = stock.get('ts_code')

            # 核心缺口检测逻辑
            if stock_level_detection and self.context.coverage_manager:
                start_date = params.get('start_date', DEFAULT_STOCK_START_DATE)
                end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))
                user_provided_dates = self.context.user_provided_dates

                # 调用 CoverageManager.detect_stock_gaps()
                gap_tasks = self.context.coverage_manager.detect_stock_gaps(
                    interface_name, ts_code, start_date, end_date,
                    interface_config, user_provided_dates, stock_info
                )

                if not gap_tasks:
                    continue  # 数据已完整，跳过

                for gap_params in gap_tasks:
                    task_params = params.copy()
                    task_params.update(gap_params)
                    yield task_params
            else:
                # 原有逻辑：直接生成任务
                stock_params = params.copy()
                stock_params['ts_code'] = ts_code
                yield stock_params
```

---

## 十、user_provided_dates 标记的传递链

```
main.py (命令行解析)
    │
    │  user_provided_start_date = '--start_date' in sys.argv
    │  user_provided_end_date = '--end_date' in sys.argv
    │  user_provided_dates = user_provided_start_date or user_provided_end_date
    │  setattr(args, 'user_provided_dates', user_provided_dates)
    │
    ▼
ParamsBuilder.build()
    │
    │  result.user_provided_dates = user_provided_dates
    │
    ▼
ParamsBuilder.build_params_list()
    │
    │  context = DownloadContext(user_provided_dates=result.user_provided_dates, ...)
    │
    ▼
PaginationContext (分页上下文)
    │
    │  self.user_provided_dates = context.user_provided_dates
    │
    ▼
PaginationComposer._apply_stock_loop()
    │
    │  user_provided_dates = self.context.user_provided_dates
    │
    ▼
CoverageManager.detect_stock_gaps()
    │
    │  根据 user_provided_dates 决定缺口检测策略
    │
    ▼
各类型具体的缺口检测方法
```

---

## 十一、总结

### 11.1 类型判断对照表

| 类型 | 判断依据 | 场景检测 | 缺口检测方法 |
|------|---------|---------|-------------|
| **Type A** | `date_column == 'trade_date'` + 有 `start_date/end_date` | `STOCK_LOOP_DATE_RANGE` | `_detect_trade_date_gaps()` - 交易日历 |
| **Type B** | `date_column != 'trade_date'` + 有 `start_date/end_date` | `STOCK_LOOP_DATE_RANGE` | `_detect_report_period_gaps()` - 报告期列表 |
| **Type C** | 有 `is_date_anchor: true` 参数 | 无用户日期→`FULL_HISTORY`，有用户日期→`DATE_ANCHOR` | `_detect_date_anchor_gaps()` - 锚点遍历 |

### 11.2 核心设计思想

1. **配置驱动**：通过 YAML 配置中的 `is_date_anchor` 和 `date_column` 区分接口类型
2. **职责分离**：
   - `ParamsBuilder` 负责场景检测（不查询存储）
   - `PaginationComposer` 负责分页组合
   - `CoverageManager` 负责缺口检测（查询存储）
3. **延迟检测**：缺口检测在分页执行阶段才进行，避免参数构建阶段频繁读取存储
4. **增量优先**：有已有数据时，优先检测缺失部分而非全量下载
5. **用户意图尊重**：`user_provided_dates` 标记确保用户显式指定的日期范围被正确处理

### 11.3 关键文件索引

| 文件 | 职责 |
|------|------|
| [main.py](file:///home/quan/testdata/aspipe_v4/app4/main.py) | 命令行解析、入口调度 |
| [params_builder.py](file:///home/quan/testdata/aspipe_v4/app4/core/params_builder.py) | 场景检测、初始参数构建 |
| [pagination.py](file:///home/quan/testdata/aspipe_v4/app4/core/pagination.py) | 分页组合、股票轮询执行 |
| [coverage_manager.py](file:///home/quan/testdata/aspipe_v4/app4/core/coverage_manager.py) | 缺口检测、类型判断 |
| [context.py](file:///home/quan/testdata/aspipe_v4/app4/core/context.py) | 下载上下文数据结构 |
