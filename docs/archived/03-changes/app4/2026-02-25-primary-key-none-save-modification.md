---
doc_type: change
module: app4
status: archived
owner: quan
created: 2026-02-25
updated: 2026-02-25
summary: Primary Key 为 None 时保存逻辑修改方案
---

# Primary Key 为 None 时保存逻辑修改方案

## 1. 需求概述

### 当前行为
- 在下载数据后保存数据时，会检查 primary key 是否为 `None`
- 如果 primary key 是 `None`，则该条数据**不保存**（被过滤掉）

### 期望行为
- 如果 primary key 是 `None`，则**仍然保存**这条数据
- 去重逻辑保持不变：仍然需要所有 primary key 字段都相同才判定为重复（包括 `None` 的情况）

---

## 2. 当前代码分析

### 2.1 数据处理流程

数据从下载到保存的完整流程：

```
下载原始数据
    ↓
process_data() [processor.py]
    ↓
1. SchemaManager.create_dataframe_safe() - 创建DataFrame
    ↓
2. _apply_type_conversions() - 类型转换
    ↓
3. _filter_primary_key_nulls() - 【关键】过滤主键为空的记录
    ↓
4. _handle_primary_keys() - 处理主键（内部去重检测）
    ↓
5. _remove_duplicates() - 批次内去重
    ↓
6. _clean_data() - 数据清洗
    ↓
save_data() [storage.py]
    ↓
与历史数据去重
    ↓
写入parquet文件
```

### 2.2 关键代码位置

#### 2.2.1 `_filter_primary_key_nulls` 方法 (processor.py:140-163)

**位置**: `/home/quan/testdata/aspipe_v4/app4/core/processor.py` 第140-163行

```python
def _filter_primary_key_nulls(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> pl.DataFrame:
    """过滤主键中的空值 - 这一步必须在应用派生字段后执行"""
    output_config = interface_config.get('output', {})
    primary_keys = output_config.get('primary_key', [])

    # 过滤掉主键字段中存在空值的行
    if primary_keys and not df.is_empty():
        # 构建过滤条件：所有主键字段都不为空
        conditions = []
        existing_keys = [key for key in primary_keys if key in df.columns]

        for key in existing_keys:
            conditions.append(pl.col(key).is_not_null())  # 【关键】要求主键不为空

        if conditions:
            # 使用所有主键字段都不为空的条件进行过滤
            filter_expr = pl.all_horizontal(conditions)
            original_count = len(df)
            df = df.filter(filter_expr)  # 【关键】过滤掉主键为空的记录
            filtered_count = len(df)

            if original_count != filtered_count:
                logger.info(f"Filtered {original_count - filtered_count} records with null primary keys "
                           f"for interface {interface_config.get('api_name', 'unknown')}, "
                           f"kept {filtered_count}/{original_count}")

    return df
```

**核心逻辑**:
- 第152行: `conditions.append(pl.col(key).is_not_null())` - 构建条件要求主键不为空
- 第157行: `filter_expr = pl.all_horizontal(conditions)` - 所有主键字段都必须不为空
- 第159行: `df = df.filter(filter_expr)` - **执行过滤，移除主键为空的记录**

#### 2.2.2 调用位置 (processor.py:78)

```python
# 关键步骤：在应用派生字段后，过滤主键中的空值
df = self._filter_primary_key_nulls(df, interface_config)
```

### 2.3 去重逻辑分析

#### 2.3.1 批次内去重 `_remove_duplicates` (processor.py:207-236)

```python
def _remove_duplicates(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> pl.DataFrame:
    """批次内去重逻辑 - 根据主键去重，保留最后记录"""
    output_config = interface_config.get('output', {})
    primary_keys = output_config.get('primary_key', [])

    existing_keys = [key for key in primary_keys if key in df.columns]

    if existing_keys:
        # 按主键去重，保留最后一条记录
        df = df.unique(subset=existing_keys, keep='last')  # 【关键】使用Polars的unique方法

    return df
```

**Polars `unique` 方法的行为**:
- `df.unique(subset=primary_keys, keep='last')` 
- 当 primary key 包含 `None` 值时，Polars 会将 `None` 视为一个有效的值
- 多条 primary key 都为 `None` 的记录会被视为重复，只保留最后一条

#### 2.3.2 与历史数据去重 `deduplicate_against_existing` (dedup.py:240-320)

