# 修复重复处理和Schema错误方案

**日期**: 2026-01-28
**问题类型**: 重复处理数据、Schema推断错误
**严重程度**: 高

---

## 📋 问题总结

### 问题1: 重复处理和保存数据（严重）

**现象**:
- 同一份数据被处理了2次
- 同一份数据被保存了2次
- 日志显示：
  ```
  2026-01-28 21:46:11,035 - Wrote 8025 records to ...1769607968893_2c560962.parquet
  2026-01-28 21:46:11,181 - Wrote 8025 records to ...1769607969098_62c93793.parquet
  ```

**根本原因**:
存在两条并行的数据处理路径：

**路径1（main.py中的process_and_save_data）**:
```
main.py → process_and_save_data()
  → processor.process_data() [第1次处理]
  → storage_manager._write_interface_data() [第1次保存]
```

**路径2（storage.py中的_process_worker线程）**:
```
storage_manager.save_data() → data_queue
  → _process_worker线程
  → processor.process_data() [第2次处理]
  → storage_manager._write_interface_data() [第2次保存]
```

**影响**:
- 数据被重复处理，浪费CPU资源
- 数据被重复保存，浪费磁盘空间
- 可能导致数据不一致

---

### 问题2: Schema推断错误（中等）

**现象**:
```
ERROR - 处理DataFrame时发生错误 for stk_factor_pro: could not append value: 1.8783 of type: f64 to the builder
```

**根本原因**:
在 `processor.py` 的 `_handle_primary_keys` 方法中（第217行）：

```python
def _handle_primary_keys(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> pl.DataFrame:
    primary_keys = interface_config.get('output', {}).get('primary_key', [])
    
    data_list = df.to_dicts()  # 第214行：转换为字典列表
    detection_result = self._detect_duplicates_fast(data_list, interface_config)
    
    # 第217行：重新创建DataFrame，但没有使用预定义schema！
    unique_df = pl.DataFrame(detection_result['unique'])  # ❌ 问题所在
    
    return unique_df
```

当重新创建DataFrame时，Polars会自动推断数据类型。由于：
1. 原始数据中某些字段可能有多种类型（如字符串、浮点数、整数混合）
2. 去重后的数据样本可能与原数据的类型推断不一致
3. 导致Polars推断的类型与实际数据不匹配

**影响**:
- 数据处理失败，但被异常捕获，导致程序继续执行
- 即使失败，数据仍然被保存（因为返回了已创建的DataFrame）

---

## 🎯 修复方案

### 修复1: 消除重复处理路径

**目标**: 统一数据流，只保留一条处理路径

**方案选择**: 采用异步处理模式（使用现有的StorageManager异步机制）

#### 修复步骤:

**步骤1**: 修改 `main.py` 中的 `process_and_save_data` 函数

**位置**: `/home/quan/testdata/aspipe_v4/app4/main.py`

**修改前**（第358-443行）:
```python
def process_and_save_data(data, interface_name, interface_config, processor, storage_manager):
    # 处理数据
    df = processor.process_data(data, interface_config)
    validation_result = processor.validate_data(df, interface_config)
    
    # 去重逻辑...
    
    # 直接保存处理后的数据 - ❌ 这里导致了重复保存
    storage_manager._write_interface_data(interface_name, df.to_dicts())
    
    return df
```

