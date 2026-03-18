# QuantaAlpha 持续挖掘设计 V2

Status: draft
Owner: QuantaAlpha team
Created: 2026-03-15
Supersedes: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/continuous mining/2026-03-12-quantaalpha-continuous-factor-design.md
Related-changes:
- /home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/quantaalpha2026-3-14checklist/README.md

---

## 1. 目的

这份文档不是重写一版“更大更全”的蓝图，而是基于当前系统真实运行结果，给出一版更可信、可执行的持续挖掘设计。

设计目标分三层：

1. 反映当前已经被代码和运行验证的能力
2. 明确哪些原始设计已被实践证明需要收缩或调整
3. 给出下一阶段最小闭环，而不是直接跳到复杂 24h 编排

---

## 2. 当前系统的真实状态

截至当前代码状态，QuantaAlpha 已经不是单次因子挖掘脚本，而是一个“可持续演进的最小研究系统”，但距离完整的 24h 持续研究平台还有明显差距。

当前已落地并保留的能力：

- 统一股票池过滤入口
- 多周期验证与稳定性聚合
- 因子库 schema 扩展
- 手动 `revalidate` CLI
- 因子状态流转规则
- 稳定性结果接入 evolution
- 任务级 LLM 路由

当前运行中新增并证明重要的稳定性能力：

- 一致性检查会在 factor construct 阶段纠偏 hypothesis / description / expression
- debug 成功项会提前退出
- planning 会约束到当前日频价量数据边界
- 结果质量门控会拦截明显坏因子
- 未知 tokenizer 会统一托底，不再刷屏

当前已经暴露、且需要在下一阶段补齐的缺口：

- `revalidate` CLI 当前主要复用已有 `period_results` 与 `stability_score`，并不等价于“重新跑一次真实回测”
- “只重试失败因子”在设计方向上成立，但批次级显式过滤与自动化验证仍需补齐
- 运行摘要、状态变更审计、关键指标采集尚未标准化
- JSON 因子库缺少并发写保护
- 外部调度虽可通过 CLI 实现，但缺少标准触发脚本与约定输出

当前未形成稳定主链路的能力：

- 数据能力注册表主 prompt 注入
- 多模型 fanout
- provider 轮询与压力池化
- 常驻 orchestrator / 24h daemon

---

## 3. 对旧设计的修正

## 3.1 数据能力注册表不再作为主 prompt 默认注入

旧设计把 `Data Capability Registry` 视为 LLM 感知新增数据维度的主通路。

实际运行后的结论是：

- 结构化注册表本身有价值
- 但默认注入 factor coding 主 prompt 会放大上下文长度
- 在调试链路中会显著增加耗时和超时风险

因此新设计改为：

- 保留数据能力注册表作为结构化事实层
- 默认不注入主 prompt
- 仅在特定任务、特定维度或需要新增数据解释时受控注入

结论：

- 注册表保留
- 主 prompt 默认不依赖它

## 3.2 多模型层从“大协作平台”收缩为“任务级路由 + 必要兜底”

旧设计中的：

- `TaskPolicy`
- `ModelProfiles`
- `ProviderPool`
- `RepairChain`
- `fanout=2`

作为长期方向成立，但不应视为下一阶段主线。

当前被真实验证有效的，是更轻量的方案：

- 按 `task_type` 路由模型
- 对空响应、坏 JSON 做本地修复和 fallback
- 对未知 tokenizer 统一托底

因此新设计不把 `fanout` 和 provider 轮询作为当前阶段目标，而将其降级为未来扩展项。

## 3.3 持续维护层不直接落为常驻 24h 调度进程

旧设计把“24h 不间断运行”放在系统目标中。

从当前系统成熟度看，直接做常驻 orchestrator 风险过高，原因包括：

- LLM 和 embedding 服务稳定性仍有波动
- 因子质量门控和一致性 gate 刚进入可用阶段
- 运行链路仍需更多回归测试

因此新设计改为：

- 优先支持“外部定时触发的持续运行”
- 不优先实现仓库内 daemon
- 不优先实现复杂队列系统

即：

