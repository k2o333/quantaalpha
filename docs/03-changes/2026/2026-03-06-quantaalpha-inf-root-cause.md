# QuantaAlpha 回测 `inf/-inf/NaN` 问题排查记录

## 结论

本次回测中出现的：

- benchmark return 为 `inf`
- excess return 为 `-inf`
- `std` / `information_ratio` 为 `NaN`

根因不是策略收益本身异常，也不是 `PortAnaRecord` 的统计逻辑出错，而是 **Qlib benchmark `SH000300` 的底层行情数据已损坏**。

更具体地说：

1. 回测配置中 benchmark 使用的是 `SH000300`
2. Qlib 从 provider 目录中读取 `features/sh000300/close.day.bin`
3. 该文件对应的 `$close` 序列已经异常，表现为交替出现 `0` 和极大值
4. 因此 `$close/Ref($close, 1)-1` 被计算成了交替的 `-1.0` 和 `inf`
5. `report_normal_1day.pkl` 中的 `bench` 列被污染
6. `port_analysis_1day.pkl` 再基于 `return - bench` 计算超额收益，于是出现 `-inf/NaN`

---

## 一、问题现象

回测日志中出现了如下结果：

```text
'The following are analysis results of benchmark return(1day).'
                   risk
mean                inf
std                 NaN
annualized_return   inf
information_ratio   NaN
max_drawdown        0.0

'The following are analysis results of the excess return without cost(1day).'
                   risk
mean               -inf
std                 NaN
annualized_return  -inf
information_ratio   NaN
max_drawdown       -inf
```

同时还伴随：

```text
factor.day.bin file not exists or factor contains `nan`. Order using adjusted_price.
trade unit 100 is not supported in adjusted_price mode.
RuntimeWarning: Mean of empty slice
```

以及指标输出：

```text
ffr = 1.0
pa  = 0.0
pos = 0.0
```

---

## 二、最初怀疑的几个方向

排查开始时，存在几个可能方向：

1. 因子或预测值异常，导致组合收益本身出现 `inf/NaN`
2. 没有实际成交，导致回测收益序列为空
3. benchmark 序列异常，污染了超额收益统计
4. `PortAnaRecord` 或 `risk_analysis()` 的实现有 bug

最终确认是第 3 种。

---

## 三、定位过程

### 3.1 指标输出的来源

Qlib 的 portfolio 分析来自：

