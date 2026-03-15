# A股分域状态识别方案 (HMM + XGBoost Voting)

基于“**先聚类分域 -> 将单域视为指数 -> HMM与XGBoost独立预测 -> 投票融合**”的逻辑，以下是为您在 A 股量化研究中设计的落地实施方案。

## 1. 核心架构设计

在已经通过某种聚类算法（例如 KMeans, 层次聚类, 或基于图谱的聚类）将 A 股划分为 $K$ 个簇（Cluster）的前提下，每个簇内部包含若干只股票。我们将每个簇视为一个**独立的合成指数（Synthetic Index）**或**行业/概念ETF**。

对于每一个簇 $C_k$，我们将独立构建一套 `[XGBoost分类器 + HMM状态推断器 + 投票决策层]`，最终输出该簇在 $t+1$ 日的市场状态预测：**牛（+1，做多）、熊（-1，做空/空仓）、震荡（0，观望/高抛低吸）**。

---

## 2. 第一阶段：数据准备与“合成指数”构建

这是 A 股分域操作中最关键的一步，我们需要把“簇内多只股票”的数据降维成“单一标的（指数）”的时间序列。

### 2.1 构建簇级别的基础量价序列 (Cluster-level OHLCT)
对簇 $C_k$ 内的所有成分股，计算每日的聚合指标：
- **簇收益率 (Cluster Return)**: 等权重或流通市值加权的日收益率均值。
- **簇波动率 (Cluster Volatility)**: 成分股日收益率的截面方差，或簇收益率的滚动时间序列方差（例如 20 日滚动标准差）。
- **簇流动性 (Cluster Turnover)**: 成分股的平均换手率。

这些基础序列组合起来，就等价于论文中输入的单一资产的时间序列。

### 2.2 定义“上帝视角的真实标签 (Oracle Labels)”
为了训练 XGBoost 以及后续对齐 HMM 的隐状态，必须先定义目标变量 $O_t$。由于 A 股波动大，建议使用**未来 $N$ 天（例如 5 天或 10 天）的累计簇收益率**作为基准：
- **牛市 (+1)**: 未来 $N$ 天累计收益率 $> \theta_1$（例如 $> 3\%$）
- **熊市 (-1)**: 未来 $N$ 天累计收益率 $< \theta_2$（例如 $< -3\%$）
- **震荡 (0)**: 未来 $N$ 天累计收益率在高低阈值之间。

---

## 3. 第二阶段：双模型异构构建 (XGBoost & HMM)

对于每个簇 $C_k$，我们独立训练两个机制完全不同的模型。

### 3.1 XGBoost: 基于技术微观层面的监督学习分类
它的任务是：**“看着历史答案，学习短期技术形态”**。
- **输入特征 $X_{xgb}$**: 基于簇级别的 OHLCT 数据，计算传统技术指标（如 RSI, MACD, Bollinger Bands, 移动平均线偏离度等）和特定的量价因子。
- **目标变量 $Y$**: $O_t$ (Oracle Labels)。
- **模型设定**: 使用 `multi:softprob` 或 `multi:softmax` 目标函数进行多分类训练。
- **输出**: $\hat{Y}^{xgb}_t \in \{-1, 0, 1\}$，代表 XGBoost 预测的下一阶段状态。

### 3.2 Gaussian HMM: 基于宏观资金形态的无监督推断
它的任务是：**“不看答案，只找资金和波动的自身聚集规律”**。
- **输入特征 $X_{hmm}$**: 必须是连续型特征。建议使用：**1. 簇滚动收益率均值，2. 簇滚动波动率，3. 簇平均换手率（资金关注度）**。
- **模型设定**: 设定隐状态数量 `n_components=3`，使用 Baum-Welch 算法（EM算法）去拟合高斯混合分布。
- **隐状态对齐**: 
  - HMM 输出每天的隐状态编号 $\hat{S}_t \in \{0, 1, 2\}$。
  - 通过计算 $\hat{S}_t$ 与 Oracle Labels $O_t$ 在训练集上的**混淆矩阵**。
  - 使用**匈牙利算法（Hungarian algorithm）**找到最大重合度的映射关系 $\pi$，将其强制重命名为牛、熊、震荡。
