# 接口日期字段设计 - 完整方案（含技术实现）

## 背景

`trade_cal`接口已经添加了`cal_date_dt`日期格式字段，用于提升polars查询性能。现在需要为所有包含日期字段的接口统一添加日期格式字段，保持数据自包含并提升查询性能。

## 方案概述

**方案1：显式添加日期格式字段**

在需要关联`trade_cal`的接口配置中，显式添加对应的日期格式字段，保持数据自包含。

## 实现方式

### 1. 配置修改示例

对于以`trade_date`作为主键的接口，在`derived_fields`中添加：

```yaml
derived_fields:
  trade_date_dt:
    description: 日期类型的trade_date（关联trade_cal.cal_date_dt）
    format: '%Y%m%d'
    source: trade_date
    type: date
```

对于以`ann_date`等其他日期字段作为主键的接口，同理添加：

```yaml
derived_fields:
  ann_date_dt:
    description: 日期类型的ann_date（关联trade_cal.cal_date_dt）
    format: '%Y%m%d'
    source: ann_date
    type: date
```

### 2. 适用接口范围及字段配置

所有需要添加日期格式字段的接口清单：

#### 2.1 基础数据

| 接口名称 | 主键日期字段 | 建议添加的日期字段 | 备注 |
|---------|------------|------------------|------|
| stock_basic | list_date, delist_date | list_date_dt, delist_date_dt | 上市/退市日期 |
| stk_premarket | trade_date | trade_date_dt | 交易日期 |
| trade_cal | cal_date, pretrade_date | cal_date_dt, pretrade_date_dt | 日历日期，已配置 |
| stock_st | trade_date | trade_date_dt | 交易日期 |
| stock_hsgt | trade_date | trade_date_dt | 交易日期 |
| namechange | start_date, end_date, ann_date | start_date_dt, end_date_dt, ann_date_dt | 开始/结束/公告日期 |
| stock_company | setup_date | setup_date_dt | 注册日期 |
| stk_managers | ann_date | ann_date_dt | 公告日期（其他日期字段保持string格式） |
| stk_rewards | ann_date, end_date | ann_date_dt, end_date_dt | 公告/截止日期 |
| bse_mapping | list_date | list_date_dt | 上市日期 |
| new_share | ipo_date, issue_date | ipo_date_dt, issue_date_dt | 发行/上市日期 |
| bak_basic | trade_date, list_date | trade_date_dt, list_date_dt | 交易/上市日期 |

#### 2.2 财务数据

| 接口名称 | 主键日期字段 | 建议添加的日期字段 | 备注 |
|---------|------------|------------------|------|
| income | ann_date, f_ann_date, end_date | ann_date_dt, f_ann_date_dt, end_date_dt | 公告/实际公告/报告期 |
| income_vip | ann_date, f_ann_date, end_date | ann_date_dt, f_ann_date_dt, end_date_dt | 复用income配置 |
| balancesheet | ann_date, f_ann_date, end_date | ann_date_dt, f_ann_date_dt, end_date_dt | 公告/实际公告/报告期 |
| balancesheet_vip | ann_date, f_ann_date, end_date | ann_date_dt, f_ann_date_dt, end_date_dt | 复用balancesheet配置 |
| cashflow | ann_date, f_ann_date, end_date | ann_date_dt, f_ann_date_dt, end_date_dt | 公告/实际公告/报告期 |
| cashflow_vip | ann_date, f_ann_date, end_date | ann_date_dt, f_ann_date_dt, end_date_dt | 复用cashflow配置 |
| forecast | ann_date, end_date, first_ann_date | ann_date_dt, end_date_dt, first_ann_date_dt | 公告/报告期/首次公告 |
| forecast_vip | ann_date, end_date, first_ann_date | ann_date_dt, end_date_dt, first_ann_date_dt | 复用forecast配置 |
| express | ann_date, end_date | ann_date_dt, end_date_dt | 公告/报告期 |
| express_vip | ann_date, end_date | ann_date_dt, end_date_dt | 复用express配置 |
| dividend | ann_date, end_date, record_date, ex_date, pay_date, div_listdate, imp_ann_date, base_date | ann_date_dt, end_date_dt, record_date_dt, ex_date_dt, pay_date_dt, div_listdate_dt, imp_ann_date_dt, base_date_dt | 公告/分红/登记/除权/派息等 |
| fina_indicator | ann_date, end_date | ann_date_dt, end_date_dt | 公告/报告期 |
| fina_indicator_vip | ann_date, end_date | ann_date_dt, end_date_dt | 复用fina_indicator配置 |
| fina_audit | ann_date, end_date | ann_date_dt, end_date_dt | 公告/报告期 |
| fina_mainbz | end_date | end_date_dt | 报告期 |
| fina_mainbz_vip | end_date | end_date_dt | 复用fina_mainbz配置 |
| disclosure_date | ann_date, end_date, pre_date, actual_date, modify_date | ann_date_dt, end_date_dt, pre_date_dt, actual_date_dt, modify_date_dt | 披露/预计/实际/修正日期 |