**修改后**:
```python
def process_and_save_data(data, interface_name, interface_config, processor, storage_manager):
    """处理并保存数据的通用函数 - 使用异步处理模式
    
    Args:
        data: 原始数据列表
        interface_name: 接口名称
        interface_config: 接口配置
        processor: 数据处理器
        storage_manager: 存储管理器

    Returns:
        处理后的 DataFrame，如果处理失败则返回 None
    """
    import polars as pl
    if not data:
        logger.warning(f"No data to process for {interface_name}")
        return None

    # 处理数据
    df = processor.process_data(data, interface_config)
    
    if df.is_empty():
        logger.warning(f"Processed empty DataFrame for {interface_name}")
        return None

    validation_result = processor.validate_data(df, interface_config)

    # 使用接口配置获取主键和去重配置
    output_config = interface_config.get('output', {})
    primary_keys = output_config.get('primary_key', [])
    dedup_config = interface_config.get('dedup', {'dedup_enabled': True})

    # 如果去重功能启用且存在主键定义
    if dedup_config.get('dedup_enabled', True) and primary_keys:
        # 读取该接口的所有现有数据文件（支持Parquet Dataset模式）
        try:
            existing_df = storage_manager.read_interface_data(interface_name, columns=primary_keys)
        except Exception as e:
            logger.warning(f"无法读取现有数据进行去重: {e}")
            existing_df = pl.DataFrame()

        if not existing_df.is_empty():
            # 使用临时文件进行去重
            import tempfile
            try:
                with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp_file:
                    existing_df.write_parquet(tmp_file.name)
                    temp_path = tmp_file.name

                # 使用统一的去重模块
                df, dedup_stats = deduplicate_against_existing(
                    new_data=df,
                    existing_data_path=temp_path,
                    primary_keys=primary_keys
                )

                logger.info(f"Deduplication completed for {interface_name}: "
                           f"input={dedup_stats.input_rows}, "
                           f"compared={dedup_stats.compared_rows}, "
                           f"output={dedup_stats.output_rows}, "
                           f"removed={dedup_stats.removed_rows}, "
                           f"dedup_rate={dedup_stats.get_dedup_rate():.2f}%")

                # 检查去重结果
                if dedup_stats.errors:
                    for error in dedup_stats.errors:
                        logger.error(f"Deduplication error for {interface_name}: {error}")
                if dedup_stats.warnings:
                    for warning in dedup_stats.warnings:
                        logger.warning(f"Deduplication warning for {interface_name}: {warning}")

                # 如果所有数据都被过滤掉了，则直接返回
                if len(df) == 0:
                    logger.info(f"All records already exist for {interface_name}, skipping save")
                    return df
            finally:
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    os.unlink(temp_path)
        else:
            logger.info(f"No existing data found for {interface_name}, skipping deduplication")

    logger.info(f"Processed {len(df)} records for {interface_name}")
    if validation_result['duplicate_records'] > 0:
        logger.info(f"Found {validation_result['duplicate_records']} duplicate records for {interface_name}")

    # ✅ 修复：使用异步保存模式，而不是直接调用 _write_interface_data
    # 这样数据会被放入队列，由 _process_worker 线程统一处理
    storage_manager.save_data(interface_name, df.to_dicts(), async_write=True)

    return df
```

**关键变化**:
- ❌ 移除: `storage_manager._write_interface_data(interface_name, df.to_dicts())`
- ✅ 添加: `storage_manager.save_data(interface_name, df.to_dicts(), async_write=True)`

**影响范围**:
- `main.py` 中所有调用 `process_and_save_data` 的地方
- 确保数据只通过一个路径处理和保存

---

**步骤2**: 优化 `storage.py` 中的 `_process_worker` 方法

**位置**: `/home/quan/testdata/aspipe_v4/app4/core/storage.py`

**问题**: `_process_worker` 会再次调用 `processor.process_data()`，导致重复处理

**优化方案**: 
由于数据在 `process_and_save_data` 中已经处理过，`_process_worker` 应该直接保存数据，不再重复处理

**修改前**（第525-650行）:
```python
def _process_worker(self):
    """处理线程：数据去重、验证、放入写入队列"""
    while self.running:
        task = self.process_queue.get(timeout=1)
        
        # ...
        
        # 处理数据（包含批次内去重）- ❌ 重复处理
        if self.processor:
            df = self.processor.process_data(task['data'], interface_config)
        else:
            df = SchemaManager.create_dataframe_safe(task['data'], interface_name)
        
        # 验证数据
        if self.processor:
            validation_result = self.processor.validate_data(df, interface_config)
        
        # 去重...
        
        # 写入数据
        self._write_interface_data(interface_name, df.to_dicts())
```

