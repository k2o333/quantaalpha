Status: draft
Owner: AI Assistant
Created: 2026-03-06
Outcome: pending

# QuantaAlpha JSON 解析错误修复方案复核版

## 结论

`/home/quan/testdata/aspipe_v4/p/2026-3-6/quantaalpha_json_decode_error_fix.md` 的方向基本正确，但还不完全符合更稳妥的修复思路。

主要差异有两点：

1. 文档正确否定了全局 `replace('\n', '\\n')` 的做法。
2. 文档高估了 `robust_json_parse()` 的能力。当前实现并 **不会** 修复字符串内部的未转义换行、回车、制表符，也不会修复字符串内部未转义双引号。

因此，当前文档可以作为“修复方向说明”，但不能作为“方案已经闭环”的依据。

---

## 一、和实际代码一致的部分

以下判断是成立的：

1. `eva_utils.py` 当前直接对模型响应做 `json.loads(...)`，缺少统一的健壮解析入口。
2. `eva_utils.py` 当前对 `JSONDecodeError` 没有重试，只要首个响应损坏就直接终止。
3. `client.py` 里现有的 JSON 修复逻辑只覆盖了部分反斜杠/LaTeX 场景，覆盖面不足。
4. 全局替换 `\n`、`\r`、`\t` 会破坏 JSON 结构本身，这是错误方案。

---

## 二、原文档仍不准确的地方

### 2.1 `robust_json_parse()` 的能力描述过强

当前 `robust_json_parse()` 实际只做了这些事：

1. 直接 `json.loads`
2. 从 markdown 代码块中提取 JSON
3. 从整段文本中提取第一个完整 `{...}` 对象
4. 修复部分 LaTeX / 非法反斜杠转义
5. 用更宽松的正则再尝试提取 JSON

它 **没有** 做这些事：

1. 没有逐字符修复字符串内部未转义换行
2. 没有逐字符修复字符串内部未转义回车/制表符
3. 没有修复字符串内部未转义双引号
4. 没有在状态机扫描时重写字符流，只是在找 JSON 边界

所以不能把它描述为“只处理字符串内部非法控制字符”的解析器。它现在只是“更健壮的 JSON 提取器”，不是“控制字符修复器”。

### 2.2 根因仍然不能下定论

报错：

```text
Expecting property name enclosed in double quotes: line 4 column 1 (char 274)
```

这更像是 JSON 结构断裂，而不是单纯的未转义换行。

更可能的情况包括：

1. 字符串提前结束，后续文本落到了对象结构位置
2. 字符串中出现未转义双引号
3. 对象字段之间缺逗号
4. 响应被截断或拼接污染

在拿到完整原始响应前，不能把“未转义换行”当成已确认根因。

### 2.3 只在 `eva_utils.py` 切换到 `robust_json_parse()` 仍然偏局部

仓库中有多处 `json_mode=True` 之后直接 `json.loads(...)`。即使这次只修 `eva_utils.py`，也只是修掉当前暴露出来的一处调用点，不能避免同类问题在别的路径重复出现。

---

## 三、建议的修复层次

### 方案 A：最小安全修复

目标：先解决当前失败路径，风险最低。

修改：

1. 在 `quantaalpha/factors/coder/eva_utils.py` 中把直接 `json.loads(...)` 改成 `robust_json_parse(...)`
2. 给 `JSONDecodeError` 增加和 `KeyError` 同级别的重试

作用：

1. 能处理 markdown 包裹、前后夹杂文本、部分反斜杠转义问题
2. 对偶发脏响应有一定恢复能力

限制：

1. 如果根因真是字符串内部控制字符或未转义引号，这个方案不一定够

### 方案 B：完整修复

目标：补上 `robust_json_parse()` 目前缺失的“字符串内部非法字符修复”。

在 `quantaalpha/llm/client.py` 中新增一个更精确的修复函数，例如：

```python
def sanitize_json_string_controls(text: str) -> str:
    """
    只在 JSON 字符串内部把非法控制字符转义：
    - \n -> \\n
    - \r -> \\r
    - \t -> \\t
    同时保留 JSON 结构空白。
    """
```

实现原则：

1. 必须逐字符扫描
2. 必须维护 `in_string` / `escape_next` 状态
3. 只能在字符串内部转义非法控制字符
4. 不能改动字符串外部的 JSON 结构空白

然后让 `robust_json_parse()` 在直接解析失败后，新增一步：

1. 先提取候选 JSON 对象
2. 对候选对象执行 `sanitize_json_string_controls`
3. 再 `json.loads`

### 方案 C：统一入口

长期应该把所有 `json_mode=True` 的响应解析收敛到统一入口，例如：

```python
def build_messages_and_create_chat_completion_json(self, ...) -> dict:
    response = self.build_messages_and_create_chat_completion(...)
    return robust_json_parse(response)
```

这样可以避免每个调用方各自写一遍 `json.loads(...)` 和异常处理。

---

## 四、推荐的最终表述

如果要保留原文档，可以把核心结论改成下面这版：

> 当前问题的直接触发点是 `eva_utils.py` 对 LLM JSON 响应直接使用 `json.loads(...)`，而该路径没有使用现有的 `robust_json_parse()`，同时也没有 `JSONDecodeError` 重试。
>
> 现有 `robust_json_parse()` 能提升对“额外包裹文本、markdown 代码块、部分非法反斜杠转义”的容错，但它尚不能修复字符串内部未转义控制字符或未转义双引号。
>
> 因此，短期可先在 `eva_utils.py` 接入 `robust_json_parse()` 并增加重试；若后续确认原始响应中存在字符串内部非法控制字符，则需要继续增强 `robust_json_parse()`，而不是采用全局 `replace('\n', '\\n')` 这类会破坏 JSON 结构的做法。

---

## 五、建议是否实施

如果目的是先让当前流程少挂一次，建议先实施方案 A。

如果目的是“确认解决这类 JSON 损坏问题”，则还不够，应该继续做方案 B 和方案 C。
