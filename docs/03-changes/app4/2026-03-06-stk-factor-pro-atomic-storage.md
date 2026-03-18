# stk_factor_pro 原子化存储修复

> 修复日期：2026-03-06

## 问题现象

运行 `--update --interface stk_factor_pro` 时：

1. **没有原子化存储**：每个交易日的 offset 分页完成后不会立即保存，而是把所有交易日的数据全部下载完才一次性保存
2. **出现大量 0 记录下载**：部分 `trade_date` 请求返回 0 条记录（待后续排查）

## 根因分析

### Bug 1：并发路径判断使用了未迁移的原始配置

`pagination_executor.py` 的 `execute()` 方法调用 `_should_use_concurrency(interface_config)` 判断是否走并发。该方法检查：

```python
time_range = pagination.get("time_range", {})
if time_range.get("reverse", False) and time_range.get("stop_on_empty", 0) > 0:
    return False  # 不并发
return name not in NON_CONCURRENT_INTERFACES
```

但传入的 `interface_config` 是**原始 YAML 配置**。`stk_factor_pro.yaml` 的分页配置为：

```yaml
pagination:
  mode: reverse_date_range  # 旧格式，没有 time_range 字段
  window_size_days: 1
```

原始配置没有 `time_range` 键 → `reverse` 判断失败 → 返回 `True` → **错误地走了 `_execute_concurrent`**。

而 `_execute_concurrent` 没有 `save_callback` 支持，所以数据全部累积在 `all_data` 列表中，最终由 `_execute_download` 一次性保存。

### Bug 2：save_callback 仅对 period_range 模式生效

`_execute_sequential` 方法原本没有 `save_callback` 参数，即使走了顺序执行也不会逐次保存。`save_callback` 仅在 `_execute_period_range_sequential` 中使用。

## 修复内容

文件：`app4/core/pagination_executor.py`

### 改动 1：save_callback 存在时强制顺序执行

```python
# 改动前
if self._should_use_concurrency(interface_config):
    return self._execute_concurrent(...)
else:
    return self._execute_sequential(...)

# 改动后
if save_callback or not self._should_use_concurrency(interface_config):
    return self._execute_sequential(..., save_callback)
else:
    return self._execute_concurrent(...)
```

### 改动 2：_execute_sequential 支持逐次保存

新增 `save_callback` 参数，每个参数请求的 offset 分页完成后立即调用保存：

```python
if save_callback:
    save_callback(interface_name, result)
    logger.info(f"[{interface_name}] 已保存 {len(result)} 条记录 (第{idx+1}/{len(params_list)}批)")
```

文件：`app4/update/update_manager.py`

- 更新了 `save_callback` 的注释（原来标注为 period_range 专用，现改为通用）

## 影响范围评估

### 不受影响

| 类型 | 接口示例 | 原因 |
|------|---------|------|
| `period_range` 模式 | 财报类接口 | 在 `execute()` 中提前 return，不经过修改的分支 |
| `offset` 单参数模式 | 简单列表接口 | `params_list <= 1` → `_execute_single` |
| `stock_loop` + `stock_level_detection: true` | cyq_chips, fina_audit, pledge_detail, stk_rewards | 通过 `_execute_gap_task` → `_execute_pagination`，不经过 `_execute_download` |
| 非 update 模式（`main()` 直接下载） | 所有接口 | `_execute_pagination` 不传 `save_callback` |

### 受影响（update 模式，save_callback 存在 → 强制串行 + 逐次保存）

以下接口在 `--update` 模式下，从"可能并发"变为"强制串行 + 逐次保存"：

| 模式 | 接口 |
|------|------|
| `reverse_date_range` + `is_date_anchor` | **stk_factor_pro**（本次修复目标）, cyq_perf |
| `reverse_date_range`（无 date_anchor） | daily_basic, moneyflow, moneyflow_cnt_ths, moneyflow_dc, moneyflow_ind_dc, moneyflow_ind_ths, moneyflow_mkt_dc, moneyflow_ths, block_trade, dividend, namechange, new_share, report_rc, repurchase, share_float, stk_holdertrade, stk_managers, stk_surv, stock_st, suspend_d |
| `date_range` | trade_cal |
| `type_split` | stock_hsgt |

### 实际影响说明

- 这些接口之前因为 `_should_use_concurrency` 检查原始配置（没有 `time_range` 字段），**实际上也是以错误的方式走了并发路径**，并发路径无 `save_callback` 支持
- 改为串行后，行为更正确（逐次保存、连续空数据检测生效）
- 性能影响：串行比并发慢，但受 API rate limit 限制，实际差异不大
- 如需恢复特定接口的并发能力，可在 `_execute_download` 中根据接口类型决定是否传 `save_callback`
