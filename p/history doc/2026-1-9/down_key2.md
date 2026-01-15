## 最简洁且灵活的基于接口配置的去重方案

### 核心设计原则
**简洁实现 + 配置驱动 + 避免不必要的API调用**

### 实现方案

#### 1. 在接口yaml中添加去重配置

每个接口可以在yaml中定义去重策略：

```yaml
# 示例：pro_bar.yaml
output:
  primary_key: ["ts_code", "trade_date"]
  sort_by: ["trade_date"]

# 去重配置
dedup:
  enabled: true
  strategy: "primary_key"  # 可选: "primary_key", "date_range", "none"
  columns: ["ts_code", "trade_date"]  # 用于去重的列
```

#### 2. 只修改一个函数：`process_and_save_data`

在保存数据前，根据接口yaml中的`dedup`配置进行去重。

**文件路径**: `app4/main.py`  
**修改位置**: 第 263-291 行

```python
def process_and_save_data(data, interface_name, interface_config, processor, storage_manager):
    """处理并保存数据的通用函数 - 支持基于接口配置的去重

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

    # [新增] 基于接口配置的去重
    dedup_config = interface_config.get('dedup', {})
    
    if dedup_config.get('enabled', False):
        strategy = dedup_config.get('strategy', 'none')
        dedup_columns = dedup_config.get('columns', [])
        
        if strategy == 'primary_key' and dedup_columns:
            # 读取现有数据
            existing_df = storage_manager.read_interface_data(
                interface_name,
                columns=dedup_columns
            )

            if not existing_df.is_empty():
                # 构建现有主键集合
                existing_keys = set()
                for row in existing_df.iter_rows(named=True):
                    key_tuple = tuple(row.get(k) for k in dedup_columns if k in row)
                    if all(v is not None for v in key_tuple):
                        existing_keys.add(key_tuple)

                logger.info(f"Found {len(existing_keys)} existing key combinations for {interface_name}")

                # 过滤出不存在的新记录
                original_count = len(df)
                new_records = []
                for row in df.iter_rows(named=True):
                    key_tuple = tuple(row.get(k) for k in dedup_columns)
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

### 配置示例

#### 1. pro_bar.yaml - 基于主键去重
```yaml
dedup:
  enabled: true
  strategy: "primary_key"
  columns: ["ts_code", "trade_date"]
```

#### 2. income_vip.yaml - 基于主键去重
```yaml
dedup:
  enabled: true
  strategy: "primary_key"
  columns: ["ts_code", "ann_date", "end_date"]
```

#### 3. top10_holders.yaml - 不去重
```yaml
dedup:
  enabled: false
```

### 方案优势

1. ✅ **最简洁**：只修改一个函数
2. ✅ **配置驱动**：每个接口可以在yaml中定义去重条件
3. ✅ **灵活性强**：支持不同的去重策略和列
4. ✅ **避免重复保存**：确保不会保存重复数据
5. ✅ **向后兼容**：未配置的接口不受影响
6. ✅ **易于维护**：代码简单清晰

### 去重策略

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| `primary_key` | 基于指定列的组合去重 | 大多数接口 |
| `none` | 不去重 | 特殊接口 |

### 实施步骤

1. 修改 `app4/main.py` 中的 `process_and_save_data` 函数
2. 在需要去重的接口yaml中添加 `dedup` 配置
3. 测试验证

### 预期效果

- ✅ 不会保存重复数据
- ✅ 每个接口可以自定义去重条件
- ✅ 简洁实现，易于维护
- ✅ 向后兼容