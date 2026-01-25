# Fields 参数配置使用说明

## 概述

通过配置文件控制 TuShare API 的 fields 参数，使系统能够返回配置中指定的额外字段。

## 配置方法

### 1. 在接口配置文件中添加 fields 配置

在接口配置文件中添加 `fields` 配置项：

```yaml
# 示例：为 stock_basic 接口配置返回所有字段
fields:
  # 默认字段（标记为"Y"的字段）
  - ts_code       # TS代码
  - symbol        # 股票代码
  - name          # 股票名称
  - area          # 地域
  - industry      # 所属行业
  - cnspell       # 拼音缩写
  - market        # 市场类型
  - list_date     # 上市日期
  - act_name      # 实控人名称
  - act_ent_type  # 实控人企业性质
  # 非默认字段（标记为"N"的字段）
  - fullname      # 股票全称
  - enname        # 英文全称
  - exchange      # 交易所代码
  - curr_type     # 交易货币
  - list_status   # 上市状态
  - delist_date   # 退市日期
  - is_hs         # 是否沪深港通标的
```

### 2. 配置说明

- 如果不配置 `fields`，则返回默认字段（与之前行为一致，保持向后兼容）
- 如果配置了 `fields`，则返回配置中指定的所有字段
- API 会返回 exactly 指定的字段，不会自动添加默认字段

### 3. 使用示例

以下接口已添加可选的 fields 配置模板：

- `stock_basic.yaml` - 已完整配置返回所有字段
- `daily.yaml` - 提供了可配置的字段模板
- `daily_basic.yaml` - 提供了可配置的字段模板

## 实现原理

在 `app4/core/downloader.py` 中实现了以下逻辑：

```python
config_fields = interface_config.get('fields', [])

if config_fields:
    # 如果配置了 fields，传递所有配置的字段
    req_params = {
        'api_name': interface_config['api_name'],
        'token': token,
        'params': params,
        'fields': ','.join(config_fields)
    }
else:
    # 如果没有配置 fields，返回默认字段
    req_params = {
        'api_name': interface_config['api_name'],
        'token': token,
        'params': params,
        'fields': ''  # 空字符串，返回默认字段
    }
```

## 注意事项

1. **权限要求**：某些字段可能需要更高的 TuShare 积分权限才能访问
2. **数据可用性**：某些字段在当前数据状态下可能没有值
3. **性能影响**：返回更多字段会增加数据量和网络传输时间
4. **向后兼容**：不配置 fields 的接口行为保持不变