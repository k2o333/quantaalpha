# 关于 reverse_date_range 接口改用 is_date_anchor 的需求评估与分析

## 1. 现状验证：Offset 发生异常时的保存逻辑

目前，在 `PaginationExecutor._execute_single_request` 核心分页执行逻辑中，如果在 Offset 翻页拉取数据的过程中遇到网络超时或 API 报错（中断），系统的处理逻辑如下：

* **默认情况（非原子提交，`commit_on_success: false`）**：如果在异常发生前，`all_data` 中已经堆积了部分该次请求的结果（且未达到批量保存的阈值 `batch_threshold=50000`），或者之前已经保存了若干批次，系统在捕获到 `RuntimeError` 时，**会执行一次 `save_callback`，将这部分未完成的残缺数据持久化落盘**。
* **数据截断问题**：因为大多数接口的返回结果是按日期倒序排列的。如果使用 `start_date` 和 `end_date` 作为跨越多个交易日的分页参数（比如 `window_size_days: 365`），一次查询涵盖了一年。当 Offset 在某个随机位置中断时，断点极有可能卡在**某一个交易日的数据中间**。
* **导致的影响**：正如您所担忧的，这会导致某一个交易日的数据**入库不完整**。而且因为目前 Coverage Manager 对于非 `date_anchor` 接口是通过全局日期范围或自动机制来判断覆盖，这部分残留的不完整交易日数据将会成为“脏数据”，并在下次重试由于部分数据已存在导致数据混乱，或者被误认为该区间已获取而跳过。

## 2. 需求评估：全量改为 `is_date_anchor` 是否合理？

您的提议：“把 `reverse date range` 的接口都改为 `is date anchor`，这样即使触发 Offset，也是按天拉取。然后保证 Offset 中间出现 Error 的数据都不保存。”

**此方案精准地抓住了原子性问题，但需要针对“高密度”和“低密度”两种接口区分对待，不可一刀切全量强改。**

### 🟢 场景 A：高密度数据接口（强烈推荐改成 `is_date_anchor`）
* **代表接口**：`daily.yaml`、`daily_basic.yaml`、`moneyflow.yaml`、`stk_factor_pro.yaml` 等。
* **特点**：单日数据条数庞大（每天 5000+ 条记录），刚好接近或超出单次 API 拉取的 `limit` (通常限制在 5000~6000)。
* **优势**：
  1. 改为 `is_date_anchor: true` 后，系统按独立的交易日进行参数构造拉取，相当于天然的 `window_size_days: 1`。
  2. 若配合 `commit_on_success: true`，在拉取某交易日（如 `20240315`）时，若 Offset 分页中断，则直接**丢弃这一天所有的片段数据**，完全不在数据库保留残缺记录。
  3. 下次启动时，由于该交易日在数据库里一条记录都没有，引擎会自动重试拉取这完整的 1 天，完美保证了单日数据的完整性与原子性。
  4. **API 请求次数成本评估**：因为这类接口本来单日数据量就很大，无论是用 1 年范围窗口还是 1 天 `date_anchor` 窗口，拉取同样多的数据消耗的 API 分页请求次数几乎相同。因此改成 `is_date_anchor` **极其合理且没有副作用**。

### 🔴 场景 B：低密度/稀疏数据接口（不推荐改成 `is_date_anchor`）
* **代表接口**：`namechange.yaml`、`block_trade.yaml` (大宗交易)、`suspend_d.yaml` (停复牌)、`repurchase.yaml` 等。
* **特点**：单日数据极少，可能几天才有一条，或者全国市场一天由于触发相关事件只有不到 100 条记录。
* **劣势 (API Quota 浪费严重)**：
  如果将这些稀疏接口强行改为 `is_date_anchor`，哪怕过去 1 年里总共只有 500 条数据（原本用 `start_date/end_date` 只需 1 次 API Request 即可拉完并完成 Offset），也会被强制拆分成按约 250 个交易日循环去逐日查询，这意味着系统会盲目**发起 250 次大部分为空的 API 请求**。这不仅极大拖慢了数据同步速度，还会造成 Tushare **积分消耗浪费和极其容易触发接口每分钟的限流（Rate Limit 触发）**。

## 3. 具体修改建议

为了既能实现“**不保留不完整的交易日数据**”，又能兼顾“**不浪费稀疏接口的 API 请求额度**”，建议采取以下混合策略：

1. **针对高密度每日行情/指标接口：在 YAML 显式启用 Date Anchor**
   * 筛选每天全量 A 股都存在的接口数据（如 `daily`, `daily_basic`, `moneyflow` 等）。
   * 把查日期的参数（通常是 `trade_date`）加上 `is_date_anchor: true`。
   * 同时保留 `reverse_date_range` 模式机制。

2. **核心机制升级保底：所有支持 Offset 的接口强制启用 `commit_on_success: true`**
   不论接口是高密度用 `is_date_anchor`，还是低密度保持用 `window_size_days: 365` 的范围查询，只要涉及 `offset` 翻页，我们需要：
   * 在这些接口 YAML 的 `pagination.offset` 节点下，显式写入 `commit_on_success: true`。（或者直接修改 `core` 逻辑把默认值调整为 `True`）。
   * **作用原理**：对于一年的范围稀疏数据窗口（比如大宗交易拉 2023 全年），如果在执行中途第二个 Offset 报错崩溃，因为开启了原子提交 `commit_on_success`，引擎会**直接丢弃这 1 年已经下回来的所有前置页数据（丢弃在内存的 `all_data` 数组），且阻断它们落盘保存**。因为是稀疏数据，丢弃重拉 1 年的代价极小（只有几次 API 请求），但却完美根治了“由于中断，落盘数据中出现了单日截断”这一数据污染顽疾。

### 修改范例：高密度接口推荐配置
```yaml
pagination:
  enabled: true
  mode: reverse_date_range    
  offset:
    enabled: true
    limit: 6000
    commit_on_success: true   # <---- 核心：异常时放弃所有当前时间块的内存数据，不触发 save_callback
parameters:
  trade_date:
    is_date_anchor: true      # <---- 仅对高密度日频接口添加，使时间块精确到单日
```

**结论汇报**：您的思路非常清晰且针对痛点。但是不用全局“一刀切”。只要我们在高密度接口应用您的 `is_date_anchor` 想法，并且配合在所有 Offset 中全面开启 `commit_on_success: true`，就能完美实现“即使中断也不产生中间截断脏数据”的初衷，且保持现有稀疏接口的高效拉取速度。