```python
def deduplicate_against_existing(
    new_data: pl.DataFrame,
    existing_data_path: str,
    primary_keys: Optional[List[str]] = None,
    ...
) -> Tuple[pl.DataFrame, DedupStats]:
    # ...
    # 执行 anti-join 来过滤已存在的记录
    joined = new_data_aligned.join(
        existing_df_aligned.select(keys_to_use).unique(),
        on=keys_to_use,
        how='anti'  # 只保留新数据中不存在于历史数据的记录
    )
    # ...
```

**Join 操作对 None 的处理**:
- Polars 的 join 操作默认会将 `None` 值视为可匹配的值
- 如果新数据和历史数据的 primary key 都是 `None`，它们会被匹配并去重

### 2.4 日志证据

从实际运行日志可以看到大量被过滤的记录：

```
2026-03-01 13:42:00,119 - core.processor - INFO - Filtered 10148 records with null primary keys for interface suspend_d, kept 105/10253
2026-02-28 15:30:39,276 - core.processor - INFO - Filtered 14537 records with null primary keys for interface daily_basic, kept 23751/38288
2026-02-28 15:34:16,444 - core.processor - INFO - Filtered 1587 records with null primary keys for interface report_rc, kept 0/1587
```

---

## 3. 修改方案

### 3.1 方案概述

**核心修改**: 移除或修改 `_filter_primary_key_nulls` 方法，不再过滤 primary key 为 `None` 的记录。

### 3.2 具体修改

#### 方案A：完全移除过滤（推荐）

**修改文件**: `app4/core/processor.py`

**修改1**: 删除或注释掉 `_filter_primary_key_nulls` 的调用

```python
# 原代码 (processor.py:78)
df = self._filter_primary_key_nulls(df, interface_config)

# 修改后
# df = self._filter_primary_key_nulls(df, interface_config)  # 不再过滤主键为空的记录
```

**修改2**: 修改 `_filter_primary_key_nulls` 方法，使其不再过滤，只记录日志

```python
def _filter_primary_key_nulls(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> pl.DataFrame:
    """记录主键为空的记录数量，但不再过滤"""
    output_config = interface_config.get('output', {})
    primary_keys = output_config.get('primary_key', [])

    if primary_keys and not df.is_empty():
        existing_keys = [key for key in primary_keys if key in df.columns]

        if existing_keys:
            # 统计主键为空的记录数量
            # 注意：使用 pl.any_horizontal 检测任意主键为空，与原过滤逻辑一致
            # 原逻辑：pl.all_horizontal(is_not_null) = 所有主键都不为空才保留
            # 统计逻辑：pl.any_horizontal(is_null) = 任意主键为空的数量
            null_conditions = [pl.col(key).is_null() for key in existing_keys]
            null_expr = pl.any_horizontal(null_conditions)  # 任意主键为空
            null_count = df.filter(null_expr).height

            if null_count > 0:
                logger.info(f"Found {null_count} records with null primary keys "
                           f"for interface {interface_config.get('api_name', 'unknown')}, "
                           f"keeping all records (including null primary keys)")

    return df  # 返回原始DataFrame，不做过滤
```

**修改3（必须）**: 修改 `validate_data` 方法，允许 primary key 为 None

**位置**: `app4/core/processor.py` 第300-360行

```python
def validate_data(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> Dict[str, Any]:
    """验证数据质量 - 允许 primary key 为 None"""
    output_config = interface_config.get('output', {})
    
    validation_result = {
        'total_records': len(df),
        'total_columns': len(df.columns),
        'missing_required_fields': [],
        'type_mismatches': [],
        'duplicate_records': 0
    }

    # 【修改】不再将 primary key 缺失值视为验证失败
    # 原逻辑会检查 primary key 是否有缺失值，现在移除此检查
    # 如果需要记录统计信息，可以只记录但不影响 valid 状态
    primary_keys = output_config.get('primary_key', []) or []
    for column_name in primary_keys:
        if column_name in df.columns:
            missing_count = df[column_name].null_count()
            if missing_count > 0:
                # 【修改】只记录警告日志，不添加到 missing_required_fields
                logger.debug(f"Field {column_name} has {missing_count} null values for {interface_config.get('api_name', 'unknown')}")

    # ... 其余验证逻辑保持不变 ...

    # 【修改】valid 判断不再依赖 missing_required_fields
    validation_result['valid'] = (
        len(validation_result['type_mismatches']) == 0
        # 移除：and len(validation_result['missing_required_fields']) == 0
    )

    return validation_result
```

