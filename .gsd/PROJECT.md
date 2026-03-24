# Project

## What This Is

`aspipe_v4` is a config-driven financial data pipeline with three integrated subsystems:

1. **app4**: Downloads and processes TuShare Pro financial data using declarative YAML configurations
2. **quantaalpha**: Factor mining and evaluation subsystem for quantitative alpha research
3. **backtest**: Factor validation and strategy backtesting, centered on Alpha101 workflows

## Core Value

Reliable, incremental financial data ingestion → factor mining → strategy validation pipeline with minimal configuration changes and strong observability.

## Current State

### M001 完成（2026-03-22）
- **状态**: ✅ 已完成
- **交付**: 修复了导致因子挖掘工作流卡死的 4 个关键 Bug
- **关键修复**: 日志参数签名、无限重试死循环、LLM 空响应检查、JSON 控制字符转义
- **文档**: `.gsd/milestones/M001/M001-SUMMARY.md`

### M002 完成（2026-03-23）
- **状态**: ✅ 已完成
- **交付**: 修复 `'dict' object has no attribute 'replace'` 错误
- **关键修复**: 在 ComplexityChecker.check() 和 RedundancyChecker.check() 添加 isinstance(expression, dict) 检查
- **验证**: 25 项单元测试全部通过（S02 13 项 + S03 12 项）
- **文档**: `.gsd/milestones/M002/M002-SUMMARY.md`

### M004 完成（2026-03-24）
- **状态**: ✅ 已完成
- **交付**: 因子库深化与自治能力增强全部 8 个切片
- **已完成切片**:
  - S01: 跨周期验证通过标准 ✅ — backtest.yaml pass_criteria + validation_judge.py (R007)
  - S02: 因子重验候选选择 ✅ — select_revalidation_candidates() + last_validated (R008)
  - S03: 因子分类标签 ✅ — tags 字段 (category/data_dependency/market_environment/time_horizon) (R009)
  - S04: 数据能力注册表扩展 ✅ — available_from + join_mode (R010)
  - S05: 因子生命周期状态机 ✅ — 5 状态转换 (pending_validation/active/stale/degraded/deprecated) (R011)
  - S06: RAG 向量检索 ✅ — vector_store.py + fewshot.py (ChromaDB + Jaccard fallback) (R012)
  - S07: Ensemble 聚合层 ✅ — EnsembleAggregator (4策略) + ProviderPool (3路由策略) (R013)
  - S08: 24H 调度中心 ✅ — MiningOrchestrator + scheduler.py + implementations.py (R014)
- **验证**: 74 项单元测试通过（含 3 处测试修复）
- **关闭时修复**: test_scheduler_summary.py (total_validated 2→3), test_data_capability_registry.py (available_from 字段)
- **文档**: `.gsd/milestones/M004/M004-SUMMARY.md`, `.gsd/milestones/M004/M004-ROADMAP.md`

### M005 进行中（2026-03-24 启动）
- **状态**: 🔄 进行中（3/6 切片完成）
- **交付目标**: 修复 6 个已验证 Bug，稳定因子挖掘 pipeline
- **已完成切片**:
  - S01: `rdagent.log` 硬依赖 fallback ✅
  - S02: `normalize_corrected_expression` 强化处理脏字符串 ✅
  - S03: consistency prompt 输出约束收紧 ✅
- **待处理切片**:
  - S04: BadRequest 快速失败重抛
  - S05: proposal.yaml 配置歧义清除
  - S06: JSON 转义修复集中化
- **文档**: `.gsd/milestones/M005/M005-ROADMAP.md`, `.gsd/milestones/M005/M005-CONTEXT.md`

### app4 (Data Pipeline)
- **Working**: 43 TuShare interfaces configured with YAML; 7 pagination modes; incremental update with checkpoint recovery; Polars-based data processing
- **Architecture**: CLI → config loader → scheduler → downloader → processor → storage
- **Storage**: Parquet format with primary-key deduplication
- **Location**: `/home/quan/testdata/aspipe_v4/app4/`

### quantaalpha (Factor Mining)
- **Working**: CLI-driven factor library management; evaluation status tracking; LLM-assisted factor generation
- **Entrypoints**: `third_party/quantaalpha/quantaalpha/cli.py`
- **Environment**: `mining` conda environment
- **Tests**: `/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests -v`

### backtest (Strategy Validation)
- **Working**: Alpha101 factor backtesting; Polars-based computation; performance metrics (sharpe, max drawdown)
- **Entrypoints**: `backtest/start/backtest_alpha101_polars.py`
- **Input**: `data/stk_factor_pro/`

## Documentation System

This project uses **dual documentation system**:

1. **Existing docs/** (197 files): Free-form documentation with governance rules, module docs, change docs, playbooks
2. **GSD .gsd/** (SQLite + Markdown): Structured state machine for requirements, decisions, milestones

### Documentation Routing

| Need | Go To |
|------|-------|
| Module current truth | `docs/02-modules/*.md` |
| Task context | `docs/03-changes/<module>/` |
| Architecture decisions | `docs/04-decisions/*.md` |
| Reusable patterns | `docs/05-playbooks/*.md` |
| Requirements status | `.gsd/REQUIREMENTS.md` |
| Decision register | `.gsd/DECISIONS.md` |

## Active Work

- **77 change documents** in `docs/03-changes/`
- **4 completed** tasks
- **12 active** (doing/planned)
- **3 ADRs** recorded

## Capability Contract

See `.gsd/REQUIREMENTS.md` for explicit capability tracking.

## Milestone Sequence

- [x] M001: QuantaAlpha 关键 Bug 修复 — 修复导致因子挖掘工作流卡死的 4 个关键 Bug（2026-03-22 完成）
- [x] M002: `'dict' object has no attribute 'replace'` 错误修复 — S01: Bug 定位 ✅, S02: 类型检查/转换 ✅, S03: 回归测试和文档 ✅（2026-03-23 完成）
- [x] M003: QuantaAlpha 持续因子挖掘体系架构实施 — ProviderPool ✅、Checkpoint ✅、PIT 对齐 ✅、ResourceManager ✅、M001 教训约束 ✅、ADR-003 设计 ✅（2026-03-23 完成）
- [x] M004: 因子库深化与自治能力增强 — S01-S08 全部完成（2026-03-24 完成）
- [ ] M005: Mining Pipeline 关键 Bug 修复 — S01/S02/S03 ✅ → S04/S05/S06 待完成（2026-03-24 启动）
