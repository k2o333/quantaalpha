# Hypothesis 与 DSL 不对齐问题：代码核对后的合并说明

## 目的

本文档合并原 `bug-report.md` 与 `solution.md`，并以当前代码与运行日志为准，保留已核实结论，修正不准确描述，给出可直接落地的修复方案。

核对范围：

- 日志：`/home/quan/testdata/aspipe_v4/third_party/facotors/terminal/20260322_184344.txt`
- Prompt 与 proposal 实现：
  - `third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml`
  - `third_party/quantaalpha/quantaalpha/factors/proposal.py`
- 一致性检查与质量门：
  - `third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py`
  - `third_party/quantaalpha/quantaalpha/factors/regulator/factor_regulator.py`
- DSL 算子：
  - `third_party/quantaalpha/quantaalpha/factors/coder/function_lib.py`

## 最终结论

当前问题不是单一 bug，而是三类问题叠加：

1. Hypothesis 生成阶段没有被 DSL 能力约束，导致 LLM 可以提出 HMM 之类当前 DSL 无法表达的假设。
2. 一致性检查异常时被错误地视为通过，导致部分本应失败的因子被质量门放行。
3. `corrected_expression` 缺少类型防御，LLM 返回 dict 时会在后续解析流程触发 `'dict' object has no attribute 'replace'`。

这三个问题会同时存在，但并不是所有因子都走同一条失败路径，也不是所有方向都必然失败。

## 已核实事实

### 1. Hypothesis prompt 当前没有 DSL 约束

当前 hypothesis 生成使用的是：

- `quantaalpha/factors/prompts/prompts.yaml` 中的 `hypothesis_gen`
- `quantaalpha/factors/proposal.py` 中的 `AlphaAgentHypothesisGen`

`hypothesis_gen.system_prompt` 目前只包含场景、输出格式和 hypothesis 规范，没有注入 `function_lib_description`，因此不会限制模型只在 DSL 能力内提出假设。

同时，`potential_direction_transformation` 也没有 DSL 约束。

### 2. hypothesis2experiment 阶段才注入了 DSL 约束

在 `AlphaAgentHypothesis2FactorExpression.prepare_context()` 中，`function_lib_description` 已被放入上下文；
在 `hypothesis2experiment.user_prompt` 中，也确实把 `{{function_lib_description}}` 渲染进去了。

这意味着当前链路是：

- hypothesis 阶段可以自由发散
- expression 阶段才被 DSL 限制

结果就是 hypothesis 可能提 HMM、regime probability 等概念，但 expression 只能回退到 `TS_STD`、`RANK`、`INV` 等可用算子组合，语义容易失配。

### 3. DSL 与依赖中没有 HMM 能力

从 `function_lib.py` 以及仓库全文检索结果看：

- 没有 HMM 相关算子
- 没有 `TRAIN_HMM`、`REGIME_PROBABILITY`、`HMM_PROB_*` 一类函数
- 没有 `hmmlearn` 或类似实现

因此“当前 DSL 不能直接表达 HMM regime probability 类 hypothesis”这一点成立。

### 4. 一致性检查异常时被错误放行

`FactorConsistencyChecker.check_consistency()` 的异常分支当前返回：

- `is_consistent=True`
- `severity="none"`

这会直接影响 `FactorQualityGate.evaluate()` 中的后续判断，使异常场景可能继续通过质量门。

这不是推测，而是代码当前行为。

### 5. `'dict' object has no attribute 'replace'` 的风险是真实存在的

在 `AlphaAgentHypothesis2FactorExpression._convert_with_history_limit()` 中，
如果质量门返回了 `results["corrected_expression"]`，当前代码会直接把它赋给 `expr`，随后调用：

- `self.factor_regulator.is_parsable(expr)`
- `self.factor_regulator.evaluate(expr)`

而 `FactorRegulator.is_parsable()` 最终会把 `expression` 送入 parser；parser 内有字符串 `.replace(...)` 路径。
一旦 `expr` 实际上是 dict，就会出现日志中的：

- `Consistency check error: 'dict' object has no attribute 'replace'`

因此这个 bug 也成立。

## 对原结论的修正

### 修正 1：不是“每个因子都因 consistency critical 被拒绝”

原文中这类表述过度概括。

根据日志，真实情况是：

- 有不少因子确实因为 consistency 或其他质量门失败而被拒绝
- 也有一部分因子在一致性检查异常或 JSON 解析异常后仍然显示 `passed all quality gates`
- 还有部分因子是真正通过了检查

因此应改为：

> 当前存在大量 hypothesis 与 expression 语义失配的因子；其中一部分被正常拦截，一部分因异常处理缺陷被错误放行。

### 修正 2：不是“所有 Direction 0 因子都完全同一路径假通过”

日志表明：

- 某些因子确实在 `JSON fix failed` 之后仍被放行
- 但很多同类因子仍然是 `failed quality gates`

因此应改为：

> HMM 风格方向中既存在被正常拒绝的因子，也存在因一致性检查异常处理缺陷而被错误放行的因子。

### 修正 3：原方案 A 少了一步

