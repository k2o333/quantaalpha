# QuantaAlpha 终端执行卡死异常分析 (2026-03-21)

## 1. 背景
根据 `20260321_190705.txt` 终端输出日志，系统在执行因子挖掘 (Factor Mining) 的提议 (proposal) 阶段出现了大规模循环刷屏报错，最终导致进程无法继续推进。

经过溯源和分析，此次故障并非单一问题导致，而是由 **三个关联的 Bug** 联动引发的系统级死循环。

---

## 2. 核心 Bug 分析

### Bug 1: 日志方法参数不匹配（底层异常被掩盖）
* **现象**：日志中出现了 `Planning LLM call failed (attempt 1): RDAgentLog.warning() takes 2 positional arguments but 5 were given` 的报错。
* **原因**：当 LLM 请求发生真正的网络错误或 API 异常时，底层的重试与日志捕获逻辑试图通过 `logger.warning(...)` 记录。然而，在传递参数时它使用了类似 `logger.warning(msg, *args)` 的 5 个位置参数，但目前系统内包装的 `RDAgentLog`（或 `_AlphaAgentLoggerWrapper`）的 `warning` 方法签名仅支持 2 个参数（`self` 和 `msg`）。
* **影响**：这引发了 `TypeError`，直接掩盖了 LLM 真实的请求失败原因，阻碍了对网络或鉴权问题的排查。

### Bug 2: LLM 返回空流导致 JSON 解析崩溃
* **现象**：终端中持续打印空的 `Response:`（或只包含换行），紧接着报错 `JSON fix failed: Expecting value: line 1 column 1 (char 0), using raw response`。
* **原因**：LLM 客户端（`codestral-latest` 等模型）在特定请求（如启用了流式输出 `stream=True` 以及强校验 `json_mode=True`）时，出现了返回空内容的情况。在 `quantaalpha.llm.client` 中，程序在尝试提取 JSON 时，使用 `resp[json_start:json_end]`。对于空字符串，截取结果为空 `""`，紧随其后的 `json.loads("")` 必然抛出 `JSONDecodeError`。

### Bug 3: 无限重试导致的死循环（系统卡死的直接原因）
* **现象**：控制台无限刷出 `JSON parse failed: Could not parse JSON; original text length: 0: line 1 column 1 (char 0), retrying...`。
* **原因**：根据近期的代码提交（如：`fix(eva_utils): 修复 JSONDecodeError 未触发重试的问题`），为了提升容错率，开发者将捕获到 JSON 解析错误时的处理方式改为了在 `while True` 循环中 `continue` 以便重试。
* **连锁反应**：当 **Bug 2** 导致模型确定性地返回空响应时，代码 100% 触发 `JSONDecodeError`，进而在 **Bug 3** 的 `while True` 逻辑中陷入无休止的死循环，彻底卡死了因子生成流程。

---

## 3. 修复建议

针对以上问题，建议在不同层级进行如下修复：

1. **补全日志方法签名 (Log Wrapper)**：
   * 修改 `quantaalpha/log/__init__.py` 等处的日志包装器，使其 `warning`、`info`、`error` 等方法能够支持不定长参数 `*args, **kwargs`，确保底层异常信息能被正确捕获打印。

2. **防御性 JSON 解析 (LLM Client)**：
   * 在 `quantaalpha.llm.client` 中提取 JSON 并进行 `loads` 前，增加对空响应或无效格式的特判（例如 `if not resp.strip(): raise Exception(...)`），防止直接向 `json.loads()` 传递空字符串。同时建议排查模型为何返回空结果，必要时降低 `temperature` 或调整 `prompt` 格式。

3. **设置最大重试次数熔断 (Robust Retry)**：
   * 必须移除诸如 `_convert_with_history_limit` 中可能导致死循环的裸 `while True` 结构。引入 `max_retries` 计数器，一旦尝试解析 JSON 的次数达到上限（如 3-5 次），应当抛出异常中断当前方向的探索，而不是无限制消耗资源和时间。