**或者更简洁的方式**：添加配置选项控制是否允许 primary key 为 None

```python
def validate_data(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> Dict[str, Any]:
    """验证数据质量"""
    output_config = interface_config.get('output', {})
    allow_null_pk = output_config.get('allow_null_primary_key', True)  # 默认允许
    
    # ...
    
    primary_keys = output_config.get('primary_key', []) or []
    for column_name in primary_keys:
        if column_name in df.columns:
            missing_count = df[column_name].null_count()
            if missing_count > 0 and not allow_null_pk:
                # 只有在配置不允许时才添加到 missing_required_fields
                validation_result['missing_required_fields'].append({
                    'field': column_name,
                    'missing_count': missing_count
                })
```

#### 方案B：添加配置选项控制行为

在接口配置中添加选项，允许用户选择是否过滤主键为空的记录：

**YAML配置示例**:
```yaml
output:
  primary_key: ["ts_code", "trade_date"]
  filter_null_pk: false  # 新增配置项，默认为false（不过滤）
```

**代码修改**:
```python
def _filter_primary_key_nulls(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> pl.DataFrame:
    """根据配置决定是否过滤主键为空的记录"""
    output_config = interface_config.get('output', {})
    primary_keys = output_config.get('primary_key', [])
    filter_null_pk = output_config.get('filter_null_pk', False)  # 默认不过滤

    if not filter_null_pk:
        # 不过滤，直接返回
        return df

    # 原有过滤逻辑...
```

### 3.3 去重逻辑验证

修改后，去重逻辑需要验证以下几点：

#### 3.3.1 Polars `unique` 对 None 的处理

```python
import polars as pl

# 测试数据
df = pl.DataFrame({
    'ts_code': ['000001.SZ', None, None, '000002.SZ'],
    'trade_date': ['20230101', '20230101', '20230101', '20230101'],
    'value': [1, 2, 3, 4]
})

# 按 ['ts_code', 'trade_date'] 去重
result = df.unique(subset=['ts_code', 'trade_date'], keep='last')
print(result)
```

**预期结果**: 
- `ts_code=None, trade_date='20230101'` 的记录会被视为一组
- 只保留最后一条（value=3）

#### 3.3.2 Polars `join` 对 None 的处理

```python
import polars as pl

df1 = pl.DataFrame({
    'ts_code': ['000001.SZ', None],
    'trade_date': ['20230101', '20230101'],
}).with_row_index('id1')

df2 = pl.DataFrame({
    'ts_code': ['000001.SZ', None],
    'trade_date': ['20230101', '20230101'],
}).with_row_index('id2')

# Anti-join
result = df1.join(df2, on=['ts_code', 'trade_date'], how='anti')
print(result)
```

**预期结果**: 
- `ts_code=None, trade_date='20230101'` 在两边都存在
- Anti-join 会将它们匹配，结果是空DataFrame

---

## 4. 影响分析

### 4.1 关键问题：`validate_data` 会阻止保存（必须修复）

**问题描述**：即使修改了 `_filter_primary_key_nulls` 不再过滤 primary key 为 None 的数据，数据仍然不会被保存。

**原因分析**：

在 `storage.py` 的 `_process_worker` 方法中（第598-600行）：

```python
# 验证数据
if self.processor:
    validation_result = self.processor.validate_data(df, interface_config)
    if not validation_result['valid']:
        logger.warning(f"Data validation failed for {interface_name}")
        continue  # 【关键】如果验证失败，会跳过保存！
```

而 `validate_data` 方法（processor.py:300-360）会检查 primary key 是否有缺失值：

```python
# 检查必填字段 - 现在基于primary_key字段
primary_keys = output_config.get('primary_key', []) or []
for column_name in primary_keys:
    if column_name in df.columns:
        missing_count = df[column_name].null_count()
        if missing_count > 0:
            validation_result['missing_required_fields'].append({
                'field': column_name,
                'missing_count': missing_count
            })

# ...
validation_result['valid'] = (
    len(validation_result['missing_required_fields']) == 0 and  # 【关键】有缺失则无效
    len(validation_result['type_mismatches']) == 0 and
    validation_result['duplicate_records'] == 0
)
```

**结论**：必须同时修改 `validate_data` 方法，否则 primary key 为 None 的数据会在验证阶段被拒绝。

