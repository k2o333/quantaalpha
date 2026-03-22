# 因子挖掘系统架构设计文档

## 概述

本文档描述了基于 QuantaAlpha 和 VNPY 的因子挖掘系统架构设计，采用 7 大模块分层架构，实现从 LLM 因子生成到实盘交易的完整闭环。

---

## 整体架构图

```mermaid
flowchart TB
    subgraph UserLayer["用户接口层"]
        CLI["CLI 命令行<br/>run.sh"]
        WebUI["Web 界面<br/>React Dashboard"]
    end

    subgraph Module1["模块一：LLM 因子生成层"]
        M1_Router["模型路由<br/>ModelRouter"]
        M1_Small["小模型<br/>Mistral/MiniMax"]
        M1_Large["大模型兜底<br/>GLM-4"]
        M1_FewShot["Few-Shot 检索<br/>Faiss/ChromaDB"]
        M1_CodeGen["代码生成器<br/>CodeGenerator"]
    end

    subgraph Module2["模块二：质量门控层"]
        M2_Orchestrator["门控编排器<br/>QualityGateOrchestrator"]
        M2_Consistency["一致性检查<br/>ConsistencyChecker"]
        M2_Complexity["复杂度检查<br/>ComplexityChecker"]
        M2_Redundancy["冗余性检查<br/>RedundancyChecker"]
        M2_HardRules["硬规则拦截<br/>HardRuleFilter"]
    end

    subgraph Module3["模块三：数据适配层"]
        M3_ParquetFeed["ParquetDatafeed<br/>数据适配器"]
        M3_Polars["Polars 懒加载<br/>LazyFrame"]
        M3_Converter["数据转换器<br/>BarDataConverter"]
    end

    subgraph Module4["模块四：事件驱动调度层"]
        M4_EventEngine["EventEngine<br/>事件引擎"]
        M4_Queue["事件队列<br/>EventQueue"]
        M4_Handlers["事件处理器组<br/>EventHandlers"]
        M4_Types["因子事件类型<br/>FactorEventType"]
    end

    subgraph Module5["模块五：回测引擎层"]
        M5_BacktestEngine["回测引擎<br/>FactorBacktestEngine"]
        M5_Inline["Inline 回测<br/>QuickICValidator"]
        M5_Full["完整回测<br/>FullBacktestRunner"]
        M5_StrategyGen["策略生成器<br/>FactorStrategyGenerator"]
        M5_ICCalc["IC 计算器<br/>ICCalculator"]
    end

    subgraph Module6["模块六：Bandit 资源调度层"]
        M6_Scheduler["调度器<br/>BanditScheduler"]
        M6_UCB["UCB 选择器<br/>UCBSelector"]
        M6_EarlyStop["早停机制<br/>EarlyStopMonitor"]
        M6_LocalFix["局部修正器<br/>LocalFixer"]
    end

    subgraph Module7["模块七：三级缓存与经验库层"]
        M7_L1["L1: 代码级 RAG<br/>FactorLibraryManager"]
        M7_L2["L2: 表达式缓存<br/>ExpressionCache"]
        M7_L3["L3: 数据缓存<br/>DataCache"]
        M7_SuccessLib["成功因子库<br/>SuccessFactorLibrary"]
        M7_FailLib["失败因子库<br/>FailureFactorLibrary"]
    end

    subgraph VNPYLayer["VNPY 交易层"]
        VN_History["HistoryManager"]
        VN_Backtest["BacktestingEngine"]
        VN_Gateway["Gateway 接口<br/>CTP/XTP/IB"]
    end

    CLI --> Module1
    WebUI --> Module1

    Module1 --> M1_FewShot --> M1_Router
    M1_Router --> M1_Small
    M1_Small -->|失败>2次| M1_Large
    M1_Small -->|通过| Module2
    M1_Large --> Module2

    Module2 --> M2_Orchestrator
    M2_Orchestrator --> M2_Consistency
    M2_Orchestrator --> M2_Complexity
    M2_Orchestrator --> M2_Redundancy
    M2_Orchestrator --> M2_HardRules
    M2_Orchestrator -->|通过| Module4

    Module4 --> M4_EventEngine
    M4_EventEngine --> M4_Queue
    M4_Queue --> M4_Handlers
    M4_Handlers -->|FACTOR_GENERATED| M4_Types
    M4_Handlers -->|FACTOR_PASSED_AST| Module6
    M4_Handlers -->|FACTOR_BACKTEST_DONE| Module5
    M4_Handlers -->|FACTOR_IC_UPDATE| Module6

    Module6 --> M6_Scheduler
    M6_Scheduler --> M6_UCB
    M6_UCB -->|选择方向| Module3
    M6_Scheduler --> M6_EarlyStop
    M6_EarlyStop -->|终止| M6_LocalFix
    M6_EarlyStop -->|继续| Module3

    Module3 --> M3_ParquetFeed
    M3_ParquetFeed --> M3_Polars
    M3_Polars --> M3_Converter
    M3_Converter --> VN_History

    Module5 --> M5_BacktestEngine
    M5_BacktestEngine --> M5_Inline
    M5_BacktestEngine --> M5_Full
    M5_BacktestEngine --> M5_StrategyGen
    M5_BacktestEngine --> M5_ICCalc
    M5_Inline -->|快速验证| Module6
    M5_Full --> VN_Backtest

    VN_History --> VN_Backtest
    VN_Backtest --> VN_Gateway

    Module7 -.->|L1 检查| Module2
    Module7 -.->|L2 缓存| Module5
    Module7 -.->|L3 缓存| Module3

    Module5 -->|存入| M7_SuccessLib
    Module5 -->|存入| M7_FailLib
```

