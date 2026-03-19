# CodeBuddy CLI 无头模式说明书

## 概述

无头模式允许您通过命令行脚本和自动化工具以编程方式运行 CodeBuddy Code，无需任何交互式 UI。

无头模式也支持定时任务相关能力。在脚本、SDK 或服务端集成场景中，可以使用 `CronCreate`、`CronList`、`CronDelete` 等工具来创建、查看和取消定时任务。

## 基本用法

CodeBuddy Code 的主要命令行接口是 `codebuddy`（或 `cbc`）命令。使用 `--print`（或 `-p`）标志在非交互模式下运行并打印最终结果：

```bash
codebuddy -p "暂存我的更改并为它们编写一组提交" \
  --allowedTools "Bash,Read" \
  --permission-mode acceptEdits
```

## 配置选项

无头模式利用 CodeBuddy Code 中所有可用的 CLI 选项。以下是用于自动化和脚本编写的关键选项：

| 标志 | 描述 | 示例 |
| --- | --- | --- |
| `--print`, `-p` | 在非交互模式下运行 | `codebuddy -p "查询"` |
| `--output-format` | 指定输出格式（`text`, `json`, `stream-json`） | `codebuddy -p --output-format json` |
| `--resume`, `-r` | 通过会话 ID 恢复对话 | `codebuddy --resume abc123` |
| `--continue`, `-c` | 继续最近的对话 | `codebuddy --continue` |
| `--verbose` | 启用详细日志记录 | `codebuddy --verbose` |
| `--append-system-prompt` | 追加到系统提示词（仅与 `--print` 配合使用） | `codebuddy -p --append-system-prompt "附加提示"` |
| `--add-dir` | 添加额外的工作目录（验证路径是否存在） | `codebuddy --add-dir /path/to/dir` |
| `--sandbox` | 在沙箱模式中运行（Beta） | `codebuddy --sandbox "分析项目"` |
| `--sandbox-kill` | 退出时终止沙箱 | `codebuddy --sandbox --sandbox-kill` |
| `--ide` | 启动时自动连接 IDE | `codebuddy --ide` |
| `--debug` | 启用调试模式 | `codebuddy --debug` |
| `-y`, `--dangerously-skip-permissions` | 跳过权限确认（非交互模式必加） | `codebuddy -p -y` |

## 重要提示

⚠️ 重要提示：`-y`（或 `--dangerously-skip-permissions`）是非交互模式的必需参数。在使用 `-p/--print` 参数进行非交互式执行时，必须添加此参数才能执行需要授权的操作（文件读写、命令执行、网络请求等），否则这些操作会被阻止。仅在受信任的环境和明确的任务场景下使用此参数。详见 CLI 参考。

## 沙箱模式（Beta）

沙箱模式提供操作系统级别的隔离，限制文件系统和网络访问。

```bash
# 容器沙箱（Docker/Podman，自动挂载当前目录）
codebuddy --sandbox "分析项目"

# 云沙箱（自动复用）
codebuddy --sandbox https://api.e2b.dev "创建 Python Web 应用"

# 退出时清理沙箱
codebuddy --sandbox --sandbox-kill "临时测试"
```

## 完整示例

```bash
# 非交互模式完整示例
codebuddy -p "分析代码并运行测试" \
  --output-format json \
  -y

# 恢复会话并执行
codebuddy --resume 550e8400-e29b-41d4-a716-446655440000 "修复所有 lint 问题" -p -y

# 在沙箱中运行分析
codebuddy --sandbox "审查代码" -y
```

## 原文文档链接

- [无头模式 （Headless Mode) | 腾讯云代码助手 CodeBuddy – AI 代码编辑器](https://copilot.tencent.com/docs/cli/headless)
- [Headless Mode | Tencent Cloud Code Assistant CodeBuddy – AI Code Editor](https://www.codebuddy.ai/docs/cli/headless)