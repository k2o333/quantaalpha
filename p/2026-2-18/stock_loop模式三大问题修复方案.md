# stock_loop 模式三大问题修复方案

## 概述

本文档记录了在测试 `test_type_abcd.sh` 脚本时发现的三个关键问题：
1. `exchange` 列不存在
2. `delist_date` 列不存在
3. dividend 等接口任务重复执行

---

## 问题一：`exchange` 列不存在

### 现象

终端输出错误信息：
```
core.cache_warmer - ERROR - 预加载股票列表失败: unable to find column "exchange"
valid columns: ["ts_code", "symbol", "name", "area", "industry", "cnspell", 
                "market", "list_date", "act_name", "act_ent_type", 
                "_update_time", "list_date_dt"]
```

### 问题代码

**文件**: `app4/core/cache_warmer.py:66-71`

```python
# 问题代码：硬编码了期望读取的列名
actual_columns = ['ts_code', 'symbol', 'name', 'area', 'industry', 'cnspell',
                 'market', 'list_date', 'act_name', 'act_ent_type', 'exchange',
                 'list_status', 'is_hs', 'list_date_dt', '_update_time']

df = pl.read_parquet(stock_basic_dir, columns=actual_columns)
```

**根本原因**（更正）:
- 根据 TuShare API 文档 (`p/tu.md`)，`exchange`, `list_status`, `delist_date`, `is_hs` 这些字段**存在**于 stock_basic 接口中
- 但它们的"默认显示"属性为 **N**，即不显式指定 fields 参数时不会返回
- 代码硬编码期望读取的列名，但实际下载的 stock_basic 数据可能只包含默认字段
- **真正的解决方案**：确保下载 stock_basic 时在 fields 参数中包含这些非默认字段

### 修改方案

**方案零（根本解决）：确保下载时包含所有需要的字段**

在调用 stock_basic 接口时，应确保 `fields` 参数包含配置文件 `stock_basic.yaml` 中定义的所有字段：

```python
# stock_basic.yaml 中 fields 配置已包含：
fields:
  # 默认字段（默认显示 Y）
  - ts_code       # TS代码
  - symbol        # 股票代码
  - name          # 股票名称
  - area          # 地域
  - industry      # 所属行业
  - cnspell       # 拼音缩写
  - market        # 市场类型
  - list_date     # 上市日期
  - act_name      # 实控人名称
  - act_ent_type  # 实控人企业性质
  # 非默认字段（默认显示 N，需要显式指定）
  - fullname      # 股票全称
  - enname        # 英文全称
  - exchange      # 交易所代码
  - curr_type     # 交易货币
  - list_status   # 上市状态
  - delist_date   # 退市日期
  - is_hs         # 是否沪深港通标的
```

downloader.py 已正确处理 fields 参数（第 633-652 行），会使用配置文件中的 fields。
问题是确保 stock_basic.yaml 中的 fields 配置完整。

downloader.py 已正确处理 fields 参数（第 633-652 行），会使用配置文件中的 fields。
问题是确保 stock_basic.yaml 中的 fields 配置完整。

---

## 问题二：`delist_date` 列不存在

### 现象

终端输出警告信息：
```
core.schema_manager - WARNING - Failed to derive field delist_date_dt: 
unable to find column 'delist_date'; 
valid columns: ['ts_code', 'symbol', 'name', 'area', 'industry', 'cnspell', 
                'market', 'list_date', 'act_name', 'act_ent_type', '_update_time']
```

### 问题代码

**文件**: `app4/config/interfaces/stock_basic.yaml:3-7`

```yaml
derived_fields:
  delist_date_dt:              # 派生字段名称
    description: 日期类型的delist_date
    format: '%Y%m%d'
    source: delist_date        # ← 源字段 delist_date 不存在
    type: date
```

**文件**: `app4/core/schema_manager.py:48-55`

```python
def apply_derived_fields(df: pl.DataFrame, interface_name: str) -> pl.DataFrame:
    for field_name, field_config in derived_config.items():
        source_field = field_config['source']  # delist_date
        
        if source_field not in df.columns:  # ← 触发警告
            logger.warning(f"Failed to derive field {target_field}: "
                          f"unable to find column '{source_field}'")
            continue
```

**根本原因**（更正）:
- 根据 TuShare API 文档 (`p/tu.md`)，`delist_date` 字段**存在**于 stock_basic 接口输出参数中
- 但它的"默认显示"属性为 **N**，即不显式指定 fields 参数时不会返回
- 如果下载 stock_basic 时没有在 fields 中包含 `delist_date`，则数据中不会有此字段
- **真正的解决方案**：确保下载 stock_basic 时在 fields 参数中包含 `delist_date`

### 修改方案

**方案零（根本解决）：确保下载时包含 delist_date 字段**

与问题一相同，确保 stock_basic.yaml 中的 fields 配置包含 `delist_date`：
```yaml
fields:
  # ... 其他字段
  - delist_date   # 退市日期
```

downloader.py 已正确处理 fields 参数，会使用配置文件中的字段列表。

---

## 问题三：dividend 等接口任务重复执行

### 现象

终端输出显示每个日志打印**两次**：

```
第20行: [dividend/000001.SZ] 缺口检测模式: date_anchor, 用户提供日期: True
第21行: [dividend/000001.SZ] 缺口检测模式: date_anchor, 用户提供日期: True  ← 重复！

第26行: [000001.SZ] Gap detection found 84 tasks to download
第27行: [000001.SZ] Gap detection found 84 tasks to download  ← 重复！

第28行:   - {'ts_code': '000001.SZ', 'ann_date': '20050331'}
第29行:   - {'ts_code': '000001.SZ', 'ann_date': '20050331'}  ← 重复！
```

