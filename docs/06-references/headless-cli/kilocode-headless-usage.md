# KiloCode CLI 无头模式 (Headless Mode) 使用指南

本文档介绍 KiloCode 的无头模式使用方法，适用于脚本编写、自动化、CI/CD 集成和 API 调用场景。

## 概述

KiloCode 提供以下几种无头模式命令：

| 命令 | 用途 |
|------|------|
| `kilo serve` | 启动无头 HTTP 服务器，提供 REST API 访问 |
| `kilo run` | 非交互式执行，直接传递提示并获取结果 |
| `kilo` (默认) | 启动 TUI 交互式界面 |

---

## 1. `kilo serve` - 无头 HTTP 服务器

`kilo serve` 启动一个无头 Kilo 后端服务器，通过 HTTP/SSE API 提供外部访问能力。

### 基本用法

```bash
# 启动服务器（默认端口 3000）
kilo serve
```

### 环境变量配置

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `KILO_SERVER_PASSWORD` | 启用 HTTP Basic Auth 的密码 | 未设置（警告：服务器无保护） |
| `KILO_SERVER_USERNAME` | HTTP Basic Auth 的用户名 | `kilo` |
| `KILO_CONFIG_CONTENT` | 提供内联 JSON 配置内容 | - |

### 使用示例

#### 启动带认证的服务器

```bash
# 设置密码启用认证
export KILO_SERVER_PASSWORD="your_secure_password"
kilo serve
```

#### 指定用户名和密码

```bash
export KILO_SERVER_USERNAME="admin"
export KILO_SERVER_PASSWORD="secure_password"
kilo serve
```

#### 使用内联配置

```bash
KILO_CONFIG_CONTENT='{"provider": "openai", "model": "gpt-4"}' kilo serve
```

---

## 2. `kilo run` - 非交互式执行

`kilo run` 命令用于单次、非交互式地执行 Kilo，直接传递消息并获取结果。

### 基本用法

```bash
# 直接提问
kilo run "解释这段代码的功能"

# 使用中文提示
kilo run "分析项目结构并生成文档"
```

### 常用选项

| 选项 | 说明 |
|------|------|
| `--auto` | 启用自主模式，自动批准所有权限请求（适用于 CI/CD） |
| `--attach <URL>` | 连接到正在运行的 Kilo 服务器（如 `http://localhost:3000`） |
| `--file <PATH>` (`-f`) | 附加文件到消息中 |
| `--format <FORMAT>` | 输出格式：`default`（格式化）或 `json`（原始 JSON 事件） |

### 使用示例

#### 自主模式（CI/CD 流水线）

```bash
# 运行测试并自动修复失败
kilo run --auto "run tests and fix any failures"
```

#### 附加文件进行代码审查

```bash
# 审查单个文件
kilo run -f src/main.ts "review this for security issues"

# 审查多个文件
kilo run -f src/main.ts -f src/utils.ts "分析这两个文件的依赖关系"
```

#### JSON 格式输出

```bash
# 以 JSON 格式输出，便于程序解析
kilo run --format json "summarize the changes in this directory"
```

#### 连接到运行中的服务器

```bash
# 终端 1：启动持久化服务器
kilo serve

# 终端 2：连接到服务器并执行命令
kilo run --attach http://localhost:3000 "解释异步编程模型"
```

---

## 3. HTTP REST API

启动 `kilo serve` 后，可以通过 HTTP REST API 进行会话管理和消息处理。

### API 端点概览

#### 会话管理

| 端点 | 方法 | 说明 |
|------|------|------|
| `/session` | GET | 获取会话列表 |
| `/session` | POST | 创建新会话 |
| `/session/status` | GET | 获取会话状态 |
| `/session/{sessionID}` | GET | 获取特定会话详情 |
| `/session/{sessionID}` | DELETE | 删除会话 |
| `/session/{sessionID}` | PATCH | 更新会话属性 |

#### 会话操作

| 端点 | 方法 | 说明 |
|------|------|------|
| `/session/{sessionID}/children` | GET | 获取子会话 |
| `/session/{sessionID}/todo` | GET | 获取待办列表 |
| `/session/{sessionID}/init` | POST | 初始化会话并生成 AGENTS.md |
| `/session/{sessionID}/abort` | POST | 中止会话 |
| `/session/{sessionID}/share` | POST | 创建分享链接 |
| `/session/{sessionID}/share` | DELETE | 删除分享链接 |
| `/session/{sessionID}/diff` | GET | 获取文件变更差异 |
| `/session/{sessionID}/summarize` | POST | 生成会话摘要 |
| `/session/{sessionID}/message/{messageID}` | GET | 获取特定消息 |
| `/session/{sessionID}/unrevert` | POST | 恢复已还原的消息 |

#### 事件流

| 端点 | 方法 | 说明 |
|------|------|------|
| `/global/event` | GET | 全局 SSE 事件流 |
| `/session/:id/event` | GET | 会话级 SSE 事件流 |

### cURL 使用示例

#### 创建会话

```bash
curl -X POST "http://localhost:3000/session?directory=/path/to/project"
```

#### 获取会话列表

```bash
curl -X GET "http://localhost:3000/session?directory=/path/to/project&limit=10"
```

#### 获取会话状态

```bash
curl -X GET "http://localhost:3000/session/status?directory=/path/to/project"
```

#### 获取特定会话

```bash
curl -X GET "http://localhost:3000/session/ses_12345?directory=/path/to/project"
```

