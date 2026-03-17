# aspipe_v4 Agent Entry

## Read This First

Start here for every task in this repository.

Required order:
1. Read `docs/00-governance/rules.md`
2. Route to the task-specific document below
3. Locate the code entrypoints before editing
4. Run the minimum required validation before finishing

## Project In One Sentence

`aspipe_v4` is a config-driven financial data pipeline:
`app4` downloads data, `quantaalpha` mines factors, and `backtest` validates strategies.

## Task Routing

| If your task is about | Read next |
|---|---|
| overall repo structure | `docs/01-overview/system-overview.md` |
| app4 downloader, storage, update behavior | `docs/02-modules/app4.md` |
| quantaalpha factor mining and validation | `docs/02-modules/quantaalpha.md` |
| backtest scripts and factor validation | `docs/02-modules/backtest.md` |
| detailed execution flow | `docs/07-technical/*.md` |
| implementation context for a module | `docs/03-changes/<module>/<status>/` |
| long-term architectural decisions | `docs/04-decisions/` |
| reusable patterns and lessons | `docs/05-playbooks/` |
| auditing agent delivery quality or closure gaps | `docs/05-playbooks/agent-delivery-audit-playbook.md` |
| writing or hardening a `planned` change doc | `docs/05-playbooks/planned-doc-hardening-playbook.md` |
| upstream or framework usage notes | `docs/06-references/` |
| documentation conversion or cleanup | `docs/00-governance/doc-rules.md` |
| branch and review workflow | `docs/00-governance/development-workflow.md` |

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

- `docs/drafts/` is not source of truth
- module docs under `docs/02-modules/` define the current valid state
- change docs under `docs/03-changes/` provide implementation context, not current truth
- `third_party/vnpy/` is not a normal edit target
- `third_party/glue/` is not a normal edit target
- passing tests do not replace the review rules in `rules.md`

## Output Expectation Before Editing

Identify these four items first:
- target module
- target files
- required validation
- whether the task requires human review under `rules.md`

For high-risk tasks, identify these four seams before editing:
- downstream consumer
- write target or source-of-truth path
- failure surface seen by operators or schedulers
- one concrete command that could disprove the claimed completion
