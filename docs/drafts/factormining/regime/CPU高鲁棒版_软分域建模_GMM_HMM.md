# CPU版：高鲁棒性软分域建模方案（GMM-HMM + Sample Weight）

## 版本：4.0 (高鲁棒性与低算力版)
## 适用场景：A股全市场单机CPU与中端GPU环境
## 核心目标：针对风格切换特征，引入具备**时序平滑能力的隐马尔可夫模型（HMM）混合高斯发放**作为门控网络，解决单点高斯分布独立性缺陷；同时补充完整的特征工程与落地代码框架。

---

### 一、 门控模型选型与优化：为什么选择 GMM-HMM？

在之前的版本中，直接使用纯 GMM 存在一个致命隐患：**GMM 假设所有样本在时间上是独立同分布的（IID）**。但A股的“大盘价值”或“小盘微盘”风格具有极强的**时序粘性（State Transition）**。
如果单日某只股票因为偶发的暴涨导致横截面特征脉冲，纯 GMM 会立刻将其概率划给另一个簇，这依然会引发微型的“簇漂移”。

**改进方案：采用 GMM-HMM (高斯混合隐马尔可夫模型)**
* **HMM 的时序平滑力**：引入一个隐状态转移矩阵 $A$。模型在计算当日属于哪个隐状态（风格簇）时，不仅看当日特征（高斯发放概率），还要看昨天的状态概率。
* **低算力保证**：`hmmlearn` 库中的 `GaussianHMM` (本质即 GMM-HMM 的单高斯或多高斯特例) 极其轻量，单机 CPU 训练 5000 只股票数年的状态仅需数分钟。
* **软权重输出**：HMM 前向-后向算法（Forward-Backward Algorithm）原生就能输出每个时刻特定隐状态的**后验概率（Posterior Probability）**，完美接棒作为 $K$ 个专家的 Sample Weight。

---

### 二、 特征工程详细规范 (Features Engineering)

为保证不泄露未来数据且逻辑自洽，特征集被严格拆分为两组。

#### 1. 门控网络特征 (X_gate) —— 寻找极其稳定的慢变锚点
用于训练 HMM，目标是描画股票的长期“骨相”，切忌使用高频或动量特征。
* `log_mcap`: 对数总市值 （核心容量锚）
* `turnover_20d_avg`: 过去20日换手率移动均值 （流动性锚）
* `volatility_20d`: 过去20日收益率标准差 （风险锚）
* `beta_60d`: 过去60日对中证全指的Beta （大市联动锚）

*数据处理*：X_gate 采用**全市场横截面百分位排位 (Rank Rank_Pct)** 进行标准化，消除极端离群点（妖股、ST股）对高斯分布的破坏。

#### 2. 专家网络特征 (X_expert) —— 挖掘瞬态Alpha
用于 LightGBM 预测，必须剥离任何绝对的“均值依赖”。
* **全市场横截面 Z-Score（当日计算）**:
  * `momentum_5d_rel = (mom_5d - mean(mom_5d_today)) / std(mom_5d_today)`
  * `rsi_14_rel = (rsi_14 - mean(rsi_14_today)) / std(rsi_14_today)`
* **行业内相对排位（避免行业偏度）**:
  * `pe_industry_rank = rank_within_industry(pe) / count(industry_stocks)`
* **新股缺值处理**：上市不满 60 天的新股，其历史依赖特征（如 `beta_60d`）填入全市场中位数（Z-score 为 0），在 HMM 中会被给予最平均的权重，不过度倾斜任何特定专家。

---

### 三、 完整训练与推理代码框架 (Python 伪代码)

#### Phase 1: HMM 预训练与权重生成 (CPU)
```python
import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM

# 1. 准备门控特征数据 X_gate (Panel Data: N只股票 * T个交易日)
# 假设 X_panel 形状为 (N * T, num_gate_features)
# 必须按股票groupby后，按时间顺序排列传入长序列，或利用lengths参数

# 2. 定义 K 个隐状态 (对应 K 个专家)
K = 5 
model_hmm = GaussianHMM(n_components=K, covariance_type="diag", n_iter=100)

# 3. 训练 HMM
# 注意：可以按股票单调序列拼接，并传入每只股票的序列长度列表 lengths
model_hmm.fit(X_panel, lengths)

# 4. 生成软权重概率 (作为后续标签)
# predict_proba 返回形状 (N*T, K)，每行和为 1
weights_matrix = model_hmm.predict_proba(X_panel) 

# 保存为 DataFrame 备用
df_weights = pd.DataFrame(weights_matrix, columns=[f'w_expert_{i}' for i in range(K)])
```