- [record_temp.py](/root/miniforge3/envs/mining/lib/python3.12/site-packages/qlib/workflow/record_temp.py#L483)
- [record_temp.py](/root/miniforge3/envs/mining/lib/python3.12/site-packages/qlib/workflow/record_temp.py#L500)

其中：

1. `report_normal_1day.pkl` 保存基础回测结果
2. `port_analysis_1day.pkl` 基于 `report_normal["return"] - report_normal["bench"]` 做风险分析
3. `indicator_analysis_1day.pkl` 基于 `indicators_normal_1day.pkl` 聚合 `ffr/pa/pos`

因此，先检查 `report_normal_1day.pkl` 最关键。

### 3.2 读取本次运行 artifact

本次对应的 artifact 路径为：

- [report_normal_1day.pkl](/home/quan/testdata/aspipe_v4/third_party/data/results/workspace_exp_20260312_005109/0b2909a85b68483884dd4e4067cd9cf8/mlruns/520496996856333815/0edd19dcb47347cf9d6e99375d9669fd/artifacts/portfolio_analysis/report_normal_1day.pkl)
- [indicators_normal_1day.pkl](/home/quan/testdata/aspipe_v4/third_party/data/results/workspace_exp_20260312_005109/0b2909a85b68483884dd4e4067cd9cf8/mlruns/520496996856333815/0edd19dcb47347cf9d6e99375d9669fd/artifacts/portfolio_analysis/indicators_normal_1day.pkl)
- [positions_normal_1day.pkl](/home/quan/testdata/aspipe_v4/third_party/data/results/workspace_exp_20260312_005109/0b2909a85b68483884dd4e4067cd9cf8/mlruns/520496996856333815/0edd19dcb47347cf9d6e99375d9669fd/artifacts/portfolio_analysis/positions_normal_1day.pkl)

读取后发现：

1. `report_normal_1day.pkl` 中 `return/account/value/cost/cash` 都正常
2. **只有 `bench` 列异常**
3. `bench` 交替出现 `-1.0` 和 `inf`

示例：

```text
2021-01-04   -1.0
2021-01-05    inf
2021-01-06   -1.0
2021-01-07    inf
```

这一步已经说明：

- 组合收益不是根因
- benchmark 才是根因

### 3.3 `positions_normal_1day.pkl` 说明回测并非“完全没交易”

读取 [positions_normal_1day.pkl](/home/quan/testdata/aspipe_v4/third_party/data/results/workspace_exp_20260312_005109/0b2909a85b68483884dd4e4067cd9cf8/mlruns/520496996856333815/0edd19dcb47347cf9d6e99375d9669fd/artifacts/portfolio_analysis/positions_normal_1day.pkl) 后确认：

1. `2021-01-04` 只有现金，这是正常的初始状态
2. 从 `2021-01-05` 开始已经有实际持仓
3. 持仓字典中已有大量股票和对应 `amount/price/weight`

因此：

- 不是“完全没持仓”
- 也不是“回测没跑起来”

### 3.4 `ffr/pa/pos` 的含义

Qlib 对这些指标的定义见：

- [executor.py](/root/miniforge3/envs/mining/lib/python3.12/site-packages/qlib/backtest/executor.py#L44)
- [evaluate.py](/root/miniforge3/envs/mining/lib/python3.12/site-packages/qlib/contrib/evaluate.py#L97)

含义为：

1. `ffr`: fulfill rate
2. `pa`: price advantage
3. `pos`: positive rate

而 [indicator_analysis_1day.pkl](/home/quan/testdata/aspipe_v4/third_party/data/results/workspace_exp_20260312_005109/0b2909a85b68483884dd4e4067cd9cf8/mlruns/520496996856333815/0edd19dcb47347cf9d6e99375d9669fd/artifacts/portfolio_analysis/indicator_analysis_1day.pkl) 只是对 `indicators_normal_1day.pkl` 的时间聚合。

这几个指标不是本次 `inf/-inf` 的根因。

---

## 四、benchmark 是如何算出来的

Qlib benchmark 逻辑位于：

- [report.py](/root/miniforge3/envs/mining/lib/python3.12/site-packages/qlib/backtest/report.py#L97)

其中 benchmark 收益来自：

```python
fields = ["$close/Ref($close,1)-1"]
```

也就是直接用 benchmark 标的自身的 `$close` 计算日收益。

本次回测配置文件是：

- [conf_baseline.yaml](/home/quan/testdata/aspipe_v4/third_party/data/results/workspace_exp_20260312_005109/0b2909a85b68483884dd4e4067cd9cf8/conf_baseline.yaml)

配置中明确写的是：

```yaml
benchmark: SH000300
```

所以只要 `SH000300` 的底层行情文件损坏，`bench` 列就一定会坏。

---

## 五、最终根因定位

### 5.1 实际被 Qlib 使用的数据目录

虽然很多配置里写的是：

```yaml
provider_uri: "~/.qlib/qlib_data/cn_data"
```

但实际初始化日志显示，当前 provider 落在：

- [qlib_data_csi300_bin](/home/quan/testdata/aspipe_v4/third_party/data/qlib_data_csi300_bin)

也就是说，`~/.qlib/qlib_data/cn_data` 当前实际链接到了这个目录。

### 5.2 该目录中确实存在 benchmark 特征目录

定位到：

- [features/sh000300](/home/quan/testdata/aspipe_v4/third_party/data/qlib_data_csi300_bin/features/sh000300)

这说明 benchmark 并不是“代码写错导致找不到数据”，而是**找到了，但数据内容坏了**。

### 5.3 直接读取 `SH000300` 原始数据的结果

使用 `/root/miniforge3/envs/mining/bin/python` 和 Qlib 直接读取：

```python
D.features(['SH000300'], ['$close', 'Ref($close,1)', '$close/Ref($close,1)-1'])
```

得到的结果是：

```text
2021-01-04  $close=0
2021-01-05  $close=5.29e+16
2021-01-06  $close=0
2021-01-07  $close=5.33e+16
```

对应收益为：

```text
2021-01-04  -1.0
2021-01-05   inf
2021-01-06  -1.0
2021-01-07   inf
```

这与 `report_normal_1day.pkl` 中的 `bench` 列完全一致。

因此根因已确认：

> `SH000300` 在当前 Qlib provider 中的原始行情文件已损坏，导致 benchmark 收益序列错误。

---

## 六、为什么会连锁变成 `-inf/NaN`

因为 Qlib 的组合分析是这样做的：

1. benchmark analysis: `risk_analysis(report_normal["bench"])`
2. excess return without cost: `risk_analysis(report_normal["return"] - report_normal["bench"])`
3. excess return with cost: `risk_analysis(report_normal["return"] - report_normal["bench"] - report_normal["cost"])`

一旦 `bench` 含有 `inf`：

1. `return - bench = -inf`
2. `mean = -inf`
3. `std` 遇到无穷值后变成 `NaN`
4. `information_ratio = mean / std = NaN`
5. `cumsum` 或 max drawdown 也会被污染

所以最终出现整片 `inf/-inf/NaN`。

---

## 七、与其他日志的关系

### 7.1 `factor.day.bin file not exists or factor contains nan`

这条日志来自：

- [exchange.py](/root/miniforge3/envs/mining/lib/python3.12/site-packages/qlib/backtest/exchange.py#L222)

它表示某些股票交易时缺少 `$factor` 或出现 `nan`，于是 Qlib 改用 adjusted price 模式。

这会影响交易细节，但**不是本次 benchmark `inf` 的直接根因**。

### 7.2 `trade unit 100 is not supported in adjusted_price mode`

这是上一条警告的连带结果，也不是本次 benchmark 异常的主因。

### 7.3 `Mean of empty slice`

这条警告和 `indicators_normal_1day.pkl` 首日 `count=0` 有关，说明某些统计窗口为空。

它可以解释某些单日 `NaN`，但不能解释 benchmark 交替 `-1/inf`。

---

## 八、修复建议

### 方案 A：修复 benchmark 数据文件

优先修复：

- [features/sh000300](/home/quan/testdata/aspipe_v4/third_party/data/qlib_data_csi300_bin/features/sh000300)

重点检查：

1. `close.day.bin`
2. `open.day.bin`
3. `return.day.bin`

如果这份数据是由转换脚本生成的，需要回溯生成过程，重新生成指数数据。

### 方案 B：临时绕过坏 benchmark

如果目的是先恢复回测可用性，可以先在回测配置里把：

```yaml
benchmark: SH000300
```

改为以下之一：

1. `benchmark: null`
2. 传入一条确认正常的 benchmark `pd.Series`
3. 使用别的可用 benchmark 标的

这样至少可以避免 `bench` 污染超额收益统计。

### 方案 C：在回测前增加 benchmark 数据体检

在启动回测前，对 benchmark 做最基本的质量检查：

1. `$close` 不应大面积为 0
2. `$close` 不应出现极端异常值
3. `$close/Ref($close,1)-1` 不应包含 `inf/-inf`

如果发现异常，直接拒绝回测并报错，比产出一堆误导性的风险指标更稳妥。

---

## 九、最终结论

本次问题的完整来龙去脉如下：

1. 回测配置使用 `benchmark: SH000300`
2. Qlib 从 provider 中读取 `features/sh000300`
3. 该目录下的行情文件已损坏
4. `SH000300` 的 `$close` 交替为 `0` 和极大值
5. benchmark 日收益被算成 `-1.0` 和 `inf`
6. `report_normal_1day.pkl` 中 `bench` 列被污染
7. `PortAnaRecord` 再基于 `return - bench` 计算超额收益
8. 最终出现 `inf/-inf/NaN`

因此，**问题根因在 benchmark 数据，不在策略逻辑，也不在风险分析实现本身。**