原方案 A 提到：

- 在 hypothesis prompt 中引用 `{{ function_lib_description }}`
- 在 `prepare_context()` 中加入该字段

这两步还不够。

因为 `AlphaAgentHypothesisGen.gen()` 在渲染 `hypothesis_gen.system_prompt` 时，当前并没有把 `function_lib_description` 传入 `.render(...)`。

如果只改 prompt 文本，不改渲染入参，`StrictUndefined` 会直接报错。

同理，如果要在 `potential_direction_transformation` 中使用该变量，也必须在它的渲染处显式传参。

## 根因分析

### Bug A：Hypothesis 生成能力边界与 DSL 不一致

问题位置：

- `quantaalpha/factors/prompts/prompts.yaml`
- `quantaalpha/factors/proposal.py`

本质：

- hypothesis 阶段缺少“仅允许使用当前 DSL 可表达概念”的约束
- direction transformation 阶段同样缺少该约束

直接后果：

- 模型容易提出 HMM、状态切换、regime probability 等当前表达式层无法落地的想法

### Bug B：Consistency check 异常即通过

问题位置：

- `quantaalpha/factors/regulator/consistency_checker.py`

本质：

- `except` 分支把失败当作通过

直接后果：

- 只要一致性检查的 LLM 输出有 JSON 格式问题，或检查链路抛异常，就可能被静默放行

### Bug D：corrected_expression 缺少类型保护

问题位置：

- `quantaalpha/factors/proposal.py`

本质：

- 假设 `corrected_expression` 一定是字符串
- 没有在写回 `expr` 前做类型归一化

直接后果：

- 当 LLM 返回结构化对象时，后续 parser 路径会崩在字符串方法上

## 与代码完全对齐的修复方案

### 方案 1：在 hypothesis 阶段显式注入 DSL 约束

目标：

- 让 hypothesis 和 direction transformation 从源头上只生成当前 DSL 能表达的内容

需要同时修改三处：

1. 修改 `quantaalpha/factors/prompts/prompts.yaml`
2. 修改 `AlphaAgentHypothesisGen.prepare_context()`
3. 修改 `AlphaAgentHypothesisGen.gen()` 里 `hypothesis_gen.system_prompt` 的 `.render(...)` 入参

如果还要在 `potential_direction_transformation` 中引用 DSL 说明，还要再改其渲染入参。

推荐约束原则：

- 明确说明 hypothesis 只能使用当前 function library 可表达的概念
- 禁止提出依赖 HMM、order book、intraday-only、外部宏观状态机等当前实现没有的能力
- 使用已有 `function_lib_description` 模板变量，不重复手写一份函数列表

### 方案 2：修复 consistency check 的异常放行

目标：

- 异常即失败，而不是异常即通过

推荐改法：

- `except` 分支返回 `is_consistent=False`
- `severity="critical"`
- `overall_feedback` 明确记录错误信息，但不再出现 “Skipping check” 的放行语义

### 方案 3：修复 corrected_expression 的类型防御

目标：

- 在质量门返回修正表达式后，先把表达式归一化为字符串，再做 parser/evaluator 检查

推荐改法：

- 如果 `corrected_expression` 是 dict，优先取 `expression` 字段
- 如果没有该字段，再退化为字符串化
- 只有归一化后才写回 `expr`

### 方案 4：是否扩 DSL 支持 HMM

这不是当前最小修复方案的一部分。

如果未来真的要支持 HMM 因子，需要同时补齐：

- DSL 算子定义
- parser 支持
- 执行实现
- 依赖管理
- prompt 文档

在当前问题上，不建议先走这条路，因为成本远高于前 3 个修复点。

## 建议实施顺序

1. 先修 `consistency_checker.py` 的异常放行。
2. 再修 `proposal.py` 中 `corrected_expression` 的类型保护。
3. 再给 hypothesis 与 potential direction prompt 注入 DSL 约束，并补齐所有实际渲染传参。
4. 最后重新跑同一实验，验证：
   - HMM 类 hypothesis 不再出现，或显著减少
   - 一致性检查异常不再被放行
   - 不再出现 `'dict' object has no attribute 'replace'`

## 验证标准

修复后，至少应满足以下条件：

1. hypothesis prompt 能稳定生成当前 DSL 可表达的假设。
2. 对于真正不一致的 hypothesis/expression，质量门应明确失败，而不是异常后通过。
3. 日志中不再出现因 `corrected_expression` 为 dict 而导致的 parser 异常。
4. `passed all quality gates` 只应出现在真实通过的因子上，不应由异常兜底造成。

## 简明结论

原两份文档的核心方向是对的：

- Hypothesis 与 DSL 能力不对齐，确实是问题核心。
- consistency check 异常放行，确实是全局 bug。
- `corrected_expression` 类型缺陷，确实会触发下游异常。

但原文有两类需要修正的地方：

- 一些日志结论写得过满，把“部分情况”写成了“全部情况”
- 方案 A 少写了 prompt 渲染传参这一步，按原文实施会失败

因此，后续应以本文档为准，不再直接引用原两份文档作为最终结论。
