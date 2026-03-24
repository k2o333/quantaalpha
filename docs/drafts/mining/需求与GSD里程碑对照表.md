# 需求与 GSD 里程碑/Slice/Task 对照表

> 生成时间: 2026-03-24（已按 M003 ROADMAP 与各 Slice Summary 复核）
> 数据来源: `.gsd/milestones/M001/`, `.gsd/milestones/M002/`, `.gsd/milestones/M003/`, `.gsd/DECISIONS.md`, `docs/drafts/mining/factor_mining_requirements.md`

---

## 总览

| 需求 | 覆盖状态 | 已完成的 Milestone/Slice | 待完成的 Milestone/Slice |
|------|----------|------------------------|------------------------|
| A. 多模型支持 | ⚠️ 部分完成 | M003 S04, S05 | Ensemble 聚合、least_latency、多 API Key/429 专项处理 |
| B. 排除北交所 | ✅ 已完成 | M003 S03 T01 | — |
| C. 跨周期回测区间 | ✅ 已完成 | M003 S03 T02, T03 | — |
| D. 丰富因子库 | ⚠️ 部分完成 | M003 S02, S06 | 大量缺口，见 §D |
| E. 数据维度感知 | ⚠️ 部分完成 | M003 S01, S07 | 实数仓接入/字段覆盖仍有边界，见 §E |
| F. 24H 自治运行 | ⚠️ 部分完成 | M003 S03, S04, S05, S06, S08, S09, S10 | 72h 无人值守验证、部分外插模块实现 |

---

## 需求 a: 多模型支持

> 不止调用一个模型：大小模型分工、不同模型不同看法、Coding 模型修格式、轮询分担压力

### 需求 a1: 大小模型分工（简单问题交给小模型）

| 层级 | 标识 | 状态 | 说明 |
|------|------|------|------|
| **Decision** | D016 | ✅ 已批准 | ProviderPool 多模型管理架构：摒弃全局单例 APIBackend，引入角色分配的动态路由 |
| **Decision** | D011 | ✅ 已批准 | Phase 2: 分层计算与多模型 |
| **Milestone** | M003 | ⚠️ 主要切片已完成 | Slice 已完成，但里程碑级 DoD 仍有未勾项（见下） |
| **Slice** | M003 S04 | ✅ 已完成 | ProviderPool 核心实现 |
| ├ Task | S04 T01 | ✅ 已完成 | ProviderPool 核心类实现 — 支持 `single`/`round_robin`/`fanout_best` 三种路由策略 |
| ├ Task | S04 T02 | ✅ 已完成 | 配置格式 + 单元测试 — experiment.yaml 中按任务类型分配 Provider |

**配置映射** (`experiment.yaml`):
```yaml
llm.provider_pool:
  providers:
    - name: "deepseek-r1"; role: "hypothesis"; weight: 3    # 大模型
    - name: "gpt4o"; role: "hypothesis"; weight: 2          # 大模型
    - name: "glm4-flash"; role: "screening"; weight: 5      # 小模型（筛选/简单任务）
    - name: "qwen-coder"; role: "json_repair"; weight: 1    # Coding 模型
  routing:
    hypothesis_generation: ["deepseek-r1", "gpt4o"]         # 难题→大模型
    feedback_summarization: "round_robin"                    # 简单任务→轮询
    json_repair: ["qwen-coder"]                              # 格式修复→Coding 模型
```

### 需求 a2: 不同模型对同一问题有不同看法

| 层级 | 标识 | 状态 | 说明 |
|------|------|------|------|
| **Slice** | M003 S04 | ✅ 已完成 | 同上 |
| **策略** | `fanout_best` | ✅ 已实现 | hypothesis_generation 任务并发调用 deepseek-r1 + gpt4o，取最优结果 |

### 需求 a3: Coding 模型修 JSON 格式

| 层级 | 标识 | 状态 | 说明 |
|------|------|------|------|
| **Decision** | D019 | ✅ 已批准 | Coding 模型 JSON 修复必须设置超时和重试上限 |
| **Milestone** | M003 | ⚠️ 主要切片已完成 | Slice 已完成，但里程碑级 DoD 仍有未勾项 |
| **Slice** | M003 S05 | ✅ 已完成 | Coding 模型 JSON 修复闭环 |
| ├ Task | S05 T01 | ✅ 已完成 | `robust_json_parse()` 策略5：规则修复失败后触发 coding 模型修复，30秒超时，最多3次重试 |
| ├ Task | S05 T02 | ✅ 已完成 | 单元测试覆盖正常修复、超时、重试上限、空响应切换 |

**关键约束** (D019):
- `MAX_JSON_REPAIR_ATTEMPTS = 3`
- `JSON_REPAIR_TIMEOUT_SECONDS = 30.0`
- 空响应立即切换 Provider，不增加 failure_count

### 需求 a4: 轮询分担调用压力

