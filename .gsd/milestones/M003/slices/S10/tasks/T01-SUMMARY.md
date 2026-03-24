# T01-T04 Summary — S10 ADR-003 设计文档

**Slice:** S10
**Milestone:** M003
**Date:** 2026-03-23

## 完成交付

| 文件 | 内容 | 行数 |
|------|------|------|
| `docs/design/orchestrator.md` | Orchestrator 调度策略、状态机、MainChainGateway 接口 | ~220 |
| `docs/design/trigger.md` | PollingTrigger、WatcherTrigger、事件去重 | ~160 |
| `docs/design/observability.md` | MetricsCollector、AlertManager、指标定义 | ~260 |
| `docs/design/revalidation.md` | CandidateSelector、RevalidationLoop、因子状态机 | ~210 |
| `docs/design/adr003_interfaces.md` | 6 个接口契约、部署结构、迁移路径 | ~140 |

## 接口契约摘要

- **IF-01**: Trigger → Orchestrator (`DataUpdateEvent`)
- **IF-02**: Orchestrator → MainChainGateway (`CycleConfig` / `CycleResult`)
- **IF-03**: Orchestrator → ResourceGate (`pre_flight_check`)
- **IF-04**: Orchestrator → Observability (`CycleMetrics`)
- **IF-05**: Orchestrator → RevalidationLoop (`RevalidationCandidate`)
- **IF-06**: MainChainGateway → FactorLibrary (现有 API)

## 迁移路径

Phase 1: `run.sh → loop.py` (当前)
Phase 2: `run.sh → Orchestrator → MainChainGateway → loop.py`
Phase 3: 完整自治 + Trigger + RevalidationLoop + Observability
