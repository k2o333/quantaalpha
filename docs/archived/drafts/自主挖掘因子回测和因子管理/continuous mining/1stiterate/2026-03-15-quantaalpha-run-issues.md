# QuantaAlpha 自主因子挖掘实验问题分析

> **实验ID**: `exp_20260315_090520`
> **终端日志**: `third_party/facotors/terminal/20260315_090519.txt`（4831行）
> **分析日期**: 2026-03-15

## 实验概况

实验通过 `run.sh` 启动，执行了完整的进化循环（Original → Mutation → Crossover → Mutation），共产生 **7 个 trajectory**，**0 个 failure**。实验从 09:05 运行至 09:20，约 15 分钟。

| 阶段 | 数量 | Direction 0 | Direction 1 |
|------|------|------------|------------|
| Original | 2 | cb3ef488de4d (RankIC=0.0220) | b4e753cb5865 (RankIC=0.0200) |
| Mutation | 3 | 60a7c720fd87, 35d1cb1f6370 | 03837f614ed4 |
| Crossover | 2 | e622cad2aefe (RankIC=0.0192) | bad318386059 |

最佳 trajectory: `cb3ef488de4d`（Original 阶段，RankIC=0.0220）

---

## 🔴 代码级问题

### 1. Tokenizer 编码器初始化失败（最高频）

**现象**：每次 LLM 调用前都会触发 WARNING + ERROR，整个实验中出现 **60+ 次**。

```
ERROR | quantaalpha.llm.client:_get_encoder:632 - Failed to get encoder even after patching with _azure_patch
WARNING | quantaalpha.llm.client:__init__:534 - Failed to initialize tokenizer encoder for model kimi-k2-0905-iflow:
'Could not automatically map kimi-k2-0905-iflow to a tokeniser.
Please use `tiktoken.get_encoding` to explicitly get the tokeniser you expect.'
```

**涉及文件**：
- `quantaalpha/llm/client.py` → `_get_encoder()` (L627-632)
- `quantaalpha/llm/client.py` → `__init__()` (L534)

**原因**：模型名 `kimi-k2-0905-iflow` 无法被 `tiktoken` 自动映射到编码器。代码先尝试直接映射，失败后尝试 `_azure_patch`，仍然失败。

**影响**：
- 无法进行精确的 token 计数
- prompt 截断或超限风险（当前 `chat_token_limit=100000`）
- token 计费不准确
- 不影响 LLM 调用本身（调用正常进行）

**建议修复**：在 `_get_encoder` 中为 kimi 系列模型做显式编码器映射：

```python
# 在 _get_encoder 中添加自定义模型的 fallback
CUSTOM_MODEL_ENCODING_MAP = {
    "kimi": "cl100k_base",  # 或其他合适的编码
}

def _get_encoder(self, model_name: str):
    # ... 现有逻辑 ...
    # fallback: 检查自定义映射
    for prefix, encoding in CUSTOM_MODEL_ENCODING_MAP.items():
        if prefix in model_name:
            return tiktoken.get_encoding(encoding)
```

---

### 2. Factor 数据中出现 NaN

**现象**：`Analyst_Disagreement_Surrogate_20D` 因子在部分股票上输出 NaN。

```
                                               feature
                      Fundamental_Inflection_Proxy_30D Analyst_Disagreement_Surrogate_20D
datetime   instrument
2026-03-05 920183.BJ                          0.000000                                NaN
```

**涉及文件**：因子表达式 `-TS_CORR(DELTA($close,1)/$close, DELTA($volume,1)/$volume, 20) * TS_STD(DELTA($close,1)/$close, 20)`

**原因**：
- `920183.BJ` 的 `Fundamental_Inflection_Proxy_30D` 值为 0.0，说明该股近期无交易数据或数据不足
- `TS_CORR` 在窗口内数据不足（如停牌）时返回 NaN
- `DELTA($volume,1)/$volume` 在 volume=0 时产生 NaN/inf

**影响**：NaN 传播到下游模型训练和回测，可能降低结果准确性。

**建议修复**：
1. 在 `factor_calculate` 阶段增加 NaN 比例检查，超过阈值时发出 warning
2. 在因子表达式中对 volume 做保护：`DELTA($volume,1)/($volume + 1e-8)`
3. 在 `runner.py` 的 `develop()` 函数中增加因子 NaN 统计

