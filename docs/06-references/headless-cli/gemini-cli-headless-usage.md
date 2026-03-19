# Gemini CLI 无头模式 (Headless Mode) 使用指南

本文档介绍 Google Gemini CLI 的无头模式使用方法，适用于脚本编写、自动化、CI/CD 集成和程序化调用场景。

## 概述

Gemini CLI 支持自动检测无头模式，当满足以下条件之一时会自动进入非交互式执行：

- 在非 TTY 环境中运行
- 设置 `CI=true` 或 `GITHUB_ACTIONS=true` 环境变量
- 提供 `-p` / `--prompt` 标志
- 提供查询参数

### 主要特性

| 特性 | 说明 |
|------|------|
| 非交互式执行 | 接收单个提示并输出结果到 stdout |
| 多种输出格式 | 支持 `text`、`json`、`stream-json` |
| 工具自动执行 | 支持配置批准模式自动执行工具 |
| 明确的退出码 | 不同退出码表示不同执行结果 |

---

## 1. 基本用法

### 命令行提示

```bash
# 使用 -p 标志提供提示
gemini -p "解释这个代码库的架构"

# 使用 --prompt 标志
gemini --prompt "分析项目结构并生成文档"

# 简短提示
gemini -p "这段代码有什么潜在问题？"
```

### 交互式提示（执行后继续交互）

```bash
# 使用 -i 标志，执行提示后进入交互模式
gemini -i "这个项目的目的是什么？"

# 使用 --prompt-interactive
gemini --prompt-interactive "帮我重构这个函数"
```

---

## 2. 命令行参数

### 提示相关参数

| 参数 | 简写 | 说明 |
|------|------|------|
| `--prompt` | `-p` | 非交互式模式，执行提示后退出 |
| `--prompt-interactive` | `-i` | 执行提示后继续交互模式 |

**注意**：`--prompt` 和 `--prompt-interactive` 不能同时使用。

### 输出格式

| 参数 | 简写 | 说明 |
|------|------|------|
| `--output-format text` | `-o text` | 人类可读输出（默认） |
| `--output-format json` | `-o json` | 完整 JSON 对象，包含响应和使用统计 |
| `--output-format stream-json` | `-o stream-json` | 流式 JSON 事件，实时输出 |

### 使用示例

```bash
# 默认文本输出
gemini -p "解释代码架构" 

# JSON 输出（适合脚本解析）
gemini -p "解释代码架构" --output-format json

# 流式 JSON 输出（适合长时间任务监控）
gemini -p "运行测试并部署" --output-format stream-json

# 简短格式
gemini -p "分析代码" -o json
```

### 模型选择

| 参数 | 简写 | 说明 |
|------|------|------|
| `--model` | `-m` | 指定使用的 Gemini 模型 |

**支持的模型别名**：
- `auto`（默认）- 根据预览功能自动选择
- `pro` - 对应 `gemini-2.5-pro`
- `flash` - 对应 `gemini-2.5-flash`
- `flash-lite` - 轻量版本

```bash
# 使用模型别名
gemini -p "快速分析" -m flash

# 使用具体模型名
gemini -p "详细分析" -m gemini-2.5-pro

# 使用 flash-lite 节省成本
gemini -p "简单查询" -m flash-lite
```

### 其他常用参数

| 参数 | 简写 | 说明 |
|------|------|------|
| `--approval-mode` | | 设置工具执行批准模式 |
| `--yolo` | `-y` | 自动批准所有操作（已废弃，使用 `--approval-mode=yolo`） |
| `--debug` | `-d` | 调试模式，详细日志输出 |
| `--include-directories` | | 指定要包含的工作目录 |

---

## 3. 批准模式 (Approval Mode)

在无头模式下，由于无法进行用户交互确认，需要配置合适的批准模式。

### 批准模式类型

| 模式 | 说明 | 无头模式行为 |
|------|------|-------------|
| `default` | 默认模式，写工具需要确认 | 需要确认的工具会被拒绝 |
| `auto_edit` | 自动批准编辑工具 | 编辑工具自动执行，其他需要确认的工具被拒绝 |
| `yolo` | 自动批准所有工具 | 所有工具自动执行（谨慎使用） |
| `plan` | 只读模式，仅研究设计 | 所有修改操作被拒绝 |

### 使用示例

