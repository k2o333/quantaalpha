# QuantaAlpha 运行问题复核与采纳建议

> 复核对象：
> [2026-03-15-quantaalpha-run-issues.md](/home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-15-quantaalpha-run-issues.md)
>
> 证据来源：
> [20260315_090519.txt](/home/quan/testdata/aspipe_v4/third_party/facotors/terminal/20260315_090519.txt)
> [trajectory_pool.json](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/log/2026-03-15_01-05-21-592975/trajectory_pool.json)
> [evolution_state.json](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/log/2026-03-15_01-05-21-592975/evolution_state.json)

## 结论摘要

原分析文档整体方向是对的，但问题优先级和个别归因不够准确。

这次运行的关键事实是：

- 任务整体成功完成，最终 `0 failures`
- 共产生 7 个 trajectory，最佳为 `cb3ef488de4d`
- 当前主问题不是“跑不通”，而是“方向漂移、调试成本偏高、结果质量门控不足”

因此，建议把问题分成三类：

1. 立即采纳并整改
2. 采纳但调整表述或实现方式
3. 仅保留为备注，不作为当前主线整改项

## 与日志一致的事实

以下信息和运行证据一致：

- 运行完成
  - 终端日志末尾有 `Task failure summary: 0 failures`
  - 终端日志末尾有 `Run finished or terminated`
- trajectory 数量为 7
  - `trajectory_pool.json` 中共有 7 条轨迹
- 最优 trajectory 为 `cb3ef488de4d`
  - 该轨迹 `RankIC=0.0219640145575839`
- 运行期间反复出现 tokenizer warning
  - 日志中多次出现 `Failed to initialize tokenizer encoder for model kimi-k2-0905-iflow`
- 至少存在一次 NaN 输出
  - 日志中出现 `920183.BJ ... NaN`
- 至少有一个因子经历多轮 debug 才通过
  - `OvernightJump_LiquidityStress_Interaction_1D` 先后出现两次 `final_decision=false`，之后转为 `true`

## 建议采纳

### 1. Tokenizer 托底策略

建议采纳，优先级高。

原因：

- 日志中反复出现 `kimi-k2-0905-iflow` tokenizer 初始化失败
- 这类问题不止可能发生在 `kimi`，任何未被 `tiktoken` 识别的模型名都可能触发
- 问题虽然不阻塞主流程，但会持续制造噪音

相关代码：

- [client.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/llm/client.py#L33)
- [client.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/llm/client.py#L528)
- [client.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/llm/client.py#L608)

建议实现：

- 不按具体模型名分别兼容
- 对任何未知模型统一回退到固定 tokenizer，例如 `cl100k_base`
- 同一个模型名只输出一次 warning
- 后续 token 统计统一使用该托底编码器，不再反复刷日志

### 2. 因子结果质量门控

建议采纳，优先级高。

原因：

- 日志里已经出现 NaN
- 当前系统虽然能继续回测，但没有把 NaN/inf 比例当成质量门槛

需要调整的一点：

- 原文档里对 NaN 原因的解释更像推测，不应写死为 `volume=0`、停牌或窗口不足
- 更稳妥的结论是：当前缺少统一的 NaN/inf 统计与阈值淘汰

建议实现：

- 在 factor calculate 或 backtest 前增加：
  - NaN 比例统计
  - inf 比例统计
  - 常数列检查
  - 有效样本比例检查
- 超阈值时：
  - 至少 warning
  - 更理想的是直接淘汰该因子

### 3. Expression 与 Description 一致性校验

建议采纳，优先级中高。

原因：

- `OvernightJump_LiquidityStress_Interaction_1D` 的 debug 反馈明确出现：
  - 描述强调 raw magnitude
  - 表达式却加了 `RANK()`
- 这类问题不属于执行错误，而是构造阶段语义漂移

建议实现：

- 在 factor construct 后增加轻量一致性检查
- 对以下模式做规则化校验：
  - description 提“raw value/raw magnitude”，expression 不应出现 `RANK/ZSCORE`
  - description 未提标准化，expression 却引入强横截面变换时给 warning
- 同时收紧 prompt，要求 description 明确披露是否做 rank/zscore

## 建议采纳，但需改写原结论

### 4. 缺失 CatBoost/XGBoost/PyTorch

可以保留，但不应作为这次运行的主要问题。

原因：

- 这次运行最终成功结束
- 7 个 trajectory 都完成了
- 最佳因子正常产出
- 日志中的 `ModuleNotFoundError` 更像“可选模型未安装”，不是主阻塞

更准确的表述应是：

- 当前回测环境只启用了可用模型子集
- 如果未来明确要做模型对比或 ML 因子训练，再补装这些依赖
- 不建议把这条排到前面

### 5. LiteLLM 价格表远程拉取失败

可以保留为环境备注，但不建议进入整改主线。

原因：

- 只出现 1 次
- 之后使用本地 fallback
- 对这次挖掘结果几乎没有直接影响

## 不建议作为当前主线问题

### 6. Qlib 警告集合

不建议作为当前主整改对象。

原因：

- 多数是第三方库提示
- 没有证据表明它们是这次 run 的主要性能或结果问题来源
- 可以保留到“环境噪音/后续优化”章节

## 原文档漏掉但应补充的问题

### 7. 研究方向漂移

这是原文档最该补的一条。

运行入口给的是“挖掘日频横截面因子”，但 planning 产出的方向很快漂移到：

- XGBoost 非线性技术因子
- 另类数据、新闻情绪、供应链关系

这类漂移虽然不一定让任务失败，但会持续把 hypothesis 推向：

- 当前数据不可得
- 当前执行链路不擅长
- 文档叙述和实际可算表达式不一致

建议实现：

- 在 planning prompt 中明确禁止不可用数据源
- 对 hypothesis/specification 做数据能力约束
- 把“只能使用当前可用日频字段”提升为硬约束

### 8. Debug 仍按 batch 推进，而不是只修失败因子

这是效率问题，也值得进入整改清单。

现状：

- [config.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/coder/costeer/config.py#L15) 仍默认 `max_loop=10`
- [evolving_agent.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/core/evolving_agent.py#L73) 仍按整批循环
- 虽然“全部通过提前退出”已经存在，但只要 batch 中仍有失败项，就继续下一轮

影响：

- 已通过的因子也被拖着继续走 batch 级调试流程
- LLM 调用成本和等待时间被放大

建议实现：

- 下一轮只保留 `final_decision=false` 的因子继续 debug
- 已通过因子直接冻结
- 如果失败集合两轮不再改善，则提前停止

## 调整后的优先级

建议将本次问题优先级调整为：

### P0

- Tokenizer 托底：未知模型统一回退固定 tokenizer，且同模型只告警一次
- 结果质量门控：NaN/inf/常数列/有效样本比例检查

### P1

- 研究方向漂移约束
- 只重试失败因子的 debug 策略
- Expression/Description 一致性校验

### P2

- 可选模型依赖安装
- Qlib 与 LiteLLM 环境噪音清理

## 最终结论

原分析文档不是没有道理，但如果按它原样推进，容易把整改资源花在次要项上。

本次更值得采纳的方向是：

- 修 tokenizer 兼容
- 增加因子结果质量门控
- 限制方向漂移
- 把 debug 改成只修失败因子
- 增加 expression/description 一致性校验

而以下项目应降级处理：

- 缺失 CatBoost/XGBoost/PyTorch
- LiteLLM 成本表拉取失败
- 大部分 Qlib warnings