### 4.2 数据完整性
- **正面影响**: 保留所有原始数据，包括 primary key 为空的记录
- **潜在问题**: 某些接口可能依赖于过滤逻辑来确保数据质量

### 4.2 去重行为
- **无变化**: Polars 的 `unique` 和 `join` 操作已经正确处理 `None` 值
- 多条 primary key 都为 `None` 的记录会被正确去重

### 4.3 下游影响
需要检查以下模块是否依赖于"主键不为空"的假设：
- 数据验证 `validate_data()`
- 数据清洗 `_clean_data()`
- 覆盖度管理 `coverage_manager.py`

### 4.4 存储影响
- 数据文件可能会变大（保留了更多记录）
- 需要确保下游分析能正确处理 primary key 为空的数据

---

## 5. 测试计划

### 5.1 单元测试

```python
def test_save_null_primary_key():
    """测试保存 primary key 为 None 的数据"""
    # 准备测试数据
    data = [
        {'ts_code': '000001.SZ', 'trade_date': '20230101', 'value': 1},
        {'ts_code': None, 'trade_date': '20230101', 'value': 2},  # ts_code为None
        {'ts_code': None, 'trade_date': '20230101', 'value': 3},  # 重复的None
    ]
    
    interface_config = {
        'api_name': 'test',
        'output': {'primary_key': ['ts_code', 'trade_date']}
    }
    
    processor = DataProcessor()
    df = processor.process_data(data, interface_config)
    
    # 验证：应该保留 ts_code=None 的记录（去重后保留最后一条）
    assert len(df) == 2  # 一条正常 + 一条None
    assert df.filter(pl.col('ts_code').is_null()).height == 1
```

### 5.2 集成测试

1. 选择一个有 primary key 为空数据的接口（如 `suspend_d`）
2. 运行数据下载
3. 验证保存的数据包含 primary key 为空的记录
4. 验证去重逻辑正确执行

---

## 6. 相关代码位置汇总

| 文件 | 行号 | 方法/功能 | 说明 | 是否必须修改 |
|------|------|-----------|------|--------------|
| `app4/core/processor.py` | 78 | `process_data()` | 调用过滤方法 | 否（修改2会处理） |
| `app4/core/processor.py` | 140-163 | `_filter_primary_key_nulls()` | 过滤主键为空的记录 | **是** - 修改1/修改2 |
| `app4/core/processor.py` | 300-360 | `validate_data()` | 数据验证 | **是** - 修改3 |
| `app4/core/processor.py` | 207-236 | `_remove_duplicates()` | 批次内去重 | 否 |
| `app4/core/processor.py` | 165-205 | `_handle_primary_keys()` | 主键处理 | 否 |
| `app4/core/dedup.py` | 240-320 | `deduplicate_against_existing()` | 与历史数据去重 | 否 |
| `app4/core/storage.py` | 598-600 | `_process_worker()` | 调用验证，valid=False会跳过保存 | 否（但需理解其行为） |

---

## 7. 结论

修改方案需要**同时修改两个地方**：

### 7.1 必须修改的位置

1. **`_filter_primary_key_nulls`** (processor.py:140-163)
   - 移除过滤逻辑，只记录日志

2. **`validate_data`** (processor.py:300-360)
   - 不再将 primary key 缺失值视为验证失败
   - 否则数据会在 storage.py 的验证阶段被拒绝保存

### 7.2 不需要修改的位置

- **去重逻辑**：Polars 的 `unique` 和 `join` 操作已经正确处理 `None` 值
- **`_handle_primary_keys`**：与去重相关的内部逻辑无需修改
- **`_remove_duplicates`**：批次内去重逻辑无需修改

### 7.3 推荐方案

建议采用**方案A**：
1. 修改 `_filter_primary_key_nulls` 方法，只记录日志不执行过滤
2. 修改 `validate_data` 方法，允许 primary key 为 None

这是最简单且向后兼容的方案。

### 7.4 关于"去重逻辑双重处理"的说明

代码中存在两个去重点：
- `_handle_primary_keys` 内部调用 `_detect_duplicates_fast`
- `_remove_duplicates` 使用 Polars 的 `unique` 方法

这**不是问题**：
- `_handle_primary_keys` 还有其他职责（schema 应用、返回正确类型的 DataFrame）
- 两者的去重策略可能不同（如 keep 策略）
- 效率影响可以忽略不计

因此不需要移除或合并这两个方法。
