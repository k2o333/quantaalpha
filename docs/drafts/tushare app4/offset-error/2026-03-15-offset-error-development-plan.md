# reverse_date_range / offset / date_anchor 开发方案

## 背景

当前 `reverse_date_range` 接口在使用 `start_date/end_date` 作为一个跨多日窗口时，如果窗口内触发了 offset 分页，中途报错会有两层风险：

1. 非原子 offset 会把当前窗口的部分页数据提前保存。
2. 即使 offset 改为原子提交，如果当前窗口本身覆盖多个交易日，那么它只能保证“窗口原子”，不能保证“单日原子”。

因此需要明确区分两个目标：

- `commit_on_success: true` 解决“当前 offset 窗口不保存半截数据”。
- `is_date_anchor: true` 解决“每个 offset 窗口只对应单个日期，从而不出现某个日期不完整”。

## 当前代码行为确认

### 1. 非原子 offset 确实会保存半截数据

`app4/core/pagination_executor.py` 中：

- `commit_on_success=false` 时，`on_data_ready` 会按页回调。
- `save_callback` 模式下，达到阈值会提前保存。
- 异常分支还会把当前 `all_data` 再保存一次。

结论：当前实现下，跨日期窗口一旦 offset 中断，保存结果中很可能包含某个日期的不完整数据。

### 2. 原子 offset 只能保证窗口完整

`commit_on_success=true` 时，当前 offset 窗口数据会先留在内存，只有整窗成功后才提交。

结论：如果一个窗口是 `20240101 ~ 20240131`，即使开启原子 offset，也只是保证“这 31 天一起成功或一起失败”；它不能保证“31 天中的每一天都独立原子”。

### 3. 已有 date_anchor 能力可直接复用

`app4/core/pagination.py` 已经支持：

- `reverse_date_range + is_date_anchor=true`
- 将 `start_date/end_date` 拆为逐日锚点请求
- 再在单日请求内部应用 offset

这正是“单日原子”的基础能力，不需要重写核心流程。

## 最终设计原则

最终方案不是只做一项，而是两项同时做：

1. 所有启用了 offset 的接口都开启 `commit_on_success: true`
2. 所有需要保证“日期完整性”的高密度日频接口都改为 `is_date_anchor: true`

只有同时满足这两点，才能实现：

- 某一天数据要么完整保存
- 要么整天都不保存
- 不会落入“某天只保存了 offset 前几页”的脏数据状态

## 接口改造策略

### A 类：必须改为 date_anchor 的接口

适用标准：

- `pagination.mode = reverse_date_range`
- 会触发 offset，或单日数据量接近/超过接口 limit
- 数据语义要求“某个交易日必须完整”
- 典型参数是 `trade_date`、`ann_date`

建议优先纳入：

- `daily.yaml`
- `daily_basic.yaml`
- `moneyflow.yaml`
- `moneyflow_dc.yaml`
- `moneyflow_cnt_ths.yaml`
- 其他单日全市场高密度接口

改法：

- 给日期参数增加 `is_date_anchor: true`
- 保持 `mode: reverse_date_range`
- offset 下增加 `commit_on_success: true`

示例：

```yaml
pagination:
  enabled: true
  mode: reverse_date_range
  window_size_days: 1
  offset:
    enabled: true
    limit: 6000
    commit_on_success: true

parameters:
  trade_date:
    description: 交易日期 YYYYMMDD
    required: false
    type: string
    is_date_anchor: true
```

### B 类：保留 date range，但必须开启原子 offset 的接口

适用标准：

- 数据较稀疏
- 单日通常远小于 limit
- 如果强制改成逐日锚点，会产生大量空请求

建议保留 range 的接口类型：

- `repurchase.yaml`
- `stock_st.yaml`
- `suspend_d.yaml`
- `namechange.yaml`
- `block_trade.yaml`
- 其他事件型、公告型、稀疏分布接口

改法：

- 不加 `is_date_anchor`
- 保持原来的 `start_date/end_date + window_size_days`
- 只补 `pagination.offset.commit_on_success: true`

这样可以保证“当前窗口不落半截数据”，同时避免大量无效逐日请求。

## 具体开发任务

### 任务 1：补齐 offset 原子提交配置

扫描 `app4/config/interfaces` 下所有：

- `pagination.mode = reverse_date_range`
- `pagination.offset.enabled = true`

统一补充：

```yaml
pagination:
  offset:
    commit_on_success: true
```

说明：

- 代码已经支持该配置，无需先改 core。
- 这是最低风险、收益最高的一步。

### 任务 2：给高密度日频接口增加 `is_date_anchor: true`

对确认属于 A 类的接口，在日期参数上增加：

- `trade_date.is_date_anchor: true`
- 或 `ann_date.is_date_anchor: true`

注意：

- 只允许一个参数作为 date anchor。
- 如果接口已有 `start_date/end_date`，保留它们用于用户输入范围，运行时由分页器拆成单日锚点。

### 任务 3：复核覆盖率与缺口检测行为

需要确认改成 `is_date_anchor` 后：

- 覆盖率检测走 `date_anchor` 策略
- 缺口检测不会把单日任务误判为已完成
- 重跑时会正确重试失败日期

该部分大概率不需要改代码，但必须在测试里验证。

### 任务 4：更新设计说明文档

需要在后续正式文档中明确两条定义：

- `commit_on_success` 是“窗口原子”
- `is_date_anchor + commit_on_success` 才是“单日原子”

否则工程师容易误以为只开原子 offset 就足够。

## 不建议的方案

### 1. 不建议只开 `commit_on_success`

原因：

- 只能防止“当前窗口半截保存”
- 不能防止“一个多日窗口内部某个日期被截断”

### 2. 不建议把所有 reverse_date_range 全量改成 date_anchor

原因：

- 稀疏接口会被拆成大量空请求
- 会增加接口耗时、积分消耗和限流风险

## 预期结果

改造完成后，系统行为应变为：

1. 高密度日频接口：
   单日请求 + 单日内 offset 原子提交
2. 稀疏接口：
   多日窗口请求 + 窗口内 offset 原子提交
3. 任意 offset 异常：
   当前任务数据不落盘，不进入中间文件，不污染覆盖率判断

## 推荐实施顺序

1. 先补所有 offset 接口的 `commit_on_success: true`
2. 再改高密度接口的 `is_date_anchor: true`
3. 最后执行完整测试，确认没有性能和覆盖率回归