---

## 模块详细设计

### 模块一：LLM 因子生成层 (Factor Generation Layer)

#### 职责
负责因子的智能生成与代码转换，实现大小模型协同路由。

#### 子模块结构

```mermaid
flowchart TB
    subgraph M1["模块一：LLM 因子生成层"]
        direction TB

        subgraph M1_Config["配置管理"]
            Config["LLMConfig<br/>模型配置"]
            Prompts["PromptTemplates<br/>提示模板库"]
        end

        subgraph M1_Retrieval["检索增强"]
            VectorDB["VectorStore<br/>Faiss/ChromaDB"]
            ExampleDB["ExampleLibrary<br/>Few-Shot 示例库"]
            Retriever["ExampleRetriever<br/>相似示例检索"]
        end

        subgraph M1_Routing["模型路由"]
            Router["ModelRouter<br/>路由决策器"]
            SmallModel["SmallModelClient<br/>小模型客户端<br/>Mistral/MiniMax"]
            LargeModel["LargeModelClient<br/>大模型客户端<br/>GLM-4"]
            Fallback["FallbackStrategy<br/>兜底策略"]
        end

        subgraph M1_Generation["代码生成"]
            Parser["FactorParser<br/>因子解析器"]
            Generator["CodeGenerator<br/>代码生成器"]
            Validator["SyntaxValidator<br/>语法预检"]
        end

        Input["研究方向输入"] --> Config
        Config --> Prompts
        Prompts --> Retriever
        VectorDB --> Retriever
        ExampleDB --> VectorDB
        Retriever --> Router
        Router -->|常规任务| SmallModel
        Router -->|复杂任务| LargeModel
        SmallModel -->|失败>2次| Fallback
        Fallback --> LargeModel
        SmallModel --> Parser
        LargeModel --> Parser
        Parser --> Generator
        Generator --> Validator
        Validator --> Output["因子代码输出"]
    end
```

#### 核心类设计

| 类名 | 职责 | 关键方法 |
|------|------|---------|
| `ModelRouter` | 路由决策 | `route(task_complexity) -> ModelType` |
| `SmallModelClient` | 小模型调用 | `generate(prompt) -> CodeSnippet` |
| `LargeModelClient` | 大模型调用 | `generate(prompt) -> CodeSnippet` |
| `ExampleRetriever` | 示例检索 | `retrieve(query, top_k=2) -> Examples` |
| `CodeGenerator` | 代码生成 | `generate_vnpy_expression(desc) -> Expression` |

#### 与 VNPY 集成

生成 `vnpy.alpha` 兼容的表达式：

