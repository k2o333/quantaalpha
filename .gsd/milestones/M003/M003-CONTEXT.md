# M003: QuantaAlpha 持续因子挖掘体系架构实施

**触发原因**: DECISIONS.md D014-D019 批准的架构决策需要转化为可执行的工程任务

**决策来源**: 
- D014: 正式批准 ADR-001 持续因子研究系统演进架构
- D015: 正式批准 ADR-003 外插模块边界与职责分离架构
- D016: ProviderPool 多模型管理架构
- D017: Checkpoint 与幂等性恢复机制
- D018: 24H 资源管理约束
- D019: M001 历史故障经验转化为设计约束

**参考文档**:
- `docs/drafts/factormining/structure/2026-03-22-quantaalpha-continuous-mining-comprehensive-plan.md`
- `docs/drafts/factormining/structure/2026-03-22-continuous-mining-plan-supplement.md`

---

## 核心目标

将 QuantaAlpha 从"单次因子挖掘单点工具"演进为"具备多模型协作、多数据维度感知、长效跨周期验证，以及 24 小时自治能力的持续因子研究体"。

---

## 关键决策摘要

### D014/D015: ADR 架构批准
- **ADR-001**: 多模型研究、多周期验证、因子知识库、数据能力注册表、持续运转调度五层架构
- **ADR-003**: quantaalpha 主链与外插模块（orchestrator、trigger、observability、test harness、registry）边界

### D016: ProviderPool 多模型管理 (S2)
- 摒弃全局单例 APIBackend
- 引入 Fanout 并发、轮询降级、角色分配的动态路由架构
- 解决 M001 Bug 2（空响应无限重试）教训

### D017: Checkpoint 与幂等性恢复 (S5)
- LoopCheckpoint 中断保存机制
- 因子库多版本历史留存
- 文件锁超时机制

### D018: 24H 资源管理约束 (S7)
- 每日 Token 预算硬上限（默认 5M tokens）
- 磁盘空间监控与告警（<5GB 触发）
- result.h5 自动清理（默认保留 30 天）
- 因子库条目上限与 SQLite 迁移阈值

### D019: M001 教训转化
- ProviderPool 区分空响应和网络错误
- Coding 模型 JSON 修复设置超时和重试上限
- 数据能力注册表类型安全检查
- Checkpoint 序列化换行符兼容性验证

---

## 实施阶段划分

参照 D011 确立的三阶段路线图：

### Phase 1: 防御与觉察
- P0: 配置解锁（排除北交所、多周期回测）
- P0.5: 数据能力注入最后一公里（S1）
- P1: 因子库 Few-shot 导出（S4）

### Phase 2: 分层计算与多模型
- P1: ProviderPool 最小实现（D016/S2）
- P1: Coding 模型 JSON 修复闭环（D019/S3）
- P2: PIT 对齐执行层（D013/S6）
- P2: Checkpoint + 因子版本化（D017/S5）

### Phase 3: 无人值守
- P3: 资源管理模块（D018/S7）
- P3: Orchestrator + Trigger + Observability（D015/ADR-003）

---

## 成功标准

- [ ] ADR-001 和 ADR-003 架构决策转化为具体代码实现
- [ ] ProviderPool 实现多 Provider 并存、健康监控、自动降级
- [ ] Checkpoint 机制支持断点续挖
- [ ] ResourceManager 实现资源边界约束
- [ ] M001 教训作为设计约束写入代码和测试
- [ ] 系统具备 24 小时无人值守运行能力

---

## 关键风险

- **架构复杂性** — ProviderPool 需要兼容现有 APIBackend 调用模式
- **状态一致性** — Checkpoint 需要处理因子库、trace、回测状态的同步
- **资源边界** — Token 预算和磁盘限制需要精确监控和拦截
- **测试覆盖** — 24H 运行场景需要长时间稳定性测试

---

## 与 M001/M002 的关系

- **M001**: 修复了 4 个高优先级 Bug，经验转化为 D019 设计约束
- **M002**: 修复 Bug #5（dict.replace 类型错误），为 M003 数据处理能力奠基
- **M003**: 基于 M001/M002 的修复，构建长期运行的架构基础
