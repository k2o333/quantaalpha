# Bug: Hypothesis 与 DSL 能力不匹配导致一致性检查全部失败

**发现日期**: 2026-03-22
**严重程度**: 高 — 多个 bug 叠加导致不一致的因子被假通过质量门，产出的因子 hypothesis 和 expression 实际不一致，甚至引发框架内深层的隐藏报错。
**影响范围**: 所有使用超出 DSL 能力的 hypothesis 方向；一致性检查的异常处理（Bug B）和表达式类型的处理（Bug D）影响全局。

## 现象

运行 `run.sh` 后，evolution loop 生成的每个因子都因 **consistency check critical** 被拒绝：

| 因子名 | LLM 生成的 Expression | Consistency 结果 |
|---|---|---|
| `Low_Volatility_Regime_Probability_21D` | `RANK(1 / (TS_STD($return, 21) + 1e-8))` | critical |
| `Multi_Scale_Volatility_Stability_63D` | `3 / (INV(TS_STD(...,21)) + INV(TS_STD(...,42)) + INV(TS_STD(...,63)) + 1e-8)` | critical |
| `Volatility_Regime_Switching_Indicator_126D` | `TS_STD($return, 21) / (TS_STD($return, 126) + 1e-8)` | critical |
| `Multi_Scale_Volatility_Regime_Persistence_21D` | `RANK(TS_STD(LOG(DELTA($close,1)),21) / (TS_MEDIAN(...,63)+1e-8))` | critical |
| `Volatility_Clustering_Stability_63D` | `ZSCORE(TS_STD(LOG(DELTA($close,1)),63) / (TS_MEAN(...,126)+1e-8))` | major |
| `Realized_Volatility_Slope_126D` | `RANK(REGBETA(TS_STD(LOG(DELTA($close,1)),21), SEQUENCE(6), 126))` | critical |

## 根因

**Hypothesis 要求了 DSL 不支持的操作。**

Hypothesis 方向为：
> Explore multi-scale volatility regime switches using **hidden Markov models (HMMs)** on daily log-returns and realized volatility, then construct a factor that ranks assets by their **probability of being in a high-volatility regime** over the past 21, 63, and 126 trading days.

DSL 可用算子（`function_lib.py`）中：
- 有 `TS_STD`, `RANK`, `INV`, `ZSCORE`, `REGBETA` 等基础统计/回归算子
- **没有** `HMM_PROB_LOW`, `TRAIN_HMM`, `REGIME_PROBABILITY` 等 HMM 相关算子
- `hmmlearn` 也不在依赖中

LLM 在 hypothesis 生成阶段输出了 HMM 方向，在 expression 生成阶段被迫用 `TS_STD` 等算子拼凑代理表达式，两者语义完全不一致。

## 涉及文件

| 文件 | 作用 |
|---|---|
| `quantaalpha/factors/prompts/prompts.yaml:294-322` | hypothesis 生成的 system/user prompt |
| `quantaalpha/factors/prompts/prompts.yaml:47-128` | DSL 算子描述 (`function_lib_description`) |
| `quantaalpha/factors/prompts/prompts.yaml:324-410` | hypothesis → expression 转换 prompt |
| `quantaalpha/factors/proposal.py:202-354` | `AlphaAgentHypothesisGen` — hypothesis 生成逻辑 |
| `quantaalpha/factors/proposal.py:383-664` | `AlphaAgentHypothesis2FactorExpression` — hypothesis → expression 转换逻辑 |
| `quantaalpha/factors/regulator/consistency_checker.py:43-232` | `FactorConsistencyChecker` — 一致性检查 |
| `quantaalpha/factors/regulator/consistency_checker.py:127-136` | **异常处理 bug (Bug B)** — JSON 解析异常时返回 `is_consistent=True`，导致假通过 |
| `quantaalpha/factors/proposal.py:534` | **类型处理 bug (Bug D)** — 接收 `corrected_expression` 时未校验类型是否为 dict |
| `quantaalpha/factors/coder/function_lib.py` | 全部 DSL 算子定义（~50 个） |

## Pipeline 流程（与本 bug 相关）