- cron / scheduler 触发 `mine`
- cron / scheduler 触发 `revalidate`
- 结果进入因子库
- 状态更新后再决定下一轮挖掘

## 3.4 因子知识库保持 JSON 为主事实源

旧设计把因子库进一步推向“知识库 + 检索 + guidance + embedding”。

当前更稳妥的原则是：

- `JSON factor library` 仍是主事实源
- 当前核心字段是：
  - `evaluation`
  - `data_requirements`
  - `status`
  - `period_results`
  - `stability_score`
- `usage_guidance`、复杂检索、向量层都属于未来增强，不应提前做成主依赖

## 3.5 持续挖掘设计必须把“系统稳定性约束”写进主线

旧设计更强调能力扩展，低估了运行期稳定性约束。

根据当前实际经验，以下内容必须进入主设计，而不能只停留在排障层：

- planning 数据边界约束
- consistency gate
- 结果质量门控
- 只重试失败因子的 debug 策略
- tokenizer 与结构输出托底策略
- `revalidate` 的语义边界与可观测性

---

## 4. 新的总体设计

当前更合理的总体设计不是“四层大平台”，而是“三层主链路 + 一层外部调度”。

```text
外部调度 / 人工触发
        ↓
研究主链路
  direction -> hypothesis -> factor construct -> debug -> backtest -> feedback
        ↓
验证与治理层
  stock universe -> multi-period validation -> quality gate -> status update
        ↓
因子事实层
  factor library JSON
```

其中：

- 研究主链路负责生成与调试
- 验证与治理层负责“能不能信”
- 因子事实层负责“当前真相是什么”
- 外部调度负责“什么时候再跑”

---

## 5. 模块设计

## 5.1 研究主链路

### 5.1.1 目标

研究主链路负责：

- 基于方向生成 hypothesis
- 从 hypothesis 构造 factor candidates
- 对候选进行代码实现与 debug
- 对通过候选进入回测
- 基于反馈更新 trace 和 library

### 5.1.2 当前已验证的关键机制

- planning 会生成多个探索方向
- direction 受当前日频数据边界限制
- construct 阶段会做一致性检查和必要纠偏
- debug 阶段成功项会尽早退出
- 失败项会被优先重试，而不是整批重复打磨

### 5.1.3 当前设计约束

- 不允许方向漂移到当前不可用数据
- 不允许坏 JSON/空响应直接打死主流程
- 不允许一个坏因子拖着整批候选满 10 轮重复调试

现阶段文档中的“失败因子”至少包括：

- expression parse 失败
- factor 计算结果无法产出有效样本
- 质量门控失败
- backtest 执行失败或结果为空

## 5.2 验证与治理层

### 5.2.1 统一股票池

股票池必须在以下阶段一致：

- factor 计算
- dataset 构建
- backtest
- multi-period validation

统一股票池不是一个“回测可选项”，而是验证可信度的前提。

### 5.2.2 多周期验证

多周期验证当前已经是主线能力，不再是未来设想。

要求：

- 一个因子不只看单次时间窗
- period 结果可聚合
- 聚合结果进入因子库
- 聚合结果参与 evolution

### 5.2.3 结果质量门控

回测前必须有轻量质量门控。

至少应检查：

- NaN 比例
- inf 比例
- 有效样本比例
- 常数列

这层是“低成本挡掉坏因子”，不是“再做一次高成本研究”。

### 5.2.4 状态更新

当前状态流转围绕以下集合：

- `pending_validation`
- `active`
- `degraded`
- `stale`
- `deprecated`

不建议现阶段再扩更多中间状态。

当前默认阈值也应明确写入设计，避免实现与文档脱节：

- `active_stability_threshold = 0.5`
- `degraded_stability_threshold = 0.3`
- `stale_threshold_days = 30`

这些值当前可视为运行默认值；下一阶段可以配置化，但不应因此重新引入更复杂的状态模型。

## 5.3 因子事实层

### 5.3.1 存储定位

当前因子库继续使用 JSON，原因是：

- 已有链路都围绕它构建
- 兼容成本低
- 目前规模还没有逼迫数据库化

### 5.3.2 当前最关键字段

每个因子至少应有：

