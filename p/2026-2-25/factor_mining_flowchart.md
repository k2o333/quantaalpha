# QuantaAlpha 因子挖掘流程图

## 1. 整体因子挖掘流程（LLM + 进化策略混合架构）

```mermaid
flowchart TB
    subgraph Input["输入层"]
        ResearchDirection["研究方向输入<br/>e.g., 'Price-Volume Factor Mining'<br/>自然语言描述"]
    end

    subgraph Planning["多样化规划初始化<br/>Diversified Planning"]
        direction TB
        PlanningLLM["LLM规划器<br/>基于研究方向生成N个探索方向"]
        DirectionPool["方向池<br/>Direction 1, 2, ..., N<br/>并行探索路径"]
        PlanningLLM --> DirectionPool
    end

    subgraph Evolution["轨迹级自进化循环<br/>Trajectory-Level Evolution"]
        direction TB
        
        subgraph Trajectory["单个轨迹进化<br/>evolve_single_trajectory()"]
            direction TB
            
            subgraph HypothesisGen["假设生成阶段<br/>LLM驱动构思"]
                Hypothesis["因子假设生成<br/>Factor Hypothesis<br/>{name, description, formulation}"]
            end
            
            subgraph CodeTrans["代码转换阶段<br/>hypothesis_code_translator"]
                Translation["假设→代码转换<br/>生成数学表达式"]
            end
            
            subgraph QualityGate["三层质量门控<br/>FactorQualityGate.check"]
                direction TB
                Consistency["一致性检查<br/>consistency_checker.py"]
                Complexity["复杂度检查<br/>complexity_checker.py"]
                Redundancy["冗余性检查<br/>redundancy_checker.py"]
                
                Consistency -->|语义对齐<br/>3次重试机制| Complexity
                Complexity -->|符号长度≤250<br/>特征数≤6<br/>参数比例≤0.5| Redundancy
            end
            
            subgraph Validation["验证阶段"]
                Compute["计算因子值<br/>daily_pv.h5<br/>CustomFactorCalculator"]
                InlineTest["内联回测<br/>InlineBacktest<br/>计算IC/RankIC"]
                PerformanceCheck{"性能评估<br/>IC ≥ 阈值?"}
                
                Compute --> InlineTest
                InlineTest --> PerformanceCheck
            end
            
            subgraph FeedbackLoop["反馈进化阶段"]
                Feedback["性能反馈<br/>{IC, RankIC, 改进建议}<br/>返回LLM"]
                EvolveDecision{"收敛判断<br/>迭代次数 < Max?"}
                
                Feedback --> EvolveDecision
            end
            
            Hypothesis --> Translation
            Translation --> QualityGate
            QualityGate -->|通过| Compute
            QualityGate -->|失败| Feedback
            PerformanceCheck -->|未达标| Feedback
            PerformanceCheck -->|达标| Converged["轨迹收敛<br/>✓ 优质因子"]
            EvolveDecision -->|继续进化| Hypothesis
        end
    end

    subgraph Output["输出层"]
        FactorLibrary["因子库<br/>all_factors_library*.json<br/>已验证因子集合"]
        FactorZoo["因子动物园<br/>Factor Zoo<br/>历史因子比对库"]
    end

    ResearchDirection --> Planning
    DirectionPool -->|并行启动N个轨迹| Trajectory
    Converged --> FactorLibrary
    Redundancy -->|相似度检查| FactorZoo
    FactorZoo -.->|更新相似度阈值| Redundancy
```

---

## 2. 进化策略 vs 传统遗传算法对比

