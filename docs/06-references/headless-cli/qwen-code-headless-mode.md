# Qwen Code 无头模式使用指南

## 1. 什么是无头模式

**无头模式（Headless Mode）** 允许你通过命令行脚本和自动化工具以编程方式运行 Qwen Code，**无需任何交互式用户界面**。

### 适用场景

- 脚本编写
- 自动化任务
- CI/CD 流水线
- 构建 AI 驱动的工具

### 核心能力

| 能力 | 说明 |
|------|------|
| 输入方式 | 通过命令行参数或标准输入（stdin）接收提示 |
| 输出格式 | 返回结构化输出（纯文本或 JSON 格式） |
| 文件操作 | 支持文件重定向与管道（piping） |
| 自动化 | 支持自动化与脚本化工作流 |
| 错误处理 | 提供一致的退出码 |
| 会话恢复 | 可基于当前项目恢复之前的会话 |

---

## 2. 启动方式

### 2.1 基本命令

```bash
# 使用 --prompt（或 -p）标志以无头模式运行
qwen --prompt "什么是机器学习？"
qwen -p "什么是机器学习？"
```

### 2.2 从标准输入传入内容

```bash
# 通过管道传递输入
echo "解释这段代码" | qwen

# 从文件读取内容
cat README.md | qwen --prompt "总结此文档"
```

### 2.3 恢复之前的会话

```bash
# 继续当前项目的最近一次会话
qwen --continue -p "再次运行测试并汇总失败项"

# 恢复指定的会话 ID
qwen --resume 123e4567-e89b-12d3-a456-426614174000 -p "应用后续重构"
```

> **注意**：会话数据以 JSONL 格式存储于 `~/.qwen/projects/<规范化当前工作目录>/chats` 目录下。

---

## 3. 认证方式

无头模式使用与交互式模式相同的认证配置。

### 3.1 OAuth 认证（推荐）

```bash
# 启用 OAuth 认证模式
QWEN_OAUTH=1 qwen -p "hi"
```

**授权流程：**

1. 运行命令后，终端会显示授权 URL
2. 在浏览器中访问该 URL
3. 使用 Google 账号完成授权

**预期输出：**
```
=== Qwen OAuth Device Authorization ===
Please visit the following URL in your browser to authorize:

https://chat.qwen.ai/authorize?user_code=XXXXXXXX&client=qwen-code

Waiting for authorization to completed...
```

### 3.2 其他认证方式

认证信息可配置在：

