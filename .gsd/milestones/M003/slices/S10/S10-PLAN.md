# S10: ADR-003 Phase 3 外插模块设计

**触发决策**: D015

**问题**: ADR-003 定义了外插模块边界，但 Orchestrator、Trigger、Observability 尚未实现。

**参考文档**:
- `docs/drafts/factormining/structure/2026-03-22-quantaalpha-continuous-mining-comprehensive-plan.md` 第 4 节
- D015: 正式批准 ADR-003

---

## 目标

设计 ADR-003 Phase 3 外插模块：
1. Orchestrator: 调度核心
2. Trigger: 数据更新事件监听
3. Observability: 监控告警
4. Revalidation Loop: 因子复验

---

## 成功标准

- [ ] Orchestrator 模块设计文档
- [ ] Trigger 事件监听设计
- [ ] Observability 监控指标设计
- [ ] Revalidation Loop 复验策略设计
- [ ] 模块间接口契约定义
- [ ] 与主链代码边界清晰

---

## 任务拆分

### T01: 设计 Orchestrator 核心
**文件**: `docs/design/orchestrator.md` (新建)
**估算**: 4h

设计内容：
1. 调度策略（定时/事件驱动）
2. 状态机管理
3. 与 ProviderPool 集成
4. 与 Checkpoint 集成

**验收**:
- [ ] 调度策略明确
- [ ] 状态机设计完整
- [ ] 接口契约定义

### T02: 设计 Trigger 事件监听
**文件**: `docs/design/trigger.md` (新建)
**估算**: 3h

设计内容：
1. 监听 app4 数据更新
2. 事件分发机制
3. 与 Orchestrator 集成

**验收**:
- [ ] 监听机制设计
- [ ] 事件格式定义
- [ ] 集成方案明确

### T03: 设计 Observability 监控
**文件**: `docs/design/observability.md` (新建)
**估算**: 3h

设计内容：
1. 监控指标（Token 使用、成功率、运行时长）
2. 告警阈值
3. 日志收集
4. 与 ResourceManager 集成

**验收**:
- [ ] 监控指标完整
- [ ] 告警策略明确
- [ ] 集成方案明确

### T04: 设计 Revalidation Loop
**文件**: `docs/design/revalidation.md` (新建)
**估算**: 3h

设计内容：
1. 复验候选选择策略
2. 复验触发条件
3. 复验结果处理
4. 与 FactorLibrary 集成

**验收**:
- [ ] 复验策略明确
- [ ] 触发条件定义
- [ ] 集成方案明确

### T05: 定义模块间接口契约
**文件**: `docs/design/adr003_interfaces.md` (新建)
**估算**: 2h

定义：
1. Orchestrator ↔ Trigger 接口
2. Orchestrator ↔ Observability 接口
3. Orchestrator ↔ Revalidation 接口
4. 与主链代码边界

**验收**:
- [ ] 接口契约文档化
- [ ] 边界清晰

---

## 依赖

- **S04**: ProviderPool 设计
- **S06**: Checkpoint 设计
- **S08**: ResourceManager 设计
- **D015**: ADR-003 批准

---

## 输出

设计文档将指导 Phase 3 实现（M004 或后续里程碑）。
