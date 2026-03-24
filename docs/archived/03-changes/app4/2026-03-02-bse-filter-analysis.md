---
doc_type: change
module: app4
status: archived
owner: quan
created: 2026-03-02
updated: 2026-03-02
summary: 北交所股票过滤问题分析
---

# 北交所股票过滤问题分析

## 症状

运行 `python app4/main.py --update --update-group stock_loop` 时，`fina_audit` 接口会下载北交所股票数据，而其他接口（如 `top10_holders`）只下载沪深两地交易所的股票。

### 数据验证

```
=== stock_basic 数据分析 ===
总记录数: 5484

交易所后缀分布:
┌─────────────────┬──────┐
│ exchange_suffix ┆ len  │
├─────────────────┼──────┤
│ SZ              ┆ 2883 │  # 深交所
│ SH              ┆ 2307 │  # 上交所
│ BJ              ┆ 294  │  # 北交所
└─────────────────┴──────┘
```

## 根本原因

**代码中没有过滤北交所（BSE/BJ）股票的逻辑。**

### 为什么有些接口只下载沪深，而 fina_audit 下载北交所？

关键区别在于 **Tushare API 行为**，而不是代码过滤：

| 接口类型 | 分页模式 | API 行为 |
|---------|---------|---------|
| `top10_holders`, `top10_floatholders` 等 | `period_range` | Tushare API 本身不支持北交所数据，即使传入北交所股票代码也返回空 |
| `fina_audit` | `stock_loop` | Tushare API 支持北交所股票的审计意见数据，所以会返回数据 |

### 代码流程

1. `update_manager.py:451` 调用 `self.downloader._get_stock_list()` 获取股票列表
2. `_get_stock_list()` 从 `stock_basic` 数据获取所有股票，**没有任何交易所过滤**
3. 对于 `stock_loop` 模式接口，会遍历所有 5484 只股票（包括北交所的 294 只）
4. API 是否返回数据取决于接口本身是否支持北交所

### 问题代码位置

`app4/core/downloader.py` 第 283-316 行：

```python
def _get_stock_list(self) -> Optional[List[Dict[str, Any]]]:
    """获取股票列表的统一方法"""
    # 从内存缓存获取
    stock_list = self._get_stock_list_from_memory_cache()

    if stock_list is None:
        logger.info("内存中未找到股票列表，正在从Data目录获取...")
        stock_list = self._get_stock_list_from_data_dir()

    if stock_list is None:
        logger.info("Data目录中未找到股票列表，正在从API获取...")
        stock_params = {"list_status": "L"}
        stock_list = self._make_request(
            self.config_loader.get_interface_config("stock_basic"), stock_params
        )
        # ... 保存逻辑
    # ❌ 没有过滤北交所的逻辑
    return stock_list
```

## 影响范围

| 分页模式 | 接口数量 | 是否使用股票列表 | 是否受过滤影响 |
|---------|---------|----------------|--------------|
| `stock_loop` | 4 个 | ✓ 是 | ✓ 会过滤北交所 |
| `period_range` | 11 个 | ✓ 是 | ✓ 会过滤北交所 |
| `reverse_date_range` | 22 个 | ✗ 否 | ✗ 不受影响 |
| `date_range` | 1 个 | ✗ 否 | ✗ 不受影响 |
| `offset` | 2 个 | ✗ 否 | ✗ 不受影响 |
| `type_split` | 1 个 | ✗ 否 | ✗ 不受影响 |
| `no_pagination` | 1 个 | ✗ 否 | ✗ 不受影响 |

## 解决方案

在 `_get_stock_list()` 方法中添加北交所过滤逻辑：

```python
def _get_stock_list(self) -> Optional[List[Dict[str, Any]]]:
    """获取股票列表的统一方法"""
    # ... 现有获取逻辑 ...

    # 过滤北交所股票（只保留沪深交易所）
    if stock_list:
        original_count = len(stock_list)
        stock_list = [
            stock for stock in stock_list
            if not stock.get('ts_code', '').endswith('.BJ')
        ]
        filtered_count = original_count - len(stock_list)
        if filtered_count > 0:
            logger.info(f"过滤北交所股票: {filtered_count} 只，保留沪深股票: {len(stock_list)} 只")

    return stock_list
```

### 修改位置

文件：`app4/core/downloader.py`

在 `_get_stock_list()` 方法的 return 语句前添加过滤逻辑。
