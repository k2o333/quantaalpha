# 统一去重功能重构方案

## 背景

当前 `app4` 目录中存在多处去重逻辑，分散在多个文件中：
- `core/dedup.py` - 统一去重模块
- `core/processor.py` - 批处理去重
- `core/downloader.py` - 下载时简单去重
- `core/storage.py` - 批量写入去重
- `core/cache_warmer.py` - 缓存预热去重

这些去重操作底层都使用 Polars 的 `.unique()` 方法，但实现分散，缺乏统一的统计信息和配置管理。

## 目标

将所有去重逻辑统一调用 `core/dedup.py` 模块，实现：
1. **代码一致性** - 所有去重使用同一套 API
2. **可配置性** - 统一的配置接口（keep_strategy, primary_keys 等）
3. **统计信息** - 获取去重统计（input_rows, output_rows, dedup_rate）
4. **可维护性** - 集中管理去重逻辑
5. **日志记录** - 统一的日志输出格式
6. **_update_time 自动处理** - 支持基于更新时间字段的自动排序

## 影响范围

### 需要修改的文件

1. **`core/processor.py`**
   - 行253, 256: `_remove_duplicates` 方法中的去重
   - 行134-157: `_handle_primary_keys` 方法中的去重（职责调整为仅检测）

2. **`core/downloader.py`**
   - 行345: `_get_stock_list_from_data_dir` 中的股票列表去重
   - 行429: `_get_trade_calendar_from_data_dir` 中的交易日历去重

3. **`core/storage.py`**
   - 行373: `_read_interface_data` 方法中的去重

4. **`core/cache_warmer.py`**
   - 行39: `preload_trade_calendar` 方法中的去重

5. **`core/dedup.py`**（增强）
   - 添加 `_update_time` 自动排序配置支持

## 实施方案

### 前置增强：DataDeduplicator 配置扩展

**在 `dedup.py` 的 DEFAULT_CONFIG 中添加：**

```python
DEFAULT_CONFIG = {
    # ... 原有配置 ...
    'sort_by_update_time': False,  # 是否自动按 _update_time 排序
    'update_time_field': '_update_time',  # 更新时间字段名
    'sort_ascending': True,  # 排序方向（True=升序，保留last；False=降序，保留first）
}
```

**在 `_perform_deduplication` 方法中添加自动排序逻辑：**

```python
def _perform_deduplication(self, df: pl.DataFrame, primary_keys: List[str]) -> pl.DataFrame:
    """Perform the actual deduplication based on the configured strategy."""
    
    # 自动处理 _update_time 排序
    if self.config.get('sort_by_update_time', False):
        update_time_field = self.config.get('update_time_field', '_update_time')
        if update_time_field in df.columns:
            ascending = self.config.get('sort_ascending', True)
            df = df.sort(update_time_field, descending=not ascending)
    
    strategy = self.config['keep_strategy']
    # ... 原有去重逻辑 ...
```

---

### 1. processor.py 改造

#### 1.1 `_remove_duplicates` 方法（行253）

**当前代码：**
```python
def _remove_duplicates(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> pl.DataFrame:
    output_config = interface_config.get('output', {})
    primary_keys = output_config.get('primary_key', [])
    existing_keys = [key for key in primary_keys if key in df.columns]

    if existing_keys:
        original_count = len(df)

        if '_update_time' in df.columns:
            df = df.sort('_update_time', descending=False)
            df = df.unique(subset=existing_keys, keep='last')
        else:
            df = df.unique(subset=existing_keys, keep='last')

        removed_count = original_count - len(df)
        if removed_count > 0:
            logger.info(f"Batch deduplication for {interface_config.get('api_name', 'unknown')}: "
                       f"removed {removed_count} duplicates within batch, "
                       f"keys={existing_keys}")
```

**改造后：**
```python
from .dedup import DataDeduplicator

def _remove_duplicates(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> pl.DataFrame:
    """
    批次内去重逻辑 - 职责：实际执行去重操作
    
    注意：此方法负责实际的数据去重，与 _handle_primary_keys 职责分离
    """
    output_config = interface_config.get('output', {})
    primary_keys = output_config.get('primary_key', [])
    existing_keys = [key for key in primary_keys if key in df.columns]

    if existing_keys:
        # 使用统一去重模块，启用 _update_time 自动排序
        deduplicator = DataDeduplicator({
            'primary_keys': existing_keys,
            'keep_strategy': 'last',
            'enable_stats': True,
            'sort_by_update_time': '_update_time' in df.columns,  # 自动检测并排序
            'sort_ascending': True  # 升序排序，配合 keep='last' 保留最新
        })

        deduplicated_df, stats = deduplicator.deduplicate(df)

        # 统一日志格式：仅在去重发生时使用 INFO 级别
        if stats.removed_rows > 0:
            logger.info(f"Batch deduplication for {interface_config.get('api_name', 'unknown')}: "
                       f"removed {stats.removed_rows} duplicates within batch, "
                       f"keys={existing_keys}, "
                       f"dedup_rate={stats.get_dedup_rate():.2f}%")
        else:
            logger.debug(f"No duplicates found within batch for {interface_config.get('api_name', 'unknown')}")

        df = deduplicated_df

    # 如果指定了排序字段，则进行排序（与去重分离）
    sort_by = output_config.get('sort_by', [])
    existing_sort_fields = [field for field in sort_by if field in df.columns]
    if existing_sort_fields:
        df = df.sort(by=existing_sort_fields)

    return df
```

