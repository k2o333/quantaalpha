# iFlow CLI 无头模式使用说明书

## 概述

iFlow CLI 的无头模式（Headless Mode）允许在非交互式环境中运行命令，适用于 CI/CD 管道、脚本自动化和服务器环境。该模式通过命令行参数指定提示（prompt），并启用 YOLO 模式以授予模型最大权限，无需用户确认。

## 系统要求

- iFlow CLI 版本：0.5.15 或更高（推荐，用于完整的无头模式会话续连支持）
- Node.js 22+
- 网络连接（用于认证和 AI 处理）
- 支持 Bash、Zsh 或 Fish shell

## 使用方法

### 基本语法

```bash
iflow -p "your prompt here" -y [其他选项]
```

### 必需参数

- `-p, --prompt`: 指定要执行的提示文本（必需）
- `-y, --yolo`: 启用 YOLO 模式，允许模型执行任何操作（必需，用于无头模式）
- `-c, --continue`: 直接继续最近一次的对话会话（可选，用于会话续连）

### 可选参数

- `--jsonl`: 输出为 JSONL 格式，便于自动化解析（推荐用于脚本）
- `-r, --resume`: 显示历史对话列表，让用户选择要恢复的对话会话（注意：无头模式下建议使用 `-c` 代替）
- `-c, --continue`: 直接继续最近一次的对话会话，无需选择（推荐用于无头模式会话续连）
- `--prompt-interactive, -i`: 以指定提示启动交互式会话（提示在交互式会话内处理）
- `--session-id <uuid>`: 指定会话 ID（如果未提供，自动生成）
- `--model <model_name>`: 指定模型，如 Qwen3-Coder（默认使用配置的模型）
- `--output <file>`: 将输出重定向到文件
- `-d, --debug`: 启用调试模式，提供更详细的输出
- `-s, --sandbox`: 为此会话启用沙箱模式

### 环境变量

- `IFLOW_API_KEY`: 设置 API 密钥（避免交互式输入）
- `IFLOW_BASE_URL`: 设置 API 基础 URL（默认 https://apis.iflow.cn/v1）
- `IFLOW_MODEL_NAME`: 设置默认模型
- `IFLOW_APPROVAL_MODE`: 设置默认审批模式（如 "yolo"、"plan"、"autoEdit"、"default"）
- `IFLOW_DISABLE_AUTO_UPDATE`: 禁用自动更新（设置为 "true"）

## 示例

### 基本代码分析

```bash
iflow -p "Analyze this codebase and generate a summary" -y
```

### 生成文档

```bash
iflow -p "Generate technical documentation for the project" -y --jsonl
```

### 指定模型和输出

```bash
export IFLOW_API_KEY=your_key_here
iflow -p "Fix the bug in main.js" -y --model Qwen3-Coder --output result.jsonl
```

### GitHub Actions 示例（类似无头模式）

在 `.github/workflows/ci.yml` 中：

```yaml
- name: Run iFlow CLI
  uses: iflow-ai/iflow-cli-action@v2.0.0
  with:
    prompt: "Run tests and generate report"
    api_key: ${{ secrets.IFLOW_API_KEY }}
    model: "qwen3-coder-plus"
```

### 无头模式会话续连（v0.5.15+）

从版本 0.5.15 开始，支持在无头模式下继续之前的会话：

```bash
# 继续最近一次的对话会话
iflow -c -p "继续之前的任务" -y

# 简写形式
iflow -cp "继续之前的任务"

# 使用 session-id 继续特定会话
iflow --session-id <uuid> -p "继续开发" -y
```

## 输出格式

### 默认输出

标准终端输出，包括 AI 响应和执行结果。

### JSONL 输出（推荐用于自动化）

使用 `--jsonl` 启用，每行一个 JSON 对象，包含：
- 时间戳
- 会话 ID
- 消息类型（prompt、response、action 等）
- 内容

示例：
```json
{"timestamp": "2026-03-18T12:00:00Z", "sessionId": "uuid", "type": "response", "content": "Analysis complete"}
```

## 故障排除

### 常见问题

1. **-r 标志挂起**：在无头模式下避免使用 `-r`（resume），因为它会显示交互式选择界面。建议使用 `-c`（continue）直接继续最近会话，或使用 `--session-id` 手动指定会话。
   
2. **认证失败**：确保设置了 `IFLOW_API_KEY` 环境变量，或使用 API 密钥参数。

3. **权限不足**：确保使用 `-y` 启用 YOLO 模式，否则模型权限受限。

4. **网络问题**：检查互联网连接和防火墙设置。

5. **模型不可用**：验证模型名称正确，支持的模型包括 Qwen3-Coder、DeepSeek v3、GLM-4.6 等。

6. **会话续连失败**：确保会话 ID 有效，或使用 `-c` 自动继续最近会话（需要 v0.5.15+）。

### 调试

- 添加 `--verbose` 获取详细日志。
- 检查 `~/.iflow/logs/` 目录的日志文件。
- 查看 GitHub Issues：https://github.com/iflow-ai/iflow-cli/issues

## 安全注意事项

- YOLO 模式授予模型最大权限，可能执行文件修改、命令运行等操作。仅在可控环境中使用。
- 不要在生产环境中运行未验证的提示。
- 定期更新 CLI 以获取安全补丁。

## 参考资源

- 官方 README: https://github.com/iflow-ai/iflow-cli/blob/main/README.md
- GitHub Action 文档: https://iflow-ai.github.io/iflow-cli-action/
- 相关 Issues:
  - Headless mode: https://github.com/iflow-ai/iflow-cli/issues/196
  - JSONL 输出: https://github.com/iflow-ai/iflow-cli/issues/239
  - Session ID: https://github.com/iflow-ai/iflow-cli/issues/372

运行 `iflow -h` 查看最新命令帮助。