| 层级 | 标识 | 状态 | 说明 |
|------|------|------|------|
| **Slice** | M003 S04 | ✅ 已完成 | 同上 |
| **策略** | `round_robin` | ✅ 已实现 | feedback_summarization 任务使用加权轮询 |

**健康降级机制**:
- healthy → degraded (≥3 次失败) → unhealthy (≥5 次失败, 300s 冷却)
- 空响应不增加 failure_count（D019 约束）

### 需求 a 相关的前置依赖

| 层级 | 标识 | 状态 | 说明 |
|------|------|------|------|
| **Milestone** | M001 | ✅ 已完成 | 修复 LLM 空响应、无限重试、JSON 控制字符等阻塞性 Bug |
| ├ Slice | M001 S02 | ✅ 已完成 | 修复无限重试死循环 — `while True` → `for attempt in range(MAX_RETRIES)`，空响应检测 |
| ├ Slice | M001 S03 | ✅ 已完成 | 修复 JSON 控制字符 — `_escape_control_chars_in_json()` 状态机函数 |

---

## 需求 b: 调整回测数据（排除北交所）

| 层级 | 标识 | 状态 | 说明 |
|------|------|------|------|
| **Decision** | D011 | ✅ 已批准 | Phase 1: 配置解锁（排除北交所、多周期回测） |
| **Milestone** | M003 | ⚠️ 主要切片已完成 | Slice 已完成，但里程碑级 DoD 仍有未勾项 |
| **Slice** | M003 S03 | ✅ 已完成 | P0 配置解锁优化 |
| ├ Task | S03 T01 | ✅ 已完成 | 配置股票过滤排除北交所 — `stock_filter.enabled=true`, `exclude_markets=["bj"]` |
| ├ Task | S03 T03 | ✅ 已完成 | 验证 YAML 语法和配置完整性 |

**配置变更** (`backtest.yaml`):
```yaml
data.stock_filter:
  enabled: true
  exclude_markets: ["bj"]    # 排除北交所低流动性股票
  exclude_st: true            # 排除 ST 股票
  min_list_days: 60           # 要求上市≥60天
```

**验证**: 12 项 UAT 测试通过

---

## 需求 c: 调整 training/backtest/validation 数据区间（跨周期验证）

> 不希望只有最近1年，而是中间隔了几年，跨周期有效的因子才会长期稳定有效

| 层级 | 标识 | 状态 | 说明 |
|------|------|------|------|
| **Decision** | D011 | ✅ 已批准 | Phase 1: 多周期回测 |
| **Decision** | D014 | ✅ 已批准 | ADR-001: 多周期验证（五层架构之一） |
| **Milestone** | M003 | ⚠️ 主要切片已完成 | Slice 已完成，但里程碑级 DoD 仍有未勾项 |
| **Slice** | M003 S03 | ✅ 已完成 | P0 配置解锁优化 |
| ├ Task | S03 T02 | ✅ 已完成 | 配置多周期回测验证 — 4 个市场周期 |
| ├ Task | S03 T03 | ✅ 已完成 | 验证 YAML 语法和配置完整性 |

**4 个市场周期** (`backtest.yaml`):

| Period | Train | Valid | Test | 市场环境 |
|--------|-------|-------|------|----------|
| 2017_2018_去杠杆 | 2015-2016 | 2017-H1 | 2017-H2 ~ 2018 | 去杠杆 |
| 2019_2020_结构牛 | 2017-2018 | 2019-H1 | 2019-H2 ~ 2020 | 结构牛 |
| 2021_2022_震荡熊 | 2019-2020 | 2021-H1 | 2021-H2 ~ 2022 | 震荡熊 |
| 2023_2025_复苏 | 2021-2022 | 2023-H1 | 2023-H2 ~ 2025 | 复苏 |

**配置**:
```yaml
multi_period_validation:
  enabled: true
  fail_fast: false    # 运行所有周期，不因单周期失败中断
  periods:
    - name: "2017_2018_去杠杆"
      train: [2015, 2016]
      valid: [2017, "H1"]
      test: ["2017-H2", 2018]
    # ... 共4个周期
```

> 注: 这里记录的是 **GSD S03 实际落地方案**（4 个周期，含 train/valid/test）。
> 原始需求文档 `factor_mining_requirements.md §C.3.1` 给出的只是一个 **3 周期、train/test** 的示例配置。两者在“跨周期验证”目标上一致，但在周期数量和区间划分上并不完全相同。

---

## 需求 d: 丰富因子库功能

> 现有因子对新因子生产没有指导作用；JSON 格式存储因子过于简单

### 已完成部分

| 层级 | 标识 | 状态 | 说明 |
|------|------|------|------|
| **Decision** | D014 | ✅ 已批准 | ADR-001: 因子知识库（五层架构之一） |
| **Decision** | D017 | ✅ 已批准 | 因子库增加 versions 字段保留历史 backtest 结果 |
| **Decision** | D018 | ✅ 已批准 | 因子库条目上限与 SQLite 迁移阈值 |
| **Milestone** | M003 | ⚠️ 主要切片已完成 | Few-shot/versions 等已落地，但知识库深层能力仍缺失 |