- 表达式与描述
- 回测结果
- `evaluation`
- `data_requirements`
- 演化来源信息

为了支持持续维护，事实层还应补充两类最小治理能力：

- 写入保护：至少提供文件锁或等价机制，避免并发写坏 JSON
- 状态审计：记录状态变化时间、旧状态、新状态、触发原因

### 5.3.3 当前不作为主线的内容

- 向量库检索
- 复杂 usage guidance 自动生成
- 全量回测历史数据库化

这些都可以后做，但不应成为当前运行依赖。

## 5.4 外部调度层

### 5.4.1 目标

支持持续研究，但不把复杂调度系统提前塞进仓库内部。

### 5.4.2 建议方式

使用外部定时触发：

- 定时执行 `mine`
- 定时执行 `revalidate --dry-run`
- 根据结果决定下一轮是否正式复验

这里需要补充一个更严格的约束：

- 仓库内应提供标准触发脚本或标准命令模板，避免调度侧各自拼装
- 调度输出应至少包含本轮成功数、失败数、待复验数、状态分布摘要
- 在真实回测版 `revalidate` 未落地前，`revalidate --dry-run` 和当前 `revalidate` 都应被明确标注为“基于现有验证结果的状态维护”，不能在文档中表述成“已重新复验”

### 5.4.3 当前不做

- 常驻 orchestrator
- 内部多队列调度
- 自动自愈 worker 池

---

## 6. 下一阶段的最小闭环

下一阶段不建议继续往“大而全平台”扩，而是先把以下闭环做稳：

### 6.1 闭环目标

```text
外部定时触发
    ↓
挖掘一轮
    ↓
多周期验证
    ↓
结果质量门控
    ↓
写入因子库
    ↓
状态更新
    ↓
筛选 stale / degraded / high-stability factors
    ↓
下一轮挖掘或复验
```

### 6.2 下一阶段必须完成的内容

1. 回归测试补齐
2. 结果质量门控专项验证
3. 明确 `revalidate` 是“状态维护”还是“真实回测复验”，并补齐对应实现或文档边界
4. `revalidate` 与定时触发联通
5. 运行日志、状态变更与关键指标可观测
6. 因子库并发写保护

### 6.3 下一阶段不建议立刻做的内容

1. 多模型 fanout
2. provider 轮询池
3. 常驻 24h daemon
4. 向量知识库

---

## 7. 推荐的实施顺序

### Phase A：稳定主链路

1. 为 planning 边界约束增加自动化测试
2. 为 debug 只重试失败因子补齐显式过滤逻辑与自动化测试
3. 为结果质量门控增加坏样本验证
4. 为状态流转增加端到端验证
5. 为 `revalidate` 补齐语义澄清：要么显式声明仅复用历史结果，要么接入真实回测链路

### Phase B：最小持续维护

1. 增加外部调度脚本或标准触发命令
2. 定时运行 `mine`
3. 定时运行 `revalidate --dry-run`
4. 输出待复验清单、状态分布与最近成功时间等运行摘要
5. 为因子库写入增加文件锁或等价保护
6. 为状态变化增加最小审计日志

### Phase C：受控增强

1. 受控恢复数据能力注册表注入，但只在特定任务启用
2. 增加单次 fallback 模型，而不是 fanout
3. 根据真实成本和质量，再决定是否引入 provider pool

---

## 8. 验收标准

新设计不是看“功能数量”，而是看以下问题是否被回答：

1. 方向是否仍被限制在当前数据边界内
2. 坏因子是否会在回测前被挡掉
3. 成功因子是否不再被重复 debug
4. 因子库是否能反映当前有效状态
5. 多周期结果是否真正参与后续选择
6. `revalidate` 的输出是否不会再混淆“状态维护”和“真实回测”
7. 系统是否能在外部调度下持续运行，而不是只能手工单次执行
8. 调度后是否能直接看到成功数、失败数、待复验数和状态分布摘要

---

## 9. 一句话结论

QuantaAlpha 下一阶段不应继续朝“更复杂的多模型平台”发散，而应先把“受约束的研究主链路 + 验证治理层 + JSON 因子事实层 + 外部定时触发”打磨成稳定的持续研究最小闭环。