```python
# 时间序列函数
"ts_delay(close, 5) / close - 1"
"ts_mean(volume, 20) / volume"
"ts_corr(close, volume, 10)"

# 截面函数
"cs_rank(ts_returns(close, 5))"
"cs_mean(volatility)"

# 技术分析函数
"ta_rsi(close, 14)"
"ta_macd(close)"
```

---

### 模块二：质量门控层 (Quality Gate Layer)

#### 职责
多级质量检查，拦截低质量因子，降低 API 成本。

#### 子模块结构

```mermaid
flowchart TB
    subgraph M2["模块二：质量门控层"]
        direction TB

        subgraph M2_Orchestrator["门控编排器"]
            Orchestrator["QualityGateOrchestrator<br/>质量门控编排器"]
            Pipeline["CheckPipeline<br/>检查流水线"]
        end

        subgraph M2_Consistency["一致性检查"]
            CC_Engine["ConsistencyEngine<br/>一致性引擎"]
            CC_HypoDesc["HypothesisDescChecker<br/>假设-描述对齐"]
            CC_DescForm["DescFormChecker<br/>描述-公式对齐"]
            CC_FormCode["FormCodeChecker<br/>公式-代码对齐"]
            CC_Correction["LLMCorrector<br/>自动修正器"]
        end

        subgraph M2_Complexity["复杂度检查"]
            CX_Engine["ComplexityEngine<br/>复杂度引擎"]
            CX_Length["SymbolLengthChecker<br/>符号长度检查"]
            CX_Features["FeatureCountChecker<br/>特征数量检查"]
            CX_Params["FreeArgsChecker<br/>自由参数检查"]
        end

        subgraph M2_Redundancy["冗余性检查"]
            CR_Engine["RedundancyEngine<br/>冗余性引擎"]
            CR_Similarity["SimilarityCalculator<br/>相似度计算"]
            CR_Dedup["Deduplicator<br/>去重器"]
        end

        subgraph M2_HardRules["硬规则拦截"]
            HR_Filter["HardRuleFilter<br/>硬规则过滤器"]
            HR_Length["PromptLengthRule<br/>长度限制"]
            HR_DivZero["DivZeroRule<br/>除零检查"]
            HR_Future["FutureFunctionRule<br/>未来函数检查"]
        end

        Input["因子候选"] --> Orchestrator
        Orchestrator --> Pipeline

        Pipeline -->|阶段1| HR_Filter
        HR_Filter --> HR_Length
        HR_Filter --> HR_DivZero
        HR_Filter --> HR_Future

        HR_Filter -->|通过| CC_Engine
        CC_Engine --> CC_HypoDesc
        CC_Engine --> CC_DescForm
        CC_Engine --> CC_FormCode
        CC_Engine -->|失败| CC_Correction
        CC_Correction -->|重试| CC_Engine

        CC_Engine -->|通过| CX_Engine
        CX_Engine --> CX_Length
        CX_Engine --> CX_Features
        CX_Engine --> CX_Params

        CX_Engine -->|通过| CR_Engine
        CR_Engine --> CR_Similarity
        CR_Similarity --> CR_Dedup

        CR_Engine -->|通过| Output["通过门控"]
        HR_Filter -->|拦截| Reject1["拒绝"]
        CC_Engine -->|拦截| Reject2["拒绝"]
        CX_Engine -->|拦截| Reject3["拒绝"]
        CR_Engine -->|拦截| Reject4["拒绝"]
    end
```

#### 检查阈值配置

| 检查类型 | 指标 | 阈值 | 说明 |
|---------|------|------|------|
| **硬规则** | Prompt 长度 | <= 500 字符 | 超长截断 |
| **硬规则** | 除零风险 | 无 | AST 静态检查 |
| **硬规则** | 未来函数 | 无 | 检查 `shift(-1)` |
| **一致性** | 语义对齐 | Pass/Fail | LLM 判断，3次重试 |
| **复杂度** | 符号长度 | <= 250 | 防止过复杂表达式 |
| **复杂度** | 基础特征数 | <= 6 | 限制特征维度 |
| **复杂度** | 自由参数比例 | <= 0.5 | 控制参数空间 |
| **冗余性** | 相似因子数 | < 5 | 避免因子库重复 |

---

### 模块三：数据适配层 (Data Adaptation Layer)

#### 职责
桥接现有 Parquet 数据与 VNPY 数据体系。