**d1. Few-shot 导出（现有因子指导新因子生成）**

| 层级 | 标识 | 状态 | 说明 |
|------|------|------|------|
| **Slice** | M003 S02 | ✅ 已完成 | 因子库 Few-shot 导出与智能采样 |
| ├ Task | S02 T01 | ✅ 已完成 | 创建 `fewshot.py` 模块 — `query_active_factors()` + `render_fewshot_examples()` |
| ├ Task | S02 T02 | ✅ 已完成 | 接入 `prepare_context()` 和 `prompts.yaml` |

**实现细节**:
- `query_active_factors()`: 过滤 `evaluation.status=="active"` 且 `stability_score >= 0.5`
- Relatedness 评分: 70% Jaccard 文本重叠 + 30% 共享数据字段
- Token 预算控制: 默认 2000 tokens (~3-5 个示例)
- 24h JSON 缓存: `~/.cache/quantaalpha/fewshot_cache.json`

**d2. 因子版本历史（保留回测结果演变）**

| 层级 | 标识 | 状态 | 说明 |
|------|------|------|------|
| **Slice** | M003 S06 | ✅ 已完成 | Checkpoint 与幂等性恢复 |
| ├ Task | S06 T02 | ✅ 已完成 | 因子库版本历史与锁超时 — `_normalize_factor_entry()` 添加 `versions: []`，保留最近 10 个版本 |

**因子条目结构**:
```json
{
  "factor_id": "xxx",
  "factor_expression": "RANK(TS_MEAN($close, 20))",
  "evaluation": {"status": "active", "stability_score": 0.72},
  "data_requirements": {"fields": ["close"], "dimensions": ["price_volume"]},
  "versions": [
    {"backtest_results": {...}, "timestamp": "2026-03-23T10:00:00", "experiment_id": "exp_001"}
  ]
}
```

### 待完成部分

| 层级 | 标识 | 状态 | 说明 |
|------|------|------|------|
| **Slice** | M003 S10 T04 | ✅ 设计已完成 | Revalidation Loop: 候选选择策略、触发条件、结果处理已形成设计文档 |
| **M003-ROADMAP** | — | 明确标记 | "Leaves for later: 因子知识库智能推荐、全自动因子复验" |

**S10 T04 Revalidation Loop 设计范围**:
1. 复验候选选择策略（哪些因子需要重新回测）
2. 复验触发条件（时间驱动? 数据更新驱动? 指标下降驱动?）
3. 复验结果处理（更新 status、stability_score、versions）
4. 与 FactorLibrary 集成

**当前缺失的能力**:
- ❌ 因子过期自动检测（如"3周未回测"标记为 stale）
- ❌ 负反馈机制（失败因子指导避免重复挖掘同类）
- ❌ 因子多维度评估（各周期表现、市值分层适用性）
- ❌ 因子库智能推荐（M003-ROADMAP 明确标记为 deferred）

---

## 需求 e: 增加数据维度时 LLM 如何感知

> 比如基本面数据，LLM 如何知道可用因子是不一样的

### 已完成部分

| 层级 | 标识 | 状态 | 说明 |
|------|------|------|------|
| **Decision** | D012 | ✅ 已批准 | Parquet 数据集成与双轨计算架构：Registry 动态扫描 schema 并注入时滞约束 |
| **Decision** | D013 | ✅ 已批准 | PIT 对齐：季度财报等非日频数据按 ann_date 动态对齐 |
| **Milestone** | M003 | ⚠️ 主要切片已完成 | S01/S07 已完成，真实数据装载链路仍属独立问题 |

**e1. 数据能力注册表（LLM 知道有哪些数据可用）**

| 层级 | 标识 | 状态 | 说明 |
|------|------|------|------|
| **Slice** | M003 S01 | ✅ 已完成 | 数据能力注入最后一公里 |
| ├ Task | S01 T01 | ✅ 已完成 | `auto_discover_capabilities()` 动态扫描 24 个 Parquet 子目录 |
| ├ Task | S01 T02 | ✅ 已完成 | `prepare_context()` 中注入 `data_capabilities` |
| ├ Task | S01 T03 | ✅ 已完成 | `prompts.yaml` 添加 Jinja2 占位符 |

**实现细节**:
- 动态扫描 `/data/*/` 下每个子目录的第一个 `.parquet` 文件
- 根据 `ann_date` 存在性推断 `freq`（quarterly vs daily）和 `lag_days`（45 vs 0）
- 24 个数据源: 13 个季度频、11 个日频
- 24h JSON 缓存: `~/.cache/quantaalpha/data_capability_registry.json`

**数据源分类**:

| 类别 | 目录 | lag_days |
|------|------|----------|
| 财务(季度) | balancesheet_vip, cashflow_vip, income_vip, fina_indicator_vip, forecast_vip, fina_audit | 45 |
| 日频 | daily_basic, stk_factor_pro, express_vip, moneyflow | 0 |
| 股东/事件 | top10_holders, top10_floatholders, pledge_stat, repurchase, block_trade | varies |
| 参考 | stock_basic, trade_cal, suspend_d, dividend | N/A |

