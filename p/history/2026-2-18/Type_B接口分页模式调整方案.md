# Type B 接口分页模式调整方案

## 一、背景

Type B 接口（报告期接口）当前统一使用 `stock_loop` 分页模式，即逐只股票循环查询。通过测试发现，大部分接口支持仅通过 `period` 参数获取某一报告期的全市场数据，这为优化分页模式提供了可能。

## 二、测试发现

### 2.1 测试方法

使用 `period` 参数（不带 `ts_code`）调用各接口，测试是否能获取全市场数据。

测试报告期：`20240930`（2024年三季报）

### 2.2 测试结果

| 接口 | 仅 period 可查 | 记录数 | 分页支持 | 完整性评估 |
|------|---------------|--------|---------|-----------|
| `income_vip` | ✅ 支持 | 6172 | ✅ 支持 | 完整 |
| `balancesheet_vip` | ✅ 支持 | 5712 | ✅ 支持 | 完整 |
| `cashflow_vip` | ✅ 支持 | 6400 | ✅ 支持 | 完整 |
| `fina_indicator_vip` | ✅ 支持 | 7128 | ✅ 支持 | 完整 |
| `fina_mainbz_vip` | ✅ 支持 | 280 | ✅ 支持 | 完整 |
| `forecast_vip` | ✅ 支持 | 266 | ✅ 支持 | 完整 |
| `top10_floatholders` | ✅ 支持 | 6000 | ❌ 不支持 | **不完整** |
| `fina_audit` | ❌ 不支持 | 0 | - | **无法使用** |

## 三、问题分析

### 3.1 fina_audit - 必须保持 stock_loop

**现象**：API 返回错误 `必填参数, ts_code`

**原因**：该接口在 API 层面强制要求 `ts_code` 参数，不支持仅通过 `period` 获取全市场数据。

**结论**：必须保持 `stock_loop` 模式，逐只股票查询。

### 3.2 top10_floatholders - 必须保持 stock_loop

**现象**：
- 支持 `period` 参数查询
- 单次查询返回约 6000 条记录
- 全市场股票数量超过 5000 只，每只股票有 10 个流通股东

**原因**：
- 该接口不支持分页机制
- 单次查询有返回条数限制（约 6000 条）
- 实际数据量 = 股票数 × 10 ≈ 50000+ 条
- 使用 `period` 查询会丢失大量数据

**数据量对比**：
```
理论数据量: ~5000 股票 × 10 股东 = ~50000 条
实际返回量: ~6000 条
数据丢失率: ~88%
```

**结论**：必须保持 `stock_loop` 模式，逐只股票查询以确保数据完整性。

### 3.3 其他 6 个接口 - 可改为 period_range

**现象**：
- 支持 `period` 参数查询
- 支持分页机制
- 单次查询可获取完整数据

**原因**：
- 这些接口返回的是聚合数据（每只股票每报告期一条）
- 单个报告期数据量约 5000-7000 条
- 在 API 返回限制范围内，可完整获取

**结论**：可改为 `period_range` 模式，按报告期批量查询。

## 四、关键问题：period_range 模式的参数转换

### 4.1 当前实现的问题

通过代码分析发现，当前 `period_range` 模式**并没有实现 `start_date`/`end_date` → `period` 的参数转换**。

```python
# pagination.py 第523-524行
elif mode == 'period_range':
    new_config['time_range'] = {'enabled': True, 'window': '1q', 'reverse': False}
```

**当前行为**：
- 只设置了时间窗口为 `1q`（一个季度）
- 用户传入的 `start_date`/`end_date` 仍然原样透传给 API
- API 接收到的是**公告日期范围**，不是**报告期**

**问题示例**：
```
用户传入: --start_date 20240101 --end_date 20241231
当前行为: 按季度切分成 4 个任务，每个任务传递 start_date/end_date
API 接收: start_date=20240101, end_date=20240331 (公告日期范围)
期望行为: period=20240331, period=20240630, period=20240930, period=20241231
```

### 4.2 参数语义混淆

| 参数 | Tushare API 定义 | 当前系统理解 | 正确理解 |
|------|-----------------|-------------|---------|
| `start_date` | 公告日开始日期 | 报告期开始 | 公告日开始 |
| `end_date` | 公告日结束日期 | 报告期结束 | 公告日结束 |
| `period` | 报告期参数 | 未使用 | **应使用此参数** |