#### 2.3 行情数据

| 接口名称 | 主键日期字段 | 建议添加的日期字段 | 备注 |
|---------|------------|------------------|------|
| daily | trade_date | trade_date_dt | 交易日期 |
| daily_basic | trade_date | trade_date_dt | 交易日期 |
| pro_bar | trade_date | trade_date_dt | 交易日期 |
| suspend_d | trade_date | trade_date_dt | 停复牌日期 |
| bak_daily | trade_date | trade_date_dt | 交易日期 |

#### 2.4 参考数据

| 接口名称 | 主键日期字段 | 建议添加的日期字段 | 备注 |
|---------|------------|------------------|------|
| top10_floatholders | ann_date, end_date | ann_date_dt, end_date_dt | 公告/报告期 |
| top10_holders | ann_date, end_date | ann_date_dt, end_date_dt | 公告/报告期 |
| pledge_stat | end_date | end_date_dt | 截止日期 |
| pledge_detail | ann_date, start_date, end_date, release_date | ann_date_dt, start_date_dt, end_date_dt, release_date_dt | 公告/质押/解押日期 |
| repurchase | ann_date, end_date, exp_date | ann_date_dt, end_date_dt, exp_date_dt | 公告/截止/过期日期 |
| share_float | ann_date, float_date | ann_date_dt, float_date_dt | 公告/解禁日期 |
| block_trade | trade_date | trade_date_dt | 交易日期 |
| stk_holdertrade | ann_date, begin_date, close_date | ann_date_dt, begin_date_dt, close_date_dt | 公告/开始/结束日期 |

#### 2.5 特色数据

| 接口名称 | 主键日期字段 | 建议添加的日期字段 | 备注 |
|---------|------------|------------------|------|
| report_rc | report_date | report_date_dt | 研报日期 |
| cyq_perf | trade_date | trade_date_dt | 交易日期 |
| cyq_chips | trade_date | trade_date_dt | 交易日期 |
| stk_factor | trade_date | trade_date_dt | 交易日期 |
| stk_factor_pro | trade_date | trade_date_dt | 交易日期 |
| stk_surv | surv_date | surv_date_dt | 调研日期 |
| moneyflow | trade_date | trade_date_dt | 交易日期 |
| moneyflow_ths | trade_date | trade_date_dt | 交易日期 |
| moneyflow_dc | trade_date | trade_date_dt | 交易日期 |
| moneyflow_cnt_ths | trade_date | trade_date_dt | 交易日期 |
| moneyflow_ind_ths | trade_date | trade_date_dt | 交易日期 |
| moneyflow_ind_dc | trade_date | trade_date_dt | 交易日期 |
| moneyflow_mkt_dc | trade_date | trade_date_dt | 交易日期 |

### 3. VIP接口字段复用规则

所有VIP接口的日期字段配置与其对应的非VIP接口完全相同，直接复用即可：

- `income_vip` → 复用 `income` 的 `ann_date_dt`, `f_ann_date_dt`, `end_date_dt`
- `balancesheet_vip` → 复用 `balancesheet` 的 `ann_date_dt`, `f_ann_date_dt`, `end_date_dt`
- `cashflow_vip` → 复用 `cashflow` 的 `ann_date_dt`, `f_ann_date_dt`, `end_date_dt`
- `express_vip` → 复用 `express` 的 `ann_date_dt`, `end_date_dt`
- `forecast_vip` → 复用 `forecast` 的 `ann_date_dt`, `end_date_dt`, `first_ann_date_dt`
- `fina_indicator_vip` → 复用 `fina_indicator` 的 `ann_date_dt`, `end_date_dt`
- `fina_mainbz_vip` → 复用 `fina_mainbz` 的 `end_date_dt`

### 4. 数据存储格式

生成的parquet文件将包含原始string格式和date格式两个字段：

