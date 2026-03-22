# QuantaAlpha 因子挖掘运行 bug 分析

- **日期**: 2026-03-21
- **终端日志**: `third_party/facotors/terminal/20260321_190705.txt`
- **触发命令**: `third_party/quantaalpha/run.sh`
- **子模块版本**: `bc2aa06` → `563147f` (feat(数据能力): 实现数据能力注册表功能)

## 环境

| 项目 | 值 |
|------|-----|
| Python | 3.12.13 |
| Chat Model | codestral-latest |
| LLM Proxy | 192.168.88.7:4000 (LiteLLM) |
| Embedding Model | bge-m3 |
| Conda Env | mining |

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

### 原因

#### 调用链

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

#### 核心矛盾

**rdagent 的 `RDAgentLog.warning()` 签名** (`rdagent/log/logger.py`):

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

#### 根源：标准 `logging` vs rdagent/loguru 封装的 API 差异

这是 **Python 标准 `logging` 模块** 与 **rdagent 对 loguru 的封装** 之间的 API 不兼容:

| | 标准 `logging.warning()` | `RDAgentLog.warning()` |
|---|---|---|
| 签名 | `warning(msg, *args, **kwargs)` | `warning(msg, *, tag="", raw=False)` |
| `%s` 格式化 | 支持，`args` 会自动做 `msg % args` | **不支持**，多传位置参数直接 TypeError |
| 示例 | `log.warning("a=%s", 1)` ✓ | `log.warning("a=%s", 1)` ✗ |

写代码的人使用了标准 `logging` 的 `%s` 多参数写法，但 `RDAgentLog` 内部用 loguru 实现，在 `_log()` 方法里直接把 `msg` 原样传给 loguru，不做任何 `%` 格式化:

```python
def _log(self, level: str, msg: str, *, tag: str = "", raw: bool = False) -> None:
    caller_info = get_caller_info(level=3)
    tag = f"{self._tag}.{tag}.{self.get_pids()}".strip(".")
    log_func = getattr(logger.patch(lambda r: r.update(caller_info)), level)
    log_func(msg)   # ← 直接传字符串，没有 msg % args 的逻辑
```

所以 `RDAgentLog.warning()` 的设计意图是：**调用方必须自己先把字符串格式化好，再传进来**。不能依赖标准 logging 的隐式 `%` 格式化。

### 修复

将位置参数改为 f-string:

```python
logger.warning(
    f"Tokenizer lookup failed for model {model}; "
    f"falling back to {DEFAULT_FALLBACK_TOKENIZER}. reason={reason}"
)
```

### 注意

同文件中其他 `logger.warning()` / `logger.info()` 调用也需要排查是否有多参数问题。例如:

- `client.py:1075`: `logger.warning(f"JSON fix failed: {e2}, using raw response")` — 已使用 f-string，无问题。
- `experiment.py` 中新增的 `logger.warning(..., exc_info=True)` — 需确认 rdagent logger 是否支持 `exc_info` 关键字参数。

---

## Bug 2: LLM 返回 `None` content，代码未做 null check

**严重度**: 高  
**文件**: `quantaalpha/llm/client.py:1030-1033`  
**日志行**: 95-1316 (大量重复)

### 现象

所有 factor proposal 的 LLM 调用返回空响应:

```
2026-03-21 19:07:18.314 | INFO | ... Response:
2026-03-21 19:07:18.316 | WARNING | ... JSON fix failed: Expecting value: line 1 column 1 (char 0), using raw response
2026-03-21 19:07:18.317 | WARNING | ... Empty hypothesis response, retrying... attempt=1
```

### 代码

```python
else:
    resp = response.choices[0].message.content   # ← 此处 content 为 None
    finish_reason = response.choices[0].finish_reason
    if LLM_SETTINGS.log_llm_chat_content:
        display_resp = resp[:200] + f"... [{len(resp)} chars]" if len(resp) > 200 else resp
        # ↑ 对 None 做切片 → TypeError
```

### 原因