```mermaid
flowchart LR
    subgraph TraditionalGA["传统遗传算法 Genetic Algorithm"]
        direction TB
        Population["种群初始化<br/>随机生成基因序列"]
        Crossover["交叉操作<br/>Crossover"]
        Mutation["变异操作<br/>Mutation"]
        Selection["选择算子<br/>Fitness-based Selection"]
        
        Population --> Crossover
        Crossover --> Mutation
        Mutation --> Selection
        Selection -->|下一代| Population
    end

    subgraph QuantaAlphaES["QuantaAlpha 进化策略 Evolutionary Strategy"]
        direction TB
        DiversifiedPlanning["多样化规划<br/>LLM生成N个方向"]
        LLMHypothesis["LLM假设生成<br/>自然语言→数学表达"]
        QualityGate["质量门控<br/>三层检查机制"]
        PerformanceFeedback["性能反馈<br/>IC/RankIC指标"]
        LLMEvolution["LLM进化<br/>基于反馈改进"]
        
        DiversifiedPlanning --> LLMHypothesis
        LLMHypothesis --> QualityGate
        QualityGate --> PerformanceFeedback
        PerformanceFeedback --> LLMEvolution
        LLMEvolution -->|迭代优化| LLMHypothesis
    end

    TraditionalGA -.->|对比| QuantaAlphaES
```

### 关键差异

| 维度 | 传统遗传算法 | QuantaAlpha进化策略 |
|------|-------------|-------------------|
| **搜索机制** | 随机交叉、变异 | LLM驱动的有针对性改进 |
| **表示方式** | 基因编码（二进制/实数） | 自然语言假设 + 数学表达式 |
| **变异操作** | 随机位翻转/数值扰动 | LLM基于反馈的语义改写 |
| **选择压力** | 适应度函数排序 | 质量门控三层筛选 |
| **并行策略** | 种群并行 | 多轨迹并行进化 |
| **收敛判断** | 代数限制/适应度 plateau | IC阈值 + 迭代次数限制 |

---

## 3. 质量门控详细流程

```mermaid
flowchart TB
    subgraph FactorCandidate["因子候选"]
        Candidate["{hypothesis, description,<br/>formulation, expression}"]
    end

    subgraph QualityGateSystem["质量门控系统<br/>quantaalpha/factor_quality_gate/"]
        Orchestrator["FactorQualityGate<br/>协调器"]
        
        subgraph ConsistencyCheck["一致性检查模块<br/>consistency_checker.py"]
            CC1["假设 ↔ 描述<br/>语义对齐检查"]
            CC2["描述 ↔ 公式<br/>逻辑一致性检查"]
            CC3["公式 ↔ 表达式<br/>代码正确性检查"]
            CCCorrection["LLM自动修正<br/>最大3次重试"]
            
            CC1 --> CC2 --> CC3 --> CCCorrection
        end
        
        subgraph ComplexityCheck["复杂度检查模块<br/>complexity_checker.py"]
            CX1["符号长度检查<br/>阈值: ≤ 250"]
            CX2["基础特征数量<br/>阈值: ≤ 6"]
            CX3["自由参数比例<br/>阈值: ≤ 0.5"]
            
            CX1 --> CX2 --> CX3
        end
        
        subgraph RedundancyCheck["冗余性检查模块<br/>redundancy_checker.py"]
            CR1["因子动物园比对<br/>Similarity Analysis"]
            CR2["重复因子阈值<br/>阈值: < 5个相似因子"]
            
            CR1 --> CR2
        end
    end

    subgraph Decision["决策节点"]
        Accept["✓ 通过<br/>进入回测验证"]
        Reject["✗ 拒绝<br/>返回反馈信息"]
    end

    Candidate --> Orchestrator
    Orchestrator --> ConsistencyCheck
    Orchestrator --> ComplexityCheck
    Orchestrator --> RedundancyCheck
    
    CCCorrection -->|通过| Accept
    CX3 -->|通过| Accept
    CR2 -->|通过| Accept
    
    CCCorrection -->|失败| Reject
    CX1 -->|失败| Reject
    CX2 -->|失败| Reject
    CX3 -->|失败| Reject
    CR2 -->|失败| Reject
```

---

## 4. 数据流与缓存架构

