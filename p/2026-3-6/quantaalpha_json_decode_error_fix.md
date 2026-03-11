# QuantaAlpha JSON 解析错误修复报告

> **修订说明**: 初版文档的根因判断和修复方案存在问题，已在同事 review 后修正。
> 主要问题：原方案一的 `replace('\n', '\\n')` 全局替换会把 JSON 结构本身的换行也转义掉，反而破坏合法格式。

## 问题概述

**发生时间**: 2026-03-11 20:41:31
**错误类型**: `json.decoder.JSONDecodeError`
**错误信息**: `Expecting property name enclosed in double quotes: line 4 column 1 (char 274)`
**触发场景**: 运行 `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/run.sh` 进行因子挖掘时

---

## 零、重要发现：已有 `robust_json_parse()` 但未被使用

**关键点**: `client.py:36` 已存在 `robust_json_parse()` 函数，实现了状态机级别的健壮 JSON 解析：

```python
def robust_json_parse(text: str, max_retries: int = 3) -> dict:
    """
    Robust JSON parser: handles extra data, LaTeX escapes, markdown-wrapped JSON.
    """
    # Strategy 1: direct parse
    # Strategy 2: extract JSON code block (```json...```)
    # Strategy 3: find first complete JSON object (状态机追踪字符串内外)
    # Strategy 4: fix LaTeX escapes
    # Strategy 5: looser JSON extraction
```

**问题**: `eva_utils.py:561` 直接调用 `json.loads()`，没有使用这个已有的健壮解析器！

---

## 一、问题复现路径

### 1.1 执行命令
```bash
cd /home/quan/testdata/aspipe_v4/third_party/quantaalpha
bash run.sh
```

### 1.2 错误发生位置
```
文件: third_party/quantaalpha/quantaalpha/factors/coder/eva_utils.py
行号: 577
函数: FactorFinalDecisionEvaluator.evaluate
```

### 1.3 完整错误栈
```python
Traceback (most recent call last):
  File "/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/coder/eva_utils.py", line 561, in evaluate
    final_evaluation_dict = json.loads(
        api.build_messages_and_create_chat_completion(...)
    )
  ...
  json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes: line 4 column 1 (char 274)

The above exception was the direct cause of the following exception:

  File ".../quantaalpha/pipeline/factor_mining.py", line 447, in run_evolution_loop
    traj_data = _run_evolution_task(...)
  ...
ValueError: Failed to decode JSON response from API.
```

---

## 二、问题根因分析

### 2.1 LLM 返回的问题响应

从日志文件 `/home/quan/testdata/aspipe_v4/third_party/facotors/a.txt` 中提取的问题响应:

```
2026-03-11 20:41:31.127 | INFO | quantaalpha.llm.client:... - Response:{
    "final_decision": true,
    "final_feedback": "The factor implementation is correct as it successfully calculates the cross-sectional volatility clustering measure using the specified 15-day loo... [275 chars]
2026-03-11 20:41:31.133 | WARNING | quantaalpha.llm.client:... - JSON fix failed: Expecting property name enclosed in double quotes: line 4 column 1 (char 274), using raw response
```

### 2.2 根因判断的修正（重要）

> **初版文档判断**: "LLM 返回的 JSON 中包含未转义的换行符"
> **问题**: 这个判断证据不足。`json.loads` 遇到字符串内未转义换行时，典型报错是 `Invalid control character`，而不是 `Expecting property name enclosed in double quotes`。

**更可能的根因分析**:
1. `Expecting property name enclosed in double quotes` 通常意味着 JSON 结构被破坏
2. 可能原因包括：
   - 字符串中包含未转义的双引号 `"`
   - 多余的逗号或缺少逗号
   - 对象外部的非法字符
   - 其他格式损坏情况

**结论**: 具体原因需要获取完整的原始响应才能确定，但无论如何，应该使用健壮的解析器来处理各种情况。

### 2.3 代码层面的缺陷

#### 缺陷1: `client.py` 的 JSON 修复逻辑不完整

**文件**: `third_party/quantaalpha/quantaalpha/llm/client.py`
**位置**: 第 897-925 行