```
用户方向 ("挖掘日频时间序列因子")
    ↓
方向扩写 (LLM) → "Explore HMM-based multi-scale regime..."
    ↓  ← prompts.yaml:294-322 hypothesis_gen
Hypothesis 生成 (LLM) → hypothesis 包含 HMM
    ↓  ← prompts.yaml:324-410 hypothesis2experiment
Expression 生成 (LLM) → 只能用 TS_STD/RANK 等拼凑
    ↓  ← consistency_checker.py:43-232
一致性检查 (LLM) → critical: hypothesis 和 expression 不一致
    ↓
Correction 尝试 (3 次) → 均失败（DSL 无法表达 HMM）
    ↓
因子被拒绝
```

## 完整运行后的发现（2026-03-22 完整 log 分析）

完整 log 共 12423 行，覆盖 Direction 0（HMM 方向）3 轮 original + mutation + crossover，以及 Direction 1（趋势/均值回归方向）。

### 发现 1：Direction 0 的因子"通过"是一致性检查的异常处理 bug

所有 Direction 0 因子（`Multi_Scale_Volatility_Regime_Persistence_21D`、`Low_Volatility_Regime_Probability_21D`、`Volatility_Ratio_Regime_63D`、`Normalized_Volatility_Slope_126D`）的通过路径完全一致：

```
Consistency Checker 的 LLM 返回含 HMM 分析的 JSON
    ↓
JSON 中有 Invalid \escape 或格式错误
    ↓
JSON fix 失败 → 抛出异常
    ↓
exception handler (consistency_checker.py:127-136) 返回 is_consistent=True
    ↓
"passed all quality gates" ✅（假通过）
```

关键代码 `consistency_checker.py:127-136`：
```python
except Exception as e:
    logger.error(f"Consistency check error: {e}")
    return ConsistencyCheckResult(
        is_consistent=True,  # ← 任何异常都当作通过
        ...
        severity="none"
    )
```

**证据**（均来自终端 log）：

| 因子 | Log 行 | 触发路径 |
|---|---|---|
| `Multi_Scale_Volatility_Regime_Persistence_21D` | L1624 | JSON fix failed: Invalid \escape (L1616) → error → passed |
| `Low_Volatility_Regime_Probability_21D` | L2932 | JSON fix failed: delimiter error (L2921) → error → passed |
| `Low_Volatility_Regime_Probability_21D` | L5519 | JSON fix failed: Invalid \escape (L5508) → error → passed |
| `Volatility_Ratio_Regime_63D` | L6328 | JSON fix failed: Invalid \escape (L6317) → error → passed |
| `Normalized_Volatility_Slope_126D` | L6850 | JSON fix failed: delimiter error (L6839) → error → passed |

### 发现 2：Direction 1 的因子是真正通过一致性检查的

`Trend_MeanReversion_Ratio_7D_21D` 和 `Regime_Adaptive_Momentum_10_21D` 真正通过了检查（`"is_consistent": true`），原因是 hypothesis 只使用了 DSL 已有算子：

- Hypothesis："7 天 EMA 趋势 / 21 天 REGRESI 残差的比值"
- Expression：`EMA(DELTA($close, 1)/DELAY($close, 1), 7) / (ABS(REGRESI($close, SEQUENCE(21), 21)) + 1e-8)`
- 所有概念（EMA、DELTA、DELAY、REGRESI、ABS、SEQUENCE）均为 DSL 已有算子

### 发现 3：三个独立 bug 叠加

1. **Bug A（本 bug 的核心）**：Hypothesis 生成不约束 DSL 能力范围，导致产出无法表达的假设
2. **Bug B（一致性检查异常处理）**：`consistency_checker.py:129` 在 JSON 解析异常时返回 `is_consistent=True`，使不一致的因子假通过
3. **Bug D（类型处理错误）**：`proposal.py` 在接收 `corrected_expression` 时未校验返回是否为 dict，直接赋值处理导致底层因调用 `.replace` 奔溃报错。

三个 bug 的交互效果：
- Bug A 导致一致性检查频繁报 critical。
- Bug D 导致当 LLM 试图自行纠正并返回含解释信息的 JSON 对象时，`proposal.py` 未正确提取出字符串形式的 expression，这随即触发了框架底层的一连串 `'dict' object has no attribute 'replace'` 异常报错。
- Bug B 紧接着捕获了由于 Bug D 失败及 JSON 格式导致的种种异常，且错误地在 `except` 里返回了 `is_consistent=True`。
- 最终 Direction 0 的因子表面上"通过"了所有的质量门，但实际上 hypothesis 和 expression 完全不一致，代码库也没有真正跑通质量检查环节。
