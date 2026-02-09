# Update 模式去重逻辑接入方案

## 问题分析

当前 Update 模式在 `update_manager.py` 的 `_execute_download()` 方法中，下载数据后：
1. 使用 `processor.process_data()` 处理数据（清洗、批次内去重）
2. 直接调用 `storage_manager.write_interface_data()` 保存

**缺失环节**：没有与已有存量数据进行去重比对。

## 解决方案

在 `UpdateManager._execute_download()` 中接入去重逻辑，与普通下载模式保持一致。

## 具体实现

### 1. 添加 import

在 `app4/update/update_manager.py` 文件顶部添加：

```python
import polars as pl
import tempfile
import os
```

### 2. 修改 `_execute_download` 方法

替换原有的 `_execute_download` 方法（约第403-476行）：

```python
def _execute_download(
    self,
    interface_name: str,
    interface_config: Dict[str, Any],
    date_range: DateRange,
    options: UpdateOptions
) -> int:
    """
    执行下载（增强版 - 增加与已有数据去重）
    """
    # 构建参数
    params = {
        'start_date': date_range.start_date,
        'end_date': date_range.end_date
    }

    # 先转换旧版分页配置为新版格式
    pagination_config = migrate_legacy_config(interface_config)

    # 获取交易日历和股票列表（如果需要）
    trade_calendar = None
    stock_list = None

    if pagination_config.get('enabled', False):
        if pagination_config.get('time_range', {}).get('enabled', False):
            trade_calendar = self.downloader.get_trade_calendar(
                date_range.start_date,
                date_range.end_date
            )

        if pagination_config.get('stock_loop', {}).get('enabled', False):
            stock_list = self.downloader._get_stock_list()

    # 构建上下文
    context = create_context_with_legacy_support(
        interface_config=interface_config,
        trade_calendar=trade_calendar,
        stock_list=stock_list,
        coverage_manager=self.coverage_manager,
        force_download=options.force
    )

    # 使用统一的分页执行入口
    result_data = self.pagination_executor.execute(
        interface_config=interface_config,
        base_params=params,
        context=context,
        make_request=self.downloader._make_request,
        coverage_manager=self.coverage_manager
    )

    # 处理和保存数据（增加去重逻辑）
    if result_data and len(result_data) > 0:
        # 使用 processor 处理数据
        df = self.processor.process_data(result_data, interface_config)

        if not df.is_empty():
            # 【新增】与已有数据进行去重
            df = self._deduplicate_against_existing(
                interface_name, interface_config, df
            )

            # 如果去重后还有数据，则保存
            if not df.is_empty():
                self.storage_manager.write_interface_data(interface_name, df)
                return len(result_data)
            else:
                logger.info(f"All records already exist for {interface_name}, skipping save")
                return 0

    return 0
```

### 3. 添加 `_deduplicate_against_existing` 方法

在 `_execute_download` 方法后添加新方法：

```python
def _deduplicate_against_existing(
    self,
    interface_name: str,
    interface_config: Dict[str, Any],
    new_df: pl.DataFrame
) -> pl.DataFrame:
    """
    与已有存量数据进行去重
    """
    from core.dedup import deduplicate_against_existing

    # 获取主键配置
    output_config = interface_config.get('output', {})
    primary_keys = output_config.get('primary_key', [])
    dedup_config = interface_config.get('dedup', {'dedup_enabled': True})

    # 如果未启用去重或无主键，直接返回
    if not dedup_config.get('dedup_enabled', True) or not primary_keys:
        return new_df

    # 检查新数据是否包含所有主键字段
    missing_keys = [k for k in primary_keys if k not in new_df.columns]
    if missing_keys:
        logger.warning(f"New data missing primary keys {missing_keys} for {interface_name}, skipping deduplication")
        return new_df

    try:
        # 读取已有数据（只读取主键列以提高性能）
        existing_df = self.storage_manager.read_interface_data(
            interface_name,
            columns=primary_keys
        )
    except Exception as e:
        logger.warning(f"Failed to read existing data for deduplication: {e}")
        return new_df

    # 如果没有已有数据，跳过去重
    if existing_df.is_empty():
        logger.debug(f"No existing data found for {interface_name}, skipping deduplication")
        return new_df

    # 使用临时文件进行去重
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp_file:
            existing_df.write_parquet(tmp_file.name)
            temp_path = tmp_file.name

        # 调用统一的去重模块
        deduped_df, dedup_stats = deduplicate_against_existing(
            new_data=new_df,
            existing_data_path=temp_path,
            primary_keys=primary_keys
        )

        logger.info(
            f"Deduplication for {interface_name}: "
            f"input={dedup_stats.input_rows}, "
            f"compared={dedup_stats.compared_rows}, "
            f"output={dedup_stats.output_rows}, "
            f"removed={dedup_stats.removed_rows}, "
            f"dedup_rate={dedup_stats.get_dedup_rate():.2f}%"
        )

        if dedup_stats.errors:
            for error in dedup_stats.errors:
                logger.error(f"Deduplication error for {interface_name}: {error}")
        if dedup_stats.warnings:
            for warning in dedup_stats.warnings:
                logger.warning(f"Deduplication warning for {interface_name}: {warning}")

        return deduped_df

    except Exception as e:
        logger.error(f"Deduplication failed for {interface_name}: {e}")
        return new_df

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {temp_path}: {e}")
```

## 变更总结

| 文件 | 变更内容 |
|------|---------|
| `app4/update/update_manager.py` | 添加 import，替换 `_execute_download`，新增 `_deduplicate_against_existing` |

## 去重流程

```
下载数据
    ↓
processor.process_data() [批次内去重]
    ↓
_deduplicate_against_existing() [与存量数据去重] ← 新增
    ↓
storage_manager.write_interface_data() [保存]
```

## 关键特性

1. **性能优化**: 只读取已有数据的主键列进行比对
2. **容错处理**: 去重失败时返回原始数据，避免数据丢失
3. **配置兼容**: 遵守接口 YAML 中的 `dedup` 和 `primary_key` 配置
4. **日志记录**: 详细记录去重统计信息
