# Knowledge Register

<!-- Append-only. Never edit or remove existing rows.
     To reverse a decision, add a new row that supersedes it.
     Read this file at the start of any planning or research phase. -->

## M001: QuantaAlpha 关键 Bug 修复 (2026-03-22)

### 修复摘要

修复了导致因子挖掘工作流卡死的 4 个关键 Bug：

1. **Logger 参数签名不匹配** - `RDAgentLog.warning()` 只接受单个 `msg` 参数，但代码使用了 `%s` 多参数格式
2. **LLM 空响应导致 JSON 解析崩溃** - 空响应进入 JSON 提取逻辑产生无效切片
3. **无限重试死循环** - `while True` 循环没有重试上限，导致进程卡死
4. **JSON 控制字符未转义** - JSON fix 逻辑只处理 LaTeX 反斜杠，不处理控制字符

### 修改的文件

| 文件 | 修改内容 |
|------|----------|
| `llm/client.py:69-74` | `log_tokenizer_fallback_once()` 使用 f-string |
| `llm/client.py:667` | `get_model_for_task()` 使用 f-string |
| `llm/client.py:1022-1027` | 流式分支空响应检查 |
| `llm/client.py:1034-1038` | 非流式分支空响应检查 |
| `llm/client.py:1078-1102` | JSON 控制字符转义（`_escape_control_chars_in_json`） |
| `backtest/universe.py:111` | `_coerce_date()` 使用 f-string |
| `factors/proposal.py:483` | `while True` → `for attempt in range(MAX_RETRIES)` |
| `factors/proposal.py:491-494` | 循环内空响应检查 |
| `factors/proposal.py:615` | 循环结束 `RuntimeError` |

### 关键教训

1. **日志兼容性**: `RDAgentLog` 与标准 `logging.Logger` API 不兼容，必须使用 f-string 而非 `%s` 格式
2. **防御性编程**: LLM 响应可能为空，必须在 JSON 解析前检查
3. **重试上限**: 任何重试循环都必须有明确上限，防止无限循环
4. **JSON 控制字符**: 需要区分 JSON 字符串内部的控制字符和结构空白，不能简单全局替换

### 验证方法

```bash
# 语法检查
python -m py_compile third_party/quantaalpha/quantaalpha/llm/client.py
python -m py_compile third_party/quantaalpha/quantaalpha/backtest/universe.py
python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py

# 日志验证（运行后检查）
grep -c "RDAgentLog.warning() takes 2 positional arguments" terminal.log  # 应为 0
grep -c "Invalid control character" terminal.log  # 应为 0
grep -c "Factor proposal failed after.*retries" terminal.log  # 应有值（10次后退出）
```

### 未解决问题（M002）

- `'dict' object has no attribute 'replace'` 错误（consistency check 数据类型问题）
- 上游 LiteLLM 代理对大 prompt 返回空响应的问题

---

## 项目知识

### 模块结构

- **app4**: TuShare Pro 数据管道（43 接口，7 分页模式）
- **quantaalpha**: 因子挖掘和评估（LLM 辅助因子生成）
- **backtest**: Alpha101 因子回测验证

### 关键文件位置

- 终端日志: `third_party/facotors/terminal/`
- 因子代码: `third_party/quantaalpha/quantaalpha/factors/`
- LLM 客户端: `third_party/quantaalpha/quantaalpha/llm/client.py`

### 运行命令

```bash
cd third_party/quantaalpha
./run.sh "挖掘日频横截面因子"
```