```python
# 示例数据结构
import polars as pl
from datetime import date

df = pl.DataFrame({
    'ts_code': ['000001.SZ', '000002.SZ'],
    'trade_date': ['20240101', '20240102'],  # 原始string格式
    'trade_date_dt': [date(2024, 1, 1), date(2024, 1, 2)],  # 新增date格式
    # ... 其他字段
})
```

## 优点

1. **查询性能最优**：polars等工具使用日期格式作为主键时性能最佳
2. **数据自包含**：无需额外join操作，简化查询逻辑
3. **类型安全**：明确区分string和date类型，减少类型转换错误
4. **向后兼容**：保留原始string格式，不影响现有代码
5. **统一规范**：所有接口遵循相同的日期格式规范

## 缺点

1. **数据冗余**：同一份日期数据存储两份（string + date）
2. **存储成本**：略微增加存储空间（约5-10%）
3. **维护成本**：需要修改多个接口配置

## 使用示例

### Polars查询优化

```python
import polars as pl
from datetime import date

# 读取数据
df = pl.read_parquet("app4/data/daily/*.parquet")

# 使用日期格式进行高效过滤
result = df.filter(
    pl.col("trade_date_dt").is_between(date(2024, 1, 1), date(2024, 12, 31))
)

# 日期运算性能更好
result = df.with_columns(
    (pl.col("trade_date_dt") + pl.duration(days=1)).alias("next_day")
)
```

### 与trade_cal关联

```python
# 无需类型转换，直接关联
trade_cal = pl.read_parquet("app4/data/trade_cal/*.parquet")
daily = pl.read_parquet("app4/data/daily/*.parquet")

# 直接join，性能更好
result = daily.join(
    trade_cal.select(["cal_date", "cal_date_dt", "is_open_bool"]),
    left_on="trade_date_dt",
    right_on="cal_date_dt",
    how="left"
)
```

### 跨表关联查询

```python
# 财务数据和行情数据关联
income = pl.read_parquet("app4/data/income_vip/*.parquet")
daily = pl.read_parquet("app4/data/daily/*.parquet")

# 基于日期字段关联
result = income.join(
    daily,
    left_on=["ts_code", "end_date_dt"],
    right_on=["ts_code", "trade_date_dt"],
    how="left"
)
```

## 实施步骤

### 阶段1：基础数据接口（高频查询）

1. **交易日历相关**：`trade_cal`（已完成）
2. **行情数据**：`daily`, `daily_basic`, `moneyflow`, `suspend_d`, `bak_daily`
3. **基础信息**：`stock_basic`, `stock_st`, `stock_hsgt`

### 阶段2：财务数据接口

1. **财报数据**：`income_vip`, `balancesheet_vip`, `cashflow_vip`
2. **财务指标**：`fina_indicator_vip`, `fina_mainbz_vip`
3. **业绩预告/快报**：`forecast_vip`, `express_vip`

### 阶段3：参考数据接口

1. **股东数据**：`top10_floatholders`, `top10_holders`
2. **交易数据**：`block_trade`, `stk_holdertrade`
3. **其他**：`pledge_detail`, `repurchase`, `share_float`

### 阶段4：特色数据接口

1. **因子数据**：`stk_factor`, `stk_factor_pro`, `cyq_perf`, `cyq_chips`
2. **其他**：`moneyflow`系列（ths/dc），`report_rc`, `stk_surv`

### 实施 checklist

- [ ] 修改接口yaml配置，添加`derived_fields`
- [ ] 重新下载数据，生成带日期格式的parquet文件
- [ ] 验证日期转换正确性
- [ ] 对比查询性能提升
- [ ] 检查数据完整性
- [ ] 更新查询代码，使用新的日期字段

## 技术实现细节

### 数据处理流程

对于包含derived_fields（如日期字段）的接口，数据处理顺序如下：

1. **数据下载**：从TuShare API获取原始数据
2. **trade_cal自检**：下载完成后立即验证数据完整性（仅对trade_cal接口）
3. **主键空值过滤**：删除主键字段（primary_key）中含有空值（None/null）的记录
   - 目的：清洗无效数据，避免后续处理错误
   - 注意：必须在添加derived_fields之前执行
4. **派生字段计算**：基于`derived_fields`配置添加新字段
   - 对于日期字段，采用内存查找方案：
     a. 首次调用时加载trade_cal到内存（惰性加载）
     b. 对每条记录的日期字段进行查询转换
     c. 如果trade_cal中不存在，降级为直接解析
