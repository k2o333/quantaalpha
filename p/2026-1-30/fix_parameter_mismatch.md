# 6个接口参数不匹配问题解决方案

## 问题概述

以下6个接口存在**参数定义与代码强制传递不匹配**的问题，导致查询失败或返回空结果：

| 接口 | 配置定义 | 代码强制传递 | 结果 |
|------|---------|-------------|------|
| **disclosure_date** | 无 `start_date`，`end_date`=财报周期 | `start_date` + `end_date` | 查询未来日期，返回0条 |
| **dividend** | 无 `start_date`，无 `end_date` | `start_date` + `end_date` | 参数被忽略，返回0条 |
| **pledge_detail** | 只有 `ts_code` | `start_date` + `end_date` | 参数被忽略 |
| **pledge_stat** | 无 `start_date`，`end_date`=截止日期 | `start_date` + `end_date` | 查询未来日期，返回0条 |
| **stk_rewards** | 无 `start_date`，`end_date`=报告期 | `start_date` + `end_date` | 查询未来日期，返回0条 |
| **top10_holders** | 无 `start_date`，使用 `period` | `start_date` + `end_date` | 使用默认period，参数被忽略 |

## 根因分析

代码在以下位置强制添加 `start_date` 和 `end_date`，而不考虑接口实际支持的参数：

1. **app4/core/downloader.py:442-448** - `download_single_stock()` 方法
2. **app4/core/pagination.py:188-193** - `generate_stock_params()` 方法
3. **app4/main.py:608-610** - 命令行参数处理

## 解决方案

### 方案1: 修改 downloader.py（推荐）

在 `download_single_stock()` 方法中，根据接口配置过滤参数：

```python
def download_single_stock(self, interface_config: Dict[str, Any], stock: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        stock_params = params.copy()
        stock_params['ts_code'] = stock['ts_code']

        # 根据接口配置过滤参数 - 只保留接口支持的参数
        supported_params = interface_config.get('parameters', {})
        if supported_params:
            # 获取支持的参数名
            supported_keys = set(supported_params.keys())
            # 始终保留 ts_code
            supported_keys.add('ts_code')
            # 过滤参数
            stock_params = {k: v for k, v in stock_params.items() if k in supported_keys}

        # 设置日期范围（仅当接口支持时）
        if 'start_date' in supported_params and 'start_date' not in stock_params:
            list_date = stock.get('list_date', '20050101')
            stock_params['start_date'] = list_date
        if 'end_date' in supported_params and 'end_date' not in stock_params:
            from datetime import datetime
            stock_params['end_date'] = datetime.now().strftime('%Y%m%d')
```

### 方案2: 修改 pagination.py

在 `generate_stock_params()` 方法中同样添加参数过滤：

```python
# 在参数生成前，先过滤不支持的参数
supported_params = interface_config.get('parameters', {})
if supported_params:
    supported_keys = set(supported_params.keys())
    supported_keys.add('ts_code')
    params = {k: v for k, v in params.items() if k in supported_keys}
```

### 方案3: 修改接口配置（备选）

如果不想修改代码，可以为这些接口添加 `start_date` 和 `end_date` 参数定义，但需要注意：
- 这可能会改变接口的语义
- TuShare API 可能不支持这些参数

## 各接口支持的参数

### disclosure_date
```yaml
parameters:
  ts_code:      # 股票代码
  end_date:     # 财报周期 YYYYMMDD
  pre_date:     # 计划披露日期
  actual_date:  # 实际披露日期
  ann_date:     # 最新披露公告日
```

### dividend
```yaml
parameters:
  ts_code:       # 股票代码
  ann_date:      # 公告日
  ex_date:       # 除权除息日
  record_date:   # 股权登记日期
  imp_ann_date:  # 实施公告日
```

### pledge_detail
```yaml
parameters:
  ts_code:  # 股票代码（必需）
```

### pledge_stat
```yaml
parameters:
  ts_code:   # 股票代码
  end_date:  # 截止日期 YYYYMMDD
```

### stk_rewards
```yaml
parameters:
  ts_code:   # 股票代码（必需）
  end_date:  # 报告期 YYYYMMDD
```

### top10_holders
```yaml
parameters:
  ts_code:  # 证券代码
  period:   # 报告期 YYYYMMDD（默认20231231）
```

## 实施步骤

1. 修改 `app4/core/downloader.py` 中的 `download_single_stock()` 方法
2. 修改 `app4/core/pagination.py` 中的 `generate_stock_params()` 方法
3. 测试各接口：
   ```bash
   python app4/main.py --interface disclosure_date --ts_code 000001.SZ
   python app4/main.py --interface dividend --ts_code 000001.SZ
   python app4/main.py --interface pledge_detail --ts_code 000001.SZ
   python app4/main.py --interface pledge_stat --ts_code 000001.SZ
   python app4/main.py --interface stk_rewards --ts_code 000001.SZ
   python app4/main.py --interface top10_holders --ts_code 000001.SZ
   ```

## 预期结果

修复后，各接口应该：
- 只传递配置中定义的参数
- 不再强制添加不支持的 `start_date`/`end_date`
- 正确返回数据（而非0条）