- 配置文件（参考 [配置指南](https://qwenlm.github.io/qwen-code-docs/zh/users/config/)）
- 环境变量
- 身份验证设置

### 3.3 版本差异说明

| 版本 | 状态 | 行为描述 |
|------|------|----------|
| **v0.2.3 及之前** | ✅ 正常 | 无头模式认证可以正常工作 |
| **v0.3 及之后** | ❌ 故障 | 认证过程可能永久卡住 |

> 如遇认证问题，可尝试使用 v0.2.3 或之前版本。

---

## 4. 命令行参数

### 4.1 核心参数

| 参数 | 简写 | 描述 | 示例 |
|------|------|------|------|
| `--prompt` | `-p` | 以无头模式运行 | `qwen -p "query"` |
| `--output-format` | `-o` | 指定输出格式（text/json/stream-json） | `qwen -p "query" --output-format json` |
| `--input-format` | - | 指定输入格式（text/stream-json） | `qwen --input-format text` |
| `--include-partial-messages` | - | 在 stream-json 输出中包含部分消息 | `qwen -p "query" --include-partial-messages` |
| `--debug` | `-d` | 启用调试模式 | `qwen -p "query" --debug` |
| `--all-files` | `-a` | 将所有文件包含在上下文中 | `qwen -p "query" --all-files` |
| `--include-directories` | - | 包含额外的目录 | `qwen -p "query" --include-directories src,docs` |
| `--yolo` | `-y` | 自动批准所有操作 | `qwen -p "query" --yolo` |
| `--approval-mode` | - | 设置审批模式 | `qwen -p "query" --approval-mode auto_edit` |
| `--continue` | - | 恢复此项目的最近一次会话 | `qwen --continue -p "继续"` |
| `--resume` | - | 恢复指定会话 | `qwen --resume 123e... -p "完成重构"` |

---

## 5. 输出格式

### 5.1 文本输出（默认）

```bash
qwen -p "法国的首都是哪里？"
```

**响应格式：**
```
法国的首都是巴黎。
```

### 5.2 JSON 输出

```bash
qwen -p "法国的首都是什么？" --output-format json
```

**输出示例：**
```json
[
  {
    "type": "system",
    "subtype": "session_start",
    "uuid": "...",
    "session_id": "...",
    "model": "qwen3-coder-plus"
  },
  {
    "type": "assistant",
    "uuid": "...",
    "session_id": "...",
    "message": {
      "role": "assistant",
      "content": [{"type": "text", "text": "法国的首都是巴黎。"}]
    }
  },
  {
    "type": "result",
    "subtype": "success",
    "is_error": false,
    "duration_ms": 1234,
    "result": "法国的首都是巴黎。"
  }
]
```

### 5.3 Stream-JSON 输出

```bash
qwen -p "解释 TypeScript" --output-format stream-json
```

**输出示例（行分隔 JSON）：**
```json
{"type":"system","subtype":"session_start","uuid":"...","session_id":"..."}
{"type":"assistant","uuid":"...","session_id":"...","message":{...}}
{"type":"result","subtype":"success","uuid":"...","session_id":"..."}
```

配合 `--include-partial-messages` 可实现实时更新：
```bash
qwen -p "编写一个 Python 脚本" --output-format stream-json --include-partial-messages
```

---

## 6. 使用场景示例

### 6.1 代码审查

```bash
cat src/auth.py | qwen -p "审查此身份验证代码是否存在安全问题" > security-review.txt
```

### 6.2 生成提交信息

```bash
result=$(git diff --cached | qwen -p "为这些更改编写简洁的提交信息" --output-format json)
echo "$result" | jq -r '.response'
```

### 6.3 批量代码分析

```bash
for file in src/*.py; do
    echo "正在分析 $file..."
    result=$(cat "$file" | qwen -p "查找潜在缺陷并提出改进建议" --output-format json)
    echo "$result" | jq -r '.response' > "reports/$(basename "$file").analysis"
    echo "已完成 $(basename "$file") 的分析" >> reports/progress.log
done
```

### 6.4 PR 代码审查

```bash
result=$(git diff origin/main...HEAD | qwen -p "审查这些变更，查找缺陷、安全问题及代码质量问题" --output-format json)
echo "$result" | jq -r '.response' > pr-review.json
```

### 6.5 日志分析

```bash
grep "ERROR" /var/log/app.log | tail -20 | qwen -p "分析这些错误，指出根本原因并提供修复建议" > error-analysis.txt
```

### 6.6 生成发布说明

```bash
result=$(git log --oneline v1.0.0..HEAD | qwen -p "根据这些提交生成发布说明" --output-format json)
response=$(echo "$result" | jq -r '.response')
echo "$response" >> CHANGELOG.md
```

### 6.7 使用情况追踪

```bash
result=$(qwen -p "解释此数据库模式" --include-directories db --output-format json)
total_tokens=$(echo "$result" | jq -r '.stats.models // {} | to_entries | map(.value.tokens.total) | add // 0')
models_used=$(echo "$result" | jq -r '.stats.models // {} | keys | join(", ")')
tool_calls=$(echo "$result" | jq -r '.stats.tools.totalCalls // 0')
echo "$(date): $total_tokens 个 token，$tool_calls 次工具调用，所用模型：$models_used" >> usage.log
```

---

## 7. 文件重定向示例

```bash
# 保存到文件
qwen -p "解释 Docker" > docker-explanation.txt
qwen -p "解释 Docker" --output-format json > docker-explanation.json

# 追加到文件
qwen -p "补充更多细节" >> docker-explanation.txt

# 管道传递给其他工具
qwen -p "Kubernetes 是什么？" --output-format json | jq '.response'
qwen -p "解释微服务" | wc -w
qwen -p "列出编程语言" | grep -i "python"

# Stream-JSON 实时处理
qwen -p "解释 Docker" --output-format stream-json | jq '.type'
```

---

## 8. 相关资源

- [官方文档 - 无头模式](https://qwenlm.github.io/qwen-code-docs/zh/users/features/headless/)
- [CLI 配置指南](https://qwenlm.github.io/qwen-code-docs/zh/users/config/)
- [身份验证配置](https://qwenlm.github.io/qwen-code-docs/zh/users/config/authentication/)
- [命令参考](https://qwenlm.github.io/qwen-code-docs/zh/users/features/commands/)
- [教程](https://qwenlm.github.io/qwen-code-docs/zh/tutorials/)
- [NPM 包](https://www.npmjs.com/package/@qwen-code/qwen-code)

---

## 9. 已知问题

| Issue | 描述 | 状态 |
|-------|------|------|
| [#1143](https://github.com/QwenLM/qwen-code/issues/1143) | 无头模式/SDK 问题追踪 | Open |
| [#1425](https://github.com/QwenLM/qwen-code/issues/1425) | v0.3+ 版本无头模式认证卡住 | Closed |