#### 1.2 `_handle_primary_keys` 方法（行134-157）

**改造策略：** 明确职责为**仅检测重复**，不进行实际去重

**改造后：**
```python
def _handle_primary_keys(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> pl.DataFrame:
    """
    处理主键 - 职责：检测重复记录，过滤主键空值，但不执行去重
    
    注意：实际去重由 _remove_duplicates 方法负责，此方法仅做检测和报告
    """
    primary_keys = interface_config.get('output', {}).get('primary_key', [])
    
    if not primary_keys:
        return df
    
    # 仅检测重复，保留原有DataFrame
    data_list = df.to_dicts()
    detection_result = self._detect_duplicates_fast(data_list, interface_config)

    interface_name = interface_config.get('api_name', 'unknown')
    predefined_schema = SchemaManager.load_schema(interface_name)

    if predefined_schema:
        try:
            result_df = pl.DataFrame(data_list, schema=predefined_schema)
        except Exception as schema_error:
            logger.warning(f"使用预定义schema失败: {str(schema_error)}，回退到自动推断")
            result_df = pl.DataFrame(data_list, infer_schema_length=len(data_list))
    else:
        result_df = pl.DataFrame(data_list, infer_schema_length=len(data_list))

    # 仅记录警告，不去重（去重由 _remove_duplicates 处理）
    if detection_result['duplicates']:
        logger.warning(f"Detected {len(detection_result['duplicates'])} duplicate records for interface "
                      f"{interface_config.get('name', 'unknown')}, will be handled by _remove_duplicates")

    return result_df
```

**职责分离说明：**
- `_handle_primary_keys`: 负责主键完整性检查、重复检测、Schema应用
- `_remove_duplicates`: 负责实际的数据去重操作

---

### 2. downloader.py 改造

#### 2.1 `_get_stock_list_from_data_dir` 方法（行345）

**改造后：**
```python
from .dedup import DataDeduplicator

# 使用统一去重模块
deduplicator = DataDeduplicator({
    'primary_keys': ['ts_code'],
    'keep_strategy': 'last',
    'enable_stats': True
    # 注意：此处无 _update_time 字段，无需启用自动排序
})

deduplicated_df, stats = deduplicator.deduplicate(df)

stock_count = len(deduplicated_df)

# 统一日志格式
if stats.removed_rows > 0:
    logger.info(f"从本地获取了 {stock_count} 只股票 (去重前: {stats.input_rows}, "
                f"去重率: {stats.get_dedup_rate():.2f}%)")
else:
    logger.info(f"从本地获取了 {stock_count} 只股票")
```

#### 2.2 `_get_trade_calendar_from_data_dir` 方法（行429）

**改造后：**
```python
from .dedup import DataDeduplicator

# 必须去重，因为 Dataset 模式下可能有重复数据
filtered_df = df.filter(
    pl.all_horizontal(conditions)
)

# 使用统一去重模块
deduplicator = DataDeduplicator({
    'primary_keys': ['cal_date'],
    'keep_strategy': 'last',
    'enable_stats': True
})

deduplicated_df, stats = deduplicator.deduplicate(filtered_df)
result_df = deduplicated_df.sort('cal_date')

# 统一日志格式：使用 DEBUG 级别记录详细统计
if stats.removed_rows > 0:
    logger.debug(f"Trade calendar dedup: {stats.input_rows} -> {stats.output_rows} "
                 f"(rate: {stats.get_dedup_rate():.2f}%)")

if result_df.is_empty():
    return None

return result_df.to_dicts()
```

---

### 3. storage.py 改造

#### 3.1 `_read_interface_data` 方法（行373）

**改造后：**
```python
from .dedup import DataDeduplicator

if primary_keys and not df.is_empty():
    existing_keys = [k for k in primary_keys if k in df.columns]
    if existing_keys:
        # 使用统一去重模块，启用 _update_time 自动排序
        deduplicator = DataDeduplicator({
            'primary_keys': existing_keys,
            'keep_strategy': 'last',
            'enable_stats': True,
            'sort_by_update_time': '_update_time' in df.columns,
            'sort_ascending': True
        })

        df, stats = deduplicator.deduplicate(df)

        # 统一日志格式
        if stats.removed_rows > 0:
            logger.debug(f"Data read dedup: {stats.input_rows} -> {stats.output_rows} "
                         f"(rate: {stats.get_dedup_rate():.2f}%)")

return df
```

---

### 4. cache_warmer.py 改造

#### 4.1 `preload_trade_calendar` 方法（行39）

