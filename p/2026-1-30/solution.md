# 6个接口参数不匹配问题解决方案

## 问题

代码强制传递 `start_date` 和 `end_date` 给所有接口，但以下6个接口的配置不支持这些参数：

| 接口 | 配置定义 | 代码强制传递 | 结果 |
|------|---------|-------------|------|
| disclosure_date | 无start_date，end_date=财报周期 | start_date + end_date | 返回0条 |
| dividend | 无日期范围参数 | start_date + end_date | 返回0条 |
| pledge_detail | 只有ts_code | start_date + end_date | 参数被忽略 |
| pledge_stat | 无start_date，end_date=截止日期 | start_date + end_date | 返回0条 |
| stk_rewards | 无start_date，end_date=报告期 | start_date + end_date | 返回0条 |
| top10_holders | 使用period参数 | start_date + end_date | 参数被忽略 |

## 根因

`app4/core/downloader.py:442-448` 无条件添加 start_date/end_date：

```python
# 设置日期范围
if 'start_date' not in stock_params:
    stock_params['start_date'] = list_date
if 'end_date' not in stock_params:
    stock_params['end_date'] = datetime.now().strftime('%Y%m%d')
```

## 解决方案

修改 `app4/core/downloader.py`，在 `download_single_stock()` 方法中根据接口配置过滤参数：

```python
# 根据接口配置过滤参数 - 只保留接口支持的参数
supported_params = interface_config.get('parameters', {})
if supported_params:
    supported_keys = set(supported_params.keys())
    supported_keys.add('ts_code')
    stock_params = {k: v for k, v in stock_params.items() if k in supported_keys}

# 设置日期范围（仅当接口支持时）
if 'start_date' in supported_params and 'start_date' not in stock_params:
    stock_params['start_date'] = stock.get('list_date', '20050101')
if 'end_date' in supported_params and 'end_date' not in stock_params:
    stock_params['end_date'] = datetime.now().strftime('%Y%m%d')
```

## 修改位置

文件：`app4/core/downloader.py`
行号：437-448

## 测试

```bash
python app4/main.py --interface disclosure_date --ts_code 000001.SZ
```

预期：能正确返回数据（而非0条）