#### 子模块结构

```mermaid
flowchart TB
    subgraph M3["模块三：数据适配层"]
        direction TB

        subgraph M3_Source["数据源"]
            TuShare["TuShare API"]
            ParquetFiles["Parquet Storage<br/>../data"]
        end

        subgraph M3_Adapter["适配器"]
            BaseFeed["BaseDatafeed<br/>抽象基类"]
            ParquetFeed["ParquetDatafeed<br/>Parquet 适配器"]
            Config["DatafeedConfig<br/>配置管理"]
        end

        subgraph M3_Processing["数据处理"]
            PolarsReader["PolarsReader<br/>懒加载读取"]
            Filter["DataFilter<br/>日期/代码过滤"]
            Transformer["DataTransformer<br/>格式转换"]
        end

        subgraph M3_Output["输出"]
            BarConverter["BarDataConverter<br/>VNPY BarData 转换"]
            TickConverter["TickDataConverter<br/>VNPY TickData 转换"]
        end

        TuShare --> ParquetFiles
        ParquetFiles --> ParquetFeed
        BaseFeed --> ParquetFeed
        Config --> ParquetFeed
        ParquetFeed --> PolarsReader
        PolarsReader --> Filter
        Filter --> Transformer
        Transformer --> BarConverter
        Transformer --> TickConverter
        BarConverter --> VNPY["VNPY HistoryManager"]
        TickConverter --> VNPY
    end
```

#### 核心类设计

```python
class ParquetDatafeed(BaseDatafeed):
    """Parquet 数据适配器"""

    def __init__(self, setting: dict):
        self.base_dir = Path(setting.get("base_dir", "../data"))
        self.polars_config = setting.get("polars", {})

    def query_bar_history(self, req: HistoryRequest) -> list[BarData]:
        """从 Parquet 加载 K 线数据"""
        # 1. 路径映射
        # 2. Polars 懒加载
        # 3. 过滤条件
        # 4. 转换为 BarData
        pass

    def query_tick_history(self, req: HistoryRequest) -> list[TickData]:
        """从 Parquet 加载 Tick 数据"""
        pass
```

---

### 模块四：事件驱动调度层 (Event-Driven Orchestration Layer)

#### 职责
基于 VNPY EventEngine 实现异步流水线，解耦各模块。

#### 子模块结构

```mermaid
flowchart TB
    subgraph M4["模块四：事件驱动调度层"]
        direction TB

        subgraph M4_Engine["事件引擎"]
            EventEngine["EventEngine<br/>VNPY 事件引擎"]
            EventQueue["EventQueue<br/>线程安全队列"]
            Timer["TimerThread<br/>定时器线程"]
            Processor["EventProcessor<br/>事件处理器"]
        end

        subgraph M4_Types["事件类型定义"]
            Enum["FactorEventType<br/>枚举定义"]
            Data["FactorEventData<br/>事件数据结构"]
        end

        subgraph M4_Events["因子事件"]
            E1["FACTOR_GENERATED<br/>因子生成"]
            E2["FACTOR_PASSED_AST<br/>AST 检查通过"]
            E3["FACTOR_BACKTEST_DONE<br/>回测完成"]
            E4["FACTOR_IC_UPDATE<br/>IC 更新"]
            E5["FACTOR_FAILED<br/>因子失败"]
            E6["FACTOR_APPROVED<br/>因子入库"]
        end

        subgraph M4_Handlers["事件处理器"]
            H1["GenerationHandler<br/>生成处理器"]
            H2["ValidationHandler<br/>验证处理器"]
            H3["BacktestHandler<br/>回测处理器"]
            H4["BanditHandler<br/>调度处理器"]
            H5["StorageHandler<br/>存储处理器"]
        end

        subgraph M4_State["状态管理"]
            StateMgr["FactorStateManager<br/>因子状态管理"]
            Registry["HandlerRegistry<br/>处理器注册表"]
        end

        EventEngine --> EventQueue
        EventEngine --> Timer
        EventQueue --> Processor

        Enum --> Data
        Data --> E1
        Data --> E2
        Data --> E3
        Data --> E4
        Data --> E5
        Data --> E6

        Processor --> Registry
        Registry --> H1
        Registry --> H2
        Registry --> H3
        Registry --> H4
        Registry --> H5

        H1 --> E1
        H2 --> E2
        H3 --> E3
        H4 --> E4
        H5 --> E5
        H5 --> E6

        H1 --> StateMgr
        H2 --> StateMgr
        H3 --> StateMgr
        H4 --> StateMgr
        H5 --> StateMgr
    end
```