#### 删除会话

```bash
curl -X DELETE "http://localhost:3000/session/ses_12345?directory=/path/to/project"
```

#### 更新会话标题

```bash
curl -X PATCH "http://localhost:3000/session/ses_12345?directory=/path/to/project" \
  -H "Content-Type: application/json" \
  -d '{"title": "New Session Title"}'
```

#### 中止会话

```bash
curl -X POST "http://localhost:3000/session/ses_12345/abort?directory=/path/to/project"
```

#### 生成会话摘要

```bash
curl -X POST "http://localhost:3000/session/ses_12345/summarize?directory=/path/to/project" \
  -H "Content-Type: application/json" \
  -d '{"providerID": "openai", "modelID": "gpt-4"}'
```

#### 获取文件变更差异

```bash
curl -X GET "http://localhost:3000/session/ses_12345/diff?directory=/path/to/project&messageID=msg_67890"
```

#### 带认证的请求

```bash
# 使用 HTTP Basic Auth
curl -X GET "http://localhost:3000/session?directory=/path/to/project" \
  -u kilo:your_password
```

---

## 4. 典型使用场景

### 场景 1：CI/CD 自动化代码审查

```bash
#!/bin/bash

# 在 CI 流水线中自动审查代码变更
kilo run --auto --format json \
  "Review the following changes for bugs and security issues" \
  > review_result.json
```

### 场景 2：批量代码分析

```bash
#!/bin/bash

# 分析项目中的关键文件
kilo run \
  --file src/main.py \
  --file src/config.py \
  --file src/api.py \
  --format json \
  "分析代码架构并生成技术文档" > architecture_analysis.json
```

### 场景 3：使用 API 进行会话管理

```bash
#!/bin/bash

# 创建新会话
SESSION_RESPONSE=$(curl -s -X POST "http://localhost:3000/session?directory=$(pwd)")
SESSION_ID=$(echo $SESSION_RESPONSE | jq -r '.id')

echo "Created session: $SESSION_ID"

# 获取会话状态
curl -X GET "http://localhost:3000/session/status?directory=$(pwd)"

# 完成后删除会话
curl -X DELETE "http://localhost:3000/session/$SESSION_ID?directory=$(pwd)"
```

### 场景 4：持久化服务器 + 多客户端

```bash
# 终端 1：启动持久化服务器（避免冷启动）
export KILO_SERVER_PASSWORD="secure_pass"
kilo serve --port 3000

# 终端 2：执行快速查询
kilo run --attach http://localhost:3000 "解释这个函数的作用"

# 终端 3：使用 API 管理会话
curl -X GET "http://localhost:3000/session"
```

### 场景 5：GitHub Actions 集成

```yaml
# .github/workflows/code-review.yml
name: AI Code Review

on: [pull_request]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install KiloCode
        run: npm install -g @kilocode/cli
        
      - name: AI Code Review
        env:
          KILO_SERVER_PASSWORD: ${{ secrets.KILO_PASSWORD }}
        run: |
          kilo run --auto \
            "Review this PR for bugs, security issues, and code quality" \
            > review_output.txt
            
      - name: Upload Review Results
        uses: actions/upload-artifact@v4
        with:
          name: ai-review
          path: review_output.txt
```

---

## 5. 配置文件

KiloCode 的配置文件位于以下位置：

- **Linux**: `~/.config/kilo/opencode.json` 或 `~/.config/kilo/opencode.jsonc`
- **macOS**: `~/Library/Application Support/kilo/opencode.json`
- **Windows**: `%APPDATA%/kilo/opencode.json`

### 配置示例

```jsonc
{
  "provider": "openai",
  "model": "gpt-4",
  "autoApprove": ["read", "write"],
  "server": {
    "port": 3000,
    "hostname": "localhost"
  }
}
```

---

## 6. 注意事项

1. **安全警告**：如果未设置 `KILO_SERVER_PASSWORD`，服务器将以无保护模式运行，警告信息会显示在终端中
2. **默认端口**：`kilo serve` 默认监听端口 3000
3. **自主模式**：`--auto` 模式会自动批准所有权限请求，仅建议在可信环境和 CI/CD 中使用
4. **会话目录**：大多数 API 端点需要 `directory` 查询参数来指定项目目录
5. **SSE 事件流**：使用 `/session/:id/event` 端点可以实时接收会话事件

---

## 7. 故障排除

### 服务器无法启动

```bash
# 检查端口是否被占用
lsof -i :3000

# 使用不同端口
kilo serve --port 8080
```

### API 请求被拒绝

```bash
# 检查是否设置了密码
echo $KILO_SERVER_PASSWORD

# 使用正确的认证信息
curl -u kilo:your_password "http://localhost:3000/session"
```

### 会话超时

- 检查服务器日志
- 使用 `--attach` 连接到现有服务器而不是每次都启动新服务器

---

## 参考链接

- GitHub 仓库：https://github.com/Kilo-Org/kilocode
- DeepWiki 搜索：
  - https://deepwiki.com/search/cli-headless-mode-commands-kil_370d8261-54fc-45f1-a5d9-addb83b199b2
  - https://deepwiki.com/search/kilo-run-command-options-flags_9e0e3bb0-60f1-444a-a6c8-5a8d8a5be0e4
  - https://deepwiki.com/search/http-api-endpoints-session-eve_7eab365b-b9af-4e7f-bdea-dc1e1a4e170f
