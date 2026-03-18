# Offset 分页错误处理分析

## 问题背景

对于 `reverse_date_range` 模式的接口（从最新日期往历史日期倒序下载），由于某些接口数据量较大（如日线行情），需要使用 offset 分页才能获取完整数据。

### 当前问题

当接口同时满足以下条件时：
1. 使用 `reverse_date_range` 分页模式
2. 启用了 offset 分页（`offset.enabled: true`）
3. 数据量大，单次请求无法获取完整数据

如果在 offset 分页过程中发生错误，会导致：
- **当前交易日的数据不完整**：已下载的部分 offset 数据会被保存到存储
- **数据质量问题**：缺失的记录无法通过增量更新补全（因为覆盖检测会认为已覆盖）

### 代码证据

位置：`app4/core/pagination_executor.py:501-513`

```python
except RuntimeError as e:
    if commit_on_success and all_data:
        # 原子模式：丢弃残留数据
        logger.warning(f"[{interface_name}] Offset分页异常，丢弃...")
    elif save_callback and all_data:
        # 非原子模式（默认）：保存残留数据
        save_callback(interface_name, all_data)
        logger.warning(f"[{interface_name}] 异常中断，已保存 {len(all_data)} 条残留数据")
```

**关键点**：默认 `commit_on_success=False`，所以中断时会保存已下载的数据。

## 当前接口分类

### 已有 is_date_anchor=true（4个）
| 接口 | 锚点参数 |
|------|----------|
| dividend | ann_date |
| cyq_perf | trade_date |
| stk_managers | trade_date |
| stk_rewards | ts_code |

### 没有 is_date_anchor 的 reverse_date_range 接口（19个）

| 接口 | 说明 |
|------|------|
| daily | 日线行情 |
| daily_basic | 日线行情基础数据 |
| moneyflow | 资金流向 |
| suspend_d | 停牌信息 |
| block_trade | 大宗交易 |
| report_rc | 研究报告 |
| stock_st | ST股票 |
| stk_surv | 调研信息 |
| stk_holdertrade | 股东增减持 |
| moneyflow_mkt_dc | 资金流向(北向) |
| moneyflow_cnt_ths | 资金流向(龙虎榜) |
| moneyflow_dc | 资金流向(单股) |
| moneyflow_ind_dc | 行业资金流向(单北) |
| moneyflow_ind_ths | 行业资金流向(同花顺) |
| moneyflow_ths | 资金流向(同花顺) |
| namechange | 名称变更 |
| share_float | 限售股解禁 |
| repurchase | 股票回购 |
| new_share | 新股上市 |
| stk_factor_pro | 股票因子 |

## 解决方案

### 方案：将 reverse_date_range 接口改为 is_date_anchor

**原理**：
- `is_date_anchor=true` 的接口，reverse_date_range 会按"锚点日期"逐日请求
- 每次请求都是**独立的交易日**，offset 分页只在该交易日内部生效
- 即使某天出错，也只是那一天的该只/多只股票数据不完整，不会影响其他交易日

**优势**：
1. 错误隔离在单个交易日，不会导致跨日数据污染
2. 增量更新时可以检测并补全缺失的交易日数据
3. 简化错误处理逻辑

### 方案二：配合 commit_on_success=true

对于确实需要跨日 offset 的接口（极少），设置：
```yaml
pagination:
  offset:
    enabled: true
    limit: 10000
    commit_on_success: true  # 新增：完整成功才提交
```

这样 offset 中间出错会**丢弃残留数据**，不写入半截结果。

## 推荐做法

1. **首选**：将所有 reverse_date_range 接口改为 is_date_anchor
   - 对于有明确日期锚点参数（如 trade_date, ann_date）的接口，配置 `is_date_anchor: true`
   - 对于使用 start_date/end_date 的接口，可以选择其中一个作为锚点

2. **可选**：对于必须使用跨日 offset 的接口，设置 `commit_on_success: true`

## 实施步骤

1. 识别19个需要添加 is_date_anchor 的接口
2. 确定每个接口的锚点参数：
   - 有 trade_date 参数 → trade_date 作为锚点
   - 有 ann_date 参数 → ann_date 作为锚点
   - 只有 start_date/end_date → 选择 end_date 作为锚点（因为是反向遍历）
3. 修改 YAML 配置文件，添加 `parameters.xxx.is_date_anchor: true`
4. 验证下载逻辑正确性