5. **数据去重**：基于主键字段进行去重
6. **数据排序**：基于sort_by配置排序
7. **保存parquet**：写入最终结果

### 数据一致性检查

在数据下载和转换过程中，必须进行数据完整性自检，确保trade_cal数据的可靠性：

**自检流程：**
1. **检查trade_cal数据是否存在**：
   - 检查内存缓存是否有trade_cal数据
   - 检查本地data目录是否有trade_cal的parquet文件
   - 如果没有，自动触发下载（调用`trade_cal`接口）

2. **数据完整性验证**：
   ```python
   def verify_trade_calendar_integrity(df: pl.DataFrame) -> bool:
       """验证交易日历完整性"""
       # 检查1：从1990-01-01到今天（当日）是否全覆盖
       expected_start = date(1990, 1, 1)
       expected_end = date.today()
       
       actual_start = df['cal_date'].min()
       actual_end = df['cal_date'].max()
       
       if actual_start > expected_start or actual_end < expected_end:
           logger.error(f"Trade calendar data incomplete: "
                       f"expected {expected_start} to {expected_end}, "
                       f"got {actual_start} to {actual_end}")
           return False
       
       # 检查2：string格式和date格式是否一一对应
       mismatched = df.filter(
           pl.col('cal_date').is_not_null() & pl.col('cal_date_dt').is_null()
       )
       
       if len(mismatched) > 0:
           logger.error(f"Found {len(mismatched)} records with mismatched date formats")
           return False
       
       # 检查3：数据量合理性（至少应该有8000个交易日）
       if len(df) < 8000:
           logger.warning(f"Trade calendar has unusually few records: {len(df)}")
           # 不返回False，只是警告
       
       logger.info(f"Trade calendar integrity check passed: {len(df)} records")
       return True
   ```

3. **自检时机**：
   - **trade_cal接口下载完成后立即执行**（最关键的时机）
   - 系统启动时验证本地trade_cal数据完整性
   - 如果自检失败，记录错误日志并触发重新下载

**在Downloader中集成的自检逻辑：**
```python
class GenericDownloader:
    def _after_download(self, interface_name: str, df: pl.DataFrame):
        """下载后处理 - 特定接口的特殊处理"""
        if interface_name == 'trade_cal':
            if not self._verify_trade_calendar_integrity(df):
                logger.error("Trade calendar integrity check failed, will retry on next run")
                # 标记需要重新下载
                self._mark_trade_cal_dirty()
```

### 回退策略

当trade_cal加载或转换失败时，系统应具备完善的回退机制：

**三层回退策略：**

1. **第一层：内存缓存**
   ```python
   # 检查内存缓存
   with self._cache_lock:
       if cache_key in self._memory_cache['trade_cal']:
           return self._memory_cache['trade_cal'][cache_key]
   ```

2. **第二层：本地数据目录**
   ```python
   # 从data/trade_cal/目录加载parquet文件（使用配置路径）
   storage_dir = self.config_loader.get_global_config()['storage']['base_dir']
   trade_calendar = self._get_trade_calendar_from_data_dir(start_date, end_date)
   if trade_calendar:
       # 加载到内存缓存
       with self._cache_lock:
           self._memory_cache['trade_cal'][cache_key] = trade_calendar
       return trade_calendar
   ```

3. **第三层：API请求（自动下载）**
   ```python
   # 如果本地没有，自动从API下载
   logger.info(f"Trade calendar not found locally, fetching from API")
   calendar_params = {
       'start_date': start_date,
       'end_date': end_date,
       'exchange': 'SSE'
   }
   trade_calendar = self._make_request(
       self.config_loader.get_interface_config('trade_cal'),
       calendar_params
   )
   
   # 下载成功后：
   # 1. 保存到parquet文件
   # 2. 加载到内存缓存
   # 3. 执行数据完整性自检
   if trade_calendar:
       # 保存到本地存储
       self.storage_manager.save('trade_cal', trade_calendar)
       
       # 添加到内存缓存
       with self._cache_lock:
           self._memory_cache['trade_cal'][cache_key] = trade_calendar
       
       # 执行自检
       df = pl.DataFrame(trade_calendar)
       if not self.verify_trade_calendar_integrity(df):
           logger.error("Downloaded trade calendar failed integrity check")
   ```