```mermaid
flowchart TB
    subgraph DataSource["数据源"]
        HDF5[("daily_pv.h5<br/>价格成交量数据<br/>398 MB")]
        QlibData[("Qlib数据<br/>cn_data<br/>493 MB")]
    end

    subgraph MiningProcess["因子挖掘过程"]
        ExpressionParser["表达式解析器<br/>CustomFactorCalculator"]
        FactorCompute["因子计算"]
    end

    subgraph CacheSystem["三级缓存系统"]
        InlineCache["内联H5缓存<br/>result.h5<br/>实验级缓存"]
        MD5Cache["MD5 Pickle缓存<br/>pickle_cache_*/<br/>内容寻址缓存"]
        QlibCache["Qlib内部缓存<br/>数据处理器缓存"]
    end

    subgraph OutputData["输出数据"]
        FactorValues["因子值<br/>计算结果"]
        FactorLib[("因子库<br/>all_factors_library*.json")]
        BacktestResults["回测结果<br/>IC/RankIC/收益指标"]
    end

    HDF5 --> ExpressionParser
    ExpressionParser --> FactorCompute
    
    FactorCompute --> InlineCache
    FactorCompute --> MD5Cache
    QlibData --> QlibCache
    
    InlineCache --> FactorValues
    MD5Cache --> FactorValues
    
    FactorValues --> FactorLib
    FactorValues --> BacktestResults
```

---

## 5. 质量门控阈值说明

| 检查类型 | 指标 | 阈值 | 目的 |
|---------|------|------|------|
| 一致性 | LLM对齐分数 | 通过/失败，3次重试 | 确保语义正确性 |
| 复杂度 | 符号长度 | ≤ 250 | 防止过度复杂的表达式 |
| 复杂度 | 基础特征数量 | ≤ 6 | 限制特征维度 |
| 复杂度 | 自由参数比例 | ≤ 0.5 | 控制参数空间 |
| 冗余性 | 相似因子数量 | < 5 | 避免因子库重复 |

---

## 6. 关键性能指标

| 指标类别 | 指标 | 数值 | 说明 |
|---------|------|------|------|
| 预测能力 | IC (Information Coefficient) | 0.1501 | 与未来收益的相关性 |
| 预测能力 | Rank IC | 0.1465 | 排名IC |
| 策略收益 | 年化超额收益 (ARR) | 27.75% | 相对基准的超额收益 |
| 风险指标 | 最大回撤 (MDD) | 7.98% | 最大资金回撤 |
| 风险调整 | Calmar比率 (CR) | 3.4774 | 收益与风险比率 |

---

## 7. 核心代码映射

| 功能模块 | 文件路径 | 关键类/函数 |
|---------|---------|------------|
| CLI入口 | `run.sh` | 调用 `quantaalpha.cli mine` |
| 挖掘命令 | `quantaalpha/cli.py` | `mine()` 主协调器 |
| 多样化规划 | `quantaalpha/scenario/` | Planning Stage |
| 轨迹进化 | `quantaalpha/` | `evolve_single_trajectory()` |
| 假设生成 | `quantaalpha/` | Factor Hypothesis Generation |
| 代码转换 | `quantaalpha/` | `hypothesis_code_translator()` |
| 质量门控 | `quantaalpha/factor_quality_gate/` | `FactorQualityGate.check()` |
| 一致性检查 | `quantaalpha/factor_quality_gate/consistency_checker.py` | LLM对齐检查 |
| 复杂度检查 | `quantaalpha/factor_quality_gate/complexity_checker.py` | 符号/特征/参数检查 |
| 冗余性检查 | `quantaalpha/factor_quality_gate/redundancy_checker.py` | 相似度分析 |
| 表达式解析 | `quantaalpha/backtest/custom_factor_calculator.py` | 因子表达式求值 |
| 内联回测 | `quantaalpha/backtest/inline_backtest.py` | `InlineBacktest` 类 |
| 完整回测 | `quantaalpha/backtest/run_backtest.py` | `run_backtest.py` |
