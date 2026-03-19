# ADR-003: QuantaAlpha 持续因子研究的外插模块边界

Status: draft
Owner:
Created: 2026-03-18
Outcome: pending

## 1. Context & Problem Statement (背景与问题)

当前 `quantaalpha` 已具备因子挖掘、多周期验证、因子库状态管理等研究主链能力，适合作为因子研究执行内核。但对于 24 小时连续因子研究系统，仅靠 `quantaalpha` 主链内部继续堆叠能力，会带来几个问题：

- **职责混杂**：调度、事件触发、监控、告警、连续测试等外层控制能力，与单次研究执行逻辑耦合过深。
- **演进速度受限**：主链代码既要处理挖掘和回测，又要承担连续运行治理，容易导致边界膨胀。
- **契约不稳定**：若主链对外缺少稳定、可机器消费的接口，外层系统只能依赖日志文本或临时脚本，难以长期维护。
- **连续运行风险更高**：24 小时系统必然会遇到重复触发、失败重试、超时补偿和上游数据突发更新，若没有明确的幂等与背压约束，系统会变得脆弱。
- **自动化验证缺口**：当前模块级测试并不能替代面向连续运行、重复执行和恢复场景的系统级测试。

因此，需要补充一层“外插式持续研究模块”，但同时保持 `quantaalpha` 主链继续聚焦于研究执行本身。

## 2. Decision Drivers (决策驱动力)

- 保持 `quantaalpha` 主链聚焦于“挖掘、回测、因子库写入与状态演化”。
- 将持续运行相关能力外置，以降低对主链流程的侵入。
- 让调度、监控、触发和系统级测试可以独立演进、独立验证、独立替换。
- 明确 `quantaalpha` 对外提供的稳定契约，避免外层模块依赖脆弱的控制台文本。
- 把**幂等性**作为主链与外层系统协作的前提，以支撑失败重试、重复调度和补偿执行。
- 在系统边界中显式纳入**资源管控与背压**，避免数据更新洪峰直接压垮研究主链。
- 从“程序是否报错”提升到“系统是否可观测”，让连续研究可以检测静默退化而非只检测崩溃。
- 采用分阶段 rollout，先建立最小可运行骨架，再引入事件驱动和元数据中心化能力。

## 3. Decision (决策)

我们决定将 `quantaalpha` 继续定义为**研究执行内核**，并将下列持续运行能力作为**外插模块层**建设：

- `continuous-orchestrator`
- `data-update-trigger`
- `observability-and-alerting`
- `continuous-test-harness`
- `data-capability-registry`

这些模块与 `quantaalpha` 的关系遵循以下总原则：

- 外插模块负责调度、触发、观测、系统级验证与元数据供给。
- `quantaalpha` 负责研究执行、回测、因子库更新和状态流转。
- 外插模块不得复制主链业务逻辑，只能通过稳定入口调用主链能力。
- 主链对外暴露的 CLI 或 Python facade 应具备明确的输入输出语义，并尽量保持幂等。
- 背压、排队、并发限制由 orchestrator 统一承担，trigger 不直接把流量压力转嫁给研究主链。

### 3.1 Continuous Orchestrator

`continuous-orchestrator` 负责以下职责：

- 编排 `Mining`、`Validation`、`Revalidation`、`Library Maintenance` 等独立作业。
- 支持定时触发与事件触发两类入口。
- 管理任务队列、并发度、重试策略和失败阶段归因。
- 统一处理资源管控、限流和背压，避免大批量事件直接压入主链。
- 驱动因子生命周期闭环，包括复验、降级、失效评估和必要的清理作业。

它不负责：

- 重新实现回测逻辑
- 重新解释状态流转规则
- 绕过 `quantaalpha` 直接写因子库

### 3.2 Data Update Trigger

`data-update-trigger` 负责以下职责：

- 感知 `app4` 或其他上游数据更新信号。
- 将数据更新翻译为标准化事件，交给 orchestrator 处理。
- 根据数据范围和更新时间，触发特定范围的复验、补挖或维护任务。

第一阶段建议采用轻量机制：

- manifest 文件
- 数据更新时间戳
- 显式事件文件

而不是一开始就引入复杂消息系统。

### 3.3 Observability And Alerting

`observability-and-alerting` 不仅负责传统监控，还要覆盖业务级可观测性：

- 消费运行摘要、退出码、状态分布、审计记录等结构化结果。
- 监测失败、卡住、长时间无产出、异常退化等系统状态。
- 关注“静默变差”，例如：
  - 连续多轮没有有效新因子
  - 单轮运行时长显著异常
  - 复验结果集中退化

因此，主链需要提供稳定、机器可消费的结果结构；纯控制台文本不能作为长期契约。

### 3.4 Continuous Test Harness

`continuous-test-harness` 负责为连续运行系统提供独立测试层：

- 调度级测试
- 黑盒入口测试
- 长运行回归测试
- 恢复与重复执行测试
- 空库、坏库、重复事件、失败重试等边界测试

这类测试的目标不是替代模块级单元测试，而是验证“连续系统是否还能稳定运行”。

### 3.5 Data Capability Registry

`data-capability-registry` 负责维护可用数据能力的统一元数据：

- 字段
- 频率
- `lag_days`
- `join_mode`
- 典型用途与限制