**改造后：**
```python
from .dedup import DataDeduplicator

# 使用统一去重模块
deduplicator = DataDeduplicator({
    'primary_keys': ['cal_date'],
    'keep_strategy': 'last',
    'enable_stats': True
})

deduplicated_df, stats = deduplicator.deduplicate(df)
sorted_df = deduplicated_df.sort('cal_date')

# 转换为字典列表
self.trade_calendar_cache = sorted_df.to_dicts()

# 统一日志格式
if stats.removed_rows > 0:
    logger.debug(f"Trade calendar preload dedup: {stats.input_rows} -> {stats.output_rows} "
                 f"(rate: {stats.get_dedup_rate():.2f}%)")

logger.info(f"预加载交易日历成功: {len(self.trade_calendar_cache)}条记录")
```

---

## 统一日志格式规范

### 日志级别使用规则

| 场景 | 日志级别 | 示例 |
|------|---------|------|
| 去重发现重复（>0条） | INFO | `Batch deduplication for daily: removed 5 duplicates...` |
| 无重复发现 | DEBUG | `No duplicates found within batch for daily` |
| 数据读取去重 | DEBUG | `Data read dedup: 1000 -> 998 (rate: 0.20%)` |
| 检测到重复（仅检测） | WARNING | `Detected 3 duplicate records for interface daily...` |
| 系统级操作 | INFO | `从本地获取了 5000 只股票` |

### 日志格式模板

```python
# 去重操作日志模板
"{operation} for {interface}: removed {removed} duplicates, keys={keys}, dedup_rate={rate:.2f}%"

# 无重复日志模板
"No duplicates found within batch for {interface}"

# 数据读取去重日志模板
"{context} dedup: {input_rows} -> {output_rows} (rate: {dedup_rate:.2f}%)"
```

---

## 改造优势

### 1. 统一的统计信息
所有去重操作都会返回详细的统计信息：
- `input_rows` - 输入行数
- `output_rows` - 输出行数
- `removed_rows` - 移除的行数
- `dedup_rate` - 去重率
- `processing_time_ms` - 处理时间

### 2. _update_time 自动处理
通过配置 `sort_by_update_time` 自动处理更新时间排序，避免重复代码：
```python
deduplicator = DataDeduplicator({
    'sort_by_update_time': '_update_time' in df.columns,  # 自动检测
    'sort_ascending': True
})
```

### 3. 职责分离
- `_handle_primary_keys`: 专注于检测和报告
- `_remove_duplicates`: 专注于实际去重

### 4. 统一日志格式
- 根据去重结果动态选择日志级别（INFO/DEBUG）
- 统一的格式模板，便于监控和排查

### 5. 更好的可维护性
- 集中管理去重逻辑
- 统一的错误处理
- 统一的配置接口

### 6. 无性能损失
底层仍然使用 Polars 的 `.unique()` 方法，性能与原来相同。

---

## 实施步骤

### Phase 1: DataDeduplicator 增强
1. 在 `dedup.py` 的 `DEFAULT_CONFIG` 中添加 `_update_time` 相关配置
2. 在 `_perform_deduplication` 方法中实现自动排序逻辑
3. 测试自动排序功能

### Phase 2: 逐文件改造
1. **改造 `processor.py`**
   - 修改 `_remove_duplicates` 方法，启用 `_update_time` 自动排序
   - 修改 `_handle_primary_keys` 方法，明确仅检测职责
   - 添加 `from .dedup import DataDeduplicator` 导入
   - 统一日志格式

2. **改造 `downloader.py`**
   - 修改 `_get_stock_list_from_data_dir` 方法
   - 修改 `_get_trade_calendar_from_data_dir` 方法
   - 添加 `from .dedup import DataDeduplicator` 导入
   - 统一日志格式

3. **改造 `storage.py`**
   - 修改 `_read_interface_data` 方法，启用 `_update_time` 自动排序
   - 添加 `from .dedup import DataDeduplicator` 导入
   - 统一日志格式

4. **改造 `cache_warmer.py`**
   - 修改 `preload_trade_calendar` 方法
   - 添加 `from .dedup import DataDeduplicator` 导入
   - 统一日志格式

### Phase 3: 测试验证

#### 3.1 单元测试

**测试文件位置**: `test/test_unified_deduplication.py`

