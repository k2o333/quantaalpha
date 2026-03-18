Status: accepted
Owner: AI Assistant
Created: 2026-03-12
Outcome: accepted

# 2026-03-12 运行问题分析与优先级排序

## 背景

- 触发方式：执行 `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/run.sh`
- 参考日志：`/home/quan/testdata/aspipe_v4/third_party/facotors/terminal/20260312_110332.txt`
- 目标：明确本次运行中暴露出来的症状、根因、代码位置、优化方案，以及哪些属于“当前跑通流程”的高优先级问题

## 执行结果概览

本次运行不是“整体流程跑不通”。

从日志看，`2026-03-12 11:10:11` 出现了一次 `Task failed: Failed to decode JSON response from API.`，但外层演化循环没有中止，而是继续执行后续任务，最终在 `2026-03-12 11:35:26` 正常收尾，并输出了 Top trajectories 和 Pool stats。

这说明：

1. 当前流程具备“单任务失败后继续跑”的能力。
2. 但单个任务的稳定性存在问题。
3. 最终“运行完成”并不等于“所有任务都成功完成”。

## 已确认的症状

### 1. evaluator 阶段发生 JSON 解析失败

日志位置：

- `/home/quan/testdata/aspipe_v4/third_party/facotors/terminal/20260312_110332.txt:1384`
- `/home/quan/testdata/aspipe_v4/third_party/facotors/terminal/20260312_110332.txt:1394`
- `/home/quan/testdata/aspipe_v4/third_party/facotors/terminal/20260312_110332.txt:1432`

关键信号：

- LLM 返回了接近完整但不合法的 JSON。
- `_create_chat_completion_inner_function` 记录了 `JSON fix failed`。
- `robust_json_parse` 最终抛出 `json.JSONDecodeError`。
- evaluator 把该异常包装成 `ValueError("Failed to decode JSON response from API.")`。

### 2. 单个任务失败后，外层流程继续执行

代码位置：

- `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/pipeline/factor_mining.py:446`
- `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/pipeline/factor_mining.py:469`

现状：

- `run_evolution_loop` 捕获 `Exception`
- 记录错误和 traceback
- 直接 `continue`

影响：

- 这能避免整次 run 因单点异常中断。
- 但会让一次运行表现为“完成”，同时静默丢失部分任务产出。

### 3. mutation / debugging 闭环存在多轮无效迭代

日志中多次出现：

- evaluator 明确返回 `final_decision: false`
- 反馈指出公式与描述不一致，例如要求 `TS_SUM`，实现却继续使用 `TS_CORR` 或 `TS_MEAN`

这说明：

- coder 对公式约束的遵循不稳定
- 反馈没有稳定收敛到下一轮生成
- 时间和 token 消耗偏高

这是真问题，但它属于质量和效率问题，不是本次“先跑通”的首要阻塞。

### 4. 存在多类环境和回测告警

包括但不限于：

- `llama is not installed`
- `CatBoostModel` / `XGBModel` / `PyTorch models` skipped
- `trade unit 100 is not supported in adjusted_price mode`
- `load calendar error: freq=day, future=True`
- `Mean of empty slice`
- `factor contains nan`

这些告警需要区分：

- 有些只是可选依赖缺失，不影响当前 LGBM 路径。
- 有些会影响回测严谨性或数据完整性，但没有直接阻断本次流程完成。

## 根因分析

### 问题 A：`JSONDecodeError` 没有进入重试逻辑

代码位置：

- `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/coder/eva_utils.py:556`
- `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/coder/eva_utils.py:578`

当前逻辑：

- `attempts = 0`
- 最多尝试 `max_attempts = 3`
- 只对 `KeyError` 执行 `attempts += 1` 和重试
- 对 `json.JSONDecodeError` 直接抛出 `ValueError`

结果：

- 一旦 LLM 返回了坏 JSON，本次 evaluator 立即失败
- 重试机制对这种最常见的结构化输出异常没有生效

结论：

这是一个真实 bug，而且是本次运行中最直接的稳健性问题。

### 问题 B：JSON 修复链路较弱，无法处理截断或未闭合结构

代码位置：

- `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/llm/client.py:36`
- `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/llm/client.py:117`
- `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/llm/client.py:923`
- `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/llm/client.py:951`

当前行为：

1. 先尝试直接 `json.loads`
2. 再尝试提取 markdown code block
3. 再尝试提取第一个完整花括号对象
4. 再处理部分 LaTeX 转义问题

局限：

- 如果返回内容是“末尾截断”“尾逗号错误”“缺失右花括号”，现有策略通常无能为力
- `_create_chat_completion_inner_function` 中的修复只覆盖少量转义问题
- 失败后仍把原始坏 JSON 交给 `robust_json_parse`

结论：

即使修了 evaluator 重试，仍可能反复撞上同类问题。重试能降低失败率，但不能从根本上提升结构化输出鲁棒性。

### 问题 C：任务失败被吞掉，导致运行结果“看起来成功”

代码位置：

- `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/pipeline/factor_mining.py:466`
- `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/pipeline/factor_mining.py:469`

当前行为：

- 任何 task 异常都会被捕获
- 仅记录日志，然后继续下一任务

风险：

- 用户容易误判为整轮 round 全部成功
- 最终 trajectory pool 只反映成功轨迹，失败轨迹没有进入统一 summary
- 对自动化脚本或上层调度来说，不利于判定运行质量

结论：

