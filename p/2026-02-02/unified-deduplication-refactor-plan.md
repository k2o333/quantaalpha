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
对每个改造的方法添加单元测试：
```python
def test_remove_duplicates_with_update_time():
    """测试带 _update_time 的去重"""
    pass

def test_remove_duplicates_without_update_time():
    """测试无 _update_time 的去重"""
    pass

def test_handle_primary_keys_detection_only():
    """测试 _handle_primary_keys 仅检测职责"""
    pass

def test_deduplicator_auto_sort():
    """测试 DataDeduplicator 自动排序功能"""
    pass
```

#### 3.2 边界测试
- 空 DataFrame 处理
- 大量数据（>100万行）性能测试
- 无主键字段场景
- 无 _update_time 字段场景

#### 3.3 集成测试
- 运行完整的数据下载流程
- 验证去重统计信息正确输出
- 验证日志格式统一

#### 3.4 向后兼容性测试
- 对比改造前后的输出结果一致性
- 验证日志级别符合预期

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
