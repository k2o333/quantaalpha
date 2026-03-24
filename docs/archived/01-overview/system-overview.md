# System Overview

## One-Sentence Summary

`aspipe_v4` is a repository for financial data ingestion, factor mining, and strategy validation.

## Main Subsystems

| Subsystem | Purpose | Main entrypoints | Primary outputs |
|---|---|---|---|
| `app4` | Download and store market data from Tushare | `app4/main.py` | `data/` parquet datasets |
| `quantaalpha` | Generate, evaluate, and manage factor research | `third_party/quantaalpha/quantaalpha/cli.py` | `third_party/quantaalpha/data/` |
| `backtest` | Run factor backtests and debugging scripts | `backtest/start/*.py` | csv/debug outputs in working directory |

## Data Flow

`Tushare API -> app4 parquet datasets -> quantaalpha factor research -> backtest validation`

## Directory Landmarks

| Path | Purpose |
|---|---|
| `app4/` | main data download system |
| `backtest/` | factor backtest scripts |
| `third_party/quantaalpha/` | factor mining subsystem |
| `data/` | local data storage |
| `cache/` | cache files |
| `log/` | runtime logs and reports |
| `test/` | project-level tests |
| `docs/` | governance, module docs, technical flows, change history |

## What Usually Counts As High Risk

- pagination logic
- storage/write-path changes
- dedup behavior
- schema semantics
- update semantics
- concurrency or worker model changes

These require stronger validation and usually human review. See `docs/00-governance/rules.md`.

## What Not To Edit By Default

- `third_party/vnpy/`
- `third_party/glue/`

Only touch these when the task explicitly requires it.

## Read Next

- Start rules: `docs/00-governance/rules.md`
- app4 details: `docs/02-modules/app4.md`
- quantaalpha details: `docs/02-modules/quantaalpha.md`
- backtest details: `docs/02-modules/backtest.md`
- technical flows: `docs/07-technical/*.md`
