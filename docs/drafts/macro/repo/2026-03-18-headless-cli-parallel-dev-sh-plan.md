---
status: draft
owner: Codex
created: 2026-03-18
purpose: 用 sh 脚本调度目录内多个任务，基于 6 个 CLI coding agent 的无头模式执行并行开发
related_to:
  - auto/test/test_all_headless_cli.sh
  - docs/06-references/headless-cli/codebuddy-headless-cli.md
  - docs/06-references/headless-cli/iflow-headless-manual.md
  - docs/06-references/headless-cli/gemini-cli-headless-usage.md
  - docs/06-references/headless-cli/kilocode-headless-usage.md
  - docs/06-references/headless-cli/opencode-headless-usage.md
  - docs/06-references/headless-cli/qwen-code-headless-mode.md
---

# Headless CLI 并行开发方案

## 一、结论

这次建议先做一个**只覆盖开发阶段**的最小系统：

`任务目录 -> auto/scripts/run_parallel_headless_dev.sh -> 按 YAML 选定 1~4 个 agent -> 并行执行 -> 汇总结果`

当前版本先不编排测试 agent，不做 develop/test/debug 三阶段流转，也不做复杂的自动重试。

核心判断如下：

1. **任务文档应区分“开发需求”和“执行提示词”**，不要合在一起。
2. **默认先由 1 个 agent 做任务拆分/预处理，再由 4 个 agent 并行开发**，不要一上来就 4 个 agent 直接吃原始任务。
3. **6 个可用 agent 全部作为资源池存在，实际使用哪几个由 YAML 配置决定**。
4. **并行前提不是“有 4 个 agent”，而是“任务切片边界已经冻结”**。
5. **脚本和两份 YAML 都统一放在 `/home/quan/testdata/aspipe_v4/auto/scripts`**。

---

## 二、为什么不建议把需求和提示词写在一起

如果把“开发需求”和“提示词”混成一份文档，后面会出现三个问题：

1. 需求会被 prompt 污染。
2. 不同 agent 的 prompt 很难做差异化。
3. 后续切换模型或调整调用参数时，需要反复改需求文档。

因此建议分成两层：

### 2.1 需求层

负责定义真实任务边界，是稳定输入。

应包含：

- task_id
- 标题
- 背景
- 目标
- 代码落点
- 禁止修改范围
- 验收标准
- 输出物要求

### 2.2 执行层

负责告诉某个具体 agent 怎么干，是可变输入。

应包含：

- 使用哪个 CLI agent
- CLI 参数
- 本轮附加 prompt
- 读哪些文件
- 写哪些文件
- 输出写到哪里

所以，**需求文档是 source of truth，prompt 只是调度脚本生成的执行包装**。

---

## 三、推荐流程

### 3.1 Phase 0：预处理与切片

先由 1 个 agent 或脚本完成：

1. 读取任务目录中的原始任务文档。
2. 校验文件名和 frontmatter。
3. 判断任务是否可并行。
4. 如可并行，拆成 2~4 个 slice。
5. 为每个 slice 生成独立执行 prompt。

这一阶段的产物应先落盘，再进入并行开发。

### 3.2 Phase 1：并行开发

sh 脚本读取 YAML 后，启动 1~4 个无头 CLI agent 并发执行：

- 每个 agent 只拿到一个 slice
- 每个 agent 只允许改自己的目标文件
- 每个 agent 输出独立日志和结果摘要

### 3.3 Phase 2：主控汇总

主控脚本不做测试，只做：

- 等待所有 agent 退出
- 收集 exit code
- 收集 stdout/stderr
- 生成汇总 markdown
- 标记成功、失败、超时、冲突待处理

---

## 四、先 1 个开发还是先 4 个开发

建议采用：

`1 个拆分/预处理 agent -> 4 个并行开发 agent`

不建议：

`4 个 agent 直接同时读取原始需求文档并开工`

原因很直接：

