# QuantaAlpha 因子挖掘完整流程图（整合版）

## 关键依赖仓库

| 仓库 | 用途 | GitHub URL |
|------|------|------------|
| QuantaAlpha | 本项目：LLM 驱动的因子挖掘系统 | https://github.com/QuantaAlpha/QuantaAlpha |
| Qlib | 量化投资平台，提供因子回测框架 | https://github.com/microsoft/qlib |
| TuShare | 金融数据接口 | https://github.com/waditu/tushare |
| vnpy | 量化交易平台框架 | https://github.com/vnpy/vnpy |
| Polars | 高性能数据处理库 | https://github.com/pola-rs/polars |
| Pandas | 数据分析库 | https://github.com/pandas-dev/pandas |
| PyArrow | 列式存储库，支持 HDF5/Parquet | https://github.com/apache/arrow |

## 整体系统架构
```mermaid
flowchart TB
    subgraph Input["1. 输入层"]
        direction TB
        ResearchDirection["研究方向输入<br/>自然语言描述<br/>e.g., 'Price-Volume Factor Mining'"]
        PaperInput["论文/PDF 输入<br/>学术文献<br/>arXiv/SSRN/CNKI"]
    end

    subgraph PaperExtract["论文知识提取<br/>load_and_process_pdfs()"]
        direction TB
        PDFLoad["PDF 加载<br/>LangChain 文档处理"]
        ReportClassify["报告分类<br/>classify_report_from_dict()"]
        FactorNameExtract["提取因子名称<br/>__extract_factors_name_and_desc()"]
        FactorFormulaExtract["提取因子公式<br/>__extract_factor_formulation()"]
        FactorLibraryFromPaper["因子库<br/>FactorExperimentLoaderFromDict"]
        
        PDFLoad --> ReportClassify --> FactorNameExtract --> FactorFormulaExtract --> FactorLibraryFromPaper
    end

    subgraph Planning["2. 多样化规划初始化<br/>Diversified Planning"]
        direction TB
        PlanningLLM["LLM 规划器<br/>generate_parallel_directions()"]
        DirectionPool["方向池<br/>Direction 1, 2, ..., N<br/>并行探索路径"]
        PlanningLLM --> DirectionPool
    end

    subgraph Evolution["3. 轨迹级自进化循环<br/>Trajectory-Level Evolution"]
        direction TB
        
        subgraph Trajectory["单个轨迹进化<br/>evolve_single_trajectory()"]
            direction TB
            
            subgraph HypothesisGen["3.1 假设生成阶段<br/>AlphaAgentLoop.factor_propose()"]
                Hypothesis["因子假设<br/>{name, description,<br/>formulation, expression}"]
            end
            
            subgraph CodeTrans["3.2 代码转换阶段<br/>AlphaAgentLoop.factor_construct()"]
                Translation["假设→代码转换<br/>生成 Qlib 兼容表达式"]
            end
            
            subgraph QualityGate["3.3 质量门控三层检查<br/>FactorQualityGate.check()"]
                direction TB
                
                subgraph Consistency["一致性检查<br/>consistency_checker.py"]
                    CC1["假设 ↔ 描述<br/>语义对齐"]
                    CC2["描述 ↔ 公式<br/>逻辑一致性"]
                    CC3["公式 ↔ 表达式<br/>代码正确性"]
                    CCCorrection["LLM 自动修正<br/>最大 3 次重试"]
                    CC1 --> CC2 --> CC3 --> CCCorrection
                end
                
                subgraph Complexity["复杂度检查<br/>complexity_checker.py"]
                    CX1["符号长度 ≤ 250"]
                    CX2["基础特征数 ≤ 6"]
                    CX3["自由参数比例 ≤ 0.5"]
                    CX1 --> CX2 --> CX3
                end
                
                subgraph Redundancy["冗余性检查<br/>redundancy_checker.py"]
                    CR1["因子动物园比对<br/>Similarity Analysis"]
                    CR2["相似因子数量 < 5"]
                    CR1 --> CR2
                end
            end
            
            subgraph Validation["3.4 验证阶段<br/>AlphaAgentLoop.factor_backtest()"]
                Compute["因子计算<br/>CustomFactorCalculator<br/>daily_pv.h5"]
                InlineTest["内联回测<br/>InlineBacktest"]
                Metrics["性能指标<br/>IC / RankIC / 夏普 / 回撤"]
                PerformanceCheck{"IC ≥ 阈值？"}
                
                Compute --> InlineTest --> Metrics --> PerformanceCheck
            end
            
            subgraph FeedbackLoop["3.5 反馈进化阶段<br/>AlphaAgentLoop.feedback()"]
                Feedback["性能反馈<br/>{因子弱点，优化建议}"]
                EvolveDecision{"收敛判断<br/>迭代次数 < Max?"}
                Feedback --> EvolveDecision
            end
            
            %% 内部流程连接
            Hypothesis --> Translation
            Translation --> QualityGate
            
            %% 成功路径指向具体节点 Compute
            CCCorrection -->|通过 | Compute
            CX3 -->|通过 | Compute
            CR2 -->|通过 | Compute
            
            %% 失败路径指向 Feedback 节点
            CCCorrection -->|失败 | Feedback
            CX1 -->|失败 | Feedback
            CX2 -->|失败 | Feedback
            CX3 -->|失败 | Feedback
            CR2 -->|失败 | Feedback
            
            PerformanceCheck -->|未达标 | Feedback
            PerformanceCheck -->|达标 | Converged["轨迹收敛<br/>✓ 优质因子"]
            EvolveDecision -->|继续进化 | Hypothesis
        end
    end

    subgraph Output["4. 输出层"]
        direction TB
        FactorLibrary["因子库<br/>all_factors_library*.json<br/>FactorLibraryManager"]
        FactorZooNode["因子动物园<br/>Factor Zoo<br/>历史因子比对库"]
    end

    subgraph DataFlow["数据流与缓存"]
        direction TB
        HDF5[("daily_pv.h5<br/>价格成交量数据")]
        QlibData[("Qlib 数据<br/>cn_data")]
        CacheSystem["三级缓存<br/>Inline H5 / MD5 Pickle / Qlib Cache"]
    end

    %% 外部连接关系
    ResearchDirection --> PlanningLLM
    PaperInput --> PDFLoad
    FactorLibraryFromPaper -->|种子因子 | DirectionPool
    
    DirectionPool -->|并行启动 N 个轨迹 | Hypothesis
    
    Converged --> FactorLibrary
    
    CR1 -->|相似度检查 | FactorZooNode
    FactorZooNode -.->|更新相似度阈值 | CR1
    
    HDF5 --> Compute
    QlibData -.-> CacheSystem
    Compute -.-> CacheSystem
```    