第一阶段采用：

- 静态配置文件
- 轻量加载类
- 结构化查询接口或 prompt 渲染接口

而不引入额外常驻服务。后续如有需要，再考虑升级为更中心化的元数据服务。

## 4. Module Boundaries (模块边界)

### 4.1 Responsibility Boundary

- `quantaalpha`：研究执行、回测、因子库更新、状态流转。
- orchestrator：任务编排、重试、并发控制、生命周期作业调度。
- trigger：事件发现与标准化投递。
- observability：观测、统计、告警。
- test harness：连续系统级验证。
- registry：数据能力元数据供给。

### 4.2 Invocation Boundary

外插模块调用主链时，只应依赖以下稳定入口：

- CLI 入口
- Python facade
- 因子库与状态摘要
- 审计记录
- 结构化运行结果

不应依赖：

- 临时日志文本
- 未声明语义的中间文件
- 主链内部私有控制流

### 4.3 Data Boundary

外插模块与主链之间的关键数据边界包括：

- 因子库 JSON
- 因子状态分布摘要
- 审计记录
- 数据更新时间或 manifest
- 可机器消费的运行结果

## 5. Integration Contracts (集成契约)

为了保证外插模块可稳定演进，主链与外层模块之间需要维持以下契约：

### 5.1 Idempotency Contract

主链公开入口应尽量满足以下要求：

- 重复触发同一作业时，不因重复执行产生不可控副作用。
- 失败重试时，不应写出重复因子或破坏既有状态。
- 对写入型操作，至少要有“重复调用的行为定义”，即使不能做到严格无副作用，也必须可预测。

### 5.2 Structured Output Contract

主链应提供稳定、机器可消费的输出，至少支持：

- 阶段结果
- 成功/失败统计
- 可归因的失败语义
- 因子库状态摘要
- 供 observability 与 orchestrator 消费的关键字段

推荐使用 JSON 或其他稳定结构化格式，但本 ADR 不强制限定具体编码格式。

### 5.3 Event Contract

trigger 提交给 orchestrator 的事件至少应包含：

- 事件类型
- 数据范围或影响范围
- 触发时间
- 关联数据版本或更新时间

### 5.4 Backpressure Contract

orchestrator 负责：

- 队列化事件
- 限制并发
- 控制速率
- 在资源不足时延后执行，而不是继续向主链施压

### 5.5 Testability Contract

系统应保留可被 test harness 稳定调用的入口和结果面，避免系统级测试只能依赖人工观察。

## 6. Phased Rollout (分阶段落地)

### Phase 1: Minimal Continuous Skeleton

- 建立稳定 CLI / facade 边界
- 建立最小 orchestrator
- 建立基础运行摘要与可观测字段
- 明确主链幂等性预期

### Phase 2: Event-Driven Continuous Loop

- 接入 `data-update-trigger`
- 让定时触发逐步扩展到事件驱动触发
- 引入连续系统级测试，防止调度和恢复语义退化

### Phase 3: Metadata-Centered Expansion

- 将 `data-capability-registry` 打通到主链消费路径
- 让外层系统可基于统一元数据做更精细的触发与筛选

## 7. Non-Goals / Rejected Alternatives (非目标与拒绝方案)

本决策不包括：

- 把所有持续运行能力直接并入 `quantaalpha.pipeline`
- 一开始就引入复杂常驻服务、分布式队列或数据库迁移
- 在编排层复制主链的研究、回测或状态逻辑
- 将 observability 简化为仅看 exit code 的被动监控

当前不优先采用的方案包括：

- 过早将 registry 服务化
- 过早将 trigger 绑定到重量级消息总线
- 将 orchestrator 拆到完全独立且版本不同步的远端仓库

## 8. Consequences (影响与风险)

### Positive (收益)

- `quantaalpha` 主链能保持更清晰的职责边界。
- 连续运行能力可独立演进，不必每次都深入修改研究核心。
- orchestrator、observability、test harness 可以单独增强系统可靠性。
- 更利于 24 小时运行场景下的恢复、重试和扩展。

### Negative / Risks (风险与应对)

- **契约漂移风险**：外插模块和主链的接口可能随时间失配。
  - *应对策略：用结构化契约而不是临时日志文本，并用 continuous test harness 持续校验。*
- **边界过度切分**：模块拆得过多会带来链路分散与排障复杂度。
  - *应对策略：外插模块只承载明确外层职责，不复制业务逻辑。*
- **幂等性不足暴露系统脆弱性**：若主链入口重复执行语义不清，外层重试机制会放大问题。
  - *应对策略：优先明确主链公开入口的幂等边界。*
- **资源洪峰风险**：数据更新事件可能在短时间内大量到达。
  - *应对策略：将背压、排队与限流定义为 orchestrator 的核心职责。*

## 9. Implementation Notes (实施说明)

本 ADR 只定义外插模块边界，不直接等同于实现任务。

后续如要落地，建议再拆成独立 change docs 或子设计：

- orchestrator 设计
- trigger 设计
- observability 设计
- continuous test harness 设计
- registry 接入设计

仓库组织上，优先考虑与主链同仓或同版本治理，以降低契约漂移风险；但具体目录和落点不在本 ADR 中写死。