```python
#!/usr/bin/env python
"""
统一去重功能重构测试
测试 DataDeduplicator 及 processor、downloader、storage、cache_warmer 中的去重逻辑
"""

import pytest
import polars as pl
import tempfile
import os
from datetime import datetime
from app4.core.dedup import DataDeduplicator, DedupStats, deduplicate_against_existing
from app4.core.processor import DataProcessor
from app4.core.storage import StorageManager


class TestDataDeduplicator:
    """测试 DataDeduplicator 核心功能"""
    
    def test_deduplicate_with_update_time_auto_sort(self):
        """测试带 _update_time 字段的自动排序去重"""
        # 创建测试数据：相同主键，不同更新时间
        df = pl.DataFrame({
            'ts_code': ['000001.SZ', '000001.SZ', '000002.SZ'],
            'trade_date': ['20230101', '20230101', '20230101'],
            'close': [10.0, 10.5, 20.0],
            '_update_time': [
                datetime(2023, 1, 1, 10, 0, 0),
                datetime(2023, 1, 1, 11, 0, 0),  # 更新的记录
                datetime(2023, 1, 1, 10, 0, 0)
            ]
        })
        
        deduplicator = DataDeduplicator({
            'primary_keys': ['ts_code', 'trade_date'],
            'keep_strategy': 'last',
            'enable_stats': True,
            'sort_by_update_time': True,
            'sort_ascending': True
        })
        
        result_df, stats = deduplicator.deduplicate(df)
        
        # 验证去重结果：保留更新的记录
        assert len(result_df) == 2
        assert stats.input_rows == 3
        assert stats.output_rows == 2
        assert stats.removed_rows == 1
        
        # 验证保留了更新时间的记录（close=10.5）
        record = result_df.filter(
            (pl.col('ts_code') == '000001.SZ') & 
            (pl.col('trade_date') == '20230101')
        )
        assert len(record) == 1
        assert record['close'][0] == 10.5
    
    def test_deduplicate_without_update_time(self):
        """测试无 _update_time 字段的标准去重"""
        df = pl.DataFrame({
            'ts_code': ['000001.SZ', '000001.SZ', '000002.SZ'],
            'trade_date': ['20230101', '20230101', '20230101'],
            'close': [10.0, 10.5, 20.0]
        })
        
        deduplicator = DataDeduplicator({
            'primary_keys': ['ts_code', 'trade_date'],
            'keep_strategy': 'last',
            'enable_stats': True
        })
        
        result_df, stats = deduplicator.deduplicate(df)
        
        assert len(result_df) == 2
        assert stats.input_rows == 3
        assert stats.output_rows == 2
        assert stats.removed_rows == 1
        
        # 验证去重率计算
        assert stats.get_dedup_rate() == 33.33  # 1/3 * 100
    
    def test_deduplicate_empty_dataframe(self):
        """测试空 DataFrame 的处理"""
        df = pl.DataFrame({
            'ts_code': [],
            'trade_date': [],
            'close': []
        })
        
        deduplicator = DataDeduplicator({
            'primary_keys': ['ts_code', 'trade_date'],
            'keep_strategy': 'last'
        })
        
        result_df, stats = deduplicator.deduplicate(df)
        
        assert len(result_df) == 0
        assert stats.input_rows == 0
        assert stats.output_rows == 0
        assert stats.removed_rows == 0
    
    def test_deduplicate_no_duplicates(self):
        """测试无重复数据的场景"""
        df = pl.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ', '000003.SZ'],
            'trade_date': ['20230101', '20230102', '20230103'],
            'close': [10.0, 20.0, 30.0]
        })
        
        deduplicator = DataDeduplicator({
            'primary_keys': ['ts_code', 'trade_date'],
            'keep_strategy': 'last',
            'enable_stats': True
        })
        
        result_df, stats = deduplicator.deduplicate(df)
        
        assert len(result_df) == 3
        assert stats.input_rows == 3
        assert stats.output_rows == 3
        assert stats.removed_rows == 0
        assert stats.get_dedup_rate() == 0.0
    
    def test_deduplicate_missing_primary_key(self):
        """测试缺少主键字段的处理"""
        df = pl.DataFrame({
            'ts_code': ['000001.SZ', '000001.SZ'],
            'close': [10.0, 10.5]
            # 缺少 'trade_date' 主键
        })
        
        deduplicator = DataDeduplicator({
            'primary_keys': ['ts_code', 'trade_date'],
            'keep_strategy': 'last',
            'enable_stats': True
        })
        
        result_df, stats = deduplicator.deduplicate(df)
        
        # 应该返回原始数据并记录错误
        assert len(result_df) == 2
        assert len(stats.errors) > 0
        assert 'trade_date' in stats.errors[0]
    
    def test_deduplicate_different_strategies(self):
        """测试不同 keep_strategy 的效果"""
        df = pl.DataFrame({
            'ts_code': ['000001.SZ', '000001.SZ', '000001.SZ'],
            'trade_date': ['20230101', '20230101', '20230101'],
            'close': [10.0, 11.0, 12.0]
        })
        
        # 测试 keep='first'
        dedup_first = DataDeduplicator({
            'primary_keys': ['ts_code', 'trade_date'],
            'keep_strategy': 'first'
        })
        result_first, _ = dedup_first.deduplicate(df)
        assert result_first['close'][0] == 10.0
        
        # 测试 keep='last'
        dedup_last = DataDeduplicator({
            'primary_keys': ['ts_code', 'trade_date'],
            'keep_strategy': 'last'
        })
        result_last, _ = dedup_last.deduplicate(df)
        assert result_last['close'][0] == 12.0


class TestProcessorDeduplication:
    """测试 Processor 中的去重逻辑"""
    
    def test_remove_duplicates_with_update_time(self):
        """测试 processor._remove_duplicates 带 _update_time"""
        processor = DataProcessor()
        
        df = pl.DataFrame({
            'ts_code': ['000001.SZ', '000001.SZ'],
            'trade_date': ['20230101', '20230101'],
            'close': [10.0, 11.0],
            '_update_time': [
                datetime(2023, 1, 1, 10, 0, 0),
                datetime(2023, 1, 1, 11, 0, 0)
            ]
        })
        
        interface_config = {
            'api_name': 'daily',
            'output': {
                'primary_key': ['ts_code', 'trade_date'],
                'sort_by': ['trade_date']
            }
        }
        
        result_df = processor._remove_duplicates(df, interface_config)
        
        assert len(result_df) == 1
        assert result_df['close'][0] == 11.0  # 保留最新记录
    
    def test_remove_duplicates_without_update_time(self):
        """测试 processor._remove_duplicates 无 _update_time"""
        processor = DataProcessor()
        
        df = pl.DataFrame({
            'ts_code': ['000001.SZ', '000001.SZ', '000002.SZ'],
            'trade_date': ['20230101', '20230101', '20230101'],
            'close': [10.0, 11.0, 20.0]
        })
        
        interface_config = {
            'api_name': 'daily',
            'output': {
                'primary_key': ['ts_code', 'trade_date']
            }
        }
        
        result_df = processor._remove_duplicates(df, interface_config)
        
        assert len(result_df) == 2
    
    def test_handle_primary_keys_detection_only(self):
        """测试 _handle_primary_keys 仅检测职责，不执行去重"""
        processor = DataProcessor()
        
        df = pl.DataFrame({
            'ts_code': ['000001.SZ', '000001.SZ', '000002.SZ'],
            'trade_date': ['20230101', '20230101', '20230102'],
            'close': [10.0, 11.0, 20.0]
        })
        
        interface_config = {
            'api_name': 'daily',
            'output': {
                'primary_key': ['ts_code', 'trade_date']
            }
        }
        
        result_df = processor._handle_primary_keys(df, interface_config)
        
        # _handle_primary_keys 应该保留所有记录（仅检测）
        assert len(result_df) == 3


class TestStorageDeduplication:
    """测试 Storage 中的去重逻辑"""
    
    def test_read_interface_data_deduplication(self):
        """测试 storage._read_interface_data 去重"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = StorageManager(storage_dir=temp_dir)
            
            # 创建测试数据并保存
            df = pl.DataFrame({
                'ts_code': ['000001.SZ', '000001.SZ'],
                'trade_date': ['20230101', '20230101'],
                'close': [10.0, 11.0],
                '_update_time': [
                    datetime(2023, 1, 1, 10, 0, 0),
                    datetime(2023, 1, 1, 11, 0, 0)
                ]
            })
            
            interface_dir = os.path.join(temp_dir, 'daily')
            os.makedirs(interface_dir, exist_ok=True)
            df.write_parquet(os.path.join(interface_dir, 'test.parquet'))
            
            # 读取并去重
            result_df = storage._read_interface_data('daily', columns=['ts_code', 'trade_date', 'close'])
            
            # 应该根据主键去重
            assert len(result_df) == 1


class TestDeduplicationIntegration:
    """集成测试"""
    
    def test_full_pipeline_with_duplicates(self):
        """测试完整数据处理流程中的去重"""
        processor = DataProcessor()
        
        # 模拟从API获取的重复数据
        raw_data = [
            {'ts_code': '000001.SZ', 'trade_date': '20230101', 'close': 10.0, '_update_time': '2023-01-01 10:00:00'},
            {'ts_code': '000001.SZ', 'trade_date': '20230101', 'close': 10.5, '_update_time': '2023-01-01 11:00:00'},
            {'ts_code': '000002.SZ', 'trade_date': '20230101', 'close': 20.0, '_update_time': '2023-01-01 10:00:00'}
        ]
        
        interface_config = {
            'api_name': 'daily',
            'output': {
                'primary_key': ['ts_code', 'trade_date']
            }
        }
        
        # 使用 process_data 完整流程
        result_df = processor.process_data(raw_data, interface_config)
        
        # 验证最终去重结果
        assert len(result_df) == 2
        
        # 验证保留的是最新记录
        record = result_df.filter(
            (pl.col('ts_code') == '000001.SZ') & 
            (pl.col('trade_date') == '20230101')
        )
        assert len(record) == 1


class TestDeduplicationBackwardCompatibility:
    """向后兼容性测试"""
    
    def test_keep_last_behavior_unchanged(self):
        """验证 keep='last' 行为与改造前一致"""
        df = pl.DataFrame({
            'ts_code': ['000001.SZ', '000001.SZ', '000001.SZ'],
            'trade_date': ['20230101', '20230101', '20230101'],
            'close': [10.0, 11.0, 12.0]
        })
        
        # 改造前的方式
        old_result = df.unique(subset=['ts_code', 'trade_date'], keep='last')
        
        # 改造后的方式
        deduplicator = DataDeduplicator({
            'primary_keys': ['ts_code', 'trade_date'],
            'keep_strategy': 'last'
        })
        new_result, _ = deduplicator.deduplicate(df)
        
        # 验证结果一致
        assert len(old_result) == len(new_result)
        assert old_result['close'][0] == new_result['close'][0]
    
    def test_deduplicate_against_existing_function(self):
        """测试 deduplicate_against_existing 函数"""
        with tempfile.TemporaryDirectory() as temp_dir:
            existing_file = os.path.join(temp_dir, 'existing.parquet')
            
            # 创建已存在的数据
            existing_df = pl.DataFrame({
                'ts_code': ['000001.SZ', '000002.SZ'],
                'trade_date': ['20230101', '20230101'],
                'close': [10.0, 20.0]
            })
            existing_df.write_parquet(existing_file)
            
            # 新数据包含重复和新增
            new_df = pl.DataFrame({
                'ts_code': ['000001.SZ', '000003.SZ'],
                'trade_date': ['20230101', '20230101'],
                'close': [11.0, 30.0]
            })
            
            result_df, stats = deduplicate_against_existing(
                new_df, 
                existing_file,
                primary_keys=['ts_code', 'trade_date']
            )
            
            # 应该只保留新增的记录
            assert len(result_df) == 1
            assert result_df['ts_code'][0] == '000003.SZ'
            assert stats.removed_rows == 1


class TestDeduplicationPerformance:
    """性能测试"""
    
    @pytest.mark.slow
    def test_large_dataset_performance(self):
        """测试大数据集的去重性能"""
        import time
        
        # 创建100万行测试数据，其中10%是重复的
        n_rows = 1000000
        data = {
            'ts_code': [f'{i:06d}.SZ' for i in range(n_rows)],
            'trade_date': ['20230101'] * n_rows,
            'close': [float(i) for i in range(n_rows)]
        }
        
        # 添加重复数据
        for i in range(0, n_rows, 10):
            data['ts_code'][i] = '000001.SZ'
        
        df = pl.DataFrame(data)
        
        deduplicator = DataDeduplicator({
            'primary_keys': ['ts_code', 'trade_date'],
            'keep_strategy': 'last',
            'enable_stats': True
        })
        
        start_time = time.time()
        result_df, stats = deduplicator.deduplicate(df)
        elapsed_time = time.time() - start_time
        
        # 验证性能：100万行数据应在5秒内完成
        assert elapsed_time < 5.0
        assert stats.input_rows == n_rows
        assert stats.output_rows < n_rows
        
        print(f"Performance test: {n_rows} rows deduplicated in {elapsed_time:.2f}s")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
```

