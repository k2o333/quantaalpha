# Project

## What This Is

`aspipe_v4` is a config-driven financial data pipeline with three integrated subsystems:

1. **app4**: Downloads and processes TuShare Pro financial data using declarative YAML configurations
2. **quantaalpha**: Factor mining and evaluation subsystem for quantitative alpha research
3. **backtest**: Factor validation and strategy backtesting, centered on Alpha101 workflows

## Core Value

Reliable, incremental financial data ingestion → factor mining → strategy validation pipeline with minimal configuration changes and strong observability.

## Current State

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

- [ ] M001: Core data pipeline stabilization — harden error handling and logging
- [ ] M002: Interface expansion — add remaining TuShare VIP endpoints
- [ ] M003: Data quality layer — validation rules and anomaly detection
- [ ] M004: Factor mining integration — quantaalpha → backtest workflow
- [ ] M005: Strategy optimization — portfolio construction and risk management
