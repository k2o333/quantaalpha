---
doc_type: change
module: app4
status: archived
owner: quan
created: 2026-03-06
updated: 2026-03-06
summary: API重试与多阶段保存需求方案
---

# API重试与多阶段保存需求方案

## 1. 背景与问题描述
根据日志和代码分析，当前系统在处理下载任务时存在以下问题：
1. **API逻辑错误无重试机制且导致数据截断**：
   对于如“查询数据失败，请确认参数！”这类API逻辑错误（即HTTP Response 200，但业务 `code != 0` 且非限流错误），当前 `downloader._make_request` 方法会直接记录Error并返回空列表 `[]`。
   返回空列表会导致 `pagination_executor._execute_single_request` 误以为当前分页已经结束（无更多数据），从而提前终止 Offset 分页，并返回目前部分下载的数据。这甚至会被上层 `UpdateManager` 认为是 `SUCCESS`。
2. **缺乏细粒度的批次保存**：
   在 Offset 分页模式下（如 `daily_basic` 每次下载 6000 条，总计上百页），当前代码将所有页的数据积压在内存中（`all_data` 列表），直到全部分页结束才进行一次性保存。
   如果中途崩溃或被终止，之前下载的所有分页数据将全部丢失。
3. **`is_date_anchor` 日期锚点错误跳过策略**：
   在 `reverse_date_range` + `is_date_anchor` 模式下（每日一个请求），如果单日API请求因为上述逻辑错误返回 `[]`，调度器会错误地认为该日无数据，直接跨越到倒序的下一日，导致该日数据被悄无声息地遗漏。

## 2. 需求分析
1. **统一重试机制 (10次重试法则)**：
   针对所有非成功的API返回（逻辑错误、网络错误），需实现10次重试机制：
   - 第 1~3 次重试：每次间隔 10 秒；
   - 第 4~10 次重试：每次间隔 60 秒（1分钟）；
   - 如果 10 次重试均失败，则视为彻底失败，必须保存已下载的分页数据，随后抛出异常，中断所属接口的更新。
2. **每50页批次多阶段保存**：
   在 Offset 分页的大循环中，需要引入批次切分概念：
   每下载完成 50 个分页，必须立即将当前内存中累积的这 50 页数据执行去重并持久化保存。保存后清空这部分内存，继续后续分页请求。
3. **彻底失败时的数据兜底**：
   若某次请求在10次重试后依旧报错，需在抛出异常令程序中止前，把当前内存中未满50页的剩余数据进行保存。

## 3. 技术实施方案

### 3.1 改造 `downloader._make_request` 
修改其中针对重试与异常处理的部分：
- 移除原有的 `if attempt < max_retries` 和指数退避代码；
- 新设独立常量或策略：`max_retries = 10`；
- 构建延时函数：`delay = 10` 如果 `attempt <= 2`（代表第1、2、3次重试，因为attempt从0开始），否则 `delay = 60`；
- 所有API Error（`code != 0` 的业务错误）及 `requests.exceptions` 网络错误统一走上述重试逻辑。
- 10次全部尝试完毕依然失败时，**不再返回 `[]`，而是抛出明确的 `MaxRetryError` 异常**。这能防止上层误判为“无数据”。

### 3.2 改造 `pagination_executor._execute_single_request`
实现每50页的阶段性保存以及异常兜底策略：
- 方法签名新增参：传入 `save_callback` 以防上游未传入；
- 在 `while True:` 循环内累加 `all_data` 并监控 `page_num`；
- 每当 `page_num % 50 == 0` 时，调用 `save_callback(interface_name, all_data)`，并将 `all_data.clear()` 以释放内存；
- 若调用的 `make_request` 抛出 `Exception`（包含前述的重试超限异常）：
  通过 `try...except` 捕获该异常，在 except 块中执行一次 `save_callback`（将已积攒在 `all_data` 中的残余数据保存），然后**再次 `raise`** 把异常抛给更上层；
- `is_date_anchor` 中的跨日期跳过问题，因为现在 `_make_request` 抛出了异常，上层循环 `_execute_sequential` 会被迫中断，从而阻止了错误跳过至下一日的现象发生。

### 3.3 对接与兼容
利用已有的 `storage_manager.save_data(..., async_write=True)`，该底层存储层本身调用了 DataFrame 的去除重复项防腐层机制（即 Processor 和 Storage 环节里的 `_remove_duplicates`），从而自然满足了“批次内去重”的要求。
对于现有接口如 `on_data_ready` 流式回调的兼容性，由于其本身就是按页进行处理的，不受 50 页汇聚逻辑的负面影响，只需区分处理即可。
