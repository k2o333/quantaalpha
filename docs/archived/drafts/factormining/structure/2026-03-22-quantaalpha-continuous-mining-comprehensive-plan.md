# QuantaAlpha 持续因子挖掘体系：现状差距与外插结构综合落地规划

## 1. 核心背景与演进定位

基于对 `DECISIONS.md`（包含 ADR-001 和 ADR-003）的研读、QuantaAlpha 主代码库现状分析，以及当前 `/data/*.parquet` 数据资产的审视，本方案旨在将现有的“单次因子挖掘单点工具”，演进升级为**具备多模型协作、多数据维度感知、长效跨周期验证，以及 24 小时自治能力的“持续因子研究体”**。

你所提供的代码级差距分析非常有价值且精准，我们将这份分析与之前规划的 **“因子知识注册”** 及 **“Parquet 适配”** 两大方案进行深度融合，形成这套综合落地结构。

---

## 2. 需求全景打分与差距优先级 (Gap Analysis & Priorities)

结合现状，我们将所有工作按实现复杂度及投入产出比划分为 P0-P3 四个优先级，并给出了精准代码落点。

### [P0] 配置解锁即用层 (Quick Wins)
这些是系统“已经写好了地基，但只需要改配置文件就能立刻产生战略价值”的工作。

1.  **排除北交所股票 (需求 b)**
    *   **落地**：直接修改 `configs/backtest.yaml`，利用已经存在的 `universe.py:22` 功能。
    *   **动作**：将 `exclude_markets: []` 变更为 `exclude_markets: ["bj"]`。
2.  **多时间不连续区间回测 (需求 c)**
    *   **落地**：激活 `validation.py:27-62` 的逻辑，不再依赖单一 `train/valid/test`。
    *   **动作**：在 `configs/backtest.yaml` 开启 `multi_period_validation.enabled: true`，预设牛熊交替的多个不连贯时间段（如 `period_2020_2021`, `period_2023_2024`）。

### [P1] 挖掘核心增强层 (Core Mining Enhancements)
这是真正让 LLM 做到“有的放矢”、“降本增效”的关键改造。

1.  **数据能力感知注入 (Data Capability Injection) (需求 e)**
    *   **现状差距**：`data_capability.py:7-17` 空有框架，未能送达 LLM 提示词。
    *   **融合方案**：打通 `Data Registry` 与 LLM Context。大模型每次下达 prompt 时，强行注入可用 Parquet 数据的 Schema 摘要及字段使用契约（防未来函数时滞约束）。
2.  **多模型智能路由 (Multi-model Routing & Fanout) (需求 a)**
    *   **现状差距**：`client.py` 单线条执行，没有按复杂度路由分配任务，缺少错误自动修复。
    *   **融合方案**：构建 `ProviderPool`：
        *   **生成阶段 (Hypothesis)**：Fanout 给大模型（DeepSeek-R1 / GPT-4）进行头脑风暴。
        *   **格式修复与转写 (Coder)**：路由到微型代码生成模型做 JSON 语法和 AST 纠错。
        *   **初筛与验证**：使用快速廉价模型进行质量打分。

### [P2] 知识沉淀强化层 (Knowledge Asset Retention)
解决因子成为孤岛、无法传递历史演进智慧的问题。

1.  **构建因子库知识流 (Factor Knowledge Library) (需求 d)**
    *   **现状差距**：`library.py` 只能存结果，没有形成“依赖解析图谱”与“演化族谱链”。
    *   **融合方案**：利用 LLM 或 AST 提取器，补全 `_infer_fields` 解析，明确因子对基底数据库（如 `balancesheet_vip` 还是 `moneyflow`）的依赖拓扑。保留变异传承（`parent_trajectory_ids`）以便未来在挖掘发生瓶颈时，能让 LLM 调用 `status_rules` 中评估为 `Active` 的优良因子作为 **Few-shot Examples**。

### [P3] 24H 自治中枢层 (Continuous Operation Orbit)
实现全自动触发，闭环周转。

1.  **持续研究外插模块 (ADR-003 落成) (需求 f)**
    *   **现状差距**：缺乏外置的事件与排队挂载点。
    *   **融合方案**：不污染 `quantaalpha` 原生主链代码，引入轻量级 Orchestrator：
        *   **Trigger**：挂载监听 `app4` 新一天的 `data/*.parquet` 日常更新，并作为事件分发。
        *   **Revalidation Loop**：调用 `library.py:432-485` 的复验逻辑，定期让处于 `Stale` 状态的古老因子重算，淘汰失效者。
        *   **Observability**：收集退出码，对沉默崩溃的挖掘分支告警。

---

## 3. Parquet 数据生态的物理挂载架构设计

结合 `/home/quan/testdata/aspipe_v4/data` 下海量 Parquet 财务及量价数据的现状，采用 **Registry 配置代理 + 底层双轨计算** 的物理结构设计：

### 3.1 Data Capability Registry（统一描述桥梁）
写一个自动化提取器，生成全局 `registry.yaml`：
- 解析出 `income_vip` 及 `moneyflow` 下所有的字段定义。
- **强制时标约束**：标明财务数据的 `ann_date`，作为规则喂给 `llm/client.py` 阻止产生未来函数的逻辑表达式。

### 3.2 回测运算双轨制（Dual-Track Engine）
为了让这些庞大的 Parquet 实际支撑因子逻辑并兼容 Qlib：
*   **保守稳妥路线 (Pipeline Dump)**：
    每天当 `app4` 将新的 parquet 落地后，新增一步清理脚本：用 `dump_bin` 将 `balancesheet_vip` 里的字段（如 `pe_ratio`, `total_assets`）硬转入 Qlib 的二进制目录 `~/.qlib/qlib_data/cn_data`。这能确保兼容一切现存的 `TopkDropoutStrategy` 跑批逻辑。
*   **现代高性能路线 (Polars Engine)**：
    考虑到 Parquet + Polars 的性能碾压级别。不在 Qlib 层面导入原始数据，系统使用 Polars 直接 `scan_parquet`，根据大模型的 AST 公式懒加载计算出每日每股的因子权重 `(date, symbol, factor_val)`。随后，将仅仅带有这一项单值权重的 `.bin` 或单列文件送入 Qlib，让 Qlib 退化为纯粹的回测持仓模拟器。

---

## 4. 实施路线图建议 (Rollout Strategy)

我们可以将复杂的改造分解为三个战役，最小可用闭环步步为营：

*   **⚡ Phase 1: 防御与觉察 (本周目标)**
    1.  批准并采用 ADR-001。
    2.  P0 修改：干涉 `backtest.yaml` 排除北交所，并植入多重历史检验期。
    3.  P1 数据注册：完成初步的 `registry.json`，在 `llm/client.py` 的 system prompt 端把现成的 Parquet 目录能力和频率喂给大模型。
*   **🚀 Phase 2: 分层计算与基因变异 (次周目标)**
    1.  实现 `ProviderPool`：让 API 能多路并行分配。给 `llm/config.py` 瘦身，配置不同阶段的任务处理器。
    2.  Parquet 预处理：落地保守路线（写入 Qlib Bin）以保证数据全量透传。
    3.  强化 `library.py` 的因子存储丰富度（族谱链）。
*   **🔄 Phase 3: 无人值守网络 (长期目标)**
    1.  批准并采用 ADR-003。
    2.  开发独立的 `Orchestrator` 模块和 `observability`，实现因子衰变复用，彻底取代人力每日排插。