1. 原始任务通常没有冻结文件边界。
2. 多 agent 同时开发会更容易改到同一文件。
3. 无头模式下缺少交互澄清，前置拆分更重要。

### 4.1 什么时候可以直接 4 并行

只有同时满足以下条件时，才允许跳过预处理 agent：

1. 原始任务文档已经明确 slice。
2. 每个 slice 的代码落点不重叠。
3. 每个 slice 的输出路径不重叠。
4. 每个 slice 都能独立描述为一句开发任务。

否则默认还是先 1 后 4。

---

## 五、任务目录设计

建议不要让脚本直接扫描一堆随意命名的 markdown，而是给任务目录定义固定结构。

```text
tasks/
└── T20260318-001-add-foo/
    ├── task.md
    ├── task.config.yaml
    ├── slices/
    │   ├── slice-01.md
    │   ├── slice-02.md
    │   └── slice-03.md
    ├── prompts/
    │   ├── slice-01.prompt.txt
    │   ├── slice-02.prompt.txt
    │   └── slice-03.prompt.txt
    ├── runs/
    │   └── 20260318T101500Z/
    │       ├── summary.md
    │       ├── codebuddy.stdout.log
    │       ├── iflow.stdout.log
    │       └── ...
    └── status.yaml
```

### 5.1 `task.md` 文件名固定

不要把任务 ID 放进主文件名里，任务 ID 放目录名即可。  
这样脚本逻辑会简单很多。

### 5.2 `task.md` 内容格式

建议使用 YAML frontmatter + 正文。

示例：

```markdown
---
task_id: T20260318-001
title: add foo pipeline
mode: parallel_dev
parallelizable: true
max_parallel: 4
code_targets:
  - src/foo.py
  - src/bar.py
forbidden_targets:
  - src/shared.py
acceptance:
  - command returns structured output
  - docs updated if behavior changes
---

# Background

[业务背景]

# Goal

[开发目标]

# Constraints

- 不要运行测试
- 不要改未授权文件
```

### 5.3 `slice-*.md` 内容格式

每个 slice 文档必须是机器可分发的，建议字段如下：

```markdown
---
slice_id: slice-01
task_id: T20260318-001
owner_agent: auto
code_targets:
  - src/foo.py
read_targets:
  - docs/spec.md
forbidden_targets:
  - src/bar.py
output_files:
  - runs/<run_id>/slice-01.result.md
---

# Slice Goal

[一句话目标]

# Work Order

[这个 slice 具体要做什么]
```

---

## 六、脚本与 YAML 的落点

按你的要求，第一版统一放到：

```text
/home/quan/testdata/aspipe_v4/auto/scripts/
├── run_parallel_headless_dev.sh
├── headless_agents.yaml
└── headless_run_layout.yaml
```

职责划分如下：

- `run_parallel_headless_dev.sh`
  负责调度、并发启动、日志落盘、汇总结果。
- `headless_agents.yaml`
  负责定义所有 coding agent 的命令和参数。
- `headless_run_layout.yaml`
  负责定义任务文件、prompt 文件、终端输出文件、agent 报告文件的路径规则和命名规则。

我这里仍然建议：**需求文档与 prompt 文件分开**。  
所以第二份 YAML 不建议把“任务内容”和“prompt 内容”直接合成一个字段，而是分别声明它们的文件位置。

---

## 七、YAML 配置设计

需要两层 YAML：

### 7.1 全局 agent 池配置

文件：

`/home/quan/testdata/aspipe_v4/auto/scripts/headless_agents.yaml`