**注入链路**:
```
auto_discover_capabilities() → render_data_capabilities()
  → proposal.py prepare_context() → prompts.yaml hypothesis_gen.system_prompt
  → LLM 接收数据能力描述 → 生成引用实际数据字段的因子假设
```

### 已完成但仍有边界的部分

| 层级 | 标识 | 状态 | 说明 |
|------|------|------|------|
| **Slice** | M003 S07 | ✅ 已完成 | PIT 对齐执行层 — 消除基本面数据的未来函数 |
| ├ Task | S07 T01 | ✅ 已完成 | `pit_alignment.py` 核心模块和单元测试 |
| ├ Task | S07 T02 | ✅ 已完成 | 将 PIT 对齐集成到因子计算器 |

**S07 目标**: 当 `custom_factor_calculator.py` 评估引用季度财务字段（如 `$roe`）的因子表达式时，自动过滤掉 `ann_date > trade_date - lag_days` 的数据行。

**边界说明**:
- S07 的 **PIT 对齐机制本身已完成**，ROADMAP、PLAN Tasks、Slice Summary 均已对齐为完成状态
- 但 S07 Summary 也明确说明：它目前提供的是 **执行层对齐机制**，真实 Parquet 数据装载路径仍需由 D012 的后续数据链路补齐
- 因此，这里的“部分完成”来自 **端到端数据接入边界**，不是 S07 状态未确认

---

## 需求 f: 24 小时自治运行

> 24小时不间断挖掘、维护因子

| 层级 | 标识 | 状态 | 说明 |
|------|------|------|------|
| **Decision** | D004 | ⚠️ 已被 D015 取代 | D004 原为 draft 评估项，后续由 D015 正式批准并 supersede |
| **Decision** | D010 | ✅ 已批准 | 24H 自治：关键缺失能力 |
| **Decision** | D015 | ✅ 已批准 | ADR-003: 为 24H 运行提供扩展路径 |
| **Decision** | D018 | ✅ 已批准 | 24H 资源管理约束 |
| **Milestone** | M003 | ⚠️ 主要切片已完成 | Slice 已完成，但 72h 无人值守验证和部分里程碑文档同步未完成 |

### 已完成的基础设施

| 层级 | 标识 | 状态 | 说明 |
|------|------|------|------|
| **Slice** | M003 S04 | ✅ 已完成 | ProviderPool — 多 Provider 并存、健康监控、自动降级 |
| **Slice** | M003 S05 | ✅ 已完成 | Coding 模型 JSON 修复闭环 |
| **Slice** | M003 S06 | ✅ 已完成 | Checkpoint 断点续挖 — 进程崩溃后可从检查点恢复 |
| **Slice** | M003 S03 | ✅ 已完成 | 多周期验证 — 4 个市场周期覆盖 2017-2025 |
| **Slice** | M003 S08 | ✅ 已完成 | ResourceManager — Token/磁盘/result.h5/库容量边界约束 |
| **Slice** | M003 S09 | ✅ 已完成 | M001 教训转化为设计约束、回归测试、合规性检查脚本 |
| **Slice** | M003 S10 | ✅ 已完成（设计层） | Orchestrator/Trigger/Observability/Revalidation 设计文档与接口契约 |

### 仍待完成的里程碑级事项

| 层级 | 标识 | 状态 | 说明 |
|------|------|------|------|
| **运行验证** | 72h unattended run | ⏳ 待完成 | ROADMAP DoD 仍未勾选：72 小时无人值守测试通过 |
| **文档同步** | DECISIONS.md sync | ⏳ 待完成 | ROADMAP DoD 仍未勾选：架构文档更新并同步到 DECISIONS.md |
| **实现深度** | ADR-003 Phase 3 modules | ⚠️ 设计完成、实现未完整 | S10 已完成设计文档，但 Orchestrator/Trigger/Observability/Revalidation 仍主要停留在设计层 |

**M003 Definition of Done 当前未完成项**:
- [ ] 72 小时无人值守测试通过
- [ ] 架构文档更新并同步到 DECISIONS.md

**说明**:
- ROADMAP 已将 S08/S09/S10 及对应的 D018、D019、ADR-003 Phase 3 design 标记为完成
- 但 DoD 中 `D016 ProviderPool 架构实现并通过测试` 仍未勾选；这表示 **里程碑级 DoD 与 slice 完成状态存在一个未消解的不一致**
- 因此，本表对 24H 自治运行的判断采用“**基础设施与设计大体完成，但里程碑尚未完全收口**”的保守表述

---

## 需求 g: 每日新增数据驱动因子更新

> 每天都会有新数据，也会有新的数据维度