#### 3.2 边界测试

**测试文件**: `test/test_deduplication_edge_cases.py`

```python
#!/usr/bin/env python
"""
去重功能边界测试
"""

import pytest
import polars as pl
from app4.core.dedup import DataDeduplicator


class TestEdgeCases:
    """边界情况测试"""
    
    def test_single_row_dataframe(self):
        """测试单行数据"""
        df = pl.DataFrame({
            'ts_code': ['000001.SZ'],
            'trade_date': ['20230101'],
            'close': [10.0]
        })
        
        deduplicator = DataDeduplicator({
            'primary_keys': ['ts_code', 'trade_date'],
            'keep_strategy': 'last'
        })
        
        result_df, stats = deduplicator.deduplicate(df)
        
        assert len(result_df) == 1
        assert stats.removed_rows == 0
    
    def test_all_duplicates(self):
        """测试全部行都是重复的情况"""
        df = pl.DataFrame({
            'ts_code': ['000001.SZ'] * 100,
            'trade_date': ['20230101'] * 100,
            'close': [float(i) for i in range(100)]
        })
        
        deduplicator = DataDeduplicator({
            'primary_keys': ['ts_code', 'trade_date'],
            'keep_strategy': 'last'
        })
        
        result_df, stats = deduplicator.deduplicate(df)
        
        assert len(result_df) == 1
        assert stats.removed_rows == 99
        assert stats.get_dedup_rate() == 99.0
    
    def test_null_primary_key_values(self):
        """测试主键包含空值的情况"""
        df = pl.DataFrame({
            'ts_code': ['000001.SZ', None, '000001.SZ'],
            'trade_date': ['20230101', '20230102', '20230101'],
            'close': [10.0, 20.0, 11.0]
        })
        
        deduplicator = DataDeduplicator({
            'primary_keys': ['ts_code', 'trade_date'],
            'keep_strategy': 'last'
        })
        
        result_df, stats = deduplicator.deduplicate(df)
        
        # 空值应该被视为有效的不同值
        assert len(result_df) >= 2
    
    def test_unicode_and_special_chars(self):
        """测试包含Unicode和特殊字符的数据"""
        df = pl.DataFrame({
            'ts_code': ['000001.SZ', '000001.SZ', '000001.中文'],
            'name': ['股票A', '股票A', '股票B'],
            'value': [1.0, 2.0, 3.0]
        })
        
        deduplicator = DataDeduplicator({
            'primary_keys': ['ts_code'],
            'keep_strategy': 'last'
        })
        
        result_df, stats = deduplicator.deduplicate(df)
        
        assert len(result_df) == 2
        assert '000001.中文' in result_df['ts_code'].to_list()
    
    def test_various_data_types(self):
        """测试不同数据类型的去重"""
        df = pl.DataFrame({
            'string_col': ['A', 'A', 'B'],
            'int_col': [1, 1, 2],
            'float_col': [1.5, 1.5, 2.5],
            'bool_col': [True, True, False]
        })
        
        deduplicator = DataDeduplicator({
            'primary_keys': ['string_col', 'int_col'],
            'keep_strategy': 'last'
        })
        
        result_df, stats = deduplicator.deduplicate(df)
        
        assert len(result_df) == 2
        assert stats.removed_rows == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
```