#### 事件类型定义

```python
from enum import Enum
from dataclasses import dataclass
from vnpy.event import EventEngine, Event

class FactorEventType(Enum):
    """因子事件类型"""
    FACTOR_GENERATED = "eFactorGenerated"      # LLM 生成了新因子
    FACTOR_PASSED_AST = "eFactorPassedAST"     # 通过 AST 检查
    FACTOR_BACKTEST_DONE = "eFactorBacktest"   # 回测完成
    FACTOR_IC_UPDATE = "eFactorIC"             # IC 更新
    FACTOR_FAILED = "eFactorFailed"            # 因子失败
    FACTOR_APPROVED = "eFactorApproved"        # 因子入库

@dataclass
class FactorEventData:
    """因子事件数据"""
    factor_id: str
    factor_code: str
    factor_name: str
    direction: str           # 研究方向
    ic_value: float = 0.0
    sharpe_ratio: float = 0.0
    error_msg: str = ""
    metadata: dict = None
```

---

### 模块五：回测引擎层 (Backtesting Engine Layer)

#### 职责
因子计算与策略回测，支持快速验证和完整回测两种模式。

#### 子模块结构

```mermaid
flowchart TB
    subgraph M5["模块五：回测引擎层"]
        direction TB

        subgraph M5_Config["配置管理"]
            BacktestConfig["BacktestConfig<br/>回测配置"]
            StrategyConfig["StrategyConfig<br/>策略配置"]
        end

        subgraph M5_Engine["回测引擎"]
            FactorEngine["FactorBacktestEngine<br/>因子回测引擎"]
            VNPYEngine["VNPYBacktestEngine<br/>VNPY 回测引擎"]
        end

        subgraph M5_Modes["回测模式"]
            Inline["InlineBacktest<br/>快速验证模式"]
            Full["FullBacktest<br/>完整回测模式"]
        end

        subgraph M5_Components["核心组件"]
            DataLoader["DataLoader<br/>数据加载"]
            FactorCalc["FactorCalculator<br/>因子计算"]
            StrategyGen["FactorStrategyGenerator<br/>策略生成器"]
            ICCalc["ICCalculator<br/>IC 计算"]
            Metrics["MetricsCalculator<br/>指标计算"]
        end

        subgraph M5_Results["结果输出"]
            Results["BacktestResults<br/>回测结果"]
            Reports["ReportGenerator<br/>报告生成"]
            Visualization["ResultVisualizer<br/>可视化"]
        end

        BacktestConfig --> FactorEngine
        StrategyConfig --> StrategyGen

        FactorEngine --> Inline
        FactorEngine --> Full

        Inline --> DataLoader
        Inline --> FactorCalc
        Inline --> ICCalc

        Full --> VNPYEngine
        VNPYEngine --> DataLoader
        VNPYEngine --> StrategyGen
        StrategyGen --> FactorCalc
        VNPYEngine --> Metrics

        Inline --> Results
        Full --> Results
        Results --> Reports
        Results --> Visualization
    end
```

#### 双模式对比

| 特性 | Inline 回测 | Full 回测 |
|------|------------|-----------|
| **用途** | 挖矿时快速验证 | 最终评估 |
| **周期** | 有限周期（如最近1年） | 完整历史 |
| **速度** | 快（秒级） | 慢（分钟级） |
| **指标** | IC/Rank IC | IC + 策略收益 + 风险指标 |
| **技术** | Polars 直接计算 | VNPY BacktestingEngine |

#### 动态策略生成

```python
class FactorStrategyGenerator:
    """根据因子代码动态生成 VNPY 策略"""

    def generate(self, factor_code: str) -> Type[CtaTemplate]:
        """生成策略类"""

        class FactorStrategy(CtaTemplate):
            author = "FactorMining"
            factor_code = factor_code

            def on_bar(self, bar):
                # 计算因子信号
                signal = self._evaluate_factor(bar)

                # 交易逻辑
                if signal > 0.02 and self.pos == 0:
                    self.buy(bar.close_price * 1.01, 100)
                elif signal < -0.02 and self.pos > 0:
                    self.sell(bar.close_price * 0.99, abs(self.pos))

        return FactorStrategy
```

