# Fields 参数配置方案

## 1. 问题分析

### 1.1 当前问题

TuShare API 的 `fields` 参数控制返回哪些字段，当前实现存在以下问题：

- **代码问题**：`downloader.py:938` 设置 `fields: ''`，注释说"不传递fields参数，让API返回所有字段"
- **实际行为**：`fields: ''` 只返回默认字段（文档中标记为 "Y" 的字段）
- **配置缺失**：接口配置文件中没有定义完整的字段列表

### 1.2 测试结果（stock_basic 接口）

- API 实际返回：**10 个字段**（只包含标记为 "Y" 的字段）
- 文档列出：**17 个字段**
- 缺少 7 个字段：
  - `curr_type` - 交易货币
  - `delist_date` - 退市日期
  - `enname` - 英文全称
  - `exchange` - 交易所代码
  - `fullname` - 股票全称
  - `is_hs` - 是否沪深港通标的
  - `list_status` - 上市状态

### 1.3 TuShare API 行为

根据 TuShare API 文档和实际测试：

| fields 参数值 | 返回字段 |
|--------------|---------|
| 未传递或 `''` | 只返回默认字段（标记为 "Y" 的字段） |
| 指定字段列表 | 返回指定的字段 |
| `'*'` 或 `'all'` | 返回所有字段（部分接口支持） |

**重要**：TuShare API **没有**"返回所有字段"的标准参数值，必须明确指定需要的字段。

## 2. 解决方案设计

### 2.1 设计原则

1. **向后兼容**：不配置 fields 时，保持当前行为（返回默认字段）
2. **灵活性**：配置 fields 时，可以指定需要额外返回的字段
3. **并集原则**：返回字段 = 默认字段 ∪ 配置字段
4. **配置驱动**：通过 YAML 配置文件控制，无需修改代码

### 2.2 配置结构

在接口配置文件中添加 `fields` 配置项：

```yaml
# app4/config/interfaces/stock_basic.yaml

api_name: stock_basic
description: 股票列表

# 新增：fields 配置
# 如果不配置，只返回默认字段
# 如果配置，返回 默认字段 ∪ 配置字段
fields:
  # 需要额外返回的字段（非默认字段）
  - fullname
  - enname
  - exchange
  - curr_type
  - list_status
  - delist_date
  - is_hs

# 其他现有配置...
```

### 2.3 实现逻辑

```python
# downloader.py 中的实现逻辑

def _make_request(self, interface_config, params):
    # ...

    # 获取接口配置中的 fields
    config_fields = interface_config.get('fields', [])

    if config_fields:
        # 如果配置了 fields，返回 默认字段 ∪ 配置字段
        # 注意：这里不需要显式指定默认字段，API 会自动包含
        req_params = {
            'api_name': interface_config['api_name'],
            'token': token,
            'params': params,
            'fields': ','.join(config_fields)  # 只传递配置的额外字段
        }
    else:
        # 如果没有配置 fields，只返回默认字段
        req_params = {
            'api_name': interface_config['api_name'],
            'token': token,
            'params': params,
            'fields': ''  # 空字符串，返回默认字段
        }

    # ...
```

**关键点**：
- TuShare API 的 `fields` 参数是**添加字段**，不是**替换字段**
- 即使只传递非默认字段，API 也会返回默认字段 + 指定字段
- 因此，`fields` 配置中只需要列出**非默认字段**

### 2.4 字段分类

根据 TuShare 文档，字段分为两类：

**默认字段（Y）** - 无需配置，API 自动返回：
- `ts_code` - TS代码
- `symbol` - 股票代码
- `name` - 股票名称
- `area` - 地域
- `industry` - 所属行业
- `cnspell` - 拼音缩写
- `market` - 市场类型
- `list_date` - 上市日期
- `act_name` - 实控人名称
- `act_ent_type` - 实控人企业性质

**非默认字段（N）** - 需要配置才会返回：
- `fullname` - 股票全称
- `enname` - 英文全称
- `exchange` - 交易所代码
- `curr_type` - 交易货币
- `list_status` - 上市状态
- `delist_date` - 退市日期
- `is_hs` - 是否沪深港通标的

## 3. 配置示例

### 3.1 stock_basic.yaml 完整配置

```yaml
api_name: stock_basic
description: 股票列表
name: stock_basic

# Fields 配置：指定额外返回的非默认字段
fields:
  - fullname      # 股票全称
  - enname        # 英文全称
  - exchange      # 交易所代码
  - curr_type     # 交易货币
  - list_status   # 上市状态
  - delist_date   # 退市日期
  - is_hs         # 是否沪深港通标的

# 派生字段配置
derived_fields:
  delist_date_dt:
    description: 日期类型的delist_date
    format: '%Y%m%d'
    source: delist_date
    type: date
  list_date_dt:
    description: 日期类型的list_date
    format: '%Y%m%d'
    source: list_date
    type: date

# 输出配置
output:
  primary_key:
  - ts_code
  sort_by:
  - ts_code

# 分页配置
pagination:
  default_limit: 5000
  enabled: true
  limit_key: limit
  mode: offset
  offset_key: offset

# 参数配置
parameters:
  exchange:
    description: 交易所 SSE上交所 SZSE深交所
    required: false
    type: string
  list_status:
    default: L
    description: 上市状态 L上市 D退市 P暂停上市 S终止上市
    options:
    - L
    - D
    - P
    - S
    required: false
    type: string

# 权限配置
permissions:
  min_points: 2000
  query_limit: 10000
  rate_limit: 60

# 请求配置
request:
  extra_path: ''
  method: POST
  timeout: 30
```