#### 3.3 集成测试

**测试文件**: `test/test_deduplication_integration.py`

```python
#!/usr/bin/env python
"""
去重功能集成测试
测试完整数据下载和存储流程中的去重
"""

import pytest
import polars as pl
import tempfile
import os
from datetime import datetime
from app4.core.config_loader import ConfigLoader
from app4.core.downloader import GenericDownloader
from app4.core.storage import StorageManager
from app4.core.processor import DataProcessor
from app4.core.cache_warmer import CacheWarmer


class TestDownloaderDeduplication:
    """测试 Downloader 中的去重"""
    
    def test_get_stock_list_deduplication(self):
        """测试股票列表获取时的去重"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建模拟的股票基础数据
            os.makedirs(os.path.join(temp_dir, 'stock_basic'), exist_ok=True)
            
            df = pl.DataFrame({
                'ts_code': ['000001.SZ', '000001.SZ', '000002.SZ'],  # 有重复
                'symbol': ['000001', '000001', '000002'],
                'name': ['平安银行', '平安银行', '万科A'],
                'list_status': ['L', 'L', 'L']
            })
            df.write_parquet(os.path.join(temp_dir, 'stock_basic', 'data.parquet'))
            
            config_loader = ConfigLoader('app4/config')
            downloader = GenericDownloader(config_loader)
            
            # 通过 downloader 获取股票列表
            stock_list = downloader._get_stock_list_from_data_dir()
            
            # 验证去重：应该有2只股票
            assert stock_list is not None
            assert len(stock_list) == 2
            ts_codes = [s['ts_code'] for s in stock_list]
            assert '000001.SZ' in ts_codes
            assert '000002.SZ' in ts_codes


class TestCacheWarmerDeduplication:
    """测试 CacheWarmer 中的去重"""
    
    def test_preload_trade_calendar_deduplication(self):
        """测试交易日历预加载时的去重"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建模拟的交易日历数据
            os.makedirs(os.path.join(temp_dir, 'trade_cal'), exist_ok=True)
            
            df = pl.DataFrame({
                'cal_date': ['20230101', '20230101', '20230102', '20230103'],  # 有重复
                'is_open': [1, 1, 1, 1],
                'exchange': ['SSE', 'SSE', 'SSE', 'SSE']
            })
            df.write_parquet(os.path.join(temp_dir, 'trade_cal', 'data.parquet'))
            
            cache_warmer = CacheWarmer(temp_dir)
            calendar = cache_warmer.preload_trade_calendar()
            
            # 验证去重：应该有3个交易日
            assert calendar is not None
            assert len(calendar) == 3
            dates = [c['cal_date'] for c in calendar]
            assert dates == ['20230101', '20230102', '20230103']  # 已排序


class TestEndToEndDeduplication:
    """端到端测试"""
    
    def test_full_download_and_storage_with_duplicates(self):
        """测试完整下载和存储流程中的去重"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建组件
            storage = StorageManager(storage_dir=temp_dir)
            storage.start_writer()
            
            processor = DataProcessor()
            
            # 模拟API返回的重复数据
            api_data = [
                {'ts_code': '000001.SZ', 'trade_date': '20230101', 'close': 10.0, '_update_time': '2023-01-01 10:00:00'},
                {'ts_code': '000001.SZ', 'trade_date': '20230101', 'close': 10.5, '_update_time': '2023-01-01 11:00:00'},
                {'ts_code': '000002.SZ', 'trade_date': '20230101', 'close': 20.0, '_update_time': '2023-01-01 10:00:00'}
            ]
            
            interface_config = {
                'api_name': 'daily',
                'output': {
                    'primary_key': ['ts_code', 'trade_date']
                }
            }
            
            # 处理数据
            df = processor.process_data(api_data, interface_config)
            
            # 验证去重结果
            assert len(df) == 2
            
            # 保存数据
            # storage.save_data('daily', df)  # 假设有此方法
            
            storage.stop_writer()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
```

