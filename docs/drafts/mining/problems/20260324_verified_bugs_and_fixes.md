# Mining Pipeline 待修复 Bug 清单（代码验证后）

**日期**: 2026-03-24  
**来源**: 基于 `20260324_expression_parsing_and_consistency_issues.md` 文档与 archived `bug-report.md` 的问题描述，逐条对照代码库验证后的结论。

---

## 验证概览

| Bug 编号 | 问题 | 当前状态 | 优先级 |
|----------|------|---------|--------|
| Bug-1 | `normalize_corrected_expression` 缺乏注释/伪代码清洗 | **仍存在** | P0 |
| Bug-2 | `consistency_prompts.yaml` 缺乏 expression 格式约束 | **仍存在** | P0 |
| Bug-3 | API 重试对 "Invalid model name" 无特殊处理 | **仍存在** | P1 |
| Bug-4 | JSON 修复器对非法反斜杠转义不够全面 | **仍存在** | P2 |
| Bug-5 | 废弃 `proposal.yaml` 被静默覆盖，易造成混乱 | **仍存在** | P2 |
| ~~Bug-B~~ | `consistency_checker.py` 异常时返回 `is_consistent=True` | **已修复** | — |

---

## Bug-1: `normalize_corrected_expression` 缺乏注释/伪代码清洗

### 状态：🔴 仍存在

### 位置

`quantaalpha/factors/proposal.py:23-27`

### 现象

LLM 在 consistency check 的 correction 步骤中返回带注释或伪代码的 expression，parser 无法解析，导致 factor 被跳过或进入修正死循环。典型的 LLM 返回格式包括：

- 带 `//` 注释的多行代码块
- 带 `#` 行尾注释
- Python 风格变量赋值伪代码（`dispersion = ...; factor = IF(...)`）
- Python dict 格式的多方案输出（`{'primary_factor': '...', 'illiquidity_proxy': '...'}`）

### 当前代码

```python
def normalize_corrected_expression(expression) -> str:
    """Normalize quality-gate corrected expressions to a parser-safe string."""
    if isinstance(expression, dict):
        return expression.get("expression") or str(expression)
    return expression  # ← 字符串类型直接透传，无清洗
```

只处理了 `dict` 类型提取，**没有**对字符串中的注释、多行伪代码、变量赋值等进行任何清洗。

### 影响

- ~60% 的 consistency check 修正表达式因此无法解析
- 每个失败的 factor 最多浪费 3+1 次 LLM 调用

### 修复方案

在 `normalize_corrected_expression` 中增加正则清洗逻辑：

```python
import re

def normalize_corrected_expression(expression) -> str:
    """Normalize quality-gate corrected expressions to a parser-safe string."""
    if isinstance(expression, dict):
        expression = expression.get("expression") or str(expression)

    # Strip LLM-added comments (// and # style)
    lines = expression.strip().split('\n')
    cleaned_lines = []
    for line in lines:
        line = re.sub(r'\s*//.*$', '', line)
        line = re.sub(r'\s*#.*$', '', line)
        # Skip variable assignment lines (e.g., dispersion = ...)
        if re.match(r'^\s*\w+\s*=', line) and not line.strip().startswith('('):
            continue
        if line.strip():
            cleaned_lines.append(line.strip())

    result = ' '.join(cleaned_lines) if cleaned_lines else expression.strip()

    # If result still looks like a dict/invalid, try to extract first valid expression
    if result.startswith('{') or result.startswith('//'):
        match = re.search(r'([A-Z_]+\(.+\))', result)
        if match:
            result = match.group(1)

    return result
```

---

## Bug-2: `consistency_prompts.yaml` 缺乏 expression 格式约束

### 状态：🔴 仍存在

### 位置

`quantaalpha/factors/regulator/consistency_prompts.yaml:32-42`（`consistency_check_system`）  
`quantaalpha/factors/regulator/consistency_prompts.yaml:84-121`（`expression_correction_system`）

### 现象

LLM 在 consistency check 返回的 `corrected_expression` JSON 字段中自由发挥格式，是 Bug-1 的上游根因。

### 当前代码

`consistency_check_system` 的 Output Format 仅说明：

```yaml
"corrected_expression": "Corrected expression if needed (null if no correction)"
```

`expression_correction_system` 的 Rules 部分仅说明：

```yaml
- Expression must be parsable and executable
- Use only the listed functions and variables
- Keep the expression as simple as possible while maintaining correctness
- Do not use undefined variables or functions
```

两处都**没有**明确要求"单行、无注释、无伪代码"。

### 修复方案

**修改 `consistency_check_system`** 的 `corrected_expression` 字段描述：

```yaml
"corrected_expression": "Corrected expression if needed. CRITICAL: This MUST be a SINGLE-LINE expression using ONLY the available functions and variables. Do NOT include comments (// or #), variable assignments, multiple options, or pseudo-code. Example: 'STD(TS_PCTCHANGE($close, 21)) / (TS_STD($return, 63) + 1e-8)'"
```

**修改 `expression_correction_system`** 的 Rules 部分追加：

```yaml
- **CRITICAL: Return ONLY a single-line mathematical expression. No comments, no pseudo-code, no multiple options, no variable assignments.**
```

