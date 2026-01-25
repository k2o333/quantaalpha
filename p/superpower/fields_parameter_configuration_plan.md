# Fields 参数配置实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现通过配置文件控制 TuShare API 的 fields 参数，使系统能够返回配置中指定的额外字段。

**Architecture:** 配置驱动的字段控制，通过 YAML 配置文件定义接口的 fields 参数，修改 downloader 逻辑以根据配置传递 fields 参数。

**Tech Stack:** Python, YAML, TuShare API

---

### Task 1: 分析当前 fields 参数实现

**Files:**
- Modify: `app4/core/downloader.py:938-940`

**Step 1: 检查当前 fields 参数处理逻辑**

```python
# 确认在 app4/core/downloader.py 中第938-940行存在以下代码：
req_params = {
    'api_name': interface_config['api_name'],
    'token': token,
    'params': params,
    'fields': ''  # 空字符串表示不指定字段，API返回所有字段
}
```

**Step 2: 确认当前实现只返回默认字段**

当前代码中 `fields: ''` 实际上只返回默认字段，而不是所有字段。

**Step 3: 记录当前行为**

当前 TuShare API 没有 "返回所有字段" 的标准参数值，必须明确指定需要的字段。

**Step 4: 记录**

确认当前问题和需要修改的内容。

**Step 5: Commit**

```bash
git add p/superpower/fields_parameter_configuration_plan.md
git commit -m "docs: add fields parameter configuration plan"
```

### Task 2: 修改 stock_basic.yaml 配置文件

**Files:**
- Modify: `app4/config/interfaces/stock_basic.yaml`

**Step 1: 添加 fields 配置**

```yaml
# 修改 /home/quan/testdata/aspipe_v4/app4/config/interfaces/stock_basic.yaml
# 添加字段配置以返回非默认字段
api_name: stock_basic
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

**Step 2: 保存修改后的配置**

将上述内容写入 stock_basic.yaml 文件。

**Step 3: 验证配置格式**

确保 YAML 格式正确。

**Step 4: 保存文件**

保存修改后的 stock_basic.yaml 文件。

**Step 5: Commit**

```bash
git add app4/config/interfaces/stock_basic.yaml
git commit -m "feat: add fields configuration to stock_basic interface"
```

### Task 3: 修改 downloader.py 中的 fields 参数处理逻辑

**Files:**
- Modify: `app4/core/downloader.py:935-940`

**Step 1: 实现新的 fields 参数处理逻辑**

```python
# 修改 app4/core/downloader.py 中 _make_request 方法的 935-940 行部分
# 获取接口配置中的 fields
config_fields = interface_config.get('fields', [])

if config_fields:
    # 如果配置了 fields，传递配置的字段
    # TuShare API 会返回默认字段 + 指定字段的并集
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

**Step 2: 替换原代码**

将 app4/core/downloader.py 中的第935-940行的原代码替换为新实现。

**Step 3: 修改 _make_request 方法**

```python
# 在 app4/core/downloader.py 中，找到 _make_request 方法，替换这部分代码：
# 不传递fields参数，让API返回所有字段
# 因为API默认返回所有字段，不需要显式指定

# 根据TuShare API格式构建请求体
req_params = {
    'api_name': interface_config['api_name'],
    'token': token,
    'params': params,
    'fields': ''  # 空字符串表示不指定字段，API返回所有字段
}

# 替换为：
# 获取接口配置中的 fields
config_fields = interface_config.get('fields', [])

if config_fields:
    # 如果配置了 fields，传递配置的字段
    # TuShare API 会返回默认字段 + 指定字段的并集
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

**Step 4: 保存更改**

保存 app4/core/downloader.py 文件。

**Step 5: Commit**

```bash
git add app4/core/downloader.py
git commit -m "feat: implement fields parameter configuration in downloader"
```

### Task 4: 创建测试验证脚本

**Files:**
- Create: `tests/test_fields_configuration.py`

**Step 1: 创建测试脚本**

```python
#!/usr/bin/env python3
"""测试 fields 参数配置功能"""
import sys
import os
sys.path.insert(0, '/home/quan/testdata/aspipe_v4/app4')