```yaml
agents:
  codebuddy:
    enabled: true
    command: ["codebuddy", "-p"]
    append_args: ["-y"]
    output_mode: "text"
  iflow:
    enabled: true
    command: ["iflow", "-p"]
    append_args: ["-y", "--jsonl"]
    output_mode: "jsonl"
  gemini:
    enabled: true
    command: ["gemini", "-p"]
    append_args: ["--approval-mode=yolo", "--output-format", "json"]
    output_mode: "json"
  kilocode:
    enabled: true
    command: ["kilo", "run"]
    append_args: ["--auto", "--format", "json"]
    output_mode: "json"
  opencode:
    enabled: true
    command: ["opencode", "run"]
    append_args: ["--format", "json"]
    output_mode: "json"
  qwen:
    enabled: true
    command: ["qwen", "-p"]
    append_args: ["--yolo", "--output-format", "json"]
    output_mode: "json"
```

### 7.2 运行布局与文件位置配置

文件：

`/home/quan/testdata/aspipe_v4/auto/scripts/headless_run_layout.yaml`

建议内容如下：

```yaml
defaults:
  task_root: "tasks"
  task_doc_name: "task.md"
  slice_dir_name: "slices"
  prompt_dir_name: "prompts"
  run_dir_name: "runs"
  report_format: "markdown"

planner:
  enabled: true
  strategy: "planner_then_parallel_dev"
  planner_agent: "gemini"
  planner_prompt_file: "/home/quan/testdata/aspipe_v4/auto/scripts/prompts/planner.prompt.txt"

task_files:
  task_doc: "{task_root}/{task_id}/task.md"
  task_config: "{task_root}/{task_id}/task.config.yaml"
  slice_doc: "{task_root}/{task_id}/slices/{slice_id}.md"
  slice_prompt: "{task_root}/{task_id}/prompts/{slice_id}.prompt.txt"

stdout_files:
  agent_stdout: "{task_root}/{task_id}/runs/{run_id}/{slice_id}.{agent}.stdout.log"
  agent_stderr: "{task_root}/{task_id}/runs/{run_id}/{slice_id}.{agent}.stderr.log"
  agent_exit_code: "{task_root}/{task_id}/runs/{run_id}/{slice_id}.{agent}.exit_code.txt"

report_files:
  agent_result_report: "{task_root}/{task_id}/runs/{run_id}/{slice_id}.{agent}.result.md"
  planner_report: "{task_root}/{task_id}/runs/{run_id}/planner.result.md"
  summary_report: "{task_root}/{task_id}/runs/{run_id}/summary.md"
  status_file: "{task_root}/{task_id}/runs/{run_id}/status.yaml"
```

这样第二份 YAML 明确覆盖了你提到的几类信息：

1. 提示词文件位置
2. 任务文件位置
3. 终端输出文件位置和文件名
4. coding agent 输出报告的位置和文件名

### 7.3 单任务调度配置

如果后面需要支持“不同任务选不同 agent”，仍建议保留任务级配置文件：

例如 `tasks/T20260318-001-add-foo/task.config.yaml`

```yaml
execution:
  strategy: "planner_then_parallel_dev"
  planner_agent: "gemini"
  dev_agents:
    - "codebuddy"
    - "iflow"
    - "qwen"
    - "kilocode"
  max_parallel: 4
  timeout_seconds: 1800
  fail_fast: false

mapping:
  slice-01: "codebuddy"
  slice-02: "iflow"
  slice-03: "qwen"
  slice-04: "kilocode"
```

这里有两个关键点：

1. **资源池配置**解决“这 6 个工具怎么调用”。
2. **任务配置**解决“这次到底用哪几个”。

---

## 八、sh 脚本职责边界

建议把 shell 脚本只当调度器，不让它承担复杂推理。

### 7.1 shell 应该负责的事

- 扫描任务目录
- 校验任务文件是否齐全
- 读取 YAML 配置
- 生成运行目录
- 启动并发进程
- 记录 PID、退出码、日志路径
- 生成 summary

### 7.2 shell 不应该负责的事

- 自动理解业务需求
- 复杂切片推理
- 冲突自动合并
- 从自然语言中推断文件边界

这些更适合交给“预处理 agent”或显式的 slice 文档。

---

## 九、并行执行脚本的最小结构