| 层级 | 标识 | 状态 | 说明 |
|------|------|------|------|
| **Slice** | M003 S10 T02 | ✅ 设计已完成 | Trigger 事件监听 — `docs/design/trigger.md` 已定义 PollingTrigger / WatcherTrigger / 事件去重 |

**当前状态**: S10 已完成 Trigger 设计，但仍缺少可运行实现。需要：
1. 监听 app4 数据管道的数据更新事件
2. 事件分发机制
3. 与 Orchestrator 集成，触发因子回测/复验

---

## 需求 h: 因子过期检测与复验调度

> 一个因子3周没有回测过

| 层级 | 标识 | 状态 | 说明 |
|------|------|------|------|
| **Slice** | M003 S02 | ✅ 已完成 | 因子 `evaluation.status` 支持 `"stale"` 状态 |
| **Slice** | M003 S10 T04 | ✅ 设计已完成 | Revalidation Loop — `docs/design/revalidation.md` 已给出候选选择、状态机、复验策略 |

**当前状态**:
- S02 已定义 `status` 字段支持 `"active"`, `"degraded"`, `"stale"`, `"pending_validation"`，但**没有定义 stale 的判定规则**
- S10 T04 已完成 Revalidation Loop 设计，但 M003-ROADMAP 仍明确标记 "Leaves for later: 全自动因子复验"
- **缺少**: 时间驱动的 staleness 检测规则（如"N周未回测"）、指标下降检测

---

## 前置里程碑（为 M003 奠基）

### M001: QuantaAlpha 关键 Bug 修复 ✅

| Slice | 状态 | 关联需求 |
|-------|------|----------|
| S01: 修复 Logger 参数签名 | ✅ 已完成 | 基础设施 |
| S02: 修复无限重试死循环和空响应检查 | ✅ 已完成 | 需求 a 前置 |
| S03: 修复 JSON 控制字符未转义 | ✅ 已完成 | 需求 a 前置 |
| S04: 运行因子挖掘验证 | ⏳ Pending | — |

### M002: QuantaAlpha 数据类型 Bug 修复 ✅

| Slice | 状态 | 关联需求 |
|-------|------|----------|
| S01: 定位数据类型 Bug 触发位置 | ✅ 已完成 | 基础设施 |
| S02: 实现类型检查与转换逻辑 | ✅ 已完成 | 基础设施 |
| S03: 添加回归测试和文档 | ✅ 已完成 | 基础设施 |

---

## 依赖关系图

```
M001 (Bug修复) ──→ M002 (类型Bug修复) ──→ M003 (架构实施) ──→ M004 (建议)
                                                │
                    ┌───────────────────────────┘
                    │
    Phase 1 (防御与觉察): S01 → S02 → S03
    ├── S01: 数据能力注册表 (需求e)
    ├── S02: Few-shot 导出 (需求d)
    └── S03: 配置解锁 (需求b, c)
                    │
    Phase 2 (分层计算): S04 → S05 → S06 → S07
    ├── S04: ProviderPool (需求a)
    ├── S05: JSON修复闭环 (需求a3)
    ├── S06: Checkpoint + 版本历史 (需求d2, 24H)
    └── S07: PIT 对齐 (需求e)
                    │
    Phase 3 (无人值守): S08 → S09 → S10
    ├── S08: ResourceManager (24H)
    ├── S09: 设计约束转化 (24H)
    └── S10: Orchestrator/Trigger/Observability/Revalidation (24H, 需求g, h)
                    │
    Phase 4 (建议，因子库深化): S11 → S12 → S13 → S14 → S15 → S16 → S17 → S18
    ├── S11: 跨周期验证通过标准 (缺口H) ──── depends: S03 ✅
    ├── S12: 因子重验候选选择 (缺口F) ────── depends: S06 ✅
    ├── S13: 因子分类标签系统 (缺口C) ────── depends: S12
    ├── S14: 数据能力注册表扩展 (缺口G) ──── depends: S01 ✅
    ├── S15: 因子生命周期状态机 (缺口E) ──── depends: S12, S13
    ├── S16: RAG 向量检索 (缺口D) ────────── depends: S02 ✅, S13
    ├── S17: Ensemble 聚合层 (缺口A, B) ──── depends: S04 ✅
    └── S18: 24H 调度中心 (缺口I, J) ─────── depends: S08, S10, S12, S16
```

---

---

## 缺口总览：factor_mining_requirements.md 中未被 GSD 覆盖的需求

以下内容来自 `docs/drafts/mining/factor_mining_requirements.md` 的逐项对标，列出 GSD 文档中**没有规划、没有实现、或设计不充分**的需求点。

---

### 缺口 A: 多视角融合（Ensemble）完整架构

> 来源: factor_mining_requirements.md §A.3.2

GSD 中 S04 实现了 `fanout_best`（并发取最优），但 factor_mining_requirements.md 描述了更完整的 Ensemble 架构：

