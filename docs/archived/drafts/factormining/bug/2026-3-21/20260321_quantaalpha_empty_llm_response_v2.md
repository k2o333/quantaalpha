# QuantaAlpha 因子挖掘运行 bug 分析（已证实版）

- **日期**: 2026-03-21
- **终端日志**: `third_party/facotors/terminal/20260321_190705.txt`
- **触发命令**: `third_party/quantaalpha/run.sh`
- **子模块版本**: `bc2aa06` → `563147f`

## 环境

| 项目 | 值 | 证据类型 |
|------|-----|---------|
| Python | 3.12.13 | 日志第1行 |
| Chat Model (配置) | codestral-latest | `.env:26` |
| Reasoning Model (代码路径指向) | mistral-large-latest | `.env:22`，代码链见下文，**未从代理确认** |
| LLM Proxy | 192.168.88.7:4000 (LiteLLM) | `.env:18` |
| 流式模式 | 开启 | `.env` 默认、`config.py:35` 默认、日志第77行确认 `chat_stream=True` |
| Conda Env | mining | `.env:53` |

---

## Bug 1: `logger.warning()` 参数签名不匹配

**严重度**: 中  
**文件**: `quantaalpha/llm/client.py:69-74`  
**日志行**: 25

### 现象

```
Planning LLM call failed (attempt 1): RDAgentLog.warning() takes 2 positional arguments but 5 were given
```

### 代码

```python
logger.warning(
    "Tokenizer lookup failed for model %s; falling back to %s. reason=%s",
    model,
    DEFAULT_FALLBACK_TOKENIZER,
    reason,
)
```

### 调用链（代码证据）

```
client.py:22
  from quantaalpha.log import logger   →  获取 _AlphaAgentLoggerWrapper 实例

quantaalpha/log/__init__.py:43
  logger = _AlphaAgentLoggerWrapper(_rdagent_logger)
                                                    ↓
quantaalpha/log/__init__.py:33-34
  def __getattr__(self, name):
      return getattr(self._inner, name)  →  委托给 rdagent_logger
                                                    ↓
rdagent/log/logger.py
  class RDAgentLog:
      def warning(self, msg: str, *, tag: str = "", raw: bool = False) -> None:
                                                    ↑
                                              只接受 1 个位置参数 msg
```

### 核心矛盾

**rdagent 的 `RDAgentLog.warning()` 签名** (`rdagent/log/logger.py:132`):

```python
def warning(self, msg: str, *, tag: str = "", raw: bool = False) -> None:
    self._log("warning", msg, tag=tag, raw=raw)
```

- `msg: str` — 唯一的位置参数
- `*` — 后面的 `tag` 和 `raw` 都是 **keyword-only** 参数

**client.py 的调用方式**:

```python
logger.warning(
    "Tokenizer lookup failed for model %s; falling back to %s. reason=%s",
    model,                      # ← 第2个位置参数
    DEFAULT_FALLBACK_TOKENIZER, # ← 第3个位置参数
    reason,                     # ← 第4个位置参数
)
```

这里传了 5 个位置实参（self 隐式 + msg + 3 个用于 `%s` 格式化的参数），但 `warning()` 方法签名只接受 2 个（self + msg），因此抛出 `TypeError: takes 2 positional arguments but 5 were given`。

### 根源：标准 `logging` vs rdagent/loguru 封装的 API 差异

这是 **Python 标准 `logging` 模块** 与 **rdagent 对 loguru 的封装** 之间的 API 不兼容:

| | 标准 `logging.warning()` | `RDAgentLog.warning()` |
|---|---|---|
| 签名 | `warning(msg, *args, **kwargs)` | `warning(msg, *, tag="", raw=False)` |
| `%s` 格式化 | 支持，`args` 会自动做 `msg % args` | **不支持**，多传位置参数直接 TypeError |
| 示例 | `log.warning("a=%s", 1)` ✓ | `log.warning("a=%s", 1)` ✗ |