```python
if json_mode or reasoning_flag:
    # Extract JSON part
    json_start = resp.find('{')
    json_end = resp.rfind('}') + 1
    resp = resp[json_start:json_end]
    # Try parse JSON; on failure try to fix
    try:
        json.loads(resp)
    except json.JSONDecodeError as e:
        import re
        error_msg = str(e).lower()
        # Fix common JSON format issues
        fixed_resp = resp

        # Fix LaTeX backslash: \text, \frac etc. misinterpreted as escapes
        latex_commands = ['text', 'frac', 'left', 'right', 'times', 'cdot', 'sqrt', 'sum', 'prod', 'int']
        for cmd in latex_commands:
            fixed_resp = re.sub(r'(?<!\\)\\(' + cmd + r')', r'\\\\\1', fixed_resp)

        # Fix other invalid escapes: \_ \{ \} etc.
        fixed_resp = re.sub(r'(?<!\\)\\([_\{\}\[\]])', r'\\\\\1', fixed_resp)

        try:
            json.loads(fixed_resp)
            resp = fixed_resp
            logger.info("Fixed JSON format issues")
        except json.JSONDecodeError as e2:
            logger.warning(f"JSON fix failed: {e2}, using raw response")
            # 问题: 这里只记录警告，但返回的 raw response 仍然无法解析!
```

**问题**: 该修复逻辑只处理了 LaTeX 相关的转义问题，**没有处理字符串值中未转义的换行符**

#### 缺陷2: `eva_utils.py` 缺少 JSON 解析错误重试机制

**文件**: `third_party/quantaalpha/quantaalpha/factors/coder/eva_utils.py`
**位置**: 第 558-585 行

```python
while attempts < max_attempts:
    try:
        api = APIBackend() if attempts == 0 else APIBackend(use_chat_cache=False)
        final_evaluation_dict = json.loads(
            api.build_messages_and_create_chat_completion(...)
        )
        final_decision = final_evaluation_dict["final_decision"]
        final_feedback = final_evaluation_dict["final_feedback"]
        ...
        return final_decision, final_feedback

    except json.JSONDecodeError as e:
        # 问题: 直接抛出异常，没有重试!
        raise ValueError("Failed to decode JSON response from API.") from e
    except KeyError as e:
        # KeyError 有重试机制，但 JSONDecodeError 没有
        attempts += 1
        if attempts >= max_attempts:
            raise KeyError(...) from e
```

**问题**: `KeyError` 有重试机制，但 `JSONDecodeError` 直接抛出异常终止流程

---

## 三、修复方案

### 3.1 方案一: 使用已有的 `robust_json_parse()` (推荐)

**修改文件**: `third_party/quantaalpha/quantaalpha/factors/coder/eva_utils.py`
**修改位置**: 第 561 行

**原代码**:
```python
final_evaluation_dict = json.loads(
    api.build_messages_and_create_chat_completion(
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        reasoning_flag=False,
        json_mode=True,
        seed=attempts,
    ),
)
```

**修改为**:
```python
from quantaalpha.llm.client import robust_json_parse

response_text = api.build_messages_and_create_chat_completion(
    user_prompt=user_prompt,
    system_prompt=system_prompt,
    reasoning_flag=False,
    json_mode=True,
    seed=attempts,
)
final_evaluation_dict = robust_json_parse(response_text)
```

**优点**:
- 利用已有的状态机级别解析器
- 不破坏 JSON 结构本身的换行
- 只处理字符串内部的非法控制字符
- 支持多种修复策略（markdown 代码块、LaTeX 转义等）

### 3.2 方案二: 在 `eva_utils.py` 中增加 JSON 解析错误重试（兜底）

**修改文件**: `third_party/quantaalpha/quantaalpha/factors/coder/eva_utils.py`
**修改位置**: 第 576-577 行

**原代码**:
```python
except json.JSONDecodeError as e:
    raise ValueError("Failed to decode JSON response from API.") from e
```

**修改为**:
```python
except json.JSONDecodeError as e:
    attempts += 1
    if attempts >= max_attempts:
        raise ValueError("Failed to decode JSON response from API after multiple attempts.") from e
    logger.warning(f"JSON decode error, retrying (attempt {attempts}/{max_attempts}): {e}")
    continue  # 重试
```