---

## 进化策略 vs 传统遗传算法

```mermaid
flowchart LR
    subgraph TraditionalGA["传统遗传算法 GA"]
        direction TB
        Pop["种群初始化<br/>随机基因序列"] --> Cross["交叉操作<br/>Crossover"] 
        Cross --> Mut["变异操作<br/>Mutation"] 
        Mut --> Sel["选择算子<br/>Fitness-based"] 
        Sel --> Pop
    end

    subgraph QuantaAlphaES["QuantaAlpha 进化策略 ES"]
        direction TB
        DP["多样化规划<br/>LLM生成N个方向"] --> LLMH["LLM假设生成<br/>自然语言→数学表达"]
        LLMH --> QG["质量门控<br/>三层检查机制"]
        QG --> PF["性能反馈<br/>IC/RankIC指标"]
        PF --> LE["LLM进化<br/>基于反馈改进"]
        LE --> LLMH
    end

    TraditionalGA -.->|对比| QuantaAlphaES
```

---

## 核心代码映射

| 功能模块 | 文件路径 | 关键类/函数 |
|---------|---------|------------|
| CLI入口 | `run.sh` | 调用 `quantaalpha.cli mine` |
| 挖掘命令 | `quantaalpha/cli.py` | `mine()` 主协调器 |
| 进化循环入口 | `quantaalpha/pipeline/factor_mining.py` | `run_evolution_loop()` |
| 进化控制器 | `quantaalpha/pipeline/evolution/controller.py` | `EvolutionController` |
| 多样化规划 | `quantaalpha/scenario/` | Planning Stage |
| 轨迹进化 | `quantaalpha/` | `evolve_single_trajectory()` |
| 假设生成 | `quantaalpha/` | `AlphaAgentLoop.factor_propose()` |
| 代码转换 | `quantaalpha/` | `AlphaAgentLoop.factor_construct()` |
| 质量门控 | `quantaalpha/factor_quality_gate/` | `FactorQualityGate.check()` |
| 一致性检查 | `quantaalpha/factor_quality_gate/consistency_checker.py` | LLM对齐检查 |
| 复杂度检查 | `quantaalpha/factor_quality_gate/complexity_checker.py` | 符号/特征/参数检查 |
| 冗余性检查 | `quantaalpha/factor_quality_gate/redundancy_checker.py` | 相似度分析 |
| 表达式解析 | `quantaalpha/backtest/custom_factor_calculator.py` | `CustomFactorCalculator` |
| 内联回测 | `quantaalpha/backtest/inline_backtest.py` | `InlineBacktest` |
| 因子库管理 | `quantaalpha/` | `FactorLibraryManager` |

---

## 质量门控阈值配置

| 检查类型 | 指标 | 阈值 | 目的 |
|---------|------|------|------|
| 一致性 | LLM对齐分数 | 通过/失败，3次重试 | 确保语义正确性 |
| 复杂度 | 符号长度 | ≤ 250 | 防止过度复杂的表达式 |
| 复杂度 | 基础特征数量 | ≤ 6 | 限制特征维度 |
| 复杂度 | 自由参数比例 | ≤ 0.5 | 控制参数空间 |
| 冗余性 | 相似因子数量 | < 5 | 避免因子库重复 |

---

## 关键性能指标

| 指标类别 | 指标 | 数值 | 说明 |
|---------|------|------|------|
| 预测能力 | IC (Information Coefficient) | 0.1501 | 与未来收益的相关性 |
| 预测能力 | Rank IC | 0.1465 | 排名IC |
| 策略收益 | 年化超额收益 (ARR) | 27.75% | 相对基准的超额收益 |
| 风险指标 | 最大回撤 (MDD) | 7.98% | 最大资金回撤 |
| 风险调整 | Calmar比率 (CR) | 3.4774 | 收益与风险比率 |

---

## 关键差异：传统GA vs QuantaAlpha ES

| 维度 | 传统遗传算法 | QuantaAlpha进化策略 |
|------|-------------|-------------------|
| **搜索机制** | 随机交叉、变异 | LLM驱动的有针对性改进 |
| **表示方式** | 基因编码（二进制/实数） | 自然语言假设 + 数学表达式 |
| **变异操作** | 随机位翻转/数值扰动 | LLM基于反馈的语义改写 |
| **选择压力** | 适应度函数排序 | 质量门控三层筛选 |
| **并行策略** | 种群并行 | 多轨迹并行进化 |
| **收敛判断** | 代数限制/适应度 plateau | IC阈值 + 迭代次数限制 |
