# QuantaAlpha LLM 模型选择审计

日期：2026-03-12

本文档整理 QuantaAlpha 仓库内主要 `chat completion` 调用点的模型选择行为，覆盖：

- 核心模型选择逻辑
- `reasoning_flag` 与 `chat_model_map` 的真实作用
- 全仓库主要调用点的实际分支归类
- 容易误解的地方

## 1. 核心选择逻辑

核心逻辑位于 [`quantaalpha/llm/client.py`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/llm/client.py#L880) 到 [`quantaalpha/llm/client.py`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/llm/client.py#L890)：

```python
caller_locals = inspect.stack()[4].frame.f_locals
if "self" in caller_locals:
    tag = caller_locals["self"].__class__.__name__
else:
    tag = inspect.stack()[4].function

if reasoning_flag:
    model = self.reasoning_model
    json_mode = None
else:
    model = self.chat_model_map.get(tag, self.chat_model)
```

规则可简化为：

| 条件 | 使用模型 | 是否看 `chat_model_map` |
| --- | --- | --- |
| `reasoning_flag=True` | `self.reasoning_model` | 否 |
| `reasoning_flag=False` | `chat_model_map.get(tag, self.chat_model)` | 是 |

其中：

- `tag` 优先取调用者对象的类名
- 如果调用者不是类方法，则取函数名
- `chat_model_map` 只有在 `reasoning_flag=False` 时才生效

## 2. 配置初始化的真实行为

配置定义位于 [`quantaalpha/llm/config.py`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/llm/config.py#L18) 到 [`quantaalpha/llm/config.py`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/llm/config.py#L65)：

```python
chat_model: str = "gpt-4-turbo"
reasoning_model: str = ""
chat_model_map: str = "{}"
```

初始化位于 [`quantaalpha/llm/client.py`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/llm/client.py#L495) 到 [`quantaalpha/llm/client.py`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/llm/client.py#L497)：

```python
self.chat_model = LLM_SETTINGS.chat_model if chat_model is None else chat_model
self.reasoning_model = LLM_SETTINGS.reasoning_model if reasoning_model is None else reasoning_model
self.chat_model_map = json.loads(LLM_SETTINGS.chat_model_map)
```

重要结论：

- 当前代码中没有看到 `reasoning_model` 为空时自动回退到 `chat_model` 的逻辑
- 因此，`reasoning_flag=True` 时理论上会直接使用 `self.reasoning_model`
- 如果 `reasoning_model=""` 仍然能工作，那应是后续 provider 或外部兼容逻辑导致，不是这里显式实现的

## 3. `tag` 的解析规则

`tag` 用于命中 `chat_model_map`，其来源如下：

- 类方法调用：`tag = 调用者类名`
- 普通函数调用：`tag = 调用者函数名`

例如：

- `AlphaAgentHypothesisGen.gen()` 中触发时，`tag` 预期为 `AlphaAgentHypothesisGen`
- `planning.py` 顶层函数中触发时，`tag` 预期为顶层函数名

对于 `ChatSession`，虽然内部又包了一层调用，但 [`ChatSession.build_chat_completion()`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/llm/client.py#L349) 最终仍通过 `inspect.stack()[4]` 回溯到更外层调用者，因此 `tag` 仍应表现为业务侧类名或函数名，而不是 `ChatSession`。

## 4. 全仓库主要调用点归类

以下表格仅整理实际发起 `chat completion` 的主要位置，不包含 token 计算或 embedding。

### 4.1 显式使用 `reasoning_flag=False`

这些调用一定走：

`chat_model_map.get(tag, chat_model)`

| 文件位置 | 调用点 | 预期 tag | 实际模型分支 |
| --- | --- | --- | --- |
| [`quantaalpha/factors/coder/evolving_strategy.py:334`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/coder/evolving_strategy.py#L334) | `FactorParsingStrategy` 生成表达式 | `FactorParsingStrategy` | `chat_model_map[tag]` 或 `chat_model` |
| [`quantaalpha/factors/coder/eva_utils.py:127`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/coder/eva_utils.py#L127) | `FactorOutputCriticEvaluator.evaluate()` | `FactorOutputCriticEvaluator` | `chat_model_map[tag]` 或 `chat_model` |
| [`quantaalpha/factors/coder/eva_utils.py:217`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/coder/eva_utils.py#L217) | `FactorOutputFormatEvaluator.evaluate()` | `FactorOutputFormatEvaluator` | `chat_model_map[tag]` 或 `chat_model` |
| [`quantaalpha/factors/coder/eva_utils.py:559`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/coder/eva_utils.py#L559) | `FactorEvaluator.evaluate()` 最终评估 | `FactorEvaluator` 子类实例名 | `chat_model_map[tag]` 或 `chat_model` |

### 4.2 默认使用 `reasoning_flag=True`

这些调用没有显式传 `reasoning_flag=False`，因此默认走：

`reasoning_model`

| 文件位置 | 调用点 | 预期 tag | 实际模型分支 |
| --- | --- | --- | --- |
| [`quantaalpha/factors/proposal.py:274`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/proposal.py#L274) | `AlphaAgentHypothesisGen.gen()` | `AlphaAgentHypothesisGen` | `reasoning_model` |
| [`quantaalpha/factors/proposal.py:307`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/proposal.py#L307) | `AlphaAgentHypothesisGen.gen()` 最后一次尝试 | `AlphaAgentHypothesisGen` | `reasoning_model` |
| [`quantaalpha/factors/proposal.py:442`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/proposal.py#L442) | `AlphaAgentHypothesis2FactorExpression._convert_with_history_limit()` | `AlphaAgentHypothesis2FactorExpression` | `reasoning_model` |
| [`quantaalpha/factors/feedback.py:172`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/feedback.py#L172) | `QlibFactorHypothesisExperiment2Feedback.generate_feedback()` | `QlibFactorHypothesisExperiment2Feedback` | `reasoning_model` |
| [`quantaalpha/factors/feedback.py:298`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/feedback.py#L298) | `AlphaAgentQlibFactorHypothesisExperiment2Feedback.generate_feedback()` | `AlphaAgentQlibFactorHypothesisExperiment2Feedback` | `reasoning_model` |
| [`quantaalpha/factors/feedback.py:373`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/feedback.py#L373) | `QlibModelHypothesisExperiment2Feedback.generate_feedback()` | `QlibModelHypothesisExperiment2Feedback` | `reasoning_model` |
| [`quantaalpha/components/proposal/__init__.py:54`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/components/proposal/__init__.py#L54) | `LLMHypothesisGen.gen()` | 具体子类名 | `reasoning_model` |
| [`quantaalpha/components/proposal/__init__.py:109`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/components/proposal/__init__.py#L109) | `LLMHypothesis2Experiment.convert()` | 具体子类名 | `reasoning_model` |
| [`quantaalpha/factors/coder/evolving_strategy.py:70`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/coder/evolving_strategy.py#L70) | `FactorCoSTEEREvolvingStrategy.error_summary()` | `FactorCoSTEEREvolvingStrategy` | `reasoning_model` |
| [`quantaalpha/factors/coder/evolving_strategy.py:179`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/coder/evolving_strategy.py#L179) | `FactorCoSTEEREvolvingStrategy.implement_one_task()` | `FactorCoSTEEREvolvingStrategy` | `reasoning_model` |
| [`quantaalpha/contrib/model/coder/evolving_strategy.py:92`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/contrib/model/coder/evolving_strategy.py#L92) | 模型代码生成 | 相关策略类名 | `reasoning_model` |
| [`quantaalpha/contrib/model/coder/eva_utils.py:110`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/contrib/model/coder/eva_utils.py#L110) | 模型 critic 评估 | 相关 evaluator 类名 | `reasoning_model` |
| [`quantaalpha/contrib/model/coder/eva_utils.py:174`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/contrib/model/coder/eva_utils.py#L174) | 模型最终评估 | `ModelFinalEvaluator` | `reasoning_model` |
| [`quantaalpha/contrib/model/coder/one_shot/__init__.py:33`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/contrib/model/coder/one_shot/__init__.py#L33) | `ModelCodeWriter.develop()` | `ModelCodeWriter` | `reasoning_model` |
| [`quantaalpha/pipeline/planning.py:95`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/pipeline/planning.py#L95) | 方向规划 | 顶层函数名 | `reasoning_model` |
| [`quantaalpha/pipeline/evolution/mutation.py:137`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/pipeline/evolution/mutation.py#L137) | 生成 mutation | 对应类名 | `reasoning_model` |
| [`quantaalpha/pipeline/evolution/crossover.py:170`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/pipeline/evolution/crossover.py#L170) | 生成 crossover | 对应类名 | `reasoning_model` |
| [`quantaalpha/pipeline/factor_from_report.py:49`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/pipeline/factor_from_report.py#L49) | 从报告生成 hypothesis | 顶层函数名 | `reasoning_model` |
| [`quantaalpha/backtest/factor_calculator.py:288`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/backtest/factor_calculator.py#L288) | 将因子描述修正为表达式 | 对应类名 | `reasoning_model` |
| [`quantaalpha/factors/regulator/consistency_checker.py:101`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py#L101) | 一致性检查 | `FactorQualityGate` 或相关类名 | `reasoning_model` |
| [`quantaalpha/coder/costeer/knowledge_management.py:338`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/coder/costeer/knowledge_management.py#L338) | 组件分析 | 相关类名 | `reasoning_model` |
| [`quantaalpha/factors/loader/pdf_loader.py:93`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/loader/pdf_loader.py#L93) | 报告分类 | 顶层函数名 | `reasoning_model` |
| [`quantaalpha/factors/loader/pdf_loader.py:270`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/loader/pdf_loader.py#L270) | 因子相关性检查 | 顶层函数名 `__check_factor_dict_relevance` | `reasoning_model` |
| [`quantaalpha/factors/loader/pdf_loader.py:311`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/loader/pdf_loader.py#L311) | 因子可行性检查 | 顶层函数名 `__check_factor_dict_viability_simulate_json_mode` | `reasoning_model` |

### 4.3 通过 `ChatSession` 间接调用，但仍默认走 `reasoning_model`

这些位置没有直接调用 `build_messages_and_create_chat_completion*`，而是用 `ChatSession.build_chat_completion_json()`。它内部最终仍会走默认 `reasoning_flag=True`：

| 文件位置 | 调用点 | 预期 tag | 实际模型分支 |
| --- | --- | --- | --- |
| [`quantaalpha/factors/loader/pdf_loader.py:124`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/loader/pdf_loader.py#L124) | 连续抽取因子名与描述 | 顶层函数 `__extract_factors_name_and_desc_from_content` | `reasoning_model` |
| [`quantaalpha/factors/loader/pdf_loader.py:159`](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/loader/pdf_loader.py#L159) | 连续抽取 formulation | 顶层函数 `__extract_factors_formulation_from_content` | `reasoning_model` |

## 5. 对用户先前总结的修正

以下说法可以保留：

- 核心分支逻辑确实在 `quantaalpha/llm/client.py`
- `reasoning_flag=True` 与 `False` 是最关键的第一层分流
- `reasoning_flag=False` 时，确实按 `tag -> chat_model_map -> chat_model` 选择
- `factor coder` 中代码生成与 evaluator 是当前最明确的一组 `chat_model` 路径

以下说法需要修正：

1. “`reasoning_model` 空则回退到 `chat_model`”

当前代码里没有直接证据支持这句，应改为：

“代码层面未看到显式回退逻辑，`reasoning_flag=True` 时直接使用 `reasoning_model`。”

2. “仅 proposal / feedback 默认使用 reasoning_model”

不准确。实际上还有 planning、mutation、crossover、factor_from_report、pdf_loader、consistency_checker、部分 model coder 等多处调用同样默认走 `reasoning_model`。

3. “完整模型选择逻辑已经全部覆盖”

如果只指“核心分支逻辑”，这句话成立；如果指“仓库内所有业务调用点”，原总结不完整，漏掉了不少默认调用位置。

## 6. 配置使用建议

如果目标是按任务类型切模型，当前代码应按下面方式理解：

- 要让某一类调用稳定走 `chat_model_map`，必须显式传 `reasoning_flag=False`
- 仅配置 `CHAT_MODEL_MAP`，不会影响默认 `reasoning_flag=True` 的路径
- 如果希望 proposal、feedback、planning 之类任务也按 `tag` 映射，需要修改这些调用点或改底层逻辑

环境变量示例：

```bash
CHAT_MODEL="gpt-4-turbo"
REASONING_MODEL="o1"
CHAT_MODEL_MAP='{"FactorParsingStrategy":"gpt-4o","FactorOutputFormatEvaluator":"gpt-4o-mini"}'
```

## 7. 一句话结论

当前 QuantaAlpha 的模型路由并不是“所有任务都先看 `chat_model_map`”，而是“先看 `reasoning_flag`，只有显式关闭 reasoning 时才看 `chat_model_map`”。