**异常场景处理：**
- **trade_cal加载失败**：记录错误日志，使用降级方案（直接解析日期）
- **日期不在trade_cal中**：记录警告日志，使用降级方案（直接解析日期）
- **内存不足**：清理缓存，重新加载必要数据
- **数据损坏**：删除本地parquet文件，重新下载

### 为什么这个顺序很重要

**第3步：添加派生字段**
```python
# 转换日期 - 此时所有记录都有有效的trade_date
date_cache = load_trade_cal_to_memory()  # 内存查找
for record in filtered_records:
    date_str = record['trade_date']  # 不会是None
    record['trade_date_dt'] = date_cache.get(date_str) or parse_date(date_str)
```

**错误示例1：先转换后过滤**
```python
# 如果trade_date为None，会KeyError或异常
for record in raw_data:
    record['trade_date_dt'] = date_cache[record['trade_date']]  # KeyError!

filtered = [r for r in raw_data if r['trade_date']]  # 太晚过滤
```

**错误示例2：去重后转换（性能浪费）**
```python
# 浪费计算资源
deduped = deduplicate(raw_data, ['ts_code', 'trade_date'])  # 先去重
# 如果有100万条，去重后剩10万条
# 但你浪费了90万条的转换时间
for record in deduped:
    record['trade_date_dt'] = convert_date(record['trade_date'])
```

### 内存查找实现

```python
# 模块级变量，多进程下各自独立，但不需要锁
_date_map = None
_is_open_map = None
_cache_loaded = False
_cache_lock = threading.Lock()

def get_trade_date_cache():
    """获取交易日历缓存 - 模块级单例"""
    global _date_map, _is_open_map, _cache_loaded
    
    if not _cache_loaded:
        with _cache_lock:
            if not _cache_loaded:
                _load_cache()
                _cache_loaded = True
    
    return _date_map, _is_open_map

def _load_cache():
    """一次性加载trade_cal到内存"""
    global _date_map, _is_open_map
    
    # 从 data 目录加载 - 使用配置获取路径
    from app4.core.config_loader import ConfigLoader
    config_loader = ConfigLoader()
    storage_dir = config_loader.get_global_config()['storage']['base_dir']
    
    # 读取parquet文件
    import polars as pl
    df = pl.read_parquet(f"{storage_dir}/trade_cal/*.parquet")
    
    # 只加载需要的字段
    _date_map = {
        row['cal_date']: row['cal_date_dt'] 
        for row in df.to_dicts()
    }
    
    _is_open_map = {
        row['cal_date']: row['is_open_bool'] 
        for row in df.to_dicts()
    }
    
    print(f"TradeDateCache loaded: {len(_date_map)} dates")

# 使用示例
def convert_trade_date(date_str: str) -> date:
    """转换交易日"""
    if not date_str:
        return None
    
    date_map, _ = get_trade_date_cache()
    result = date_map.get(date_str)
    
    if result is None:
        # 降级方案：直接解析
        logger.warning(f"日期 {date_str} 不在trade_cal中，直接解析")
        result = datetime.strptime(date_str, '%Y%m%d').date()
    
    return result
```

**性能对比**：
- **CPU计算**：~0.5μs/次（datetime.strptime）
- **内存查找**：~0.05μs/次（dict查询）
- **提升**：**10倍性能提升**
- **内存占用**：~1.2MB（可忽略）

### 异常处理

```python
class InvalidTradeDateError(Exception):
    """无效的交易日异常"""
    pass

def convert_trade_date(date_str: str) -> date:
    """转换交易日，带验证和降级方案"""
    if not date_str:
        raise ValueError("日期字符串不能为空")
    
    # 查询内存缓存
    result = TradeDateCache.get_date(date_str)
    
    if result is None:
        # 两个可能：
        # 1. trade_cal中确实没有这个日期（非交易日）
        # 2. trade_cal数据不完整
        
        # 降级方案：直接解析
        logger.warning(f"日期 {date_str} 不在trade_cal中，直接解析")
        result = datetime.strptime(date_str, '%Y%m%d').date()
    
    return result
```

### 推荐实现策略

```python
class DateConverter:
    def __init__(self, use_memory_cache: bool = True):
        self.use_memory_cache = use_memory_cache
        self._cache = None if use_memory_cache else None
    
    def convert(self, date_str: str) -> date:
        """转换日期 - 根据策略选择"""
        if not date_str:
            return None
        
        if self.use_memory_cache:
            # 内存查找（推荐）
            if self._cache is None:
                self._cache = TradeDateCache()
            return self._cache.get_date(date_str) or self._parse_fallback(date_str)
        else:
            # CPU计算（简单场景）
            return self._parse_fallback(date_str)
    
    def _parse_fallback(self, date_str: str) -> date:
        """降级方案：直接解析"""
        return datetime.strptime(date_str, '%Y%m%d').date()
```

