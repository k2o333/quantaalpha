# 6个接口参数不匹配问题修复

## 问题

| 接口 | 配置定义 | 代码强制传递 | 结果 |
|------|---------|-------------|------|
| disclosure_date | 无start_date，end_date=财报周期 | start_date + end_date | 查询未来日期，返回0条 |
| dividend | 无start_date，无end_date | start_date + end_date | 参数被忽略，返回0条 |
| pledge_detail | 只有ts_code | start_date + end_date | 参数被忽略 |
| pledge_stat | 无start_date，end_date=截止日期 | start_date + end_date | 查询未来日期，返回0条 |
| stk_rewards | 无start_date，end_date=报告期 | start_date + end_date | 查询未来日期，返回0条 |
| top10_holders | 无start_date，使用period | start_date + end_date | 使用默认period，参数被忽略 |

## 根因

`app4/core/downloader.py:442-448` 强制添加 start_date/end_date，不考虑接口实际支持的参数。

## 修复

修改 `app4/core/downloader.py` 的 `download_single_stock()` 方法（第437行开始）：

```python
# 原始代码：
stock_params = params.copy()
stock_params['ts_code'] = stock['ts_code']

# 设置日期范围
if 'start_date' not in stock_params:
    list_date = stock.get('list_date', '20050101')
    stock_params['start_date'] = list_date
if 'end_date' not in stock_params:
    from datetime import datetime
    stock_params['end_date'] = datetime.now().strftime('%Y%m%d')
```

替换为：

```python
stock_params = params.copy()
stock_params['ts_code'] = stock['ts_code']

# 根据接口配置过滤参数 - 只保留接口支持的参数
supported_params = interface_config.get('parameters', {})
if supported_params:
    supported_keys = set(supported_params.keys())
    supported_keys.add('ts_code')
    stock_params = {k: v for k, v in stock_params.items() if k in supported_keys}

# 设置日期范围（仅当接口支持时）
if 'start_date' in supported_params and 'start_date' not in stock_params:
    list_date = stock.get('list_date', '20050101')
    stock_params['start_date'] = list_date
if 'end_date' in supported_params and 'end_date' not in stock_params:
    from datetime import datetime
    stock_params['end_date'] = datetime.now().strftime('%Y%m%d')
```

## 各接口支持的参数

- **disclosure_date**: ts_code, end_date(财报周期), pre_date, actual_date, ann_date
- **dividend**: ts_code, ann_date, ex_date, record_date, imp_ann_date
- **pledge_detail**: ts_code
- **pledge_stat**: ts_code, end_date(截止日期)
- **stk_rewards**: ts_code, end_date(报告期)
- **top10_holders**: ts_code, period

## 测试

```bash
python app4/main.py --interface disclosure_date --ts_code 000001.SZ
python app4/main.py --interface dividend --ts_code 000001.SZ
python app4/main.py --interface pledge_detail --ts_code 000001.SZ
python app4/main.py --interface pledge_stat --ts_code 000001.SZ
python app4/main.py --interface stk_rewards --ts_code 000001.SZ
python app4/main.py --interface top10_holders --ts_code 000001.SZ
```