| 子需求 | GSD 现状 | 缺口说明 |
|--------|----------|----------|
| 裁判模型汇总 | ❌ 无 | S04 `fanout_best` 取评分最高的单个结果，**没有裁判模型汇总多个模型输出** |
| 取交集策略（保守） | ❌ 无 | GSD 仅支持 `single`/`round_robin`/`fanout_best`，无交集策略 |
| 取并集后去重 | ❌ 无 | 无并集+去重策略 |
| 投票机制 | ❌ 无 | 无多模型投票聚合 |
| 融合评分 | ❌ 无 | 无多模型输出融合评分机制 |

**factor_mining_requirements.md 描述的流程**:
```
同一 Prompt → GPT-4 ──┐
            → Claude ──┤──▶ 裁判模型 ──▶ 最终因子
            → Qwen ────┘     │
                          汇总策略:
                          - 取交集（保守）
                          - 取并集后去重
                          - 投票机制
                          - 融合评分
```

**GSD 现有实现**: `fanout_best` 并发调用多个 Provider 但只取**单个最优结果**，无裁判模型、无聚合策略。

**需要的操作**: 在 S04 ProviderPool 基础上新增 Ensemble 聚合层，或在 M004 中规划独立 Slice。

---

### 缺口 B: 平台轮询的 `least_latency` 策略

> 来源: factor_mining_requirements.md §A.3.4

| 子需求 | GSD 现状 | 缺口说明 |
|--------|----------|----------|
| `least_latency` 策略 | ❌ 无 | GSD 仅支持 `single`/`round_robin`/`fanout_best` |
| 多 API Key 同 Provider | ⚠️ 未明确 | GSD 的 Provider 定义中每个 provider 只有一个 api_key 字段 |
| `retry_on_429` 限流处理 | ⚠️ 未明确 | GSD 健康机制处理通用失败，未专门处理 429 限流 |

**factor_mining_requirements.md 描述的配置**:
```yaml
llm:
  api_pool:
    - provider: "openai"
      api_keys: ["sk-xxx1", "sk-xxx2"]    # 同一 provider 多 key
    - provider: "deepseek"
      api_keys: ["sk-deepseek-1"]
  load_balance:
    strategy: "least_latency"              # 延迟最低优先
    retry_on_429: true
```

**需要的操作**: 扩展 ProviderPool 的路由策略，支持同 Provider 多 Key 轮询和 `least_latency` 策略。

---

### 缺口 C: 因子分类标签系统

> 来源: factor_mining_requirements.md §D.3.1

| 字段 | GSD 现状 | 缺口说明 |
|------|----------|----------|
| `tags.category` (momentum/reversal/value/quality/liquidity) | ❌ 无 | 因子条目无分类标签 |
| `tags.data_dependency` (price_volume/financial/alternative) | ❌ 无 | 仅有 `data_requirements.fields` 和 `dimensions`，无分类标签 |
| `tags.market_environment` (bull/bear/sideways/high_vol) | ❌ 无 | 无市场环境适用性标签 |
| `tags.time_horizon` (short_term/intraday) | ❌ 无 | 无时间维度标签 |

**factor_mining_requirements.md 描述的结构**:
```json
{
  "factor_id": "xxx",
  "tags": {
    "category": ["momentum", "reversal"],
    "data_dependency": ["price_volume"],
    "market_environment": ["bull", "volatile"],
    "time_horizon": ["short_term", "intraday"]
  }
}
```

**GSD 现有因子条目**: 只有 `evaluation.status` + `stability_score`，无任何分类标签。

**需要的操作**: 扩展 `library.py` 的 `_normalize_factor_entry()` 添加 `tags` 字段；扩展 fewshot.py 的 relatedness 评分支持标签匹配。

---

### 缺口 D: RAG 向量检索架构

> 来源: factor_mining_requirements.md §D.3.2, §D.3.3

| 子需求 | GSD 现状 | 缺口说明 |
|--------|----------|----------|
| 向量数据库存储因子 embedding | ❌ 无 | GSD 仅用 JSON 文件存储因子 |
| 向量相似度检索优秀因子 | ❌ 无 | S02 fewshot.py 用 Jaccard 文本重叠，无向量检索 |
| "总结共性，演绎新因子" 的 Prompt 模式 | ❌ 无 | S02 仅导出因子表达式为 few-shot 示例，无共性总结 |
| 向量库技术选型 (ChromaDB/sqlite-vss/Milvus) | ❌ 无 | GSD 无任何向量库规划 |

**factor_mining_requirements.md 描述的流程**:
```
1. 查询向量库: SELECT * FROM factors WHERE embedding ~ query_embedding ORDER BY ic DESC LIMIT 5
2. 构建 Few-Shot Prompt: "以下是当前周期表现优秀的因子范式...请总结共性，演绎新因子"
3. LLM 生成新因子
```

**GSD 现有实现**: S02 `fewshot.py` 用文本重叠+共享字段做 relatedness 评分，导出因子表达式为 JSON 示例。**无 embedding、无向量检索、无共性总结 prompt。**

