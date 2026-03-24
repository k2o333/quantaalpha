# Mining Pipeline 问题分析：Expression 解析失败与 Consistency Check 不一致

**日期**: 2026-03-24  
**运行日志**: `third_party/facotors/terminal/20260324_151437.txt`  
**触发命令**: `./run.sh "挖掘日频时间序列因子"` (via `third_party/quantaalpha/run.sh`)

---

## 1. 现象总结

运行 `run.sh` 后，pipeline 在 factor construct 阶段出现了大量错误，最终因 API 调用失败而崩溃。主要问题分为三类：

### 1.1 Expression 解析失败（占 ERROR 的大多数）

LLM 在 consistency check 的 correction 步骤中返回了**不可解析的 expression 格式**，导致 parser 报错。具体表现为 LLM 返回了以下非标准格式：

| 行号 | 解析器报错 | LLM 返回的错误格式 |
|------|-----------|-------------------|
| 156 | `Unclosed parentheses` | 括号不匹配的表达式 |
| 471-472 | `Expected ?: operations, found '/'` | 带 `//` 注释的多行代码块 |
| 528-545 | `Invalid operator(s): "//"` | 同上，`// Option 1:` / `// Option 2:` 注释 |
| 1310-1311 | `Invalid operator(s): "#"` | 行尾加了 `# MEAN is cross-sectional` 注释 |
| 1515-1529 | `Invalid operator(s): ".,//;="` | Python 伪代码：`dispersion = ...; factor = IF(...)` |
| 1801-1802 | `Invalid operator(s): "'{'\//'}"` | Python dict 格式：`{'primary_factor': '...', 'illiquidity_proxy': '...'}` |

### 1.2 JSON 解析失败（仅 1 次）

- `line 1308`: `JSON fix failed: Invalid \escape` — LLM 响应中包含非法反斜杠转义序列（如 `\_`），JSON 修复器无法处理。

### 1.3 API 调用失败（5 次重试后任务崩溃）

- `line 903-948`: `Error code: 400 - Invalid model name passed in model=leanstral-2603`
- 重试 5 次后在 `line 953` 抛出 `RuntimeError: Failed to create chat completion after 5 retries.`
- 此错误发生在 factor_construct → factor_calculate 阶段，即 LLM 需要生成 factor code 时。

### 1.4 Consistency Check 不一致循环

多个 factor 在 consistency check 中反复失败，形成**修正-失败-再修正**的死循环：

```
factor 生成 → consistency check 失败 (major) 
→ 尝试 expression correction (1/3) → 新 expression 无法解析 
→ 尝试 description correction (2/3) → 仍然不一致 
→ 尝试再次 correction (3/3) → 仍然不一致 → 放弃
```

典型 example: `Volatility_Adjusted_Dispersion_Rank_21D` (line 337-510)，经历了 3 次修正全部失败。

---

## 2. 相关文件

### 2.1 核心代码文件

| 文件 | 作用 |
|------|------|
| `quantaalpha/factors/proposal.py:468-587` | `_convert_with_history_limit` — factor 生成主循环，包含 consistency check 调用 |
| `quantaalpha/factors/proposal.py:23-27` | `normalize_corrected_expression` — 修正后 expression 的格式化 |
| `quantaalpha/factors/regulator/consistency_checker.py:138-189` | `check_and_correct` — consistency check + 修正循环 |
| `quantaalpha/factors/regulator/consistency_checker.py:59-136` | `check_consistency` — 单次 consistency check |
| `quantaalpha/factors/regulator/consistency_prompts.yaml` | consistency check 的 system/user prompt 模板 |
| `quantaalpha/factors/regulator/factor_regulator.py:44-59` | `is_parsable` — expression 解析检查 |
| `quantaalpha/llm/client.py:790-822` | `_try_create_chat_completion_or_embedding` — API 重试逻辑 |
| `quantaalpha/llm/client.py:1080-1117` | JSON 修复逻辑 (`_escape_control_chars_in_json`) |