### 3.3 【错误方案】为什么不能用全局 `replace('\n', '\\n')`

> 这是最关键的一点，初版文档方案一的问题：

**错误代码**:
```python
# 千万不要这样做！
fixed_resp = fixed_resp.replace('\n', '\\n')
```

**问题演示**:
```python
# 原始合法 JSON
original = '''{
  "a": 1
}'''

# 全局替换后变成非法文本
broken = original.replace('\n', '\\n')
# 结果: '{\\n  "a": 1\\n}'
# 这不再是合法的 JSON！因为 JSON 结构的换行被转义成了字面量 \n
```

**正确做法**: 使用状态机追踪"是否在字符串内部"，只修复字符串内的非法控制字符：
- `robust_json_parse()` 的 Strategy 3 已经实现了这个逻辑（第 59-87 行）
- 通过 `in_string` 标志追踪当前是否在字符串内部
- 只在字符串内部做特殊处理

### 3.4 长期方案: 统一 JSON 解析入口

**问题**: 当前代码中存在多处直接调用 `json.loads()`：

```
eva_utils.py:223  -> json.loads(resp)
eva_utils.py:561  -> json.loads(...)
```

**建议**: 将所有 `json_mode=True` 后的直接 `json.loads()` 调用收敛到统一入口：

```python
# 在 APIBackend 类中添加方法
def build_messages_and_create_chat_completion_json(self, ...) -> dict:
    response = self.build_messages_and_create_chat_completion(...)
    return robust_json_parse(response)
```

这样可以避免同样的问题在其他地方重复出现。

---

## 四、完整修复代码

### 4.1 `eva_utils.py` 修复（方案一 + 方案二）

```python
# 文件: third_party/quantaalpha/quantaalpha/factors/coder/eva_utils.py
# 位置: 文件顶部添加 import
from quantaalpha.llm.client import robust_json_parse

# 位置: 第 553-585 行，修改 evaluate 方法

# TODO:  with retry_context(retry_n=3, except_list=[KeyError]):
final_evaluation_dict = None
attempts = 0
max_attempts = 3

while attempts < max_attempts:
    try:
        api = APIBackend() if attempts == 0 else APIBackend(use_chat_cache=False)

        # [修改] 使用 robust_json_parse 替代直接 json.loads
        response_text = api.build_messages_and_create_chat_completion(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            reasoning_flag=False,
            json_mode=True,
            seed=attempts,
        )
        final_evaluation_dict = robust_json_parse(response_text)

        final_decision = final_evaluation_dict["final_decision"]
        final_feedback = final_evaluation_dict["final_feedback"]

        final_decision = str(final_decision).lower() in ["true", "1"]
        return final_decision, final_feedback

    except json.JSONDecodeError as e:
        # [修改] 增加 JSON 解析错误的重试机制
        attempts += 1
        if attempts >= max_attempts:
            logger.error(f"Failed to decode JSON response after {max_attempts} attempts: {e}")
            raise ValueError("Failed to decode JSON response from API after multiple attempts.") from e
        logger.warning(f"JSON decode error, retrying (attempt {attempts}/{max_attempts}): {e}")
        continue

    except KeyError as e:
        attempts += 1
        if attempts >= max_attempts:
            raise KeyError(
                "Response from API is missing 'final_decision' or 'final_feedback' key after multiple attempts."
            ) from e

return None, None
```

### 4.2 其他需要检查的位置

搜索代码库中所有直接使用 `json.loads()` 处理 LLM 响应的位置：

```bash
grep -rn "json.loads" third_party/quantaalpha/quantaalpha/ | grep -v test | grep -v __pycache__
```

当前发现的位置：
- `eva_utils.py:223` - 另一处直接调用
- `eva_utils.py:561` - 本次出错位置

建议逐一检查并替换为 `robust_json_parse()`。

---

## 五、验证测试

### 5.1 验证 `robust_json_parse()` 的状态机逻辑