**需要的操作**: 新增向量检索模块（推荐 ChromaDB 作为轻量方案），将因子表达式+元数据编码为 embedding，替换或增强 S02 的 relatedness 评分。

---

### 缺口 E: 因子生命周期 `seasonal` / `archived` 状态

> 来源: factor_mining_requirements.md §D.3.4, §C.3.2

| 状态 | GSD 现状 | 缺口说明 |
|------|----------|----------|
| `pending` → `active` | ✅ 已有 | S02 定义 |
| `active` → `degraded` | ✅ 已有 | S02 定义 |
| `active` ↔ `degraded` 恢复 | ⚠️ 未明确 | GSD 无 degraded→active 恢复规则 |
| `active` → `seasonal` | ❌ 无 | factor_mining_requirements.md 定义：大部分周期通过时标记为 seasonal + 标记有效周期 |
| `degraded` → `archived` | ❌ 无 | factor_mining_requirements.md 定义：长期失效时归档 |
| `archived` → 重新激活 | ❌ 无 | 无归档因子恢复机制 |
| **状态转换触发规则** | ❌ 无 | GSD 仅定义状态名，**无转换条件逻辑** |

**factor_mining_requirements.md 定义的状态机**:
```
所有周期通过 ──────▶ stable_active (稳定有效)
大部分周期通过 ─────▶ seasonal (特定环境有效) + 标记有效周期
少数周期通过 ───────▶ degraded (效果衰减)
全部周期失败 ───────▶ archived (归档废弃)
```

**需要的操作**: 在 `library.py` 或新增 `status_rules.py` 中实现完整状态机，新增 `seasonal`/`archived` 状态及转换规则。

---

### 缺口 F: 因子重验的 `select_revalidation_candidates(days=21)` 实现

> 来源: factor_mining_requirements.md §F.3.1

| 子需求 | GSD 现状 | 缺口说明 |
|--------|----------|----------|
| `select_revalidation_candidates(days=21, status="active")` | ❌ 无 | GSD S10 T04 仅设计阶段，无此函数 |
| 按天数筛选未验证因子 | ❌ 无 | 因子条目无 `last_validated` 时间戳字段（或未使用） |
| 自动触发回测 | ❌ 无 | 无自动化触发链路 |
| 结果自动更新因子状态 | ⚠️ 部分 | `apply_validation_result()` 已存在但未被自动调用 |

**factor_mining_requirements.md 描述的流程**:
```python
def run_maintenance():
    manager = FactorLibraryManager(library_path)
    candidates = manager.select_revalidation_candidates(days=21, status="active")
    for factor in candidates:
        result = backtest_factor(factor, latest_data_period)
        manager.apply_validation_result(factor_entry=factor, validation_result=result)
```

**需要的操作**: 新增 `select_revalidation_candidates()` 方法到 `FactorLibraryManager`，在 S10 T04 Revalidation Loop 设计中明确实现。

---

### 缺口 G: 数据能力注册表 `available_from` 和 `join_mode` 字段

> 来源: factor_mining_requirements.md §E.3.1

| 字段 | GSD S01 现状 | 缺口说明 |
|------|-------------|----------|
| `available_from` (数据起始日期) | ❌ 无 | S01 注册表只有 fields/freq/lag_days/factor_hints |
| `join_mode` (same_day / forward_fill) | ❌ 无 | S01 无 join 模式定义 |

**factor_mining_requirements.md 描述的结构**:
```python
"financial": {
    "fields": ["$roa", "$roe", "$net_profit_margin", "$debt_ratio"],
    "freq": "quarterly",
    "lag_days": 45,
    "join_mode": "forward_fill",       # 缺失
    "factor_hints": ["quality", "value"],
    "available_from": "2012-01-01",    # 缺失
}
```

**需要的操作**: 扩展 S01 `auto_discover_capabilities()` 的返回结构，添加 `available_from`（从 Parquet 文件时间推断）和 `join_mode`（根据 freq 推断）。

---

### 缺口 H: 跨周期验证的 `require_all_pass` 和 `pass_criteria`

> 来源: factor_mining_requirements.md §C.3.1

| 配置项 | GSD S03 现状 | 缺口说明 |
|--------|-------------|----------|
| `require_all_pass: true` | ❌ 无 | S03 仅配置了 periods，无通过标准 |
| `pass_criteria.min_ic` | ❌ 无 | 无 IC 阈值配置 |
| `pass_criteria.min_rank_ic` | ❌ 无 | 无 Rank IC 阈值配置 |
| `pass_criteria.min_periods_pass` | ❌ 无 | 无最少通过周期数配置 |

**factor_mining_requirements.md 描述的配置**:
```yaml
multi_period_validation:
  require_all_pass: true
  pass_criteria:
    min_ic: 0.03
    min_rank_ic: 0.03
    min_periods_pass: 2    # 至少通过N个周期
```

**需要的操作**: 扩展 `backtest.yaml` 的 `multi_period_validation` 配置，添加通过标准；在回测结果聚合逻辑中实现判定。