这不是导致本次错误的根因，但它是“问题暴露方式不清晰”的重要缺陷，优先级应该很高。

### 问题 D：LLM 生成与 evaluator 反馈闭环不稳定

现象：

- 多个因子在 Debugging 环节出现重复性错误
- 错误反馈已经指出公式不匹配，下一轮生成仍然偏离原始定义

可能原因：

- prompt 对公式约束不够刚性
- evaluator 的反馈虽然正确，但不够结构化，难以强约束下一轮生成
- 当前模型在复杂数学表达翻译上稳定性不足

结论：

这是优化项，不是当前跑通流程的第一优先级。

## 非问题或低优先级项说明

### `No comment found` 不是异常

代码位置：

- `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/coder/qa_prompts.yaml:99`

该提示词明确要求：如果没有发现明显问题，就返回 `No comment found`。

因此日志里多次出现该文本，不应被视为失败症状。

### 可选依赖缺失不是当前阻塞

`CatBoost`、`xgboost`、`PyTorch` 未安装只会影响可选模型路径，不影响这次日志中已经成功执行的 LGBM 路径。

### 回测表现一般不是当前“跑通”优先级

收益、IR、IC、RankIC 属于实验结果质量问题，不属于本次流程稳定性修复的第一顺位。

## 优先级排序

### P0：立即处理

#### 1. 让 `JSONDecodeError` 进入重试

目标：

- 避免 evaluator 因一次坏 JSON 立即失败
- 提高任务成功率

建议修改：

- 在 `eva_utils.py` 中对 `json.JSONDecodeError` 执行 `attempts += 1`
- 超过最大重试次数后再抛出带上下文的异常

建议方向：

- 将 `json.JSONDecodeError` 与 `KeyError` 统一纳入同一类“响应结构异常”重试逻辑

#### 2. 对任务失败做显式统计和最终汇总

目标：

- 避免“部分失败但整体看似成功”
- 让 run 结果对使用者可判断

建议修改：

- 在 `run_evolution_loop` 中累计失败任务数、失败阶段、失败方向
- 在最终 summary 中打印失败统计
- 如失败数超过阈值，允许 `run.sh` 或主流程返回非零状态

### P1：高优先级

#### 3. 加强 LLM JSON 输出鲁棒性

目标：

- 降低截断、未闭合、转义异常导致的失败率

定位说明：

- 这一项属于“提升鲁棒性”的方案，不应被视为根治手段。
- `统一重试`、`finish_reason == length 时续写或重试` 是高性价比缓解措施。
- 更强的 JSON 修复能力只能作为补充，不应作为主要方案。

原因：

- 如果模型输出本身不稳定，激进的 JSON 修复容易把错误内容修成“语法合法但语义错误”的 JSON。
- 因此，比起“尽力修坏 JSON”，更可靠的顺序是：
  1. 让结构化输出异常可重试
  2. 让失败任务可观测、可统计
  3. 让模型更稳定地产出结构化结果
  4. 只对少量确定性坏格式做保守修复

可选方案：

1. 在 `build_messages_and_create_chat_completion_json` 外层加入统一重试
2. 对 `finish_reason == "length"` 的 JSON 输出做更强的续写或补全
3. 对常见坏格式做有限、保守的修复
4. 失败时记录原始响应片段，便于后续统计和分析

注意：

- 不建议无限修 JSON，也不建议引入过度激进的自动补全逻辑
- 更可靠的主策略仍然是“重试 + 更严格输出约束 + 更清晰日志”
- JSON 修复应只覆盖少量高确定性场景，例如 markdown 包裹、已知转义问题、轻微格式瑕疵

### P2：中优先级

#### 4. 优化 coder prompt 和 feedback 结构

目标：

- 降低重复犯错
- 提高 debugging 收敛速度

可选方案：

1. 在生成前强制输出“公式映射检查”
2. evaluator 反馈改成结构化字段，例如“错误算子”“错误窗口”“错误优先级”
3. 在下一轮生成时显式注入“禁止重复上轮错误”

#### 5. 审视 NaN 和 warm-up 区间处理

目标：

- 区分“正常 warm-up 缺数”与“表达式本身导致大面积失效”

可选方案：

1. 统计因子有效覆盖率
2. 在 feedback 阶段加入覆盖率告警
3. 对起始窗口不足的情况做显式说明

### P3：低优先级

#### 6. 环境补齐和回测配置修饰

包括：

- 可选模型依赖安装
- `trade unit` / `future calendar` 配置核对
- mlflow filesystem backend 的后续迁移

这些都值得做，但不应排在当前稳健性修复之前。

## 建议的实施顺序

1. 修复 `eva_utils.py` 中 `JSONDecodeError` 不重试的问题。
2. 给 `run_evolution_loop` 增加失败统计、失败汇总和必要的退出码策略。
3. 强化 `llm/client.py` 的 JSON 结构化输出处理。
4. 再处理 prompt、反馈闭环和 NaN 覆盖率等质量问题。
5. 最后再考虑可选依赖、回测配置和性能优化。

## 建议的最小修复集合

如果目标是“先把当前流程变得更稳、更可判定”，最小修改集合应包括：

1. evaluator 遇到 `JSONDecodeError` 自动重试
2. 运行结束时输出失败任务统计
3. 当失败任务数超过阈值时，主流程显式标记为 degraded 或 failed

只做这三项，就能显著改善当前流程的可用性和可观测性。