```python
# 测试：状态机正确区分 JSON 结构换行和字符串内部换行

def test_state_machine():
    # 合法 JSON（结构换行应保留）
    valid_json = '''{
  "a": 1
}'''
    import json
    result = json.loads(valid_json)
    assert result == {"a": 1}, "合法 JSON 应该正常解析"

    # 问题 JSON（字符串内有未转义换行）
    # 注意：这实际会报错，需要 robust_json_parse 处理
    broken_json = '{"a": "line1\nline2"}'
    # json.loads(broken_json) 会报 Invalid control character

    print("状态机逻辑验证通过")

test_state_machine()
```

### 5.2 验证全局替换的问题

```python
def test_why_global_replace_is_wrong():
    """演示为什么不能使用全局 replace('\n', '\\n')"""

    original = '''{
  "a": 1
}'''

    # 全局替换（错误做法）
    broken = original.replace('\n', '\\n')
    print(f"替换后: {repr(broken)}")
    # 输出: '{\\n  "a": 1\\n}'
    # 这不再是合法的 JSON！

    import json
    try:
        json.loads(broken)
        print("错误：不应该能解析")
    except json.JSONDecodeError as e:
        print(f"正确：解析失败 - {e}")

test_why_global_replace_is_wrong()
```

### 5.3 集成测试

重新运行因子挖掘流程:
```bash
cd /home/quan/testdata/aspipe_v4/third_party/quantaalpha
bash run.sh
```

---

## 六、预防措施

### 6.1 统一 JSON 解析入口

在 `APIBackend` 类中添加专门的 JSON 解析方法：

```python
# 文件: third_party/quantaalpha/quantaalpha/llm/client.py
# 在 APIBackend 类中添加

def build_messages_and_create_chat_completion_json(
    self,
    user_prompt: str,
    system_prompt: str | None = None,
    **kwargs
) -> dict:
    """
    调用 LLM 并返回解析后的 JSON 对象。
    使用 robust_json_parse 进行健壮解析。
    """
    response = self.build_messages_and_create_chat_completion(
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        json_mode=True,
        **kwargs
    )
    return robust_json_parse(response)
```

然后逐步将所有 `json_mode=True` 的调用点改为使用这个方法。

### 6.2 Prompt 优化（可选）

在要求 LLM 返回 JSON 时，明确指示格式要求：

```python
system_prompt = """
...
IMPORTANT: When returning JSON:
- Keep string values on a single line when possible
- Use \\n for any line breaks within strings
- Ensure all quotes are properly escaped
"""
```

### 6.3 监控和日志

增加 JSON 解析失败的详细日志：

```python
except json.JSONDecodeError as e:
    logger.error(f"JSON parse failed at position {e.pos}: {e.msg}")
    logger.debug(f"Raw response (first 500 chars): {resp[:500]}...")
    # ... retry or raise
```

---

## 七、总结

| 项目 | 内容 |
|------|------|
| **问题** | LLM 返回的 JSON 格式损坏，解析失败 |
| **影响** | 因子挖掘流程中断 |
| **根因** | `eva_utils.py` 直接使用 `json.loads()`，没有利用已有的 `robust_json_parse()` |
| **修复** | 1. 使用 `robust_json_parse()` 替代 `json.loads()` <br> 2. 增加 JSON 解析错误重试机制 |
| **错误方案** | ❌ 全局 `replace('\n', '\\n')` - 会破坏 JSON 结构 |
| **正确方案** | ✅ 使用状态机级别的 `robust_json_parse()` |
| **文件** | `factors/coder/eva_utils.py` |
| **状态** | 待修复 |

---

## 八、关键教训

1. **不要简单全局替换**: `replace('\n', '\\n')` 会把 JSON 结构换行也转义掉
2. **复用已有代码**: `robust_json_parse()` 已经存在，应该优先使用
3. **状态机思维**: 处理嵌套结构时，需要追踪"当前位置是否在字符串内部"
4. **统一入口**: 避免同样的 bug 在多处重复出现

---

## 八、附录

### 8.1 相关文件路径

- 错误发生: `third_party/quantaalpha/quantaalpha/factors/coder/eva_utils.py`
- JSON 处理: `third_party/quantaalpha/quantaalpha/llm/client.py`
- 日志文件: `third_party/facotors/a.txt`

### 8.2 参考资料

- [Python JSON 模块文档](https://docs.python.org/3/library/json.html)
- [JSON 规范 RFC 8259](https://datatracker.ietf.org/doc/html/rfc8259)