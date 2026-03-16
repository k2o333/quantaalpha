Status: draft
Owner: AI Assistant
Created: 2026-03-12
Outcome: pending

# JSON Decode Error 分析与修复计划

## 错误概述
- **时间**: 2026-03-12
- **错误类型**: `ValueError: Failed to decode JSON response from API.` (由 `json.decoder.JSONDecodeError` 引起)
- **触发场景**: 运行 `run.sh` 执行因子挖掘的 `factor_construct` 阶段。

## 错误根源分析
1. **LLM 响应截断**: LLM 客户端在 `_create_chat_completion_inner_function` 收到了不完整的 JSON 响应。
2. **解析失败**: 底层健壮性解析函数 `robust_json_parse` 尝试了多种策略修复该截断的 JSON 失败，最终抛出 `json.JSONDecodeError`。
3. **重试机制失效 (核心 Bug)**: 在 `/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/coder/eva_utils.py` 的重试循环中（第 557-573 行），代码仅对 `KeyError` 执行了 `attempts += 1` 并重试。当捕获到 `json.JSONDecodeError` 时，代码直接通过 `raise ValueError` 退出了，导致重试机制未能生效。

## 修复步骤
修改 `eva_utils.py` 的异常处理部分，使 `json.JSONDecodeError` 也能正确触发重试：

```python
            except json.JSONDecodeError as e:
                attempts += 1
                if attempts >= max_attempts:
                    raise ValueError("Failed to decode JSON response from API after multiple attempts.") from e
            except KeyError as e:
                attempts += 1
                if attempts >= max_attempts:
                    raise KeyError(
                        "Response from API is missing 'final_decision' or 'final_feedback' key after multiple attempts."
                    ) from e
```

或者将两个异常合并处理。

## 执行操作
1. 将此分析文档写入到 `/home/quan/testdata/aspipe_v4/p/2026-3-12/json_decode_error_analysis.md`。
2. 修复 `eva_utils.py` 中的代码。

从 20260312_110332.txt 的日志来看，除了之前提到的 eva_utils.py 中的 JSON 解析重试 Bug
  外，还存在以下几个值得关注的问题：


  1. 因子实现质量问题 (多次迭代失败)
  日志显示在 mutation 阶段，多个因子在 Debugging 环节经历了多次迭代（10次迭代中的前5次全部失败），主要表现为：
   - 逻辑不匹配：LLM 生成的表达式（如使用 TS_CORR）与因子本身的描述（要求使用 TS_SUM）不符。
   - 反馈闭环偏差：即使评估器给出了明确的错误反馈（如 "final_decision": false 并指出应使用
     TS_SUM），后续生成的代码依然在重复同样的错误。
   - 结论：这表明当前的 coder 提示词或 LLM
     模型（Qwen3-Coder）在处理复杂的数学表达转换时存在一定的理解偏差，导致了较多的 Token 浪费和时间消耗。


  2. 环境与配置警告
   - 缺失可选依赖：
     - llama is not installed (导致无法使用 llama 相关的 LLM 功能)。
     - CatBoostModel, XGBModel, PyTorch models 被跳过，因为环境中未安装对应的库（虽然这不影响 LGBM
       运行，但限制了模型多样性）。
   - Qlib 运行警告：
     - trade unit 100 is not supported in adjusted_price mode：这可能导致回测时的成交逻辑与实际 A
       股（100股一手）不完全一致。
     - load calendar error: freq=day, future=True; return current calendar!：Qlib
       无法获取未来交易日历，可能影响到某些需要前瞻性信息的因子（尽管在该场景下通常不鼓励使用）。


  3. 性能表现
   - 因子表现平平：Direction 0 和 Direction 1 的因子回测结果显示，超额收益的 IR 虽然在 1.0
     左右，但相比于基准并没有质的突破。
   - 计算耗时：factor_calculate 和 factor_backtest 的每个回合大约需要 40-60
     秒，如果迭代次数多且逻辑复杂，整体挖掘速度会受限。


  4. 数据处理警告
   - 空值告警：RuntimeWarning: Mean of empty slice 和 factor contains
     nan。这说明在某些回测时点或股票上，因子计算结果全为空，这通常是因为 Lookback Window（如 60
     天）在回测起始阶段数据不足导致的。


  建议操作
   1. 优先修复 eva_utils.py：这是最紧急的阻塞性 Bug，能显著提高系统的健壮性。
   2. 优化提示词 (Prompt)：如果这种“逻辑不匹配”的问题持续发生，建议检查 coder
      的系统提示词，强制要求其在生成表达式前先检查数学公式的对应关系。
   3. 完善环境安装：如果需要更强的预测能力，可以考虑安装 xgboost 或 pytorch。