#### Phase 2: 独立专家树模型训练 (GPU 2060 加速)
```python
import lightgbm as lgb

expert_models = []
# 基础参数配置
lgb_params = {
    'objective': 'regression', # 或 lambdarank
    'metric': 'rmse',
    'device_type': 'gpu',      # 极速调用 2060
    'gpu_platform_id': 0,
    'gpu_device_id': 0,
    'num_leaves': 63,
    'learning_rate': 0.05,
    'feature_fraction': 0.8
}

# 准备包含所有特征的数据 df_train (包含 X_expert 和 标签 y_true)
for k in range(K):
    print(f"--- 正在训练 专家 {k} ---")
    
    # 核心：获取刚才 HMM 算出的针对专家 k 的概率权重
    sample_weights_k = df_train[f'w_expert_{k}'].values
    
    # 【优化项】：对权重极低（如 < 0.05）的样本进行硬过滤以加速计算
    mask = sample_weights_k > 0.05
    X_subset = df_train[mask][X_expert_cols]
    y_subset = df_train[mask]['target_return']
    w_subset = sample_weights_k[mask]
    
    # 构建 Dataset 并应用权重
    train_data = lgb.Dataset(X_subset, label=y_subset, weight=w_subset)
    
    # 训练模型
    gbm = lgb.train(lgb_params, train_data, num_boost_round=500)
    
    # 保存模型
    gbm.save_model(f'expert_model_{k}.txt')
    expert_models.append(gbm)
```

#### Phase 3: 每日在线推理 (极速平滑)
```python
def daily_inference(df_today):
    """
    df_today: 包含今日 5000 只股票的所有交叉特征
    其中：
    X_gate_today: 昨日或今日盘前已算好的门控横截面特征
    X_expert_today: 实时抽取的预测专家横截面特征
    """
    # 1. 过 HMM 拿到今日每个股票的当期分布概率
    # (实盘中，需要传入该股票最近几天的序列以利用隐状态的平滑性)
    today_weights = model_hmm.predict_proba(X_gate_today) 
    
    # 2. 开启并行专家预测
    expert_preds = np.zeros((len(df_today), K))
    for k in range(K):
        # 每个模型打分
        expert_preds[:, k] = expert_models[k].predict(X_expert_today)
    
    # 3. 结果平滑点乘 (w1*y1 + w2*y2 + ... + wK*yK)
    # today_weights.shape = (N, K)
    # expert_preds.shape = (N, K)
    final_score = np.sum(today_weights * expert_preds, axis=1)
    
    return final_score
```

---

### 四、 关键技术细节应对

1. **异常处理（某只股票所有权重极其均等）**
   如果 HMM 对一只股票输出了 $[0.2, 0.2, 0.2, 0.2, 0.2]$，这说明该股票当前处于极其模糊的市场缝隙中（如发生重大重组的异动股）。本方案直接让 5 个模型的结果平均相加。这恰恰是最高容错的做法——避免了单边模型的极端误判，实现了自然的风险对冲。

2. **训练时序防泄漏**
   绝对禁止使用 $K$ 折交叉验证等随机打破时间序列的打法。必须使用 **Walk-Forward 滚动切分**：例如使用 2018-2022 年数据完整训练 HMM 和 $K$ 个 LightGBM，用来预测 2023 年；随后滚动窗口至 2019-2023 重新跑全流程。

3. **极端异常值权重控制 (Thresholding)**
   如代码所示，我们在 LightGBM 构建数据时，强制过滤了 `w_k < 0.05` 的极低相关样本。虽然理论上 `weight=0.01` 对梯度的影响微乎其微，但剔除它们大大节省了 2060 的内存占用，加速了建树过程，解决了反馈中所担心的“隐患”。