---

### 3. Factor Debugging 中 Expression 与 Description 不一致

**现象**：Crossover 阶段的 `OvernightJump_LiquidityStress_Interaction_1D` 因子经历了 **3 轮 debug** 才通过。

```
# 第 1 轮：description 说返回原始值，但 expression 里有 RANK
final_decision: false
"The formulation returns the raw economic magnitude, but the code applies an extra RANK at the end"

# 第 2 轮：修改后仍有问题
final_decision: false
"Move 1e-8 to the denominator after volume_t..."

# 第 3 轮：最终通过
final_decision: true
```

**涉及文件**：
- `quantaalpha/coder/costeer/` 下的 factor expression 生成和校验逻辑
- `quantaalpha/factors/regulator/factor_regulator.py`

**影响**：
- 增加了 LLM 调用次数和耗时（该因子 debug 阶段耗时 60s，而正常因子约 17-29s）
- 浪费了 token 额度

**建议修复**：
1. 在 `factor_construct` 阶段增加 expression ↔ description 一致性校验
2. 对 LLM 生成的 expression 做预检查：如果 description 要求"原始值"，则不应包含 `RANK()` / `ZSCORE()` 等变换
3. 在 factor construct prompt 中明确要求：如果使用了 RANK/ZSCORE 等变换，description 中必须提及

---

## 🟡 环境/配置问题

### 4. 缺失可选 ML 模型库

**现象**：每次 backtest 都出现以下提示（共 ~8 次 backtest）。

```
ModuleNotFoundError. CatBoostModel are skipped. (optional: maybe installing CatBoostModel can fix it.)
ModuleNotFoundError. XGBModel is skipped(optional: maybe installing xgboost can fix it).
ModuleNotFoundError. PyTorch models are skipped (optional: maybe installing pytorch can fix it).
```

**影响**：回测只使用了 `LGBModel`（LightGBM），缺少模型多样性。

**建议**：
```bash
conda activate mining
pip install catboost xgboost torch
```

---

### 5. LiteLLM 远程模型价格表获取失败

```
LiteLLM:WARNING: Failed to fetch remote model cost map from
https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json:
_ssl.c:993: The handshake operation timed out. Falling back to local backup.
```

**影响**：成本跟踪可能不准确（使用了本地 fallback 数据）。

**建议**：检查网络连接或配置代理。

---

### 6. Qlib 相关 Warning（来自第三方库）

| Warning | 含义 | 影响 |
|---------|------|------|
| `factor.day.bin file not exists` | 缺少因子日频文件 | 回测使用 adjusted_price 替代，`trade unit 100` 不支持 |
| `load calendar error: freq=day, future=True` | 未来日历数据缺失 | 使用当前日历替代 |
| `<PRED> lookes like a placeholder` | 预测模板占位符未匹配 | 可能影响预测信号配置 |
| `SettingWithCopyWarning` | pandas 切片赋值 | qlib 自身代码问题，不影响结果 |
| Gym deprecation | `gym` 库已废弃 | 建议 qlib 升级到兼容 `gymnasium` 的版本 |
| MLflow FileStore deprecation | filesystem backend 将废弃 | 建议迁移到 `sqlite:///mlflow.db` |

---

## 📊 问题优先级总结

| 优先级 | 问题 | 严重程度 | 出现频率 | 建议 |
|-------|------|---------|---------|------|
| P0 | Tokenizer 映射失败 | 🔴 中高 | 60+ 次 | 为 kimi 模型显式配置编码器 |
| P1 | Factor NaN 值 | 🔴 中 | ≥1 因子 | 加强因子计算的 NaN 检查和处理 |
| P1 | Expression/Description 不一致 | 🟡 中 | 2 次 | 增强构建阶段的一致性校验 |
| P2 | 缺失 ML 模型库 | 🟡 低 | 每次 backtest | 按需安装 catboost/xgboost/pytorch |
| P3 | SSL/网络问题 | ⚪ 低 | 1 次 | 检查网络或配置代理 |
| P3 | Qlib warnings | ⚪ 低 | 多次 | 大多是 qlib 自身的已知问题 |