当 LLM 代理返回 `choices[0].message.content = None` 时，代码直接赋值给 `resp`，后续对 `resp` 做 `[:200]` 切片和 `len()` 操作会抛出 `TypeError: 'NoneType' object is not subscriptable`。

但实际运行中可能被外层 try/except 吞掉，导致 `resp` 以 `None` 或空字符串 `""` 继续传递到下游，最终在 JSON 解析环节报 `Expecting value: line 1 column 1 (char 0)`。

### 修复

在赋值后立即检查:

```python
resp = response.choices[0].message.content
if resp is None:
    resp = ""
finish_reason = response.choices[0].finish_reason
```

同时在 `return resp, finish_reason` 之前增加上游检查，对空响应直接抛出明确异常，避免无意义重试。

---

## Bug 3: 所有 factor proposal LLM 调用返回空响应（根因）

**严重度**: 致命  
**涉及文件**:
- `quantaalpha/llm/client.py` (LLM 调用层)
- `quantaalpha/factors/proposal.py` (factor 生成层)
- `.env` / `configs/experiment.yaml` (配置层)

### 现象对比

| 阶段 | Prompt 大小 | Token 数 | 结果 |
|------|------------|---------|------|
| Planning (generate_parallel_directions) | ~1200 chars | 413 | 成功，返回 2 个方向 |
| Factor Proposal (gen) | ~8963 + 881 chars | 10000+ | 全部返回空，无限重试 |

Planning 调用成功，但进入 evolution loop 后所有 factor proposal 调用均返回空内容，导致:

1. `gen()` 重试 3 次后 fallback 到 deterministic hypothesis
2. `_convert_with_history_limit()` 无限重试（日志显示 30+ 次），每次间隔 ~0.1s
3. 整个 workflow 实质卡死，无法生成任何因子

### 可能原因

1. **Codestral JSON mode 兼容性**: 代码在 `json_mode=True` 时设置 `response_format: {"type": "json_object"}` (client.py:1009)。`codestral-latest` 可能对此支持不完整，返回 null content。

2. **Prompt 大小触发代理限制**: Factor proposal 的 system prompt 达 10000+ chars，可能触发了 LiteLLM 代理 (192.168.88.7:4000) 的 token 限制或内容过滤规则。

3. **子模块升级引入的 prompt 膨胀**: 子模块从 `bc2aa06` 升级到 `563147f`，新增了 `data_capability_registry` 功能 (experiment.py)，向 system prompt 注入了额外的数据能力描述，增大了 prompt 体积。

4. **`_convert_with_history_limit` 重试逻辑缺陷**: proposal.py:487-491 的重试循环没有空响应检测和退出条件，导致无限循环:

```python
resp = APIBackend().build_messages_and_create_chat_completion(...)
try:
    response_dict = robust_json_parse(resp)  # 空字符串 → JSONDecodeError
except json.JSONDecodeError as e:
    logger.warning(f"JSON parse failed: {e}, retrying...")
    continue  # ← 无退出条件，无限循环
```

### 排查建议

1. 检查 LiteLLM 代理日志 (192.168.88.7:4000)，确认请求是否被转发到上游、返回内容是什么
2. 将 `CHAT_MODEL` 从 `codestral-latest` 换成其他模型 (如 `mistral-large-latest`)，排除模型因素
3. 临时关闭 `data_capability_registry.enabled: false`，排除 prompt 膨胀因素
4. 在 `_create_chat_completion_inner_function` 中增加 `resp` 为空时的日志，打印 `response` 原始对象以定位问题

---

## 关联提交

| 提交 | 说明 | 关联 |
|------|------|------|
| `563147f` | feat(数据能力): 实现数据能力注册表功能 | 可能增大 prompt，触发空响应 |
| `66545b5` | chore: 更新第三方库quantaalpha的子模块引用 | 引入上述变更 |
| `c9db0d7` | fix(eva_utils): 修复 JSONDecodeError 未触发重试的问题 | 之前修过类似问题，但未覆盖当前场景 |