from app4.core.config_loader import ConfigLoader
from app4.core.downloader import GenericDownloader
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_fields_configuration():
    """测试 fields 参数配置功能"""
    print("=" * 80)
    print("开始测试 fields 参数配置功能...")
    print("=" * 80)

    # 初始化配置加载器
    config_loader = ConfigLoader(config_dir='/home/quan/testdata/aspipe_v4/app4/config')

    # 初始化下载器
    downloader = GenericDownloader(
        config_loader=config_loader,
        storage_manager=None,
        force_download=True
    )

    # 获取 stock_basic 接口配置
    interface_config = config_loader.get_interface_config('stock_basic')

    print("stock_basic 接口配置中的 fields 设置:")
    fields_config = interface_config.get('fields', [])
    print(f"配置的额外字段: {fields_config}")
    print()

    # 下载 stock_basic 数据
    print("正在下载 stock_basic 数据...")
    params = {'list_status': 'L'}  # 只获取上市股票
    data = downloader.download('stock_basic', params)

    if not data:
        print("❌ 下载失败，没有返回数据")
        return

    print(f"✅ 成功下载 {len(data)} 条记录")
    print()

    # 分析返回的字段
    if data:
        first_record = data[0]
        returned_fields = list(first_record.keys())

        print(f"API 实际返回 {len(returned_fields)} 个字段:")
        for i, field in enumerate(returned_fields, 1):
            value = first_record.get(field)
            value_str = str(value) if value is not None else "NULL"
            print(f"  {i:2d}. {field:20s} = {value_str}")

        print()

        # 检查是否包含了配置中指定的字段
        missing_config_fields = [f for f in fields_config if f not in returned_fields]
        if missing_config_fields:
            print(f"❌ 配置中指定的字段但API未返回 ({len(missing_config_fields)}个):")
            for field in missing_config_fields:
                print(f"  - {field}")
        else:
            print(f"✅ 配置中指定的 {len(fields_config)} 个字段都已返回")

        print()

        # 显示所有返回的字段
        print("所有返回的字段:")
        for field in returned_fields:
            if field in fields_config:
                print(f"  [配置] {field}")
            else:
                print(f"  [默认] {field}")

if __name__ == '__main__':
    test_fields_configuration()
```

**Step 2: 保存测试脚本**

将测试脚本保存到正确位置。

**Step 3: 确保脚本可执行**

确保 Python 脚本格式正确。

**Step 4: 保存文件**

保存测试脚本。

**Step 5: Commit**

```bash
mkdir -p tests
git add tests/test_fields_configuration.py
git commit -m "test: add fields configuration test script"
```

### Task 5: 运行测试验证配置功能

**Files:**
- Test: `tests/test_fields_configuration.py`

**Step 1: 运行测试脚本**

```bash
python tests/test_fields_configuration.py
```

**Step 2: 检查测试结果**

确认：
- stock_basic 接口返回了配置中指定的额外字段
- 返回的字段数量符合预期

**Step 3: 记录测试结果**

记录测试执行的结果。

**Step 4: 根据测试结果调整**

如果测试失败，需要根据错误信息调整实现。

**Step 5: Commit**

```bash
git add .
git commit -m "docs: document test results for fields configuration"
```

### Task 6: 为其他需要完整字段的接口添加配置

**Files:**
- Modify: `app4/config/interfaces/*.yaml`

**Step 1: 选择其他接口进行配置**

选择几个可能需要完整字段的接口进行配置（如 daily, daily_basic 等）。

**Step 2: 为 daily 接口添加配置**

```yaml
# 修改 app4/config/interfaces/daily.yaml
# 在需要完整字段的接口中添加 fields 配置
api_name: daily
description: 日线行情

permissions:
  min_points: 0
  rate_limit: 120
  query_limit: 10000

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"

output:
  primary_key: ["ts_code", "trade_date"]
  sort_by: ["trade_date"]
  columns:
    ts_code: {type: string, required: true}
    trade_date: {type: date, format: "%Y%m%d", required: true}

duplicate_detection:
  enabled: true
  date_column: "trade_date"
  threshold: 0.95

# fields 配置：如果需要额外字段，请取消注释并配置
# fields:
#   - pre_close      # 前一日收盘价
#   - change         # 涨跌额
#   - pct_change     # 涨跌幅
#   - vol            # 成交量
#   - amount         # 成交额
```

**Step 3: 为 daily_basic 接口添加配置**

```yaml
# 修改 app4/config/interfaces/daily_basic.yaml
# 在需要完整字段的接口中添加 fields 配置
api_name: daily_basic
description: 每日指标

permissions:
  min_points: 0
  rate_limit: 120
  query_limit: 10000

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"

output:
  primary_key: ["ts_code", "trade_date"]
  sort_by: ["trade_date"]
  columns:
    ts_code: {type: string, required: true}
    trade_date: {type: date, format: "%Y%m%d", required: true}

duplicate_detection:
  enabled: true
  date_column: "trade_date"
  threshold: 0.95

# fields 配置：如果需要额外字段，请取消注释并配置
# fields:
#   - close         # 当日收盘价
#   - turnover_rate # 换手率
#   - turnover_rate_f # 换手率(自由流通股)
#   - volume_ratio # 量比
#   - pe           # 市盈率
#   - pe_ttm       # 市盈率TTM
#   - pb           # 市净率
#   - ps           # 市销率
#   - ps_ttm       # 市销率TTM
#   - dv_ratio   # 股息率
#   - dv_ttm     # 股息率TTM
#   - total_share # 总股本
#   - float_share # 流通股本
#   - free_share  # 自由流通股本
#   - total_mv    # 总市值
#   - circ_mv     # 流通市值
```

**Step 4: 保存文件**

保存对其他接口配置文件的修改。

**Step 5: Commit**

```bash
git add app4/config/interfaces/daily.yaml app4/config/interfaces/daily_basic.yaml
git commit -m "feat: add optional fields configuration to daily and daily_basic interfaces"
```