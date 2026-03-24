# M004: 因子库深化与自治能力增强 — Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

## 来源

本里程碑覆盖 `docs/drafts/mining/需求与GSD里程碑对照表.md` 中识别的缺口 A-J，对应 `docs/drafts/mining/factor_mining_requirements.md` 中未被 M003 覆盖的需求。

## 依赖关系

M004 建立在 M003 已完成的基础设施之上：
- M003 S01: 数据能力注册表 (data_capability.py)
- M003 S02: 因子库 Few-shot 导出 (fewshot.py)
- M003 S03: 配置解锁 (backtest.yaml 多周期验证)
- M003 S04: ProviderPool 核心实现
- M003 S06: Checkpoint + 版本历史 (library.py versions)

## Implementation Decisions

- 使用 M004 新里程碑而非扩展 M003，因为这些是增强功能而非架构实施
- Slice 编号从 S01 重新开始（M004/S01 而非 M003/S11）
- 向量库首选 ChromaDB（轻量级，Python 原生）
- Ensemble 聚合层在 ProviderPool 基础上扩展，不引入新类

## Agent's Discretion

- 各 Slice 的 Task 粒度由执行时确定
- 状态机转换阈值的具体数值在 S05 实现时确定

## Deferred Ideas

- Grafana 监控面板
- 生产环境 Milvus 迁移
- Celery 分布式任务队列