建议新增一个真正面向并行的脚本，而不是直接改 `auto/test/test_all_headless_cli.sh`。

固定路径：

```text
/home/quan/testdata/aspipe_v4/auto/scripts/run_parallel_headless_dev.sh
```

脚本流程：

1. 接收 `task_dir`
2. 读取 `task.config.yaml`
3. 决定是否先跑 planner agent
4. 读取或生成 `slices/` 和 `prompts/`
5. 用后台进程并行启动各 agent
6. `wait` 所有 PID
7. 生成 `runs/<run_id>/summary.md`

### 8.1 进程模型

每个 agent 一个后台进程：

```bash
run_agent_for_slice "$agent" "$slice" >"$stdout_log" 2>"$stderr_log" &
pid=$!
```

然后统一：

```bash
wait "$pid"
```

### 8.2 并发控制

第一版即使配置了 6 个 agent，也建议：

- 默认并发数 `max_parallel: 4`
- 预留 2 个 agent 作为候补

原因：

1. 你当前问题本身就是“4 个并行开发是否合适”。
2. 6 个全开会放大上下文漂移和文件冲突。
3. 有些 agent 适合做 planner 或 fallback，而不是主开发。

---

## 十、6 个 agent 的建议分工

结合当前无头模式文档，建议先按“单次 run 能力”来设计，不先引入 attach/serve 模式。

### 9.1 第一版主力 agent

- `codebuddy`
- `iflow`
- `gemini`
- `qwen`

理由：都支持明确的 prompt 入口，且有自动批准参数。

### 9.2 第一版候补 agent

- `kilocode`
- `opencode`

理由：也能 run，但更适合后续扩展到 server/attach 模式；第一版不必一起压上生产路径。

这不是能力高低判断，而是为了降低第一版编排复杂度。

---

## 十一、输出与审计

每次运行都应固化到独立目录：

```text
tasks/<task-id>/runs/<run-id>/
├── summary.md
├── status.yaml
├── planner/
├── slice-01/
├── slice-02/
├── slice-03/
└── slice-04/
```

每个 slice 目录至少保留：

- `prompt.txt`
- `stdout.log`
- `stderr.log`
- `exit_code.txt`
- `result.md`

这样后面你才能比较不同 agent 在同类任务上的表现。

---

## 十二、失败策略

第一版建议采用保守策略：

1. 单个 agent 失败，不自动重试。
2. 单个 slice 失败，整个任务标记为 `partial_failed`。
3. 如果 planner 阶段失败，则不进入并行开发。
4. 如果检测到 slice 目标文件重叠，则直接拒绝并行。

先把可审计性做对，再考虑自动补位和二次调度。

---

## 十三、推荐的最小落地版本

### 12.1 V1 范围

只做以下能力：

1. 任务目录格式固定。
2. `task.md` 与 `task.config.yaml` 固定。
3. 支持 `planner_then_parallel_dev`。
4. 支持最多 4 个并行开发 agent。
5. 支持从 6 个 agent 池中选用指定 agent。
6. 输出独立运行日志和 summary。

### 12.2 V1 不做

- 测试阶段并行
- debug 阶段并行
- 自动冲突合并
- 自动重试换 agent
- server/attach 模式
- 多轮会话续跑

---

## 十四、最终建议

如果目标是尽快把“无头 CLI 并行开发”跑起来，建议定这个决策组合：

1. **文档分层**：需求文档和执行 prompt 分开。
2. **执行策略**：默认先 1 个 planner，再 4 个开发 agent 并行。
3. **编排技术**：先用 sh 做调度，不让 sh 负责复杂推理。
4. **agent 选择**：6 个作为资源池，单任务用 YAML 指定其中 1~4 个。
5. **阶段范围**：第一版只覆盖开发，不碰测试编排。

这条路线比“直接让 4 个 agent 吃原始需求”稳得多，也比“一开始上 6 个 agent 全并行”更可控。