#### 3.4 向后兼容性测试

**测试文件**: `test/test_deduplication_compatibility.py`

```python
#!/usr/bin/env python
"""
去重功能向后兼容性测试
验证改造前后的行为一致性
"""

import pytest
import polars as pl
from app4.core.dedup import DataDeduplicator


class TestBackwardCompatibility:
    """向后兼容性测试"""
    
    def test_old_vs_new_api_compatibility(self):
        """测试旧API与新API的兼容性"""
        df = pl.DataFrame({
            'ts_code': ['000001.SZ', '000001.SZ', '000002.SZ'],
            'trade_date': ['20230101', '20230101', '20230101'],
            'close': [10.0, 11.0, 20.0]
        })
        
        # 模拟旧的直接调用方式
        old_way_result = df.unique(subset=['ts_code', 'trade_date'], keep='last')
        
        # 新的统一去重方式
        deduplicator = DataDeduplicator({
            'primary_keys': ['ts_code', 'trade_date'],
            'keep_strategy': 'last'
        })
        new_way_result, stats = deduplicator.deduplicate(df)
        
        # 验证结果完全一致
        assert old_way_result.shape == new_way_result.shape
        assert old_way_result['close'].to_list() == new_way_result['close'].to_list()
    
    def test_default_config_behavior(self):
        """测试默认配置行为"""
        df = pl.DataFrame({
            'ts_code': ['000001.SZ', '000001.SZ'],
            'trade_date': ['20230101', '20230101'],
            'close': [10.0, 11.0]
        })
        
        # 使用默认配置
        deduplicator = DataDeduplicator()
        result_df, stats = deduplicator.deduplicate(df)
        
        # 默认应该使用配置中的主键和策略
        assert len(result_df) == 1
        assert stats.input_rows == 2
        assert stats.output_rows == 1
    
    def test_config_override_behavior(self):
        """测试配置覆盖行为"""
        df = pl.DataFrame({
            'ts_code': ['000001.SZ', '000001.SZ', '000002.SZ'],
            'trade_date': ['20230101', '20230101', '20230101'],
            'close': [10.0, 11.0, 20.0]
        })
        
        # 初始化时配置
        deduplicator = DataDeduplicator({
            'primary_keys': ['ts_code'],
            'keep_strategy': 'first'
        })
        
        # 调用时覆盖主键
        result_df, stats = deduplicator.deduplicate(
            df, 
            primary_keys=['ts_code', 'trade_date']
        )
        
        # 应该使用调用时的主键
        assert len(result_df) == 2  # 按ts_code+trade_date去重
    
    def test_error_handling_compatibility(self):
        """测试错误处理兼容性"""
        df = pl.DataFrame({
            'ts_code': ['000001.SZ'],
            'close': [10.0]
            # 缺少 trade_date 主键
        })
        
        deduplicator = DataDeduplicator({
            'primary_keys': ['ts_code', 'trade_date'],
            'enable_stats': True
        })
        
        # 应该优雅处理，返回原始数据
        result_df, stats = deduplicator.deduplicate(df)
        
        assert len(result_df) == 1  # 返回原始数据
        assert len(stats.errors) > 0  # 记录错误
        assert 'trade_date' in stats.errors[0]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
```