### 4.3 需要新增的转换逻辑

**核心需求**：将用户传入的日期区间转换为报告期列表，每次只下载一个 `period` 的数据。

```python
def convert_date_range_to_periods(start_date: str, end_date: str) -> List[str]:
    """
    将日期区间转换为报告期列表
    
    规则：只有当日期区间完全包含某个报告期时，才下载该报告期数据
    
    Args:
        start_date: 用户传入的开始日期
        end_date: 用户传入的结束日期
    
    Returns:
        报告期列表，如 ['20240331', '20240630', '20240930', '20241231']
    """
    periods = []
    start_year = int(start_date[:4])
    end_year = int(end_date[:4])
    
    quarter_ends = ["0331", "0630", "0930", "1231"]
    
    for year in range(start_year, end_year + 1):
        for qe in quarter_ends:
            period = f"{year}{qe}"
            # 只有当报告期在用户日期范围内时才包含
            if start_date <= period <= end_date:
                periods.append(period)
    
    return periods
```

### 4.4 其他需要注意的问题

#### 问题 1：用户日期区间的语义

用户传入 `--start_date 20240101 --end_date 20240630` 时：

| 理解方式 | 包含的报告期 | 说明 |
|---------|-------------|------|
| 作为公告日期范围 | 需要反向映射 | 年报(20231231)公告在2024年1-4月 |
| 作为报告期范围 | 20240331, 20240630 | 直接取季度末日期 |

**建议**：明确用户传入的日期区间语义为**报告期范围**，简化逻辑。

#### 问题 2：增量下载场景

改为 `period_range` 模式后，缺口检测策略从 `stock` 变为 `period`：

| 场景 | stock 策略 | period 策略 |
|------|-----------|------------|
| 检测维度 | 每只股票 | 每个报告期 |
| 检测逻辑 | 股票是否有数据 | 报告期是否有数据 |
| 跳过条件 | 股票已有完整数据 | 报告期已有完整数据 |

**注意**：`period` 策略检测的是**全市场**某报告期是否有数据，不是单只股票。

#### 问题 3：用户直接传入 period 参数

如果用户直接传入 `--period 20240930`，系统应该：
1. 识别这是一个单报告期查询
2. 直接使用该参数，不做转换
3. 跳过时间窗口切分

#### 问题 4：公告日期与报告期的关系

根据 Tushare API 设计，`start_date`/`end_date` 是公告日期范围：

| 报告期 | 典型公告日期范围 | 说明 |
|-------|-----------------|------|
| 20231231（年报） | 2024-01-01 ~ 2024-04-30 | 年报在次年公告 |
| 20240331（一季报） | 2024-04-01 ~ 2024-04-30 | 一季报在4月公告 |
| 20240630（半年报） | 2024-07-01 ~ 2024-08-31 | 半年报在7-8月公告 |
| 20240930（三季报） | 2024-10-01 ~ 2024-10-31 | 三季报在10月公告 |

**建议**：为简化实现，将用户日期参数语义定义为**报告期范围**，避免反向映射的复杂性。

## 五、修改方案

### 5.1 分类调整

| 接口 | 当前模式 | 调整后模式 | 原因 |
|------|---------|-----------|------|
| `income_vip` | stock_loop | **period_range** | 支持 period 查询，数据完整 |
| `balancesheet_vip` | stock_loop | **period_range** | 支持 period 查询，数据完整 |
| `cashflow_vip` | stock_loop | **period_range** | 支持 period 查询，数据完整 |
| `fina_indicator_vip` | stock_loop | **period_range** | 支持 period 查询，数据完整 |
| `fina_mainbz_vip` | stock_loop | **period_range** | 支持 period 查询，数据完整 |
| `forecast_vip` | stock_loop | **period_range** | 支持 period 查询，数据完整 |
| `top10_floatholders` | stock_loop | stock_loop | 不支持分页，数据不完整 |
| `fina_audit` | stock_loop | stock_loop | API 强制要求 ts_code |

### 5.2 配置文件修改

需要修改以下 6 个配置文件：

```
app4/config/interfaces/income_vip.yaml
app4/config/interfaces/balancesheet_vip.yaml
app4/config/interfaces/cashflow_vip.yaml
app4/config/interfaces/fina_indicator_vip.yaml
app4/config/interfaces/fina_mainbz_vip.yaml
app4/config/interfaces/forecast_vip.yaml
```