```bash
# 自动批准所有操作（适合 CI/CD）
gemini -p "运行测试并修复失败" --approval-mode=yolo

# 自动批准编辑工具
gemini -p "重构这个函数" --approval-mode=auto_edit

# 只读分析模式
gemini -p "分析代码质量问题" --approval-mode=plan

# 默认模式（需要确认的操作会被跳过）
gemini -p "检查代码" --approval-mode=default
```

### 优先级规则

- 命令行参数优先于配置文件设置
- `--approval-mode` 优先于 `general.defaultApprovalMode` 设置
- 工作区不受信任时，`yolo` 和 `auto_edit` 会被降级为 `default`

---

## 4. 环境变量配置

### 认证相关

| 环境变量 | 说明 |
|----------|------|
| `GEMINI_API_KEY` | Gemini API 密钥（用于 API Key 认证） |
| `GOOGLE_API_KEY` | Google API 密钥（用于 Vertex AI 认证） |
| `GOOGLE_CLOUD_PROJECT` | Google Cloud 项目 ID |
| `GOOGLE_CLOUD_LOCATION` | Google Cloud 位置 |

### 模型配置

| 环境变量 | 说明 |
|----------|------|
| `GEMINI_MODEL` | 指定默认使用的模型 |

### 其他配置

| 环境变量 | 说明 |
|----------|------|
| `CI` | 设置为 `true` 自动进入无头模式 |
| `GITHUB_ACTIONS` | 设置为 `true` 自动进入无头模式 |
| `GEMINI_TELEMETRY_ENABLED` | 启用遥测 |
| `GEMINI_SANDBOX` | 沙箱设置 |

### 使用示例

```bash
# 设置 API 密钥
export GEMINI_API_KEY="your_api_key_here"

# 设置默认模型
export GEMINI_MODEL="gemini-2.5-flash"

# 在 CI 环境中
export CI=true
gemini -p "分析代码变更"

# 使用 Vertex AI 认证
export GOOGLE_API_KEY="your_vertex_key"
export GOOGLE_CLOUD_PROJECT="my-project"
export GOOGLE_CLOUD_LOCATION="us-central1"
```

---

## 5. 退出码

Gemini CLI 在无头模式下使用特定退出码表示执行结果：

| 退出码 | 含义 |
|--------|------|
| `0` | 成功 |
| `1` | 一般错误或 API 失败 |
| `42` | 输入错误（无效提示或参数） |
| `53` | 超出轮次限制 |
| `130` | 用户取消（Ctrl+C） |

### 在脚本中使用退出码

```bash
#!/bin/bash

gemini -p "运行测试并修复" --approval-mode=yolo

case $? in
  0)
    echo "执行成功"
    ;;
  1)
    echo "执行失败"
    exit 1
    ;;
  42)
    echo "输入参数错误"
    exit 1
    ;;
  53)
    echo "超出轮次限制"
    exit 1
    ;;
  130)
    echo "用户取消操作"
    exit 1
    ;;
esac
```

---

## 6. 典型使用场景

### 场景 1：CI/CD 代码审查

```bash
#!/bin/bash

# GitHub Actions 中的代码审查
export GEMINI_API_KEY="${{ secrets.GEMINI_API_KEY }}"

gemini -p "Review this PR for bugs, security issues, and code quality" \
  --approval-mode=auto_edit \
  --output-format json \
  > review_result.json
```

### 场景 2：自动化测试修复

```bash
#!/bin/bash

# 运行测试并自动修复失败
export GEMINI_API_KEY="your_key"

gemini -p "Run tests and fix any failures" \
  --approval-mode=yolo \
  --output-format stream-json \
  | while read line; do
      echo "Processing: $line"
      # 实时处理输出
    done
```

### 场景 3：批量代码分析

```bash
#!/bin/bash

# 分析多个文件并生成报告
export GEMINI_API_KEY="your_key"

gemini -p "Analyze the code architecture and generate technical documentation" \
  --output-format json \
  --model flash \
  > architecture_report.json

# 解析 JSON 结果
jq '.response' architecture_report.json
```

### 场景 4：GitHub Actions 完整工作流

