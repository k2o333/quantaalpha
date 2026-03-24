# aspipe_v4 Agent Entry

Status: active
Owner: quan
Created: 2026-03-15
Updated: 2026-03-21
Outcome: accepted

## Read This First

Start here for every task in this repository.

Required order:
1. read `docs/00-governance/rules.md`
2. identify whether you need current truth or task context
3. read the next routed document only
4. locate code entrypoints before editing
5. run the minimum required validation before reporting completion

## Project In One Sentence

`aspipe_v4` is a config-driven financial data pipeline:
`app4` downloads data, `quantaalpha` mines factors, and `backtest` validates strategies.

## Truth Priority

Use this order when materials disagree:
1. `docs/00-governance/agent.md`
2. `docs/00-governance/rules.md`
3. `docs/02-modules/*.md`
4. `docs/04-decisions/*.md`
5. `docs/05-playbooks/*.md`
6. `docs/06-references/*.md`
7. `docs/07-technical/*.md`
8. `docs/03-changes/<module>/`
9. `docs/drafts/`
10. current code, when docs are stale and must be corrected

## Fast Routing

| If your task is about | Read next |
|---|---|
| overall repo structure | `docs/01-overview/system-overview.md` |
| current valid behavior of `app4` | `docs/02-modules/app4.md` |
| current valid behavior of `quantaalpha` | `docs/02-modules/quantaalpha.md` |
| current valid behavior of `backtest` | `docs/02-modules/backtest.md` |
| one concrete implementation task or closure record | `docs/03-changes/<module>/` |
| long-term architecture or policy | `docs/04-decisions/` |
| repeatable engineering procedure or lesson | `docs/05-playbooks/` |
| upstream or framework usage notes | `docs/06-references/` |
| deep call flow or implementation detail | `docs/07-technical/` |
| documentation standards, placement, or workflow | `docs/00-governance/doc-rules.md` |
| branch and review workflow | `docs/00-governance/development-workflow.md` |
| agent operating boundary | `docs/00-governance/agent-constraints.md` |
| document validation rules | `docs/00-governance/doc-validation.md` |

## Change-Doc Routing

`docs/03-changes/` is module-flat:

- use `docs/03-changes/app4/` for `app4` task context
- use `docs/03-changes/quantaalpha/` for `quantaalpha` task context
- use `docs/03-changes/backtest/` for `backtest` task context
- use `docs/03-changes/common/` for cross-module task context

Do not route by status directory.

Change-doc status lives in document metadata, not in the filesystem path.

When status discovery is needed, use the fixed indexing script defined by governance docs instead of scanning guessed subdirectories.

## Code Entrypoints

### app4

- CLI: `app4/main.py`
- Runtime Python: `/root/miniforge3/envs/get/bin/python`
- Global config: `app4/config/settings.yaml`
- Interface configs: `app4/config/interfaces/*.yaml`
- Core logic: `app4/core/`
- Update logic: `app4/update/`

### quantaalpha

- CLI: `third_party/quantaalpha/quantaalpha/cli.py`
- Runtime Python: `/root/miniforge3/envs/mining/bin/python`
- Configs: `third_party/quantaalpha/configs/`
- Factor library: `third_party/quantaalpha/data/factorlib/`
- Tests: `third_party/quantaalpha/tests/`

### backtest

- Entrypoints: `backtest/start/*.py`
- Input data: `data/stk_factor_pro/`

## Validation Entrypoints

### app4

- Config check: `/root/miniforge3/envs/get/bin/python -c "from app4.core.config_loader import ConfigLoader; ConfigLoader().validate_config()"`
- Smoke run: `/root/miniforge3/envs/get/bin/python app4/main.py --interface trade_cal --start_date 20240101 --end_date 20240131`
- Update preview: `/root/miniforge3/envs/get/bin/python app4/main.py --update --update-dry-run`

### quantaalpha

- Tests: `/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests -v`
- Health check: `/root/miniforge3/envs/mining/bin/quantaalpha health_check`

### backtest

- Main run: `python backtest/start/backtest_alpha101_polars.py`
- Short debug run: `python backtest/start/debug_pure_polars_fixed.py`

## Do Not Assume

- `docs/drafts/` is never current truth
- `docs/03-changes/` is process context, not default truth
- module docs under `docs/02-modules/` define the current valid state
- change-doc status is not encoded by directory names
- passing tests do not replace the review rules in `rules.md`
- `third_party/vnpy/` is not a normal edit target
- `third_party/glue/` is not a normal edit target

## Output Expectation Before Editing

Identify these five items first:
- target module
- target files
- truth docs consulted
- required validation
- whether human review is required

For high-risk tasks, identify these four seams before editing:
- downstream consumer
- write target or source-of-truth path
- failure surface seen by operators or schedulers
- one concrete command that could disprove the claimed completion