修改内容：

```yaml
pagination:
  enabled: true
  mode: period_range    # 从 stock_loop 改为 period_range
```

### 5.3 保持不变的配置

以下 2 个配置文件保持 `stock_loop` 模式不变：

```
app4/config/interfaces/top10_floatholders.yaml
app4/config/interfaces/fina_audit.yaml
```

### 5.4 代码修改建议

需要在 `pagination.py` 中新增参数转换逻辑：

```python
def _apply_period_range(self, params_stream: List[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
    """
    应用报告期范围维度
    
    将用户的 start_date/end_date 转换为 period 参数
    每次只下载一个 period 的数据
    """
    for params in params_stream:
        # 如果用户直接传入了 period 参数，直接使用
        if 'period' in params:
            yield params
            continue
        
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        
        if not start_date or not end_date:
            yield params
            continue
        
        # 转换日期区间为报告期列表
        periods = self._convert_date_range_to_periods(start_date, end_date)
        
        for period in periods:
            period_params = params.copy()
            # 移除 start_date/end_date，使用 period
            period_params.pop('start_date', None)
            period_params.pop('end_date', None)
            period_params['period'] = period
            period_params['_period_query'] = True
            yield period_params

def _convert_date_range_to_periods(self, start_date: str, end_date: str) -> List[str]:
    """
    将日期区间转换为报告期列表
    
    规则：只有当报告期日期在用户日期区间内时，才包含该报告期
    """
    periods = []
    start_year = int(start_date[:4])
    end_year = int(end_date[:4])
    
    quarter_ends = ["0331", "0630", "0930", "1231"]
    
    for year in range(start_year, end_year + 1):
        for qe in quarter_ends:
            period = f"{year}{qe}"
            if start_date <= period <= end_date:
                periods.append(period)
    
    return periods
```

### 5.5 缺口检测调整

修改 `coverage_manager.py` 中的 `period` 策略检测逻辑：

```python
def _check_period_existence(self, interface_name: str, params: Dict[str, Any]) -> bool:
    """
    检查报告期是否存在（全市场维度）
    
    对于 period_range 模式，检测的是整个报告期是否有数据
    而不是单只股票是否有数据
    """
    period = params.get('period')
    if not period:
        return False
    
    # 检查该报告期是否已有数据（任意股票）
    # 如果已有数据，说明该报告期已下载过，跳过
    ...
```

## 六、预期效果

### 6.1 性能提升

| 指标 | stock_loop 模式 | period_range 模式 | 提升 |
|------|----------------|------------------|------|
| 单报告期 API 调用次数 | ~5000 次 | 1 次 | **99.98%** |
| 网络请求开销 | 高 | 低 | 显著降低 |
| 数据获取时间 | 分钟级 | 秒级 | 显著缩短 |

### 6.2 数据完整性

- `period_range` 模式：单次查询获取全市场数据，无遗漏
- `stock_loop` 模式：逐只股票查询，确保数据完整

## 七、风险评估

### 7.1 低风险

- 修改仅涉及分页模式，不影响数据字段和存储逻辑
- 可通过回滚配置文件快速恢复

### 7.2 验证建议

1. 先在测试环境验证 `period_range` 模式数据完整性
2. 对比新旧模式获取的数据量
3. 确认无数据丢失后再上线

## 八、总结

| 分类 | 接口数量 | 接口列表 |
|------|---------|---------|
| 改为 period_range | 6 | income_vip, balancesheet_vip, cashflow_vip, fina_indicator_vip, fina_mainbz_vip, forecast_vip |
| 保持 stock_loop | 2 | fina_audit, top10_floatholders |

**核心原则**：
1. API 强制要求 `ts_code` 的接口 → 保持 `stock_loop`
2. 不支持分页且数据量超限的接口 → 保持 `stock_loop`
3. 支持 `period` 查询且数据完整的接口 → 改为 `period_range`

**修改要点**：
1. 新增 `start_date`/`end_date` → `period` 的参数转换逻辑
2. 每次只下载一个 `period` 的数据
3. 用户日期区间语义定义为报告期范围
4. 缺口检测从股票维度改为报告期维度