`RDAgentLog` 内部用 loguru 实现，在 `_log()` 方法里直接把 `msg` 原样传给 loguru，不做任何 `%` 格式化:

```python
def _log(self, level: str, msg: str, *, tag: str = "", raw: bool = False) -> None:
    ...
    log_func = getattr(logger.patch(lambda r: r.update(caller_info)), level)
    log_func(msg)   # ← 直接传字符串，没有 msg % args 的逻辑
```

所以 `RDAgentLog.warning()` 的设计意图是：**调用方必须自己先把字符串格式化好，再传进来**。

### 修复

```python
logger.warning(
    f"Tokenizer lookup failed for model {model}; "
    f"falling back to {DEFAULT_FALLBACK_TOKENIZER}. reason={reason}"
)
```

---

## Bug 2: 流式 LLM 空响应传播到 JSON 解析

**严重度**: 高  
**文件**: `quantaalpha/llm/client.py:1013-1027` (流式路径) + `client.py:1047-1051` (JSON 提取)  
**日志行**: 95-1316 (大量重复)

### 代码路径确认（代码证据）

此次运行走的是**流式分支**（`chat_stream=True`，client.py:1013），不是非流式分支。依据：`config.py:35` 默认 `chat_stream=True`，日志第77行确认 `chat_stream=True`。

流式路径有 `None` 保护，不会崩溃:

```python
if self.chat_stream:
    resp = ""
    for chunk in response:
        content = (
            chunk.choices[0].delta.content
            if len(chunk.choices) > 0 and chunk.choices[0].delta.content is not None
            else ""                                      # ← None 保护
        )
        resp += content
```

但如果 LLM 返回的所有 chunk 都没有 content，`resp` 保持 `""`。

### 失败路径（代码证据）

`reasoning_flag=True`（默认值，client.py:900）触发 JSON 提取块（client.py:1047），对空字符串操作:

```
resp = "" (流式收集的所有 chunk 无 content)
  → reasoning_flag=True → 进入 JSON 提取块 (client.py:1047: if json_mode or reasoning_flag)
    → resp.find('{') 返回 -1               # 空字符串找不到 {
    → resp.rfind('}') + 1 返回 0           # 空字符串找不到 }
    → resp[-1:0] = ""                      # 切片结果仍是空字符串
    → json.loads("") → JSONDecodeError     # "Expecting value: line 1 column 1 (char 0)"
      → logger.warning("JSON fix failed: ...")   # 日志第96行
        → resp 返回空字符串给调用方
```

这就是日志中 `Response:` 后面为空 + `JSON fix failed: Expecting value: line 1 column 1 (char 0)` 的完整解释。

### 修复

在流式循环结束后、JSON 提取之前，增加空响应检查:

```python
if self.chat_stream:
    resp = ""
    for chunk in response:
        ...
    if not resp:
        raise RuntimeError(f"LLM returned empty response for model {model}")
```

---

## Bug 3: LLM 大 prompt 请求返回空内容（根因）+ proposal 无限重试

**严重度**: 致命  
**涉及文件**:
- `quantaalpha/llm/client.py` (LLM 调用层)
- `quantaalpha/factors/proposal.py` (factor 生成层)

### 已确认的事实

| 阶段 | 模型 (代码路径指向) | Prompt 大小 | Token 数 | 结果 | 证据 |
|------|------|------------|---------|------|------|
| Planning | mistral-large-latest | ~1200 chars | 413 | 成功，返回 2 个方向 | 日志第37-39行 |
| Hypothesis | mistral-large-latest | ~8963 + 881 chars | 未记录 | 全部返回空 | 日志第95-96行 |
| Factor Proposal | mistral-large-latest | ~10110 + 8121 chars | 未记录 | 全部返回空 | 日志第260+行 |

### 关于实际使用的模型（代码证据链）

**代码链**（以下每一步均有代码证据）:

```
proposal.py:301-306
  api.build_messages_and_create_chat_completion(
      user_prompt, system_prompt,
      json_mode=json_flag,                  # 传入 json_mode
      task_type="hypothesis_generation"
  )
  # 注意：未传 reasoning_flag
      ↓
client.py:731
  self._try_create_chat_completion_or_embedding(
      messages=messages, chat_completion=True, **kwargs
  )
  # kwargs = {json_mode, task_type}，无 reasoning_flag
      ↓
client.py:806
  self._create_chat_completion_auto_continue(**kwargs)
  # 仍无 reasoning_flag
      ↓
client.py:775
  self._create_chat_completion_inner_function(messages=messages, **kwargs)
  # 仍无 reasoning_flag → 走默认值
      ↓
client.py:900 (函数签名)
  def _create_chat_completion_inner_function(
      self, messages, reasoning_flag = True, ...
  )
  # reasoning_flag 默认 = True
      ↓
client.py:954-956
  if reasoning_flag:
      model = self.reasoning_model    # ← 用 reasoning_model，不用 chat_model
      json_mode = None                # ← 覆盖传入的 json_mode=json_flag
      ↓
client.py:539
  self.reasoning_model = LLM_SETTINGS.reasoning_model if reasoning_model is None else reasoning_model
      ↓
config.py:32 + .env:22
  REASONING_MODEL=mistral-large-latest
```

**结论**: 代码路径指向 `mistral-large-latest`，且 `json_mode` 被覆盖为 `None`。

**证据缺口**: 代码证据只能证明变量赋值，无法确认实际发往 `192.168.88.7:4000` 的 HTTP 请求中的 `model` 字段值。需查 LiteLLM 代理日志确认。

### 关于 json_mode 被覆盖（代码证据）

```
proposal.py:304    →  传入 json_mode=json_flag（可能为 True）
client.py:956      →  json_mode = None（被 reasoning_flag=True 覆盖）
client.py:1003     →  if json_mode:  为 False → response_format 不加入 kwargs
```

**结论**: 此次调用**未使用** `response_format: {"type": "json_object"}`。

**证据缺口**: 无日志确认实际 HTTP 请求中是否带了 response_format，但从代码逻辑 `json_mode=None` → `if json_mode` 为 False → 不应带。

### 关于 reasoning_flag=True 触发 JSON 提取（代码证据）

```
client.py:1047: if json_mode or reasoning_flag:
  # json_mode=None (False), reasoning_flag=True → 条件成立 → 进入 JSON 提取块
client.py:1049: resp.find('{')    # 空字符串 → -1
client.py:1050: resp.rfind('}')+1 # 空字符串 → 0
client.py:1051: resp[-1:0] = ""   # 切片结果空字符串
client.py:1054: json.loads("")    # JSONDecodeError
client.py:1075: logger.warning("JSON fix failed: ...")  # 日志第96行
```

**结论**: `reasoning_flag=True` 是触发空字符串 JSON 提取的直接原因。如果 `reasoning_flag=False`，空字符串不会进入 JSON 提取块，`resp` 会以 `""` 直接返回给调用方（虽然也会失败，但不会报 JSONDecodeError）。

### 已证实的完整事故链

1. **LLM 对大 prompt 返回空流式内容** 【日志证据】
   - 规划阶段 prompt 小（~1200 chars，413 tokens），成功返回 JSON（日志第37-39行）
   - hypothesis 阶段 prompt 大（~9800 chars），Response 为空（日志第95行）
   - proposal 阶段 prompt 大（~18000 chars），Response 为空（日志第260+行）
   - **为什么大 prompt 返回空？——证据不足**。可能原因：
     - LiteLLM 代理对大 prompt 的 token 限制
     - 上游 `mistral-large-latest` 对大 prompt 的处理异常
     - 代理超时或内容过滤
     - 需查代理日志确认

2. **流式空响应传播到 JSON 提取** 【代码证据】
   - `resp = ""`（流式路径，所有 chunk 无 content）
   - `reasoning_flag=True` → 进入 JSON 提取块（client.py:1047）
   - `json.loads("")` → JSONDecodeError（见 Bug 2）

