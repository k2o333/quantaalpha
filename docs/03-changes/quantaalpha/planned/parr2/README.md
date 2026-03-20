# QuantaAlpha Parallel Round 2

本目录把 4 个任务拆成 `dev`、`test`、`debug` 三阶段。

规则：

- 每个阶段单独运行一次。
- 同一个任务的 `dev`、`test`、`debug` 必须由不同 agent 执行。
- 6 个 agent 尽量均匀轮转。
- `test` 必须先读同名 `dev` 文档和 `dev` 阶段产出。
- `debug` 必须先读同名 `dev`、`test` 文档和前两阶段产出。

推荐分配：

| Task | Dev | Test | Debug |
| --- | --- | --- | --- |
| parallel-01 | iflow | opencode | kilocode |
| parallel-02 | gemini | codebuddy | qwen |
| parallel-03 | opencode | kilocode | gemini |
| parallel-04 | codebuddy | qwen | iflow |

阶段目录：

- `dev/`
- `test/`
- `debug/`

批次运行时，每个阶段目录内都保留：

- `*.task.md`
- `*.prompt.txt`

同名前缀表示同一个任务。