- **输出**: $\hat{Y}^{hmm}_t = \pi(\hat{S}_t) \in \{-1, 0, 1\}$，代表 HMM 认为当前所处的真实环境状态。

---

## 4. 第三阶段：投票决策融合 (Voting Ensemble)

在时间 $t$，对于簇 $C_k$，我们得到了两票：$\hat{Y}^{xgb}_t$ 和 $\hat{Y}^{hmm}_t$。由于 A 股市场具有较强的均值回归和假突破特性，我们设计以下投票逻辑：

### 4.1 强共识策略 (Conservative / High Conviction)
只有当两个模型意见完全一致时才行动，否则默认观望或保持原仓位状态。
- **做多簇 $C_k$**: 当且仅当 $\hat{Y}^{xgb}_t = +1$ 且 $\hat{Y}^{hmm}_t = +1$。
- **做空/清仓簇 $C_k$**: 当且仅当 $\hat{Y}^{xgb}_t = -1$ 且 $\hat{Y}^{hmm}_t = -1$。
- **观望/减仓**: 其他意见分歧的情况。
*优点：胜率极高，能避开大部分“技术面骗线”或“宏观假摔”。*

### 4.2 权重/概率融合 (Soft Voting / Dynamic Weighting)
提取 XGBoost 的输出概率向量 $P_{xgb}$ 和 HMM 过滤后的状态概率向量 $P_{hmm}$：
$$ P_{final} = \alpha P_{xgb} + (1-\alpha) P_{hmm} $$
- **$\alpha$ 的动态分配**:
  - 如果簇的换手率急剧放大，说明资金博弈激烈，短线情绪主导，**增大 $\alpha$ (更信 XGBoost)**。
  - 如果簇的波动率降至冰点，进入缩量长草期，说明结构性态势主导，**减小 $\alpha$ (更信 HMM 状态)**。

---

## 5. 工程落地的伪代码/工作流建议

1. **聚类预处理**：定期（如月末）根据个股过去一揽子特征（如行业暴露、Beta、估值、市值等）截面聚类，输出 $K$ 个簇列表。
2. **构建特征池阶段**：
   ```python
   for cluster_id in clusters:
       # 计算该簇的合成指数行情序列 (return, vol, turnover)
       cluster_df = build_synthetic_index(stock_data, cluster_id)
       
       # 生成 Oracle Label
       cluster_df['oracle_label'] = generate_labels(cluster_df)
       
       # 生成 XGBoost 技术特征 和 HMM 状态特征
       cluster_df_xgb = extract_tech_factors(cluster_df)
       cluster_df_hmm = extract_state_features(cluster_df)
   ```
3. **训练映射阶段**：
   ```python
       # 1. 训练 XGBoost
       xgb_model = train_xgb(cluster_df_xgb, y='oracle_label')
       
       # 2. 训练 HMM
       hmm_model = train_gaussian_hmm(cluster_df_hmm, n_components=3)
       hidden_states = hmm_model.decode()
       
       # 3. 匈牙利算法对齐映射 (关键)
       mapping_dict = hungarian_alignment(hidden_states, cluster_df['oracle_label'])
   ```
4. **推理投票阶段**：每天收盘后，提取特征推断两股势道的状态，交由交易模块按照策略执行调仓。

### 总结
这套架构在 A 股分域极其有效。原因在于：**XGBoost 负责捕捉该板块短期的“超跌反弹”和“技术突破”，而 HMM 负责定性该板块当下的“气候条件”**。只有在“气候是暖春（HMM=牛）”的前提下，“技术上的金叉（XGB=牛）”才具有高胜率的参与价值。
