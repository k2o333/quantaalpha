# Solution: 让 Hypothesis 生成与 DSL 能力对齐

## 方案概述

在 hypothesis 生成阶段注入 DSL 可用算子信息，使 LLM 只在现有算子能力范围内提出假设，避免产生无法表达的 hypothesis。

## 方案 A：修改 Hypothesis 生成 Prompt（推荐，改动量最小）

### 改动点

**文件**: `quantaalpha/factors/prompts/prompts.yaml`

在 `hypothesis_gen` 的 system prompt（约 L294-322）中，追加 DSL 算子约束说明，**并使用模板变量引用 `{{ function_lib_description }}` 代替硬编码**。

当前 system prompt 内容示例（需核实实际内容）：
```yaml
hypothesis_gen:
  system: |
    You are a senior quant researcher...
```

修改为：
```yaml
hypothesis_gen:
  system_prompt: |-
    The user is working on generating new hypotheses...
    
    CRITICAL CONSTRAINT: You can ONLY use functions from the available function library below.
    Do NOT propose hypotheses that require techniques not expressible with the available functions.
    
    Allowed operators and functions:
    {{ function_lib_description }}
    
    Your hypothesis MUST be implementable using ONLY these functions and variables.
```

> **非常重要的一步（配套修改 `proposal.py` 传参）**：
> 由于当前系统在渲染 `hypothesis_gen` 的 prompt 时并未给模板上下文传入上面这个变量，你必须同时修改 `quantaalpha/factors/proposal.py` 的 `AlphaAgentHypothesisGen.prepare_context` 方法（约在第 245-250 行）。
> 
> 将原来的：
> ```python
>         context_dict = {
>             "hypothesis_and_feedback": hypothesis_and_feedback,
>             "RAG": None,
>             "hypothesis_output_format": qa_prompt_dict["hypothesis_output_format"],
>             "hypothesis_specification": qa_prompt_dict["factor_hypothesis_specification"],
>         }
> ```
> 补充为：
> ```python
>         context_dict = {
>             "hypothesis_and_feedback": hypothesis_and_feedback,
>             "RAG": None,
>             "hypothesis_output_format": qa_prompt_dict["hypothesis_output_format"],
>             "hypothesis_specification": qa_prompt_dict["factor_hypothesis_specification"],
>             "function_lib_description": qa_prompt_dict["function_lib_description"]
>         }
> ```
> 这样模板渲染出来才会是算子列表大全，而不会是空白。

### 同时修改方向扩写 Prompt

**文件**: `quantaalpha/factors/prompts/prompts.yaml`

`potential_direction_transformation`（L1-6）也需要加相同约束，避免方向本身就要求 HMM。

### 预期效果

| 改动前 | 改动后 |
|---|---|
| 方向："Explore HMM-based multi-scale regime switches..." | 方向："Explore multi-scale volatility persistence using rolling std ratios across 21/63/126 day windows..." |
| Hypothesis 提到 HMM regime probability | Hypothesis 提到 TS_STD / TS_CORR / RANK 等可表达概念 |
| Expression 用 TS_STD 拼凑 → 不一致 | Expression 与 hypothesis 对齐 → 通过 |

---

## 方案 B：扩展 DSL 支持 HMM 算子（改动量大，不推荐）

如果未来确实需要 HMM 因子，需要：

1. 在 `function_lib.py` 中新增 `HMM_PROB_LOW(series, n, n_states=2)` 算子
2. 添加 `hmmlearn` 到项目依赖
3. 实现算子：对滚动窗口训练 HMM，返回低波动 regime 概率
4. 在 `function_lib_description`（prompts.yaml:47-128）中补充文档
5. 在 `expr_parser.py` 中确保新算子能被正确解析

---

## 方案 C：修复一致性检查异常处理 bug（必须同时做）

完整 log 分析发现，Direction 0 的 HMM 因子实际上从未真正通过一致性检查，而是因为 LLM 返回 JSON 格式错误触发了异常处理，被静默放行。

**文件**: `quantaalpha/factors/regulator/consistency_checker.py:127-136`

当前代码：
```python
except Exception as e:
    logger.error(f"Consistency check error: {e}")
    return ConsistencyCheckResult(
        is_consistent=True,  # ← BUG: 异常不应等于通过
        hypothesis_to_description=f"Error during check: {str(e)}",
        description_to_formulation="",
        formulation_to_expression="",
        overall_feedback=f"Consistency check failed with error: {str(e)}. Skipping check.",
        severity="none"
    )
```

修改为：
```python
except Exception as e:
    logger.error(f"Consistency check error: {e}")
    return ConsistencyCheckResult(
        is_consistent=False,  # ← 异常应视为不通过
        hypothesis_to_description=f"Error during check: {str(e)}",
        description_to_formulation="",
        formulation_to_expression="",
        overall_feedback=f"Consistency check failed with error: {str(e)}",
        severity="critical"  # ← 异常应视为 critical
    )
```

**不修复此 bug 的后果**：即使方案 A 实施后，任何导致 LLM 返回 JSON 解析失败的场景（如包含特殊字符的 hypothesis）都会被放行，一致性检查形同虚设。

---

---

## 方案 D：修复 `proposal.py` 中的类型处理 Bug

终端日志中多次出现 `Consistency check error: 'dict' object has no attribute 'replace'` 的异常崩溃。这是由于大模型在被要求修正 `corrected_expression` 时可能返回了一个 JSON 对象（包含结构化的键值）而非单纯的字符串。

**文件**: `quantaalpha/factors/proposal.py` (约 534 行附近)

在接收 `corrected_expression` 并将其赋值给 `expr` 之前，增加类型防御护栏，防止未校验直接交给下游 `is_parsable()` 引发异常链：

```python
                        if results.get("corrected_expression") and results["corrected_expression"] != expr:
                            logger.info(f"Consistency check corrected expression: {expr} -> {results['corrected_expression']}")
                            expr = results["corrected_expression"]
                            
                            # 增加防御性类型校验护栏（修复处）
                            if isinstance(expr, dict):
                                expr = expr.get("expression") or str(expr)
                            
                            factor_data["expression"] = expr
```

---

## 实施步骤

1. 修复 `consistency_checker.py:129` 的异常状态放行（方案 C）
2. 修复 `proposal.py:534` 的表达式字典类型转换报错（方案 D）
3. 修改 `prompts.yaml` 的 `hypothesis_gen` System Prompt，改换为引用 `{{ function_lib_description }}` 语法；并同步修改 `potential_direction_transformation` 方向引导 Prompt（方案 A）
4. 配套修改 `proposal.py`，将 `function_lib_description` 字典注入其环境上下文中以确保渲染成功（配套方案 A）
5. 重新运行 `run.sh` 验证整个链路是健康干净的。

## 风险

- **探索多样性降低**：约束后 LLM 只能在已知算子范围内组合，可能错过 DSL 外的创新方向
- **缓解方式**：未来扩展 DSL 算子库后，同步更新约束说明即可