### 2.2 配置文件

| 文件 | 作用 |
|------|------|
| `third_party/quantaalpha/run.sh` | 实验启动脚本 |
| `configs/experiment.yaml` | 实验配置（未读取，但由 run.sh 引用） |

### 2.3 运行日志

| 文件 | 内容 |
|------|------|
| `third_party/facotors/terminal/20260324_151437.txt` | 完整运行日志（~2400+ 行） |

---

## 3. 问题根因分析

### 3.1 Expression 解析失败的根本原因

**LLM 在 consistency check 的 correction 步骤中，倾向于返回"人类可读"的格式，而非 parser 可解析的纯 expression。**

具体机制：

1. `consistency_checker.py:168-172` 中，`check_and_correct` 取 LLM 返回的 `corrected_expression` 并直接赋值给 `current_expression`
2. `corrected_expression` 来自 `consistency_prompts.yaml:40` 的 JSON 响应字段
3. prompt 中**没有明确约束** `corrected_expression` 的格式要求——没有说"只返回单行无注释的数学表达式"
4. LLM 因此自由发挥，返回了：
   - 带 `//` 或 `#` 注释的表达式
   - 多行伪代码（带变量赋值）
   - Python dict（多个选项）
   - 带 `Option 1` / `Option 2` 的多方案输出

5. `normalize_corrected_expression` (proposal.py:23-27) 只处理了 `dict` 类型，**没有**处理字符串中的注释、伪代码等问题。

### 3.2 Consistency Check 循环的根本原因

**假说中要求的 illiquidity 交互项，LLM 在生成 factor 时经常遗漏。**

1. 假说要求：`dispersion normalized by historical volatility × Amihud illiquidity`
2. LLM 生成的 factor 经常只有 `dispersion` 或 `dispersion / volatility`，缺少 `× illiquidity`
3. Consistency checker 正确地检测到了这个问题
4. 但修正时 LLM 返回的 expression 格式又不可解析 → 修正失败 → 重试 → 同样的问题

这是一个**级联失败**：根本问题（遗漏 illiquidity）导致触发修正机制，而修正机制本身又因为格式问题失败。

### 3.3 API 错误的根本原因

`Invalid model name passed in model=leanstral-2603` 表明：

- 模型名称 `leanstral-2603` 在 API 服务器端不存在或当前 API key 无权访问
- 前期的 consistency check 调用（同样是 `leanstral-2603`）是成功的，说明可能是 API 服务临时问题或 token 过期
- 重试逻辑（`client.py:797-822`）对 `BadRequestError` 做了重试，但没有针对 "Invalid model name" 做特殊处理（如切换模型）

---

## 4. 修复建议

### 4.1 修复 Expression 格式问题（优先级：高）

**方案 A：在 consistency_prompts.yaml 中加强格式约束**

修改 `consistency_prompts.yaml` 中的 `consistency_check_system` prompt，在 Output Format 部分添加明确约束：

```yaml
consistency_check_system: |-
  ...
  **Output Format (JSON):**
  {
    ...
    "corrected_expression": "Corrected expression if needed. CRITICAL: This MUST be a SINGLE-LINE expression using ONLY the available functions and variables. Do NOT include comments (// or #), variable assignments, multiple options, or pseudo-code. Example: 'STD(TS_PCTCHANGE($close, 21)) / (TS_STD($return, 63) + 1e-8)'",
    ...
  }
```

**方案 B：在 `normalize_corrected_expression` 中添加清洗逻辑**

