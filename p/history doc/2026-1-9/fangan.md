# 基于主键的记录级重复检测方案

## 问题概述

当前系统在下载数据时，使用"覆盖率阈值"来判断是否跳过**整个请求**。这导致：
- 若覆盖率低于阈值，会重新下载所有数据，包括已存在的记录
- 无法实现"只下载新记录，跳过已存在记录"的增量更新

## 解决方案

实现**两层基于主键的去重机制**：

1. **下载前**：在**所有待下载主键均已知**的前提下（如基于交易日历的日线数据），计算预期的主键集合。检查这些主键是否**全部**已存在于数据库中。若全部存在，则直接跳过请求；否则发起下载。（严格的全量检查）
2. **保存前**：逐条检查下载回来的每条记录的主键是否已存在，只保存不存在的记录。（细粒度写入过滤）

---

## 实施步骤

### 第一步：修改 `main.py` 中的 `process_and_save_data` 函数

**文件路径**: `app4/main.py`

**修改位置**: 第 263-291 行的 `process_and_save_data` 函数

**修改内容**：在保存数据前，读取现有数据的主键集合，过滤出不存在的新记录。

```python
def process_and_save_data(data, interface_name, interface_config, processor, storage_manager):
    """处理并保存数据的通用函数 - 支持基于主键的记录级去重

    Args:
        data: 原始数据列表
        interface_name: 接口名称
        interface_config: 接口配置
        processor: 数据处理器
        storage_manager: 存储管理器

    Returns:
        处理后的 DataFrame，如果处理失败则返回 None
    """
    if not data:
        logger.warning(f"No data to process for {interface_name}")
        return None

    # 处理数据
    df = processor.process_data(data, interface_config)
    validation_result = processor.validate_data(df, interface_config)

    # [新增] 基于主键的记录级去重
    primary_keys = interface_config.get('output', {}).get('primary_key', [])
    
    if primary_keys:
        # 读取现有数据的主键
        existing_df = storage_manager.read_interface_data(
            interface_name, 
            columns=primary_keys
        )
        
        if not existing_df.is_empty():
            # 构建现有主键集合
            existing_keys = set()
            for row in existing_df.iter_rows(named=True):
                key_tuple = tuple(row.get(k) for k in primary_keys if k in row)
                if all(v is not None for v in key_tuple):
                    existing_keys.add(key_tuple)
            
            logger.info(f"Found {len(existing_keys)} existing primary key combinations for {interface_name}")
            
            # 过滤出不存在的新记录
            original_count = len(df)
            
            # 构建过滤条件：检查每行的主键组合是否在现有集合中
            def is_new_record(row):
                key_tuple = tuple(row.get(k) for k in primary_keys if k in row.keys())
                return key_tuple not in existing_keys
            
            # 使用 Polars 过滤
            import polars as pl
            
            # 方法：逐行检查主键是否存在
            new_records = []
            for row in df.iter_rows(named=True):
                key_tuple = tuple(row.get(k) for k in primary_keys)
                if key_tuple not in existing_keys:
                    new_records.append(row)
            
            if not new_records:
                logger.info(f"All {original_count} records already exist for {interface_name}, skipping save")
                return df
            
            # 重新创建 DataFrame
            df = pl.DataFrame(new_records)
            logger.info(f"Filtered {original_count - len(df)} duplicate records, saving {len(df)} new records for {interface_name}")

    # 保存数据
    storage_manager.save_data(interface_name, df.to_dicts(), async_write=True)

    logger.info(f"Saved {len(df)} processed records for {interface_name}")
    if validation_result['duplicate_records'] > 0:
        logger.info(f"Found {validation_result['duplicate_records']} duplicate records for {interface_name}")

    return df
```

---

### 第二步：修改 `core/downloader.py` 中的 `download_single_stock` 方法

**文件路径**: `app4/core/downloader.py`

**修改位置**: 第 920-969 行的 `download_single_stock` 方法

**修改内容**：将策略从 `'stock'` 改为 `'date_range'`，使其基于日期范围计算覆盖率。