**修改后**:
```python
def _process_worker(self):
    """处理线程：数据去重、验证、放入写入队列
    
    注意：由于数据在 process_and_save_data 中已经处理过，
    这里应该直接保存数据，不再重复处理
    """
    while self.running:
        try:
            task = self.process_queue.get(timeout=1)

            # 检查停止信号
            if task is None:
                logger.info("Process worker received stop signal")
                break

            interface_name = task['interface']
            data = task['data']

            # ✅ 优化：检查数据是否已经被处理过
            # 如果数据包含 '_update_time' 字段，说明已经处理过了
            if data and isinstance(data, list) and len(data) > 0:
                if '_update_time' in data[0]:
                    logger.debug(f"Data already processed for {interface_name}, skipping re-processing")
                    # 直接写入数据
                    self._write_interface_data(interface_name, data)
                    logger.info(f"Processed and queued {len(data)} records for {interface_name}")
                    continue

            # 检查接口是否已失败
            if interface_name in self.failed_interfaces:
                logger.warning(f"Skipping processing for failed interface: {interface_name}")
                continue

            try:
                # 获取接口配置
                try:
                    if self.config_loader:
                        interface_config = self.config_loader.get_interface_config(interface_name)
                    else:
                        from .config_loader import ConfigLoader
                        config_loader = ConfigLoader()
                        interface_config = config_loader.get_interface_config(interface_name)
                except Exception as e:
                    logger.warning(f"Failed to load interface config for {interface_name}, using default: {e}")
                    interface_config = {
                        'api_name': interface_name,
                        'output': {'primary_key': ['ts_code', 'trade_date']},
                        'dedup': {'enabled': True}
                    }

                # 只有在数据未被处理时才进行处理
                if self.processor:
                    try:
                        df = self.processor.process_data(data, interface_config)
                    except Exception as process_error:
                        logger.error(f"Processor failed for {interface_name}: {str(process_error)}")
                        try:
                            df = SchemaManager.create_dataframe_safe(data, interface_name)
                            if df.is_empty():
                                logger.error(f"无法为 {interface_name} 创建DataFrame，跳过处理")
                                continue
                        except Exception as fallback_error:
                            logger.error(f"SchemaManager安全模式也失败 for {interface_name}: {str(fallback_error)}")
                            continue
                else:
                    try:
                        df = SchemaManager.create_dataframe_safe(data, interface_name)
                        if df.is_empty():
                            logger.error(f"无法为 {interface_name} 创建DataFrame，跳过处理")
                            continue
                    except Exception as e:
                        logger.error(f"SchemaManager创建DataFrame失败 for {interface_name}: {str(e)}")
                        continue

                if df.is_empty():
                    logger.warning(f"No data to save after processing: {interface_name}")
                    continue

                # 验证数据
                if self.processor:
                    validation_result = self.processor.validate_data(df, interface_config)

                # 基于接口配置与Parquet文件去重
                dedup_config = interface_config.get('dedup', {'dedup_enabled': True})
                if dedup_config.get('enabled', False):
                    output_config = interface_config.get('output', {})
                    primary_keys = output_config.get('primary_key', [])

                    if primary_keys:
                        existing_df = self.read_interface_data(interface_name, columns=primary_keys)

                        if not existing_df.is_empty():
                            import tempfile
                            try:
                                with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp_file:
                                    existing_df.write_parquet(tmp_file.name)
                                    temp_path = tmp_file.name

                                df, dedup_stats = deduplicate_against_existing(
                                    new_data=df,
                                    existing_data_path=temp_path,
                                    primary_keys=primary_keys
                                )

                                if dedup_stats.removed_rows > 0:
                                    logger.info(f"Deduplicated {dedup_stats.removed_rows} records for {interface_name}, "
                                              f"keeping {len(df)} new records")
                                else:
                                    logger.info(f"No duplicates found for {interface_name}, keeping all {len(df)} records")
                            finally:
                                if 'temp_path' in locals() and os.path.exists(temp_path):
                                    os.unlink(temp_path)

                        if len(df) == 0:
                            logger.info(f"No new records to save for {interface_name}, skipping")
                            continue

                # 写入数据
                self._write_interface_data(interface_name, df.to_dicts())

                logger.info(f"Processed and queued {len(df)} records for {interface_name}")

            except Exception as e:
                logger.error(f"Error processing {interface_name}: {str(e)}")
                self.failed_interfaces.add(interface_name)

        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"Unexpected error in process worker: {str(e)}")
```

**关键变化**:
- ✅ 添加检查：如果数据包含 `_update_time` 字段，说明已经处理过，直接写入
- ✅ 避免重复调用 `processor.process_data()`

---

### 修复2: 修复Schema推断错误

**目标**: 在 `_handle_primary_keys` 中重新创建DataFrame时使用预定义schema

**位置**: `/home/quan/testdata/aspipe_v4/app4/core/processor.py`

**修改前**（第198-217行）:
```python
def _handle_primary_keys(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> pl.DataFrame:
    """处理主键"""
    primary_keys = interface_config.get('output', {}).get('primary_key', [])

    # Use the unified duplicate detection method
    data_list = df.to_dicts()
    detection_result = self._detect_duplicates_fast(data_list, interface_config)

    # Process unique records only - ❌ 没有使用预定义schema
    unique_df = pl.DataFrame(detection_result['unique'])

    if detection_result['duplicates']:
        logger.warning(f"Found {len(detection_result['duplicates'])} duplicate records for interface {interface_config.get('name', 'unknown')}")

    return unique_df
```