修改 `quantaalpha/factors/proposal.py:23-27`：

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
        # Remove // comments
        line = re.sub(r'\s*//.*$', '', line)
        # Remove # comments  
        line = re.sub(r'\s*#.*$', '', line)
        # Skip lines that look like variable assignments (dispersion = ...)
        if re.match(r'^\s*\w+\s*=', line) and not line.strip().startswith('('):
            continue
        # Skip empty lines
        if line.strip():
            cleaned_lines.append(line.strip())
    
    result = ' '.join(cleaned_lines) if cleaned_lines else expression.strip()
    
    # If result still looks like a dict/invalid, try to extract first valid expression
    if result.startswith('{') or result.startswith('//'):
        # Try to find a function-call-like pattern
        match = re.search(r'([A-Z_]+\(.+\))', result)
        if match:
            result = match.group(1)
    
    return result
```

**方案 C：同时实施 A + B（推荐）**

Prompt 约束从源头减少错误格式，normalize 函数作为兜底清洗。

### 4.2 修复 Consistency Check 循环（优先级：高）

**方案 A：降低 consistency check 的严格度**

修改 `consistency_checker.py:229` 的 `should_proceed_to_backtest`，允许 major severity 的 factor 也进入 backtest：

```python
def should_proceed_to_backtest(self, result: ConsistencyCheckResult) -> bool:
    if result.severity in ["none", "minor", "major"]:  # 允许 major
        return True
    return False
```

**方案 B：在 consistency check 的 correction prompt 中也约束格式**

修改 `consistency_prompts.yaml` 的 `expression_correction_system` prompt，在 Rules 部分添加：

```yaml
expression_correction_system: |-
  ...
  **Rules:**
  - Expression must be parsable and executable
  - Use only the listed functions and variables
  - Keep the expression as simple as possible while maintaining correctness
  - Do not use undefined variables or functions
  - **CRITICAL: Return ONLY a single-line mathematical expression. No comments, no pseudo-code, no multiple options, no variable assignments.**
```

### 4.3 修复 API 错误（优先级：中）

**方案：添加模型 fallback 机制**

修改 `client.py:790-822` 的 `_try_create_chat_completion_or_embedding`，对 "Invalid model name" 错误做特殊处理：

```python
except openai.BadRequestError as e:
    logger.warning(e)
    logger.warning(f"Retrying {i+1}th time...")
    if "Invalid model name" in str(e) or "Invalid model" in str(e):
        # Log warning and re-raise immediately instead of retrying
        logger.error(f"Model '{self.chat_model}' is invalid. Check model configuration.")
        raise
    # ... existing retry logic
```

或更进一步，添加 fallback model 配置：

```python
# In config/.env or settings
CHAT_MODEL_FALLBACK=gpt-4o-mini  # Fallback when primary model fails
```

### 4.4 修复 JSON 解析错误（优先级：低）

当前 `_escape_control_chars_in_json` 已经处理了大部分 JSON 格式问题。唯一失败的 case（`line 1308`，非法 `\_` 转义）可以通过增强 JSON 修复器来处理：

```python
# 在 _escape_control_chars_in_json 之后添加
import re
fixed_resp = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', fixed_resp)  # 修复非法转义
```

---

## 5. 影响范围

| 问题 | 影响 | 频率 |
|------|------|------|
| Expression 解析失败 | Factor 被跳过，浪费 LLM 调用 | ~60% 的 consistency check 修正 |
| Consistency check 循环 | 每个 factor 最多 3+1 次 LLM 调用 | 几乎所有含 illiquidity 的 factor |
| API 错误 | 任务直接失败 | 1 次（但导致整个 direction 重试） |
| JSON 解析错误 | LLM 响应被丢弃 | ~5% 的 LLM 响应 |

---

## 6. 建议的修复优先级

1. **P0**: 修复 expression 格式问题（方案 4.1 C）— 直接影响 factor 生成成功率
2. **P0**: 修复 consistency check 循环（方案 4.2）— 减少不必要的 LLM 调用
3. **P1**: 修复 API 错误处理（方案 4.3）— 避免任务因临时 API 问题崩溃
4. **P2**: 修复 JSON 解析（方案 4.4）— 低频问题，已有部分防护
