# CPU版：市场状态制导的高维分域方案 (Market-HMM + GMM-Expert)

## 版本：5.0 (终极融合版：解决时序与个股对齐的矛盾)
## 适用场景：A股全市场中高频Alpha，单机CPU+中端GPU环境
## 核心目标：采纳工程师关于“HMM不能简单拼接个股序列”的洞见。将时序平滑彻底上移至“市场环境”层面（Market-Level HMM），个股定位回归到基于当日横截面的 GMM，最终构建出严密的“市场先验 + 个股后验”门控系统。

---

### 一、 核心架构修正：市场状态与个股归属的分离

在上一版的设计中，我们企图用一个 HMM 直接给 5000 只股票做个股级（Stock-Level）的时序平滑。但诚如工程师指出的隐患：股票 A 的序列和股票 B 的序列拼在一起送给 HMM `fit()` 是没有物理意义的；如果每只股票单训一个 HMM，不仅维度炸裂，而且无法共享统一的“专家库”。

**终极解法：解耦“时序平滑”与“截面分配”**
风格切换的本质是**市场环境的变迁**，而不是某只个股自己突然决定要换风格。我们要把 HMM 的应用场景抬升到宏观/全市场维度：

1. **Market-Level HMM（市场环境引擎）**：
   * **输入**：全市场级别的宏观/风格表征序列（如：今日微盘股指数收益、中证1000换手率、全市场涨跌停比例等）。
   * **输出**：当前市场的**隐状态概率 $S = [s_1, s_2, ..., s_K]$** (例如：70%概率是小盘普涨市，30%概率是价值防守市)。
   * **作用**：这就是那把解决“剧烈换手和风格横跳”的降噪锁，它具有极强的时序粘滞性。

2. **Stock-Level GMM（个股骨相引擎）**：
   * **输入**：个股的“慢变锚点” $X_{gate}$（如个股的相对市值排位、20日换手率排位等）。
   * **输出**：在纯横截面意义上，该股票属于 $K$ 种经典风格的**条件概率 $C = [c_1, c_2, ..., c_K]$**。

3. **最终门控权重法则 (Bayesian Fusion)**：
   * $W_{expert} = \text{Softmax}(S \times C)$ 
   * **业务直觉**：一只平时偏向小盘股特点的股票（$C_{小盘}$很高），在今天极其明确的“大盘蓝筹吸血”市场状态下（$S_{大盘}$极大，$S_{小盘}$极小），它分给小盘专家的综合权重 $W$ 会被宏观 HMM 强行压低。这就是通过大环境来平滑个股的异动。

---

### 二、 流水线设计与代码落地框架

#### Phase 1: 市场级时序 HMM 训练 (寻找大环境基调)
```python
import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM

# 1. 准备市场级别宏观特征 X_market (仅仅是 1条 时间序列! T天 * num_features)
# 特征建议：大小盘收益剪刀差、全市场平均换手率、全市场波动率偏度等
X_market = pd.read_csv('market_macro_features.csv') 

# 2. 训练全局唯一的 Market HMM
K = 5 
model_market_hmm = GaussianHMM(n_components=K, covariance_type="diag", n_iter=200)
model_market_hmm.fit(X_market)

# 3. 输出历史上每一天的市场隐状态概率 (T * K)
# 这一步天然解决了时序平滑，且没有任何截面拼接的漏洞
market_states_prob = model_market_hmm.predict_proba(X_market)
```

#### Phase 2: 个股级横截面 GMM 训练 (寻找个股骨相)
```python
from sklearn.mixture import GaussianMixture

# 1. 准备个股门控特征 X_gate (Panel Data，但剔除了时间维度，只看横截面分布)
# 为了避免分布被破坏，X_gate 全是横截面 Rank_Pct 
X_gate = pd.read_csv('stock_slow_features.csv')

# 2. 训练纯横截面 GMM
model_stock_gmm = GaussianMixture(n_components=K, covariance_type='diag')
model_stock_gmm.fit(X_gate)

# 3. 输出每只股票的骨相概率 (N*T * K)
stock_cluster_prob = model_stock_gmm.predict_proba(X_gate)
```

#### Phase 3: 构造专家专属样本权重 (The Fusion)
```python
# 将 T*K 的大盘状态 广播对齐到每一只当天的股票上
# 假设对齐后的矩阵为 broadcast_market_prob (N*T * K)

# 融合宏观先验与个股后验 (这里用简单的对应元素相乘后归一化)
raw_weights = broadcast_market_prob * stock_cluster_prob
final_weights = raw_weights / raw_weights.sum(axis=1, keepdims=True)

# 此时，final_weights 的每一列就是喂给 5 个 LightGBM 的 sample_weight！
# 所有的专家模型训练代码与上一版(V3.0)完全一致：用 Weight 强行规训专家
```

---

### 三、 工程师反馈采纳与技术细节补全

#### 1. 关于“冷启动与停牌复牌”的终极解决
* **宏观层面不中断**：因为 HMM 提拔到了“全市场指数”级别，全市场序列永远是不停牌、不断更的。这意味着 `market_states_prob` 每天都能稳定推断。
* **个股截面极度鲁棒**：停牌股票复牌当天，只需用它复牌当天的 $X_{gate}$（市值、排位）喂给 GMM 算出 $C$ 即可。
* **新股处理**：新股上市初期，无论是换手还是波动都在天上，直接将其 $X_{gate}$ 強制赋为全市场均值（Rank=0.5），GMM 自然会吐出极其均匀的平庸权重 $[0.2, 0.2, 0.2, 0.2, 0.2]$，保证了它不会因为新股特效被错误地丢给某个极端专家。

#### 2. 关于“Walk-Forward”时序交叉验证的规范
在A股绝对禁止随机 Shuffle。评测和训练体系严格按照以下“扩容滚动窗 (Expanding Window)”执行：
* **Train Fold 1**: 2017-01 到 2020-12 (用于训练 HMM、GMM、LightGBM)
  * **Test Fold 1**: 2021-01 到 2021-12
* **Train Fold 2**: 2017-01 到 2021-12 (模型使用最新数据全部重训更新)
  * **Test Fold 2**: 2022-01 到 2022-12
* **总结**：所有的模型更新频率设定为 **年度重训** (在每年末跑一次脚本重新锚定专家)。在年内每个交易日，只做极为廉价的前向 Inference。

#### 3. 关于“隐状态可解释性验证”的必做项
在产出 `model_stock_gmm` 后，量化团队必须执行以下校验审计：
```python
# 验证 K=5 个专家各自负责什么盘面
# 提纯出每个组权重 > 0.8 的“极度典型股票池”
for k in range(K):
    typical_stocks = X_gate[final_weights[:, k] > 0.8]
    print(f"专家 {k} 的典型特征画像:")
    print(typical_stocks.describe()) # 观察平均市值大小、换手高低等
    
# 如果发现专家 2 和专家 3 的特征均值几乎一样，说明 K 设大了，发生了“专家坍缩”。
```
