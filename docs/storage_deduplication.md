# 存储去重功能

## 设计理念

app4架构中，存储去重逻辑已经从主程序移至存储模块，实现了单一职责原则。存储相关的去重操作全部由StorageManager处理。

## 主要组件

### StorageManager类

存储管理器现在包含以下与去重相关的方法：

#### `filter_new_records(interface_name, new_data, dedup_config)`

根据去重配置过滤新记录，只返回不存在的记录。

参数:
- `interface_name`: 接口名称
- `new_data`: 新数据列表
- `dedup_config`: 去重配置

返回值:
- 过滤后的新记录列表

#### `save_data_with_dedup(interface_name, data, dedup_config, async_write=True)`

带去重功能的数据保存方法。

参数:
- `interface_name`: 接口名称
- `data`: 要保存的数据
- `dedup_config`: 去重配置
- `async_write`: 是否异步写入

## 配置格式

接口配置文件中可包含以下去重配置：

```yaml
dedup:
  enabled: true          # 是否启用去重
  strategy: primary_key  # 去重策略
  columns: ["ts_code", "trade_date"]  # 用于去重的列
```

## 使用示例

在main.py中的数据处理流程中：

```python
def process_and_save_data(data, interface_name, interface_config, processor, storage_manager):
    # 处理数据
    df = processor.process_data(data, interface_config)

    # 从接口配置获取去重配置
    dedup_config = interface_config.get('dedup', {})

    # 保存数据（内部处理去重逻辑）
    storage_manager.save_data_with_dedup(interface_name, df.to_dicts(), dedup_config, async_write=True)
```

## 性能考虑

- 去重操作会读取现有数据以构建唯一键集合
- 对于大表，这可能影响性能
- 建议合理配置去重策略，避免不必要的去重操作