---
doc_type: change
module: quantaalpha
status: done
owner: quan
created: 2026-03-21
updated: 2026-03-22
summary: Root-cause analysis for the 2026-03-21 quantaalpha factor-mining run failure
code_paths:
  - third_party/quantaalpha/quantaalpha/llm/client.py
  - third_party/quantaalpha/quantaalpha/factors/proposal.py
  - third_party/quantaalpha/quantaalpha/pipeline/planning.py
  - third_party/quantaalpha/.env
doc_refs:
  - docs/00-governance/agent.md
  - docs/00-governance/doc-rules.md
  - docs/02-modules/quantaalpha.md
validation:
  - python3 scripts/doc_index.py validate
review_required: false
outcome: accepted
---

# QuantaAlpha 因子挖掘执行问题分析

## Purpose

记录 `2026-03-21` 这次 `quantaalpha` 因子挖掘运行失败的已证实问题、根因链路和后续修复方向。

按 `docs/00-governance/agent.md` 与 `docs/00-governance/doc-rules.md`，这份内容属于 `quantaalpha` 的模块级任务记录，应存放在 `docs/03-changes/quantaalpha/`，而不是继续留在 `docs/drafts/`。

## Scope

- 终端日志：`third_party/facotors/terminal/20260321_190705.txt`
- 执行入口：`third_party/quantaalpha/run.sh`
- 涉及模块：
  - `quantaalpha/llm/client.py`
  - `quantaalpha/factors/proposal.py`
  - `quantaalpha/pipeline/planning.py`

## Final Conclusion

这次失败不是单一问题，而是以下三件事串联造成：

1. 上游 LiteLLM 未为实际调用的模型配置可用 API key，导致部分请求返回空响应或异常响应。
2. `quantaalpha` 在收到空响应后仍继续做 JSON 提取与解析，触发连续 `JSONDecodeError`。
3. `proposal.py` 中的无限重试逻辑把上游故障放大成“终端卡死”。

另外，还有一个独立但重要的问题：

- `RDAgentLog.warning()` 与标准 `logging.warning(msg, *args)` 调用方式不兼容，掩盖了 planning 首次失败时的底层错误细节。

## Evidence Summary

### 1. 终端日志里的直接症状

planning 首次调用先报：

```text
Planning LLM call failed (attempt 1): RDAgentLog.warning() takes 2 positional arguments but 5 were given
```

但随后重试成功，说明 planning 本身不是主卡点。

进入 hypothesis 和 factor proposal 阶段后，日志持续出现：

```text
Response:
JSON fix failed: Expecting value: line 1 column 1 (char 0), using raw response
```

这说明客户端拿到的是空文本或无法提取出有效 JSON 的内容。

### 2. 实际调用路径默认走 reasoning model

`quantaalpha/llm/client.py` 中：

```python
if reasoning_flag:
    model = self.reasoning_model
    json_mode = None
else:
    model = self.get_model_for_task(task_type=task_type, tag=tag)
```

而 hypothesis / proposal 这几条调用链没有显式传 `reasoning_flag=False`，因此默认优先走 `REASONING_MODEL`。

这意味着，原先把主因归结为 `CHAT_MODEL=codestral-latest` 不准确；这次故障更应看作“实际调用到的上游模型不可用”。

### 3. 额外运行证据

后续排查确认：当时 LiteLLM 上游没有为对应模型配置可用 API key，因此模型请求无法正常完成；在切换到可用模型后，后一个终端输出文档不再出现相同问题。

这条证据把根因从“模型可能不适合”提升为“上游模型配置不可用”。

## Confirmed Problems

## Problem 1: 上游模型配置不可用，导致 LLM 返回空响应

### Symptoms

- planning 之后的 hypothesis/proposal 阶段连续输出空 `Response:`
- 后续马上出现 `JSON fix failed: Expecting value`
- hypothesis 生成只能 fallback
- factor proposal 阶段无法推进

### Confirmed Root Cause

当时 LiteLLM 上游没有为实际调用的模型配置可用 API key，导致请求无法正常返回有效内容。

由于这条调用链默认走 `REASONING_MODEL`，所以把问题简单写成“`codestral-latest` 配置不当”是不准确的。更准确的描述应为：