---

### 模块六：Bandit 资源调度层 (Bandit Resource Scheduling Layer)

#### 职责
智能分配计算资源，优化探索效率，实现早停机制。

#### 子模块结构

```mermaid
flowchart TB
    subgraph M6["模块六：Bandit 资源调度层"]
        direction TB

        subgraph M6_Core["核心调度"]
            Scheduler["BanditScheduler<br/>Bandit 调度器"]
            TrajectoryPool["TrajectoryPool<br/>轨迹池"]
        end

        subgraph M6_Selection["选择策略"]
            UCB["UCBSelector<br/>UCB1 选择器"]
            Thompson["ThompsonSampler<br/>Thompson 采样"]
            Epsilon["EpsilonGreedy<br/>ε-贪婪"]
        end

        subgraph M6_Tracking["轨迹跟踪"]
            Trajectory["StrategyTrajectory<br/>策略轨迹"]
            RewardCalc["RewardCalculator<br/>奖励计算"]
            Stats["TrajectoryStats<br/>轨迹统计"]
        end

        subgraph M6_EarlyStop["早停机制"]
            Monitor["EarlyStopMonitor<br/>早停监控"]
            ICDecay["ICDecayDetector<br/>IC 下降检测"]
            ICThreshold["ICThresholdChecker<br/>阈值检查"]
            Window["SlidingWindow<br/>滑动窗口"]
        end

        subgraph M6_Fix["局部修正"]
            LocalFix["LocalFixer<br/>局部修正器"]
            ErrorParser["ErrorContextParser<br/>错误解析"]
            CodePatch["CodePatcher<br/>代码补丁"]
        end

        Scheduler --> TrajectoryPool
        Scheduler --> UCB
        Scheduler --> Thompson
        Scheduler --> Epsilon

        UCB --> Trajectory
        Trajectory --> RewardCalc
        Trajectory --> Stats

        Stats --> Monitor
        Monitor --> ICDecay
        Monitor --> ICThreshold
        Monitor --> Window

        Monitor -->|早停| LocalFix
        LocalFix --> ErrorParser
        LocalFix --> CodePatch

        Monitor -->|继续| Output["继续探索"]
        LocalFix --> Output
    end
```

#### 核心算法

```python
import numpy as np
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class Trajectory:
    """策略轨迹"""
    direction: str           # 研究方向
    params: Dict             # 参数配置
    n_pulls: int = 0         # 尝试次数
    total_reward: float = 0.0 # 累计奖励
    ic_history: List[float] = None  # IC 历史

    @property
    def avg_reward(self) -> float:
        return self.total_reward / max(self.n_pulls, 1)

    def ucb_score(self, total_trials: int, c: float = 1.414) -> float:
        """UCB1 公式"""
        if self.n_pulls == 0:
            return float('inf')
        exploitation = self.avg_reward
        exploration = c * np.sqrt(np.log(total_trials) / self.n_pulls)
        return exploitation + exploration

class BanditScheduler:
    """Bandit 资源调度器"""

    def __init__(self, directions: List[str], c: float = 1.414):
        self.trajectories = {
            d: Trajectory(direction=d, params={}, ic_history=[])
            for d in directions
        }
        self.total_trials = 0
        self.c = c

    def select_direction(self) -> str:
        """UCB 选择最有希望的方向"""
        scores = {
            name: traj.ucb_score(self.total_trials, self.c)
            for name, traj in self.trajectories.items()
        }
        return max(scores, key=scores.get)

    def update(self, direction: str, ic: float):
        """更新轨迹奖励"""
        traj = self.trajectories[direction]
        traj.n_pulls += 1
        traj.total_reward += ic
        traj.ic_history.append(ic)
        self.total_trials += 1

    def should_early_stop(self, direction: str,
                         window: int = 3,
                         threshold: float = 0.02) -> bool:
        """早停检查"""
        traj = self.trajectories[direction]
        if len(traj.ic_history) < window:
            return False

        recent_ics = traj.ic_history[-window:]
        # IC 持续下降
        decreasing = all(recent_ics[i] > recent_ics[i+1]
                         for i in range(len(recent_ics)-1))
        # IC 始终低于阈值
        always_low = all(ic < threshold for ic in recent_ics)

        return decreasing or always_low
```