**影响的接口**（类型 C：date_anchor 模式）:
- `dividend`
- `top10_holders`
- `top10_floatholders`
- `disclosure_date`
- `pledge_stat`
- `stk_rewards`

**不影响**（类型 A：trade_date 模式）:
- `stk_factor_pro`
- `cyq_chips`
- `moneyflow_dc`

### 问题代码

**双重缺口检测的调用链**:

```
main.py: run_concurrent_stock_download()
    │
    ├── 构建任务列表
    │   for params in params_list:
    │       task = {'func': downloader.download_single_stock, ...}
    │
    └── scheduler.submit_tasks(tasks)
            │
            └── downloader.download_single_stock()    # downloader.py:438
                    │
                    └── detect_stock_gaps()            # downloader.py:481 ← 第一次检测
                            │
                            └── 遍历 gap_tasks 下载
                                    │
                                    └── _execute_paginated_download()
                                            │
                                            └── ParamsBuilder._apply_stock_loop()  # pagination.py:259
                                                    │
                                                    └── detect_stock_gaps()         # pagination.py:272 ← 第二次检测！
```

**第一处：`app4/core/downloader.py:476-497`**

```python
def download_single_stock(self, interface_config, stock, params, context=None):
    # ...
    if detection_config.get('stock_level_detection', False):
        # 第一次缺口检测
        gap_tasks = self.coverage_manager.detect_stock_gaps(
            interface_config['api_name'],
            ts_code,
            start_date,
            end_date,
            interface_config,
            user_provided_dates=user_provided_dates,
            stock_info=stock
        )
        
        logger.info(f"[{ts_code}] Gap detection found {len(gap_tasks)} tasks")
        for task in gap_tasks:
            logger.info(f"  - {task}")  # ← 这里打印了任务列表
    # ...
```

**第二处：`app4/core/pagination.py:266-293`**

```python
def _apply_stock_loop(self, params_stream: List[Dict[str, Any]], stock_list: List[Dict[str, Any]]):
    # ...
    if stock_level_detection and self.context.coverage_manager:
        # 第二次缺口检测（重复！）
        gap_tasks = self.context.coverage_manager.detect_stock_gaps(
            self.interface_config.get('api_name', ''),
            ts_code,
            start_date,
            end_date,
            self.interface_config,
            user_provided_dates=user_provided_dates,
            stock_info=stock
        )
        
        for gap_params in gap_tasks:
            task_params = params.copy()
            task_params.update(gap_params)
            yield task_params  # ← 又生成了任务
    # ...
```

**根本原因**:
- `downloader.download_single_stock()` 已经执行了缺口检测并生成了 `gap_tasks`
- 但 `_execute_paginated_download()` 内部又调用了 `ParamsBuilder._apply_stock_loop()`
- `ParamsBuilder._apply_stock_loop()` 再次执行缺口检测，导致重复

### 修改方案

**方案二（推荐）：在 pagination 层移除缺口检测**

修改 `app4/core/pagination.py:266-293`，移除 `_apply_stock_loop` 中的缺口检测：

```python
def _apply_stock_loop(self, params_stream: List[Dict[str, Any]], stock_list: List[Dict[str, Any]]):
    """应用股票循环维度"""
    if not stock_list:
        return
    
    stock_loop_config = self.config.get('stock_loop', {})
    skip_existing = stock_loop_config.get('skip_existing', False)
    
    # [移除] 不在此处执行缺口检测，由 downloader 层负责
    # detection_config = self.interface_config.get('duplicate_detection', {})
    # stock_level_detection = detection_config.get('stock_level_detection', False)
    
    for params in params_stream:
        for stock in stock_list:
            ts_code = stock.get('ts_code')
            if not ts_code:
                continue
            
            # 原有跳过逻辑
            if skip_existing and not self.context.force_download:
                if self._stock_data_exists(ts_code):
                    continue
            
            stock_params = params.copy()
            stock_params['ts_code'] = ts_code
            stock_params['_stock_info'] = stock
            yield stock_params
```

---

## 修改优先级

| 优先级 | 问题 | 影响范围 | 严重程度 | 修改复杂度 |
|--------|------|----------|----------|------------|
| 高 | 问题三：任务重复 | 类型C接口 | 严重（性能问题） | 中 |
| 中 | 问题一：exchange列 | 所有接口 | 中等（启动报错） | 低 |
| 低 | 问题二：delist_date | stock_basic | 低（警告信息） | 低 |

---

## 测试验证

修改后需要验证的测试用例：

1. **问题一验证**:
   ```bash
   python app4/main.py --interface stk_factor_pro --ts_code 000001.SZ \
       --start_date 20240101 --end_date 20240630
   ```
   预期：无 `exchange` 列错误

2. **问题二验证**:
   ```bash
   python app4/main.py --interface stock_basic
   ```
   预期：无 `delist_date` 列警告

3. **问题三验证**:
   ```bash
   python app4/main.py --interface dividend --ts_code 000001.SZ \
       --start_date 20240101 --end_date 20240630
   ```
   预期：日志中每个任务只打印一次

---

## 相关文件

- `app4/core/cache_warmer.py` - 预加载缓存
- `app4/core/schema_manager.py` - Schema 管理
- `app4/core/downloader.py` - 下载器
- `app4/core/pagination.py` - 分页执行器
- `app4/config/interfaces/stock_basic.yaml` - stock_basic 配置

---

## 变更历史

| 日期 | 作者 | 变更内容 |
|------|------|----------|
| 2026-02-20 | Claude | 初稿，记录三大问题及修复方案 |