```python
def download_single_stock(self, interface_config: Dict[str, Any], stock: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """下载单只股票的数据 - 原子化方法供调度器调用

    Args:
        interface_config: 接口配置
        stock: 股票信息字典，包含ts_code等
        params: 基础请求参数

    Returns:
        该股票的数据列表，如果出错则返回空列表
    """
    try:
        stock_params = params.copy()
        stock_params['ts_code'] = stock['ts_code']

        # 设置日期范围
        if 'start_date' not in stock_params:
            # 如果没有指定起始日期，使用该股票的上市日期
            list_date = stock.get('list_date', '20050101')
            stock_params['start_date'] = list_date
        if 'end_date' not in stock_params:
            from datetime import datetime
            stock_params['end_date'] = datetime.now().strftime('%Y%m%d')

        # [修改] 使用 precise_existence 策略检查是否存在
        # 前提：能通过参数（如日期范围+交易日历）推算出所有预期的主键
        if self.coverage_manager:
            should_skip = self.coverage_manager.should_skip(
                interface_config['api_name'],
                stock_params,
                strategy='precise_existence'  # 改为精确存在性检查
            )
            if should_skip:
                logger.info(f"Skipping stock {stock['ts_code']} for {interface_config['api_name']} (all expected records exist)")
                return []

        logger.info(f"Downloading data for stock {stock['ts_code']}, date range: {stock_params.get('start_date')} - {stock_params.get('end_date')}")

        # 执行日期范围分页下载
        stock_data = self._execute_date_range_pagination(interface_config, stock_params)

        if stock_data:
            logger.info(f"Downloaded {len(stock_data)} records for {stock['ts_code']}")

        return stock_data or []
    except Exception as e:
        # 捕获异常，避免影响其他股票
        logger.error(f"Error downloading stock {stock['ts_code']}: {str(e)}")
        import traceback
        logger.debug(f"Full traceback: {traceback.format_exc()}")
        return []  # 返回空列表，让其他股票继续下载
```

---

### 第三步：修改 `core/coverage_manager.py` 中的 `_check_precise_existence` 方法

**文件路径**: `app4/core/coverage_manager.py`

**修改位置**: 新增 `_check_precise_existence` 方法（替代原计划的 `_check_range_coverage`）

**修改内容**：实现基于主键的精确存在性检查。

