# 重构：将存储去重逻辑从主程序移至存储模块

## 背景

当前的 `app4` 系统中，`process_and_save_data` 函数位于 `main.py` 中，包含了与存储相关的去重逻辑。这种设计违反了单一职责原则，导致主程序承担了过多的数据处理职责。

## 问题分析

### 当前架构问题

1. **职责混乱**: 主程序同时处理业务逻辑和数据存储逻辑
2. **代码重复**: 相似的去重逻辑可能在多处出现
3. **维护困难**: 修改存储逻辑需要修改主程序
4. **测试复杂**: 难以独立测试存储相关的去重功能

### 当前的 `process_and_save_data` 函数

```python
def process_and_save_data(data, interface_name, interface_config, processor, storage_manager):
    # ...
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
                    if all(v is not None) for v in key_tuple:
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
```

## 重构方案

### 1. 在 `storage.py` 中添加去重相关方法

#### 新增方法

- `filter_new_records(interface_name: str, new_data: List[Dict], dedup_config: Dict[str, Any]) -> List[Dict]`
  - 根据去重配置过滤新记录
  - 返回仅包含新记录的数据列表

- `save_data_with_dedup(interface_name: str, data: List[Dict], dedup_config: Dict[str, Any], async_write: bool = True)`
  - 带去重功能的数据保存
  - 内部调用 `filter_new_records`

### 2. 修改 `main.py` 中的 `process_and_save_data`

重构后的函数将只负责参数传递和流程控制：

```python
def process_and_save_data(data, interface_name, interface_config, processor, storage_manager):
    """处理并保存数据的通用函数 - 重构后"""
    if not data:
        logger.warning(f"No data to process for {interface_name}")
        return None

    # 处理数据
    df = processor.process_data(data, interface_config)
    validation_result = processor.validate_data(df, interface_config)

    # 从接口配置获取去重配置
    dedup_config = interface_config.get('dedup', {})
    
    # 保存数据（内部处理去重逻辑）
    storage_manager.save_data_with_dedup(interface_name, df.to_dicts(), dedup_config, async_write=True)

    logger.info(f"Saved {len(df)} processed records for {interface_name}")
    if validation_result['duplicate_records'] > 0:
        logger.info(f"Found {validation_result['duplicate_records']} duplicate records for {interface_name}")

    return df
```

### 3. 重构 `storage.py` 的具体实现

```python
def filter_new_records(self, interface_name: str, new_data: List[Dict], dedup_config: Dict[str, Any]) -> List[Dict]:
    """
    根据去重配置过滤新记录，只返回不存在的记录
    
    Args:
        interface_name: 接口名称
        new_data: 新数据列表
        dedup_config: 去重配置
        
    Returns:
        过滤后的新记录列表
    """
    if not dedup_config.get('enabled', False):
        return new_data

    strategy = dedup_config.get('strategy', 'none')
    dedup_columns = dedup_config.get('columns', [])

    if strategy != 'primary_key' or not dedup_columns:
        return new_data

    # 读取现有数据
    existing_df = self.read_interface_data(interface_name, columns=dedup_columns)
    
    if existing_df.is_empty():
        return new_data

    # 构建现有主键集合
    existing_keys = set()
    for row in existing_df.iter_rows(named=True):
        key_tuple = tuple(row.get(k) for k in dedup_columns if k in row)
        if all(v is not None for v in key_tuple):
            existing_keys.add(key_tuple)

    logger.info(f"Found {len(existing_keys)} existing key combinations for {interface_name}")

    # 过滤出不存在的新记录
    original_count = len(new_data)
    new_records = []
    for record in new_data:
        key_tuple = tuple(record.get(k) for k in dedup_columns if k in record)
        if key_tuple not in existing_keys and all(v is not None for v in key_tuple):
            new_records.append(record)

    if not new_records:
        logger.info(f"All {original_count} records already exist for {interface_name}, skipping save")
        return []
    
    logger.info(f"Filtered {original_count - len(new_records)} duplicate records, "
                f"saving {len(new_records)} new records for {interface_name}")
    
    return new_records

def save_data_with_dedup(self, interface_name: str, data: List[Dict], dedup_config: Dict[str, Any], async_write: bool = True):
    """
    带去重功能的数据保存
    
    Args:
        interface_name: 接口名称
        data: 要保存的数据
        dedup_config: 去重配置
        async_write: 是否异步写入
    """
    # 先过滤新记录
    filtered_data = self.filter_new_records(interface_name, data, dedup_config)
    
    if not filtered_data:
        return  # 没有新数据需要保存
    
    # 保存过滤后的数据
    self.save_data(interface_name, filtered_data, async_write)
```

## 重构步骤

### 步骤 1: 在 `storage.py` 中实现新方法
- 添加 `filter_new_records` 方法
- 添加 `save_data_with_dedup` 方法

### 步骤 2: 修改 `main.py`
- 简化 `process_and_save_data` 函数
- 调用新的存储方法

### 步骤 3: 测试验证
- 单元测试新的存储方法
- 集成测试整个流程
- 确保去重功能正常工作

### 步骤 4: 文档更新
- 更新架构文档
- 更新API文档

## 预期收益

1. **职责分离**: 存储逻辑集中在存储模块
2. **可维护性**: 修改存储逻辑不再影响主程序
3. **可测试性**: 可以独立测试存储相关的去重功能
4. **复用性**: 去重逻辑可以在其他地方复用
5. **清晰性**: 代码结构更加清晰，易于理解

## 注意事项

1. **向后兼容**: 确保现有功能不受影响
2. **性能影响**: 验证重构后性能没有显著下降
3. **错误处理**: 保持原有的错误处理机制
4. **日志记录**: 保持适当的日志记录级别