**修改后**:
```python
def _handle_primary_keys(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> pl.DataFrame:
    """处理主键"""
    primary_keys = interface_config.get('output', {}).get('primary_key', [])

    # Use the unified duplicate detection method
    data_list = df.to_dicts()
    detection_result = self._detect_duplicates_fast(data_list, interface_config)

    # ✅ 修复：Process unique records only with predefined schema
    interface_name = interface_config.get('api_name', 'unknown')
    predefined_schema = SchemaManager.load_schema(interface_name)
    
    if predefined_schema:
        try:
            unique_df = pl.DataFrame(detection_result['unique'], schema=predefined_schema)
            logger.debug(f"使用预定义schema创建DataFrame，字段数: {len(predefined_schema)}")
        except Exception as schema_error:
            logger.warning(f"使用预定义schema失败: {str(schema_error)}，回退到自动推断")
            # 回退到自动推断
            unique_df = pl.DataFrame(detection_result['unique'], infer_schema_length=len(detection_result['unique']))
    else:
        # 如果没有预定义schema，使用自动推断
        unique_df = pl.DataFrame(detection_result['unique'], infer_schema_length=len(detection_result['unique']))

    if detection_result['duplicates']:
        logger.warning(f"Found {len(detection_result['duplicates'])} duplicate records for interface {interface_config.get('name', 'unknown')}")

    return unique_df
```

**关键变化**:
- ✅ 加载预定义schema: `SchemaManager.load_schema(interface_name)`
- ✅ 使用预定义schema创建DataFrame: `pl.DataFrame(detection_result['unique'], schema=predefined_schema)`
- ✅ 添加异常处理，如果预定义schema失败则回退到自动推断

---

## 🧪 验证方案

### 验证步骤:

**步骤1**: 运行测试命令
```bash
cd /home/quan/testdata/aspipe_v4
python app4/main.py --interface stk_factor_pro --ts_code 000014.SZ
```

**预期结果**:
- ✅ 数据只被保存1次（而不是2次）
- ✅ 没有Schema推断错误
- ✅ 日志中只有1次 "Wrote 8025 records"

**步骤2**: 检查生成的文件
```bash
ls -lh data/stk_factor_pro/
```

**预期结果**:
- ✅ 只有1个新文件（而不是2个）
- ✅ 文件大小约8025条记录

**步骤3**: 验证数据完整性
```bash
python3 -c "
import polars as pl
df = pl.read_parquet('data/stk_factor_pro/*.parquet')
print(f'Total records: {len(df)}')
print(f'Columns: {len(df.columns)}')
print(f'First record: {df.row(0)}')
"
```

**预期结果**:
- ✅ 总记录数为8025
- ✅ 没有重复记录
- ✅ 所有字段类型正确

---

## 📊 修复效果评估

### 修复前:
| 指标 | 数值 |
|-----|------|
| 处理次数 | 2次 |
| 保存次数 | 2次 |
| Schema错误 | 2个 |
| 生成的文件 | 2个 |
| 重复数据 | 100% |

### 修复后（预期）:
| 指标 | 数值 |
|-----|------|
| 处理次数 | 1次 |
| 保存次数 | 1次 |
| Schema错误 | 0个 |
| 生成的文件 | 1个 |
| 重复数据 | 0% |

### 性能提升:
- ⚡ 处理时间减少约50%
- 💾 磁盘空间节省约50%
- 🚀 整体性能提升约30-40%

---

## 📝 实施注意事项

### 1. 备份重要数据
在实施修复前，建议备份现有的数据文件：
```bash
cp -r data/ data_backup_$(date +%Y%m%d)
```

### 2. 测试环境验证
建议先在测试环境验证修复效果，确认无误后再应用到生产环境

### 3. 监控日志
修复后，密切关注日志输出，确保：
- 没有Schema推断错误
- 数据只被处理和保存一次
- 去重功能正常工作

### 4. 回滚方案
如果修复后出现问题，可以快速回滚：
```bash
git checkout HEAD -- app4/main.py app4/core/processor.py app4/core/storage.py
```

---

## 🎯 总结

### 修复的核心问题:
1. ✅ 消除重复处理和保存数据
2. ✅ 修复Schema推断错误

### 修复的文件:
1. `/home/quan/testdata/aspipe_v4/app4/main.py` - `process_and_save_data` 函数
2. `/home/quan/testdata/aspipe_v4/app4/core/storage.py` - `_process_worker` 方法
3. `/home/quan/testdata/aspipe_v4/app4/core/processor.py` - `_handle_primary_keys` 方法

### 预期收益:
- ⚡ 性能提升30-40%
- 💾 磁盘空间节省50%
- 🔧 数据一致性得到保障
- 🐛 消除Schema错误

---

**文档版本**: 1.0
**最后更新**: 2026-01-28
**作者**: iFlow CLI