```python
def _check_precise_existence(self, interface_name: str, params: Dict[str, Any]) -> bool:
    """
    检查预期数据是否完全存在 (基于主键的精确检查)
    
    前提：必须能根据 params 推算出所有预期的主键（例如通过交易日历）

    Args:
        interface_name: 接口名称
        params: 请求参数，应包含start_date, end_date, ts_code等

    Returns:
        True表示所有预期数据都已存在（应跳过），False表示有缺失（应下载）
    """
    start_date = params.get('start_date')
    end_date = params.get('end_date')
    target_stock = params.get('ts_code')

    if not start_date or not end_date or not target_stock:
        logger.debug(f"Missing necessary parameters for precise check in {interface_name}")
        return False

    # 生成缓存键
    cache_key = f"{interface_name}_precise_{start_date}_{end_date}_{target_stock}"
    
    with self._cache_lock:
        if cache_key in self._coverage_cache:
            return self._coverage_cache[cache_key]

    try:
        # 1. 计算【预期】的主键集合
        # 这里的逻辑主要针对"日期"相关的主键，如 trade_date
        # 如果是其他类型的主键，需要相应的逻辑支持
        
        # 获取交易日历
        if not self.downloader:
             # 如果没有downloader无法获取日历，则无法进行精确检查
             return False 
             
        trade_calendar = self.downloader.get_trade_calendar(start_date, end_date)
        if not trade_calendar:
            # 无法获取日历，保守起见不跳过
            return False

        # 预期存在的日期集合 (Set[str])
        expected_dates = {day['cal_date'] for day in trade_calendar if day.get('is_open', 0) == 1}
        
        if not expected_dates:
             # 区间内无交易日，也就是预期数据为空，可以视为"已完成"（不需要下载）
             with self._cache_lock:
                self._coverage_cache[cache_key] = True
             return True

        # 2. 获取【实际】的主键集合
        interface_config = self.config_loader.get_interface_config(interface_name)
        detection_config = interface_config.get('duplicate_detection', {})
        date_column = detection_config.get('date_column', 'trade_date')
        
        # 只读取必要的列：日期列 + 股票代码列
        columns_to_read = [date_column, 'ts_code']
        
        # 从存储中读取实际数据
        # 注意：这里假设 read_interface_data 支持按日期范围过滤，这通常比较快
        df = self.storage_manager.read_interface_data(
            interface_name,
            start_date=start_date,
            end_date=end_date,
            columns=columns_to_read
        )
        
        if df.is_empty():
            actual_dates = set()
        else:
            # 过滤出该股票的数据
            import polars as pl
            # 确保列名存在
            if 'ts_code' in df.columns:
                stock_df = df.filter(pl.col('ts_code') == target_stock)
                actual_dates = set(stock_df[date_column].to_list())
            else:
                # 如果没有ts_code列，可能接口本身就不区分股票，或者数据结构不同
                # 这里假设如果有ts_code参数，就应该有ts_code列
                logger.warning(f"ts_code column missing in data for {interface_name}")
                return False

        # 3. 比较：是否所有预期日期都存在
        # 只有当 expected_dates 是 actual_dates 的子集时，才算完全存在
        missing_dates = expected_dates - actual_dates
        
        if not missing_dates:
            logger.info(f"Precise check passed for {target_stock} ({start_date}-{end_date}): All {len(expected_dates)} expected records exist.")
            result = True
        else:
            # 只要有缺失，就认为需要下载（哪怕只缺一天）
            # 详细日志可以帮助调试，但生产环境可能需要减少
            logger.info(f"Precise check failed for {target_stock} ({start_date}-{end_date}): Missing {len(missing_dates)}/{len(expected_dates)} records.")
            result = False

        with self._cache_lock:
            self._coverage_cache[cache_key] = result
            
        return result

    except Exception as e:
        logger.warning(f"Precise existence check failed for {interface_name}: {e}")
        return False
```

---

## 数据流说明

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           数据下载流程                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. download_single_stock()                                             │
│     │                                                                   │
│     ├─→ coverage_manager.should_skip(strategy='precise_existence')      │
│     │   └─→ _check_precise_existence() 检查精确存在性                    │
│     │       └─→ 如果所有预期主键都存在，跳过整个请求 (全量检查)              │
│     │                                                                   │
│     └─→ 如果有任何缺失，发起 API 请求下载数据                               │
│                                                                         │
│  2. process_and_save_data()                                             │
│     │                                                                   │
│     ├─→ processor.process_data() 处理数据                                │
│     │                                                                   │
│     ├─→ [新增] 读取现有数据的主键集合                                     │
│     │   └─→ 逐条检查每条记录的主键是否已存在                              │
│     │       └─→ 过滤出不存在的新记录 (细粒度过滤)                         │
│     │                                                                   │
│     └─→ storage_manager.save_data() 只保存新记录                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 验证方法

### 测试步骤

1. **首次运行**：下载 `income_vip` 接口的某只股票数据
   ```bash
   python main.py --interface income_vip --ts_code 000001.SZ --start_date 20230101 --end_date 20231231
   ```
   预期：下载并保存所有记录

2. **再次运行相同参数**：
   ```bash
   python main.py --interface income_vip --ts_code 000001.SZ --start_date 20230101 --end_date 20231231
   ```
   预期：日志显示 "Skipping stock ... (all expected records exist)"，不发起网络请求

3. **扩展日期范围运行**：
   ```bash
   python main.py --interface income_vip --ts_code 000001.SZ --start_date 20230101 --end_date 20241231
   ```
   预期：日志显示 "Filtered X duplicate records, saving Y new records"，只保存新增的2024年数据

---

## 预期效果

1. **预期数据全部存在**：跳过整个请求，不发起 API 调用
2. **预期数据存在缺失**：发起 API 请求，但保存时根据主键过滤，只保存不存在的记录
3. **避免数据重复**：无论运行多少次，相同主键的记录只会保存一次