#### 早停配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `window` | 3 | IC 监控窗口大小 |
| `threshold` | 0.02 | IC 低阈值 |
| `c` | 1.414 | UCB 探索参数 |

---

### 模块七：三级缓存与经验库层 (Caching & Experience Layer)

#### 职责
最大化复用，避免重复计算，积累成功/失败经验。

#### 子模块结构

```mermaid
flowchart TB
    subgraph M7["模块七：三级缓存与经验库层"]
        direction TB

        subgraph M7_L1["L1: 代码级 RAG"]
            L1_Manager["FactorLibraryManager<br/>因子库管理器"]
            L1_Vector["VectorIndex<br/>向量索引"]
            L1_Similarity["SimilarityChecker<br/>相似度检查"]
            L1_Blocker["DuplicateBlocker<br/>重复拦截器"]
        end

        subgraph M7_L2["L2: 表达式缓存"]
            L2_Cache["ExpressionCache<br/>表达式缓存"]
            L2_Compile["CompiledExprCache<br/>编译表达式缓存"]
            L2_Result["ResultCache<br/>计算结果缓存"]
        end

        subgraph M7_L3["L3: 数据缓存"]
            L3_Lazy["LazyFrameCache<br/>Polars 懒加载缓存"]
            L3_Parquet["ParquetCache<br/>Parquet 文件缓存"]
            L3_Memory["MemoryCache<br/>内存缓存"]
        end

        subgraph M7_Library["经验库"]
            SuccessLib["SuccessFactorLibrary<br/>成功因子库"]
            FailLib["FailureFactorLibrary<br/>失败因子库"]
            Metadata["FactorMetadata<br/>因子元数据"]
        end

        subgraph M7_Storage["存储"]
            JSON["JSON Storage<br/>因子定义"]
            HDF5["HDF5 Storage<br/>因子值"]
            Pickle["Pickle Cache<br/>中间结果"]
        end

        Input["因子候选"] --> L1_Manager
        L1_Manager --> L1_Vector
        L1_Vector --> L1_Similarity
        L1_Similarity -->|相似度>0.9| L1_Blocker
        L1_Blocker --> Reject["拦截重复"]

        L1_Manager -->|通过| L2_Cache
        L2_Cache --> L2_Compile
        L2_Compile --> L2_Result

        L2_Cache --> L3_Lazy
        L3_Lazy --> L3_Parquet
        L3_Parquet --> L3_Memory

        L2_Result --> SuccessLib
        L2_Result --> FailLib
        SuccessLib --> Metadata
        FailLib --> Metadata

        SuccessLib --> JSON
        SuccessLib --> HDF5
        L2_Result --> Pickle
    end
```

#### 缓存层级对比

| 层级 | 类型 | 技术 | 作用 | 命中率目标 |
|------|------|------|------|-----------|
| **L1** | 代码级 RAG | FactorLibraryManager + Faiss | 避免重复失败因子 | 60%-80% |
| **L2** | 表达式缓存 | LRU Cache + 编译缓存 | 中间计算结果复用 | 70%-90% |
| **L3** | 数据缓存 | Polars LazyFrame + Parquet | 内存占用优化 | 80%-95% |

#### 经验库结构

```python
# 成功因子库示例
{
    "factor_id": "f_20240309_001",
    "factor_name": "Momentum_5D",
    "expression": "ts_delay(close, 5) / close - 1",
    "category": "momentum",
    "ic_mean": 0.045,
    "ic_ir": 0.35,
    "sharpe_ratio": 1.2,
    "created_at": "2024-03-09T10:30:00",
    "metadata": {
        "direction": "momentum",
        "complexity_score": 0.3,
        "stability": "high"
    }
}

# 失败因子库示例
{
    "factor_id": "f_20240309_002",
    "expression": "ts_mean(close, 500) / close",
    "failure_reason": "IC consistently below threshold",
    "ic_history": [0.01, 0.005, -0.002],
    "error_type": "low_predictive_power",
    "created_at": "2024-03-09T10:35:00"
}
```