```yaml
# .github/workflows/ai-code-review.yml
name: AI Code Review

on:
  pull_request:
    branches: [main, develop]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          
      - name: Install Gemini CLI
        run: npm install -g @google/gemini-cli
        
      - name: AI Code Review
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: |
          gemini -p "Review this PR for bugs, security issues, and code quality" \
            --approval-mode=auto_edit \
            --output-format json \
            > review_result.json
            
      - name: Upload Review Results
        uses: actions/upload-artifact@v4
        with:
          name: ai-review
          path: review_result.json
          
      - name: Post Review Comment
        if: always()
        uses: actions/github-script@v7
        with:
          script: |
            const review = require('./review_result.json');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## AI Code Review\n\n${review.response}`
            });
```

### 场景 5：自动化文档生成

```bash
#!/bin/bash

# 为项目生成 API 文档
export GEMINI_API_KEY="your_key"

gemini -p "Generate comprehensive API documentation for this project" \
  --output-format json \
  --model pro \
  | jq -r '.response' > API.md

echo "API documentation generated: API.md"
```

### 场景 6：安全扫描

```bash
#!/bin/bash

# 代码安全扫描
export GEMINI_API_KEY="your_key"

gemini -p "Scan this codebase for security vulnerabilities and suggest fixes" \
  --approval-mode=plan \
  --output-format json \
  --model pro \
  > security_scan.json

# 检查是否有安全问题
if jq -e '.response | contains("vulnerability")' security_scan.json > /dev/null; then
  echo "Security vulnerabilities found!"
  exit 1
fi
```

---

## 7. 特殊命令处理

### Slash 命令

Gemini CLI 支持斜杠命令，在无头模式下会自动处理：

```bash
# Bug 分析
gemini -p "/bug 这个功能有问题"

# 聊天模式
gemini -p "/chat 解释这个算法"
```

### @ 命令

`@` 命令用于引用文件内容：

```bash
# 引用单个文件
gemini -p "@src/main.py 解释这个文件的功能"

# 引用多个文件
gemini -p "@src/main.py @src/utils.py 分析这两个文件的关系"
```

---

## 8. 配置文件

Gemini CLI 的配置文件位置：

- **Linux/macOS**: `~/.gemini/settings.json`
- **Windows**: `%USERPROFILE%\.gemini\settings.json`

### 配置示例

```json
{
  "general": {
    "defaultApprovalMode": "auto_edit",
    "excludeTools": ["ask_user"]
  },
  "model": {
    "default": "gemini-2.5-flash"
  },
  "advanced": {
    "excludedEnvVars": ["DEBUG", "DEBUG_MODE"]
  }
}
```

---

## 9. 注意事项

1. **认证限制**：无头模式不支持 OAuth 认证（需要浏览器交互），请使用 API Key 或 Vertex AI 认证
2. **工具排除**：`ask_user` 工具在无头模式下默认被排除
3. **安全警告**：`yolo` 模式会执行所有工具，仅在可信环境中使用
4. **输出解析**：使用 `--output-format json` 便于程序解析
5. **实时输出**：长时间任务使用 `--output-format stream-json` 进行实时监控

---

## 10. 故障排除

### 认证失败

```bash
# 检查 API 密钥是否设置
echo $GEMINI_API_KEY

# 重新设置
export GEMINI_API_KEY="your_valid_key"
```

### 工具执行被拒绝

```bash
# 使用合适的批准模式
gemini -p "修改代码" --approval-mode=auto_edit

# 或完全自动（谨慎）
gemini -p "修改代码" --approval-mode=yolo
```

### 输出格式错误

```bash
# 确保使用有效的输出格式
gemini -p "查询" --output-format text   # 正确
gemini -p "查询" --output-format json   # 正确
gemini -p "查询" --output-format xml    # 错误：不支持
```

---

## 参考链接

- GitHub 仓库：https://github.com/google-gemini/gemini-cli
- DeepWiki 搜索：
  - https://deepwiki.com/search/headless-mode-cli-commands-usa_c1db2cca-5c46-40fb-82fe-1798b3ab337b
  - https://deepwiki.com/search/command-line-arguments-flags-p_a84e0a80-f54e-4eec-a438-585fd9f78efc
  - https://deepwiki.com/search/environment-variables-geminiap_4201c476-3be8-4adc-8ee4-7dc7c4e7cce5
  - https://deepwiki.com/search/approval-mode-approvalmode-yol_2fc37196-404a-47ba-a7c4-1faa5907b19e