3. **hypothesis 阶段有限重试后 fallback** 【日志证据】
   - 日志 attempt=1,2,3（第97、107、117行）
   - 第3次后 `logger.warning("Hypothesis generation failed, falling back to deterministic hypothesis")`（第118行）
   - workflow 可继续，但质量降级

4. **factor proposal 阶段无限重试导致进程卡死** 【代码+日志证据】
   - `proposal.py:483-492` 的 `while True` 无退出条件:

   ```python
   while True:          # ← 无重试上限
       if flag:
           break
       resp = APIBackend().build_messages_and_create_chat_completion(
           user_prompt, system_prompt, json_mode=json_flag
       )
       try:
           response_dict = robust_json_parse(resp)   # 空字符串 → JSONDecodeError
       except json.JSONDecodeError as e:
           logger.warning(f"JSON parse failed: {e}, retrying...")
           continue   # ← 直接 continue，无计数器，无退出条件
   ```

   - 只要上游持续返回空响应，程序就会无限刷 `JSON parse failed ... retrying...`
   - 日志显示 30+ 次重复（第260-1316行），进程表现为卡死

5. **独立的日志兼容性 bug 掩盖了 planning 首次失败的真实原因** 【日志证据】
   - 日志第25行: `Planning LLM call failed (attempt 1): RDAgentLog.warning() takes 2 positional arguments but 5 were given`
   - 触发链：`_create_chat_completion_inner_function` 内部 → `log_tokenizer_fallback_once`（client.py:64）→ `logger.warning(...)`（client.py:69）→ TypeError
   - 这个 TypeError 被 `planning.py:142` 的 `except Exception` 捕获，表现为 "LLM call failed"
   - 第二次重试不再触发此错误（tokenizer fallback 是一次性逻辑），planning 成功
   - 掩盖了 tokenizer fallback 的真实底层原因（是哪个 model 触发了 fallback？）

### 排查建议

1. **检查 LiteLLM 代理日志** (192.168.88.7:4000)：
   - 确认大 prompt 请求是否被转发到上游
   - 确认实际 model 字段是 `mistral-large-latest` 还是其他
   - 确认返回内容是什么、是否有 token 限制或超时
   - 这是弥补上述"证据缺口"的唯一方法

2. **直接测试 `mistral-large-latest` 大 prompt**：
   - 用 curl 直接调用代理 `192.168.88.7:4000`
   - 发送与 hypothesis 阶段类似的 10000+ token prompt
   - 观察是否返回空

3. **临时关闭 `data_capability_registry.enabled: false`**：
   - 排除子模块升级引入的 prompt 膨胀因素
   - **证据不足**：无法确认 prompt 膨胀是否是空响应的直接原因

4. **修复 proposal.py 无限重试**（确定性修复，不依赖根因排查）：

```python
MAX_RETRIES = 10
for attempt in range(MAX_RETRIES):
    resp = APIBackend()...(user_prompt, system_prompt, json_mode=json_flag)
    if not resp or not resp.strip():
        logger.warning(f"Empty LLM response, attempt {attempt+1}/{MAX_RETRIES}")
        continue
    try:
        response_dict = robust_json_parse(resp)
        break
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed: {e}, attempt {attempt+1}/{MAX_RETRIES}")
        continue
else:
    raise RuntimeError("Factor proposal failed after max retries: persistent empty LLM response")
```

---

## 关联提交

| 提交 | 说明 | 关联 |
|------|------|------|
| `563147f` | feat(数据能力): 实现数据能力注册表功能 | 增大了 system prompt（注入 data capabilities 文本），但**证据不足**——无法确认 prompt 膨胀是否是空响应的直接原因 |
| `66545b5` | chore: 更新第三方库quantaalpha的子模块引用 | 引入上述变更 |
| `c9db0d7` | fix(eva_utils): 修复 JSONDecodeError 未触发重试的问题 | 之前修过类似问题，但未覆盖当前场景（proposal.py 的 while True 未被修复） |