> 实际被调用的上游模型在 LiteLLM 侧不可用，QuantaAlpha 侧收到空响应后继续按 JSON 结果处理，最终触发失败。

### Impact

- hypothesis 生成失败，退回 deterministic fallback
- factor proposal 无法拿到结构化结果
- 大量无效重试，浪费时间和配额

## Problem 2: `RDAgentLog.warning()` 参数签名不兼容

### Symptoms

日志中出现：

```text
Planning LLM call failed (attempt 1): RDAgentLog.warning() takes 2 positional arguments but 5 were given
```

### Root Cause

`quantaalpha/llm/client.py` 使用了标准 `logging` 风格：

```python
logger.warning(
    "Tokenizer lookup failed for model %s; falling back to %s. reason=%s",
    model,
    DEFAULT_FALLBACK_TOKENIZER,
    reason,
)
```

但 `rdagent` 的 `warning()` 只接受一个位置参数 `msg`，不支持 `msg, *args` 形式。

### Impact

- 掩盖了 planning 首次失败时更底层的真实异常
- 增加了排查成本
- 让日志看起来像是 planning 本身失败，实际不是主故障点

## Problem 3: 空响应后继续 JSON 解析，错误被放大

### Symptoms

日志里反复出现：

```text
JSON fix failed: Expecting value: line 1 column 1 (char 0), using raw response
```

### Root Cause

`quantaalpha/llm/client.py` 在得到 `resp` 后，不论是否为空，都继续做：

```python
json_start = resp.find('{')
json_end = resp.rfind('}') + 1
resp = resp[json_start:json_end]
json.loads(resp)
```

当 `resp` 为空字符串时，`json.loads("")` 必然失败。

### Impact

- 上游模型不可用的症状被转化成 JSON 解析报错
- 从日志表面看像“JSON 修复失败”，但这只是后续症状，不是最初根因

## Problem 4: `proposal.py` 无限重试导致终端卡死

### Symptoms

终端持续刷：

```text
JSON parse failed: Could not parse JSON; original text length: 0: line 1 column 1 (char 0), retrying...
```

### Root Cause

`quantaalpha/factors/proposal.py` 中使用了裸 `while True`：

```python
while True:
    resp = APIBackend().build_messages_and_create_chat_completion(...)
    try:
        response_dict = robust_json_parse(resp)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed: {e}, retrying...")
        continue
```

当上游持续返回空响应时，这里没有熔断条件，就会无限循环。

### Impact

- 这是“终端卡死”的直接代码原因
- 即使根因是上游模型不可用，本地逻辑也没有及时失败退出

## What Was Misleading In Earlier Drafts

- 不能把根因直接写成 `codestral-latest` 不适合。
- 不能把“流式响应累积问题”当作已证实根因；现有日志只证明空响应存在，不足以单独证明 stream chunk 解析逻辑本身有 bug。
- `CHAT_MODEL` 与 `REASONING_MODEL` 需要区分；本次主要调用路径默认走的是 `REASONING_MODEL`。

## Recommended Fixes

### Immediate

1. 修正 LiteLLM 上游模型配置，确保实际调用模型具备可用 API key。
2. 在 `llm/client.py` 中对空响应做显式检测，空值时直接抛出明确异常，不进入 JSON 提取。
3. 为 `proposal.py` 的 JSON 解析重试增加 `max_retries` 或熔断机制。
4. 将 `logger.warning(msg, *args)` 改为预先格式化后的单字符串调用。

### Follow-up Hardening

1. 在 LLM 调用日志中明确打印最终选用的 model 名称。
2. 在空响应场景下记录上游返回对象摘要，便于区分鉴权失败、路由失败、模型拒绝和流式空 chunk。
3. 为 hypothesis / proposal 的空响应场景补回归测试。

## Validation Notes

- 基于原始终端日志核对了 planning 成功、hypothesis 失败、proposal 死循环这三段现象。
- 基于源码核对了默认 `reasoning_flag=True` 的模型选择逻辑。
- 基于后续运行对比，确认切换到可用模型后不再复现同类问题。

## Residual Risk

即使上游模型配置修正，如果本地仍保留：

- 空响应继续 JSON 解析
- 无限重试
- logger 参数签名不兼容

那么未来仍可能在其他上游异常场景下重复出现“难排查”和“卡死”问题。