### 测试执行命令

```bash
# 运行所有去重测试
pytest test/test_unified_deduplication.py -v

# 运行边界测试
pytest test/test_deduplication_edge_cases.py -v

# 运行集成测试
pytest test/test_deduplication_integration.py -v

# 运行兼容性测试
pytest test/test_deduplication_compatibility.py -v

# 运行性能测试（较慢）
pytest test/test_unified_deduplication.py::TestDeduplicationPerformance -v --slow

# 运行所有去重相关测试
pytest test/test_*deduplication*.py -v
```

### Phase 4: 文档更新
1. 在 `dedup.py` 顶部添加详细的使用示例
2. 更新 CLAUDE.md 中关于去重的说明
3. 记录各方法的职责分离说明

---

## 注意事项

### 1. 向后兼容性
- **行为兼容**：所有改造保持原有的 `keep='last'` 行为
- **日志兼容**：保留原有的关键日志信息，仅增强统计信息
- **配置兼容**：`DataDeduplicator` 的新配置项有默认值，不影响现有调用

### 2. 错误处理
- `dedup.py` 已有完善的错误处理机制，会返回原始 DataFrame 并记录错误
- 各调用方无需额外错误处理

### 3. 性能考虑
- `_update_time` 自动排序仅在配置启用时执行
- 排序和去重仍然是 Polars 原生操作，无额外性能损失
- 无需实例化缓存（过早优化），每次调用创建新实例即可

### 4. 职责分离
- `_handle_primary_keys` **不**应执行实际去重，避免与 `_remove_duplicates` 重复
- 如需修改此行为，需同步调整 `processor.py` 中的调用顺序

---

## 预期效果

改造完成后：
- ✅ 所有去重逻辑统一使用 `dedup.py` 模块
- ✅ `_update_time` 排序逻辑集中管理，消除重复代码
- ✅ 获得详细的去重统计信息（input/output/removed/dedup_rate）
- ✅ 日志输出统一格式，级别选择合理（INFO/DEBUG）
- ✅ `_handle_primary_keys` 和 `_remove_duplicates` 职责清晰分离
- ✅ 代码可维护性显著提升
- ✅ 无性能损失
- ✅ 向后完全兼容

---

## 总结

本方案将分散在 4 个文件中的去重逻辑统一调用 `core/dedup.py` 模块，并特别强化了 `_update_time` 自动处理能力，实现了：

1. **配置增强**：支持 `_update_time` 自动排序配置
2. **职责分离**：`_handle_primary_keys` 仅检测，`_remove_duplicates` 执行去重
3. **日志统一**：制定统一的日志格式和级别使用规范
4. **统计完善**：所有去重操作返回详细的统计信息
5. **完全兼容**：保持向后兼容，无行为变更风险

改造后，所有去重操作都将获得一致的统计信息和日志输出，便于监控、排查和优化。
