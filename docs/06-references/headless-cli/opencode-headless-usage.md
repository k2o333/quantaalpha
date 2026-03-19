# OpenCode 无头模式 (Headless Mode) 使用指南

本文档介绍 OpenCode 的无头模式使用方法，适用于脚本编写、自动化和与其他应用集成的场景。

## 概述

OpenCode 提供以下几种无头模式命令：

| 命令 | 用途 |
|------|------|
| `opencode run` | 非交互式执行，直接传递提示并获取结果 |
| `opencode serve` | 启动无头服务器，提供 API 访问 |
| `opencode web` | 启动无头服务器并打开 Web 界面 |
| `opencode acp` | 启动 ACP (Agent Client Protocol) 服务器，通过 stdin/stdout 通信 |

---

## 1. `opencode run` - 非交互式执行

`opencode run` 命令用于在非交互式模式下执行 OpenCode，直接传递提示并获取结果，无需启动完整的 TUI（终端用户界面）。

### 基本用法

```bash
# 直接提问
opencode run "Explain the use of context in Go"

# 使用中文提示
opencode run "解释 Go 语言中 context 的用途"
```

### 常用选项

| 选项 | 简写 | 说明 |
|------|------|------|
| `--attach <URL>` | | 连接到正在运行的 OpenCode 服务器 |
| `--file <PATH>` | `-f` | 附加文件到消息中 |
| `--format <FORMAT>` | | 输出格式：`default`（格式化）或 `json`（原始 JSON 事件） |
| `--model <MODEL>` | `-m` | 指定使用的模型，格式为 `provider/model` |
| `--agent <AGENT>` | | 指定使用的 agent |

### 使用示例

#### 附加文件

```bash
# 附加单个文件
opencode run --file ./main.go "分析这段代码"

# 附加多个文件
opencode run -f file1.py -f file2.py "比较这两个文件的差异"
```

#### 指定模型

```bash
opencode run --model openai/gpt-4 "解释量子计算"
```

#### JSON 输出格式

```bash
# 以 JSON 格式输出，便于程序解析
opencode run --format json "列出 Python 的十大特性"
```

#### 连接到运行中的服务器

```bash
# 在终端 1 中启动服务器
opencode serve

# 在终端 2 中连接到服务器并执行命令
opencode run --attach http://localhost:4096 "解释 async/await 在 JavaScript 中的用法"
```

---

## 2. `opencode serve` - 无头服务器

`opencode serve` 启动一个无头 OpenCode 服务器，提供 API 访问，无需 TUI。该服务器可被其他应用或 `opencode run --attach` 命令使用。

### 基本用法

```bash
# 启动服务器（默认端口 4096）
opencode serve
```

### 常用选项

| 选项 | 说明 |
|------|------|
| `--port <PORT>` | 指定监听端口（默认：4096） |
| `--hostname <HOST>` | 指定监听主机名 |
| `--mdns` | 启用 mDNS 发现 |
| `--cors <ORIGINS>` | 允许额外的浏览器源（用于 CORS） |

### 使用示例

#### 指定端口

```bash
opencode serve --port 8080
```

#### 启用认证

```bash
# 设置环境变量启用 HTTP 基本认证
export OPENCODE_SERVER_PASSWORD="your_password"
opencode serve
```

#### 指定监听地址

```bash
# 监听所有网络接口
opencode serve --hostname 0.0.0.0 --port 4096
```

---

## 3. `opencode web` - Web 界面模式

`opencode web` 命令启动无头 OpenCode 服务器并自动打开 Web 浏览器访问其 Web 界面。

### 基本用法

```bash
opencode web
```

### 常用选项

与 `opencode serve` 相同的网络配置选项：

| 选项 | 说明 |
|------|------|
| `--port <PORT>` | 指定监听端口 |
| `--hostname <HOST>` | 指定监听主机名 |
| `--mdns` | 启用 mDNS 发现 |
| `--cors <ORIGINS>` | 允许额外的浏览器源 |

---

## 4. `opencode acp` - ACP 服务器

`opencode acp` 启动一个 Agent Client Protocol (ACP) 服务器，通过 stdin/stdout 使用 nd-JSON 进行通信。

### 基本用法

```bash
opencode acp
```

### 常用选项

| 选项 | 说明 |
|------|------|
| `--cwd <DIR>` | 指定工作目录 |
| `--port <PORT>` | 指定监听端口 |
| `--hostname <HOST>` | 指定监听主机名 |

---

## 典型使用场景

### 场景 1：脚本自动化

```bash
#!/bin/bash

# 在脚本中使用 opencode run
result=$(opencode run "生成一个 Python 函数，计算斐波那契数列的第 n 项")
echo "$result"
```

### 场景 2：代码分析流水线

```bash
# 分析项目中的多个文件
opencode run \
  --file src/main.py \
  --file src/utils.py \
  --format json \
  "分析代码结构并生成文档" > analysis.json
```

### 场景 3：开发环境中的快速查询

```bash
# 终端 1：启动持久化服务器（避免冷启动）
opencode serve --port 4096

# 终端 2：快速查询
opencode run --attach http://localhost:4096 "解释 Rust 的所有权概念"
```

### 场景 4：CI/CD 集成

```yaml
# GitHub Actions 示例
- name: Code Review with OpenCode
  run: |
    opencode run --file ${{ github.event.pull_request.diff_url }} \
      "审查此代码变更，指出潜在问题"
```

---

## 注意事项

1. **服务器端口**：`opencode serve` 默认监听端口 4096
2. **认证**：通过 `OPENCODE_SERVER_PASSWORD` 环境变量启用 HTTP 基本认证
3. **开发模式**：开发时可使用 `bun dev serve` 和 `bun dev web` 命令（分别等同于 `opencode serve` 和 `opencode web`）
4. **文档来源**：相关命令文档位于 `packages/web/src/content/docs/cli.mdx`

---

## 参考链接

- GitHub 仓库：https://github.com/anomalyco/opencode
- DeepWiki 搜索：https://deepwiki.com/search/headless-mode-cli-usage-comman_102acb21-24a3-4541-9e07-8d26f1293e34