### 3.2 其他接口配置示例

**示例 1：只返回默认字段（不配置 fields）**

```yaml
api_name: daily
description: 日线行情
# 不配置 fields，只返回默认字段
```

**示例 2：返回所有字段**

```yaml
api_name: balancesheet_vip
description: 资产负债表
fields:
  # 列出所有非默认字段
  - end_date
  - report_type
  - comp_type
  - # ... 其他字段
```

## 4. 实现步骤

### 4.1 第一步：修改接口配置文件

为需要返回完整字段的接口添加 `fields` 配置：

1. **stock_basic.yaml** - 添加 7 个非默认字段
2. **其他接口** - 根据需要添加

### 4.2 第二步：修改 downloader.py

修改 `_make_request` 方法中的 `fields` 参数处理逻辑：

```python
# 修改前（第 938 行）
req_params = {
    'api_name': interface_config['api_name'],
    'token': token,
    'params': params,
    'fields': ''  # 空字符串表示不指定字段，API返回所有字段
}

# 修改后
config_fields = interface_config.get('fields', [])
if config_fields:
    # 如果配置了 fields，传递配置的字段
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
        'fields': ''
    }
```

### 4.3 第三步：测试验证

1. 运行测试脚本验证 stock_basic 接口返回所有 17 个字段
2. 验证其他接口的行为（未配置的接口仍返回默认字段）
3. 检查派生字段是否正常工作

## 5. 测试验证方案

### 5.1 测试脚本

使用现有的测试脚本 `test_stock_basic_fields.py`：

```bash
/root/miniforge3/bin/python test_stock_basic_fields.py
```

**预期结果**：
- API 返回 17 个字段（10 个默认字段 + 7 个配置字段）
- 缺少字段列表为空
- 派生字段正常添加

### 5.2 手动验证

```python
from app4.core.config_loader import ConfigLoader
from app4.core.downloader import GenericDownloader

config_loader = ConfigLoader(config_dir='/home/quan/testdata/aspipe_v4/app4/config')
downloader = GenericDownloader(config_loader=config_loader)

# 测试 stock_basic
data = downloader.download('stock_basic', {'list_status': 'L'})
print(f"返回字段数: {len(data[0].keys())}")
print(f"所有字段: {list(data[0].keys())}")

# 验证特定字段
assert 'fullname' in data[0]
assert 'enname' in data[0]
assert 'exchange' in data[0]
# ...
```

## 6. 影响范围分析

### 6.1 向后兼容性

- ✅ **向后兼容**：未配置 `fields` 的接口行为不变
- ✅ **可配置**：需要完整字段的接口通过配置实现
- ✅ **无破坏性**：不影响现有数据和代码

### 6.2 受影响的接口

**需要立即修改**：
- `stock_basic.yaml` - 添加 7 个非默认字段

**可能需要修改**：
- 其他需要完整字段的接口（根据业务需求）

**无需修改**：
- 只使用默认字段的接口（保持现状）

### 6.3 数据存储影响

- 新增字段会存储到数据文件中
- 需要确保 schema 兼容性
- 可能需要更新数据验证逻辑

## 7. 注意事项

### 7.1 TuShare API 限制

- 不是所有接口都支持所有字段
- 某些字段可能需要更高权限
- 字段名称必须完全匹配 TuShare 文档

### 7.2 性能考虑

- 返回更多字段会增加数据量
- 网络传输和存储成本会增加
- 建议只配置业务需要的字段

### 7.3 数据质量

- 非默认字段可能包含大量空值
- 需要在数据处理中考虑空值处理
- 建议添加数据验证逻辑

## 8. 总结

### 8.1 方案优势

1. **配置驱动**：通过 YAML 配置控制，无需修改代码
2. **向后兼容**：不影响现有接口行为
3. **灵活可控**：根据业务需求选择返回字段
4. **易于维护**：配置清晰，易于理解和修改

### 8.2 实施建议

1. **先实施 stock_basic**：作为验证示例
2. **逐步推广**：根据业务需求扩展到其他接口
3. **充分测试**：确保数据完整性和正确性
4. **文档更新**：更新接口文档说明字段配置

### 8.3 下一步行动

1. ✅ 编写配置方案文档（本文档）
2. ⏳ 修改 `stock_basic.yaml` 配置文件
3. ⏳ 修改 `downloader.py` 代码逻辑
4. ⏳ 运行测试验证
5. ⏳ 推广到其他接口