---

## 模块间交互流程

### 完整因子挖掘流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant M1 as 模块一<br/>LLM生成
    participant M2 as 模块二<br/>质量门控
    participant M7 as 模块七<br/>缓存检查
    participant M4 as 模块四<br/>事件调度
    participant M6 as 模块六<br/>Bandit调度
    participant M3 as 模块三<br/>数据适配
    participant M5 as 模块五<br/>回测引擎
    participant VN as VNPY

    User->>M1: 输入研究方向
    M1->>M1: Few-Shot检索
    M1->>M1: 模型路由生成代码
    M1->>M2: 提交因子候选

    M2->>M2: 硬规则检查
    M2->>M2: 一致性检查
    M2->>M2: 复杂度检查
    M2->>M2: 冗余性检查
    M2->>M7: L1相似度检查
    M7-->>M2: 返回检查结果

    M2->>M4: 发布 FACTOR_GENERATED
    M4->>M4: AST检查
    M4->>M6: 发布 FACTOR_PASSED_AST

    M6->>M6: UCB选择方向
    M6->>M3: 请求数据
    M3->>VN: 加载历史数据
    VN-->>M3: 返回 BarData
    M3-->>M5: 提供数据

    M5->>M5: Inline快速回测
    M5->>M4: 发布 FACTOR_BACKTEST_DONE
    M4->>M6: 发布 FACTOR_IC_UPDATE

    M6->>M6: 早停检查
    alt IC持续下降或<阈值
        M6->>M6: 局部修正
        M6->>M1: 反馈修正
    else 继续探索
        M6->>M5: 请求完整回测
        M5->>VN: VNPY完整回测
        VN-->>M5: 返回结果
        M5->>M7: 存入因子库
    end
```

---

## 技术栈汇总

| 模块 | 核心技术 | 开源依赖 |
|------|---------|---------|
| 模块一 | LLM 路由、向量检索 | openai, faiss-cpu, chromadb |
| 模块二 | AST 分析、语义检查 | ast, tree-sitter |
| 模块三 | 数据适配、懒加载 | polars, pyarrow |
| 模块四 | 事件驱动 | vnpy.event |
| 模块五 | 回测引擎 | vnpy, backtesting |
| 模块六 | Bandit 算法 | 自研 / optuna |
| 模块七 | 缓存、向量库 | faiss, redis(可选) |

---

## 部署架构

```mermaid
flowchart TB
    subgraph Local["本地部署"]
        subgraph Compute["计算层"]
            Mining["因子挖掘服务<br/>Python"]
            Backtest["回测服务<br/>VNPY"]
        end

        subgraph Storage["存储层"]
            Parquet["Parquet 数据"]
            SQLite["SQLite 元数据"]
            VectorDB["Faiss 向量库"]
        end

        subgraph Cache["缓存层"]
            Memory["内存缓存"]
            Disk["磁盘缓存"]
        end

        subgraph External["外部服务"]
            LLM["LLM API<br/>OpenAI/GLM"]
            DataAPI["数据 API<br/>TuShare"]
        end

        Mining --> Backtest
        Mining --> VectorDB
        Mining --> LLM
        Backtest --> Parquet
        Backtest --> SQLite
        Mining --> Cache
        Backtest --> Cache
        DataAPI --> Parquet
    end

    subgraph Gateway["交易网关"]
        CTP["CTP 期货"]
        XTP["XTP 股票"]
        IB["Interactive Brokers"]
    end

    Backtest -.->|实盘信号| Gateway
```

---

## 总结

本架构设计采用 7 大模块分层架构，实现：

1. **模块化**：各模块职责清晰，便于独立开发和测试
2. **可扩展**：事件驱动架构支持灵活扩展新功能
3. **高性能**：三级缓存 + Bandit 调度优化资源利用
4. **可落地**：基于 VNPY 成熟框架，支持实盘交易

后续开发建议按模块优先级逐步实现：
1. P0：模块三（数据）、模块四（事件）、模块五（回测）
2. P1：模块一（LLM）、模块二（门控）
3. P2：模块六（Bandit）、模块七（缓存）