**使用建议**：
- **生产环境/服务**：使用内存缓存（启动时预加载）
- **脚本/单次任务**：使用惰性加载（第一次调用时加载）
- **简单测试**：可直接使用CPU计算

## 性能预期

- **查询性能**：日期格式过滤比string格式快3-5倍
- **存储增加**：约5-10%（date类型比string更紧凑）
- **内存占用**：polars中date类型内存占用减少约30%
- **join性能**：日期类型join性能提升50-100%
- **转换性能**：内存查找比CPU计算快10倍

## 注意事项

1. **日期格式统一**：所有接口使用相同的日期格式（`%Y%m%d`）
2. **空值处理**：确保日期转换时正确处理空值或非法日期
3. **时区问题**：日期类型不包含时区信息，统一使用本地日期
4. **兼容性**：保留原始string字段，确保向后兼容
5. **VIP接口复用**：VIP接口直接复用非VIP接口的日期字段配置
6. **特殊字段处理**：`stk_managers`接口只处理`ann_date`，其他日期字段（birthday, begin_date, end_date）保持string格式不变
7. **处理顺序**：必须在主键空值过滤之后、去重之前添加派生字段
8. **数据自检**：首次加载trade_cal时必须执行完整性自检，确保数据覆盖范围和格式正确性

## 决策建议

**推荐采用方案1**，原因：

1. 金融数据分析中日期查询是高频操作，性能提升明显
2. 存储成本增加在可接受范围内
3. 数据自包含，降低使用复杂度
4. 与`trade_cal`的设计保持一致
5. 所有接口统一规范，便于维护
6. 内存查找方案提供10倍性能提升，内存占用可忽略

对于低频使用的接口，可以考虑不添加日期字段，以节省存储空间。

## 附录：日期字段配置模板

### 模板1：单日期字段（如trade_date）

```yaml
derived_fields:
  trade_date_dt:
    description: 日期类型的trade_date（关联trade_cal.cal_date_dt）
    format: '%Y%m%d'
    source: trade_date
    type: date
```

### 模板2：双日期字段（如ann_date + end_date）

```yaml
derived_fields:
  ann_date_dt:
    description: 日期类型的ann_date（关联trade_cal.cal_date_dt）
    format: '%Y%m%d'
    source: ann_date
    type: date
  end_date_dt:
    description: 日期类型的end_date（关联trade_cal.cal_date_dt）
    format: '%Y%m%d'
    source: end_date
    type: date
```

### 模板3：三日期字段（如ann_date + f_ann_date + end_date）

```yaml
derived_fields:
  ann_date_dt:
    description: 日期类型的ann_date
    format: '%Y%m%d'
    source: ann_date
    type: date
  f_ann_date_dt:
    description: 日期类型的f_ann_date
    format: '%Y%m%d'
    source: f_ann_date
    type: date
  end_date_dt:
    description: 日期类型的end_date
    format: '%Y%m%d'
    source: end_date
    type: date
```

### 模板4：特殊日期字段（如dividend）

```yaml
derived_fields:
  ann_date_dt:
    description: 日期类型的ann_date
    format: '%Y%m%d'
    source: ann_date
    type: date
  end_date_dt:
    description: 日期类型的end_date
    format: '%Y%m%d'
    source: end_date
    type: date
  record_date_dt:
    description: 日期类型的record_date
    format: '%Y%m%d'
    source: record_date
    type: date
  ex_date_dt:
    description: 日期类型的ex_date
    format: '%Y%m%d'
    source: ex_date
    type: date
  pay_date_dt:
    description: 日期类型的pay_date
    format: '%Y%m%d'
    source: pay_date
    type: date
  div_listdate_dt:
    description: 日期类型的div_listdate
    format: '%Y%m%d'
    source: div_listdate
    type: date
  imp_ann_date_dt:
    description: 日期类型的imp_ann_date
    format: '%Y%m%d'
    source: imp_ann_date
    type: date
  base_date_dt:
    description: 日期类型的base_date
    format: '%Y%m%d'
    source: base_date
    type: date
```
