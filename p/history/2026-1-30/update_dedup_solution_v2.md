# Update 模式去重逻辑接入方案 V2

## 问题分析

当前 Update 模式调用 `storage_manager.write_interface_data()` 保存数据，但该方法会添加 `_update_time` 字段，导致数据跳过 `_process_worker` 中的去重逻辑。

普通模式使用 `storage_manager.save_data()`（传入字典列表，不含 `_update_time`），数据会进入 `process_queue` 进行去重。

## 解决方案

将 UpdateManager 中的 `write_interface_data()` 改为 `save_data()`，与普通模式保持一致。

## 具体实现

修改 `app4/update/update_manager.py` 的 `_execute_download` 方法：

```python
def _execute_download(
    self,
    interface_name: str,
    interface_config: Dict[str, Any],
    date_range: DateRange,
    options: UpdateOptions
) -> int:
    # ... 保持原有下载逻辑不变 ...

    # 处理和保存数据（与普通模式保持一致）
    if result_data and len(result_data) > 0:
        # 使用 processor 处理数据
        df = self.processor.process_data(result_data, interface_config)

        if not df.is_empty():
            # 【修改】使用 save_data 而不是 write_interface_data
            # 传入字典列表，不添加 _update_time，让 _process_worker 进行去重
            self.storage_manager.save_data(interface_name, df.to_dicts(), async_write=True)
            return len(result_data)

    return 0
```

## 去重流程

```
下载数据
    ↓
processor.process_data() [批次内去重]
    ↓
storage_manager.save_data() → process_queue → _process_worker [与存量数据去重]
    ↓
storage_manager.write_interface_data() [保存]
```

## 变更总结

| 文件 | 变更内容 |
|------|---------|
| `app4/update/update_manager.py` | 将 `write_interface_data()` 改为 `save_data()` |

## 关键特性

1. **复用现有逻辑**：直接利用 `_process_worker` 中的去重逻辑，无需新代码
2. **一致性**：Update 模式与普通模式使用相同的去重流程
3. **简单**：只需修改一行代码
