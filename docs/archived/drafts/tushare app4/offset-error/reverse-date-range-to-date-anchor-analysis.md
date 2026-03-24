# Reverse Date Range 接口改为 Date Anchor 模式分析

## 问题背景

`reverse_date_range` 模式的接口，部分是 `is_date_anchor`，部分不是。非 `is_date_anchor` 的接口如果有 `start_date/end_date` 参数，配合 offset 分页时存在问题：

**问题场景**：
- 请求 `start_date=20250101, end_date=20250110` 的数据
- offset 分页到第 3 页时出错中断
- 已保存的数据：这 10 天内只有部分股票的数据
- **结果**：某个交易日的数据不完整（只有部分股票）

## 用户提出的方案

将 `reverse_date_range` 的接口都改为 `is_date_anchor` 模式：
- 每次请求只针对**单个日期**（如 `trade_date=20250101`）
- offset 分页出错时，只影响那一天的数据
- 结合 `commit_on_success`，保证"要么完整，要么没有"

## 代码验证

### 异常处理逻辑 (pagination_executor.py:501-514)

```python
except RuntimeError as e:
    # 原子提交模式下丢弃当前窗口残留数据，避免写入半截结果
    if commit_on_success and all_data:
        logger.warning(
            f"[{interface_name}] Offset分页异常，丢弃当前窗口已下载的 "
            f"{len(all_data)} 条未完整数据"
        )
    # 非原子模式保持原有行为
    elif save_callback and all_data:
        save_callback(interface_name, all_data)  # ← 这里会保存不完整数据
        logger.warning(
            f"[{interface_name}] 异常中断，已保存 {len(all_data)} 条残留数据"
        )
```

**结论**：
- 没有 `commit_on_success: true` 时，中断**确实会保存已下载的不完整数据**
- 这验证了用户的担忧

## 当前 reverse_date_range 接口分类

### A. 已设置 is_date_anchor: true（正确示例）

| 接口 | date anchor 参数 |
|-----|-----------------|
| cyq_perf.yaml | trade_date |
| stk_factor_pro.yaml | trade_date |
| dividend.yaml | (已设置) |
| stk_managers.yaml | (已设置) |
| stk_rewards.yaml | (已设置) |

### B. 未设置 is_date_anchor（需要改的）

以下接口有 `trade_date` 参数但未标记 `is_date_anchor`：

| 接口文件 | 备注 |
|---------|-----|
| daily.yaml | window_size_days: 1 |
| daily_basic.yaml | window_size_days: 1 |
| repurchase.yaml | |
| moneyflow.yaml | |
| moneyflow_ths.yaml | |
| moneyflow_dc.yaml | |
| moneyflow_ind_dc.yaml | |
| moneyflow_ind_ths.yaml | |
| moneyflow_mkt_dc.yaml | |
| moneyflow_cnt_ths.yaml | |
| namechange.yaml | |
| new_share.yaml | |
| share_float.yaml | |
| stock_st.yaml | |
| suspend_d.yaml | |
| block_trade.yaml | |
| report_rc.yaml | |
| stk_surv.yaml | |
| stk_holdertrade.yaml | |

## 方案可行性分析

### 1. API 是否支持单日期查询？

检查 `daily` 接口参数：
```yaml
trade_date:
  description: 交易日期 YYYYMMDD
  required: false
```
**支持**，可以传单个 `trade_date`。

### 2. window_size_days: 1 的接口行为变化

像 `daily.yaml` 已经设置了 `window_size_days: 1`，改为 `is_date_anchor` 后：
- 行为基本一致（每天一个请求）
- 参数形式从 `start_date=20250101&end_date=20250101` 变为 `trade_date=20250101`

### 3. 改动方案

对于支持 `trade_date` 参数的接口，改动很简单：

```yaml
# 修改前
trade_date:
  description: 交易日期 YYYYMMDD
  required: false
  type: string

# 修改后
trade_date:
  description: 交易日期 YYYYMMDD
  required: false
  type: string
  is_date_anchor: true  # 添加这行
```

同时建议添加 `commit_on_success` 配置：

```yaml
pagination:
  enabled: true
  mode: reverse_date_range
  window_size_days: 1
  offset:
    enabled: true
    limit: 10000
    commit_on_success: true  # 添加这行
```

## 结论

**用户的方案是合理的**，建议采纳：

1. 对支持单日期参数的 `reverse_date_range` 接口，添加 `is_date_anchor: true`
2. 配置 `commit_on_success: true` 保证原子性
3. 这样 offset 出错时，只会丢弃当前日期的不完整数据，不会影响其他日期

## 需要注意的点

1. **部分接口可能不支持单日期查询**：需要确认 Tushare API 是否支持 `trade_date` 参数
2. **性能影响**：改为逐日请求后，请求数量会增多，但 `window_size_days: 1` 的接口本身已经是逐日请求
3. **已有数据的兼容性**：改动后不影响已下载的数据，只是下载方式变化

---

*分析日期: 2026-03-15*
