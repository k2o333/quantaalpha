# Processor 批次内去重逻辑冲突与修复方案 (终极版)

## 1. 问题背景
在 `StorageManager` 接收到一整个 batch 的下载数据后，会调用 `processor.py` 中的 `process_data` 方法进行初步的清洗与加工。
当开发者查看日志时发现，即使在配置文件中开启了 `dedup`，在终端也一直**看不到预期的 `Batch deduplication for ... removed X duplicates within batch` 的日志输出**，似乎批次内去重并没有生效。

## 2. 根因分析：双重去重逻辑冲突
在 `process_data` 的执行顺序中，相继调用了两个涉及到去重的方法：

```python
# app4/core/processor.py
df = self._handle_primary_keys(df, interface_config) # 步骤A
...
df = self._remove_duplicates(df, interface_config)   # 步骤B
```

### 步骤 A: `_handle_primary_keys` （隐式去重 & Schema 应用）
*   **策略实现：** 底层调用了纯 Python 的 `_detect_duplicates_fast`，顺序遍历输入列表，仅保留 **第一条（keep='first'）**。
*   **副作用：** 它是目前流程中唯一根据 `predefined_schema` 显式重新构建 `DataFrame` 的地方。

### 步骤 B: `_remove_duplicates` （显式去重）
*   **底层引擎：** 使用 Polars 原生方法 `df.unique(subset=existing_keys, keep='last')`。
*   **业务逻辑：** 对金融时序数据而言，`keep='last'` 至关重要，它确保了最新的修正数据能覆盖旧快照。

### 冲突结果
由于**步骤 A** 率先去除了重复数据（保留了第一条），导致**步骤 B** 接收到的是已经“干净”的 `DataFrame`，导致 `keep='last'` 逻辑完全失效。

## 3. 终极修复方案
**核心思想：单一职责。`_handle_primary_keys` 仅负责脏数据报警与 Schema 强制转换，物理去重动作完整保留并下放到 `_remove_duplicates`。**

### 建议修复代码：
```python
def _handle_primary_keys(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> pl.DataFrame:
    """处理主键 - (终极修复版：仅做统计报警与Schema应用，将去重逻辑统一下放)"""
    primary_keys = interface_config.get('output', {}).get('primary_key', [])
    interface_name = interface_config.get('api_name', 'unknown')
    
    # 提前计算 data_list，既避免 NameError 风险，又复用于后续报警和 Schema 应用
    data_list = df.to_dicts()

    # 1. 重复检测与报警 (仅用于监控报警，不再此处过滤数据)
    if primary_keys:
        detection_result = self._detect_duplicates_fast(data_list, interface_config)
        if detection_result['duplicates']:
            logger.warning(f"Found {len(detection_result['duplicates'])} duplicate records for interface {interface_name}")

    # 2. 强制 Schema 应用 (修复：保留原有 Schema 处理，但作用于包含重复项的全量数据)
    predefined_schema = SchemaManager.load_schema(interface_name)
    if predefined_schema:
        try:
            # 重新构建 DF 以套用预定义 Schema 类型
            df = pl.DataFrame(data_list, schema=predefined_schema)
            logger.debug(f"Applied predefined schema for all {len(df)} records")
        except Exception as schema_error:
            logger.warning(f"Failed to apply predefined schema for {interface_name}: {str(schema_error)}")

    return df
```

## 4. 改进点说明
1.  **健壮性优化**：将 `data_list = df.to_dicts()` 移至函数顶部。这解决了当 `primary_keys` 配置缺失而 `predefined_schema` 存在时，原本可能出现的 `NameError: name 'data_list' is not defined` 错误。
2.  **Schema 完整性**：修正了最初版本丢失预定义 Schema 应用的问题，确保后续的 `_remove_duplicates` 在正确的数据类型基础上运行。
3.  **遵循 keep='last'**：通过返回包含重复项的 `df`，确保 Polars 引擎在最后的 `_remove_duplicates` 阶段能够根据 `_update_time` 筛选出最新的记录，符合金融业务逻辑。

## 5. 预期结果
修复应用后，批次内去重将由 `_remove_duplicates` 统一接管，终端将准确打印去重日志（如 `Batch deduplication ... removed 5 duplicates`），且入库数据将正确保留每一批次中的最新修正记录。