---

### 缺口 I: 24H 调度中心的完整三合一架构

> 来源: factor_mining_requirements.md §F.2

factor_mining_requirements.md 描述了完整的调度中心架构，包含三个并行模块：

```
调度中心 (Scheduler)
├── 数据监控器: 每日检测新数据入库
├── 温故: select_revalidation_candidates(days=21)
└── 知新: RAG + 新因子挖掘
```

| 子需求 | GSD 现状 | 缺口说明 |
|--------|----------|----------|
| 数据监控器（每日检测新数据） | ⚠️ S10 T02 仅设计 | Trigger 监听 app4 数据更新未实现 |
| 温故（定期重验旧因子） | ⚠️ S10 T04 仅设计 | Revalidation Loop 未实现 |
| 知新（RAG + 新因子挖掘） | ⚠️ S02 部分 | fewshot 导出已有但无向量检索 |
| 三者统一调度 | ❌ 无 | GSD S10 Orchestrator 仅设计阶段 |
| 异常处理和故障恢复 | ⚠️ S06 部分 | Checkpoint 已实现，但无调度级异常处理 |

**需要的操作**: S10 Orchestrator 设计需扩展为完整的三合一调度架构，而非仅设计文档。

---

### 缺口 J: 技术选型（向量库、任务调度、进程管理）

> 来源: factor_mining_requirements.md §四

| 模块 | factor_mining_requirements.md 推荐 | GSD 现状 |
|------|-----------------------------------|----------|
| 向量数据库 | ChromaDB (首选) / sqlite-vss / Milvus | ❌ 无规划 |
| 任务调度 | APScheduler / Celery / Prefect | ❌ 无规划 |
| 进程管理 | Supervisor / systemd | ❌ 无规划 |
| 日志监控 | Loguru + Grafana | ⚠️ Loguru 已用，Grafana 无规划 |
| 配置管理 | YAML + Pydantic | ⚠️ YAML 已用，Pydantic 无规划 |

**需要的操作**: 在 M004 或后续 milestone 中明确技术选型并规划实现。

---

## 缺口汇总表

| # | 缺口 | 来源章节 | GSD 现状 | 优先级建议 |
|---|------|----------|----------|-----------|
| A | 多视角融合(Ensemble)完整架构：裁判模型、交集/并集/投票/融合评分 | §A.3.2 | S04 仅 fanout_best 取单个最优 | P2 |
| B | `least_latency` 路由策略 + 同 Provider 多 Key 轮询 | §A.3.4 | 仅 single/round_robin/fanout_best | P2 |
| C | 因子分类标签系统 (category/data_dependency/market_environment/time_horizon) | §D.3.1 | 无任何标签 | P1 |
| D | RAG 向量检索架构 (ChromaDB/embedding/共性总结prompt) | §D.3.2 | 仅有 Jaccard 文本重叠 | P1 |
| E | 因子生命周期 `seasonal`/`archived` 状态 + 状态转换规则 | §D.3.4, §C.3.2 | 仅 active/degraded/stale/pending，无转换逻辑 | P1 |
| F | `select_revalidation_candidates(days=21)` 实现 | §F.3.1 | S10 T04 仅设计 | P0 |
| G | 数据能力注册表 `available_from`/`join_mode` 字段 | §E.3.1 | S01 仅有 fields/freq/lag_days/factor_hints | P1 |
| H | 跨周期验证 `require_all_pass`/`pass_criteria` (min_ic, min_rank_ic, min_periods_pass) | §C.3.1 | S03 仅配置 periods，无通过标准 | P0 |
| I | 24H 调度中心三合一架构（数据监控+温故+知新统一调度） | §F.2 | S10 Orchestrator 仅设计 | P3 |
| J | 技术选型（向量库/任务调度/进程管理/监控） | §四 | 无规划 | P2 |

---

## 建议新增 Milestone/Slice 规划

基于以上缺口，建议在 M003 完成后规划 M004，或在 M003 中新增 Slice：

| 建议 Slice | 覆盖缺口 | 依赖 | 估算复杂度 |
|-----------|----------|------|-----------|
| **S11: 跨周期验证通过标准** | H | S03 ✅ | ⭐ 低（配置+判定逻辑） |
| **S12: 因子重验候选选择** | F | S06 ✅, library.py | ⭐⭐ 中 |
| **S13: 因子分类标签系统** | C | library.py | ⭐⭐ 中 |
| **S14: 数据能力注册表扩展** | G | S01 ✅ | ⭐ 低（字段扩展） |
| **S15: 因子生命周期状态机** | E | S12 | ⭐⭐ 中 |
| **S16: RAG 向量检索** | D | S02 ✅ | ⭐⭐⭐ 高（引入新依赖） |
| **S17: Ensemble 聚合层** | A, B | S04 ✅ | ⭐⭐⭐ 高 |
| **S18: 24H 调度中心** | I, J | S08, S10, S12, S16 | ⭐⭐⭐⭐ 很高 |