---

## Bug-3: API 重试对 "Invalid model name" 无特殊处理

### 状态：🔴 仍存在

### 位置

`quantaalpha/llm/client.py:797-822`（`_try_create_chat_completion_or_embedding` 方法）

### 现象

当 API 返回 `Invalid model name passed in model=leanstral-2603` 时，代码会重试直到耗尽次数后抛出 `RuntimeError`。对于本质上不可恢复的错误（模型名称错误），重试毫无意义。

### 当前代码

```python
except openai.BadRequestError as e:
    logger.warning(e)
    logger.warning(f"Retrying {i+1}th time...")
    if "'messages' must contain the word 'json' in some form" in e.message:
        kwargs["add_json_in_prompt"] = True
    elif embedding and "maximum context length" in e.message:
        kwargs["input_content_list"] = [...]
    # ← 无 "Invalid model name" 判断，直接进入等待重试
    if i < max_retry - 1:
        time.sleep(self.retry_wait_seconds)
```

### 修复方案

在 `BadRequestError` 处理分支中增加对 `Invalid model name` 的判断，立即抛出：

```python
except openai.BadRequestError as e:
    logger.warning(e)
    logger.warning(f"Retrying {i+1}th time...")
    if "Invalid model name" in str(e) or "Invalid model" in str(e):
        logger.error(f"Model '{self.chat_model}' is invalid. Check model configuration.")
        raise  # 不可恢复，立即终止
    if "'messages' must contain the word 'json' in some form" in e.message:
        kwargs["add_json_in_prompt"] = True
    elif embedding and "maximum context length" in e.message:
        kwargs["input_content_list"] = [...]
    if i < max_retry - 1:
        time.sleep(self.retry_wait_seconds)
```

---

## Bug-4: JSON 修复器对非法反斜杠转义处理不全面

### 状态：🟡 部分存在

### 位置

`quantaalpha/llm/client.py:1066-1114`

### 现象

LLM 返回的 JSON 中包含非法反斜杠转义（如 `\_`），当前的修复代码仅枚举了常见 LaTeX 命令和 `_{}[]` 字符，没有使用通用正则来捕获所有非法转义。

### 当前修复逻辑

```python
# 仅枚举处理：\text, \frac, \left, \right, \times, \cdot, \sqrt, \sum, \prod, \int
# 加上 \_, \{, \}, \[, \]
```

### 修复方案

在现有枚举修复之后，追加一个通用兜底正则：

```python
# 修复所有非标准 JSON 反斜杠转义
fixed_resp = re.sub(r'\\(?!["\\\/bfnrtu])', r'\\\\', fixed_resp)
```

---

## Bug-5: 废弃 `proposal.yaml` 被静默覆盖

### 状态：🟡 代码隐患

### 位置

`quantaalpha/factors/proposal.py:61` 与 `quantaalpha/factors/proposal.py:207`

### 现象

`proposal.py` 中 `qa_prompt_dict` 变量被赋值两次：

```python
# Line 61
qa_prompt_dict = Prompts(file_path=Path(__file__).parent / "prompts" / "proposal.yaml")

# Line 207 — 覆盖了上面的赋值
qa_prompt_dict = Prompts(file_path=Path(__file__).parent / "prompts" / "prompts.yaml")
```

`proposal.yaml` 中的 `hypothesis_gen.system_prompt` **缺少 DSL 约束**（没有 `{{ function_lib_description }}`），但由于被 `prompts.yaml` 覆盖，实际运行时不会使用到 `proposal.yaml` 的内容。

这不是一个运行时 bug，但极易误导维护者。archived 的 `bug-report.md` 中 Bug A（hypothesis 缺少 DSL 约束）的描述基于的就是 `proposal.yaml`，而非实际运行的 `prompts.yaml`。

### 修复方案

- 删除 `proposal.py:61` 处对 `proposal.yaml` 的第一次赋值
- 或者将 `proposal.yaml` 中不再使用的 prompt 清理掉（整个文件可考虑删除或归档）
- 确保仅保留一次 `qa_prompt_dict` 赋值

---

## 已修复的历史 Bug

### ~~Bug-B: `consistency_checker.py` 异常时返回 `is_consistent=True`~~

**状态**: ✅ 已修复

在 `consistency_checker.py:127-136` 中，异常处理分支已经从：

```python
# 旧代码
return ConsistencyCheckResult(
    is_consistent=True,   # ← 任何异常都当作通过
    severity="none"
)
```

修复为：

```python
# 当前代码
return ConsistencyCheckResult(
    is_consistent=False,  # ← 异常视为不通过
    severity="critical"   # ← 异常视为 critical
)
```

---

## 修复优先级总结

1. **P0**: Bug-1 + Bug-2 — 同时修复 prompt 约束（源头减少错误格式）和 normalize 函数（兜底清洗）
2. **P1**: Bug-3 — 对不可恢复的 API 错误立即终止，避免浪费重试
3. **P2**: Bug-4 — 增强 JSON 修复器的通用性
4. **P2**: Bug-5 — 清理废弃配置，消除维护隐患
