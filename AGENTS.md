# Repository Guidelines

## Project Structure & Module Organization
`quantaalpha/` contains the Python package and core pipeline code. Key areas include `pipeline/` for mining and backtest entrypoints, `core/` for framework logic, `factors/` for factor generation utilities, and `backtest/` for standalone backtesting. Runtime configs live in `configs/`, generated outputs go to `data/results/` and `log/`, and longer-form docs live in `docs/`. The web UI is isolated in `frontend-v2/` with React sources under `frontend-v2/src/` and a small Python backend in `frontend-v2/backend/`.

## Build, Test, and Development Commands
Install the Python package in editable mode with `SETUPTOOLS_SCM_PRETEND_VERSION=0.1.0 pip install -e .` and then `pip install -r requirements.txt`. Start the main workflow with `./run.sh "Price-Volume Factor Mining"` after copying `configs/.env.example` to `.env`. Use `python launcher.py mine --direction "momentum reversal"` for direct CLI access, or `python -m quantaalpha.backtest.run_backtest -c configs/backtest.yaml --factor-source custom --factor-json all_factors_library.json` for independent backtests. Build docs with `make -C docs html`. For the frontend, run `cd frontend-v2 && npm run dev`, `npm run build`, or `npm run lint`.

## Coding Style & Naming Conventions
Follow existing Python style: 4-space indentation, type hints where practical, snake_case for modules/functions, and PascalCase for classes. Keep imports grouped and formatted for `isort`; use `black` for formatting and `ruff` plus `mypy` for linting and static checks:
`python -m black quantaalpha`
`python -m isort quantaalpha`
`python -m ruff check quantaalpha`
`python -m mypy quantaalpha`

In `frontend-v2/src/`, prefer TypeScript function components, PascalCase component files, and camelCase hooks/state names.

## Testing Guidelines
Python test dependencies are listed in `requirements/test.txt` and use `pytest` with `coverage`. The repository does not currently ship a dedicated `tests/` tree, so new tests should be added under `tests/` or beside the module they exercise using `test_*.py` naming. Run `pytest` before opening a PR; use `coverage run -m pytest` when touching mining, backtest, or config-loading paths.

## Commit & Pull Request Guidelines
Recent history uses short, plain subjects (`first`, `first real shot`), but contributors should use clearer imperative messages such as `Add factor cache validation`. Keep commits focused and easy to review. PRs should summarize the behavioral change, list any config or data prerequisites, link related issues, and include screenshots for `frontend-v2` UI changes. Call out any `.env`, dataset, or backtest assumptions explicitly.

## Security & Configuration Tips
Do not commit `.env`, API keys, raw datasets, or generated logs. Keep large HDF5/Qlib inputs under ignored data directories such as `git_ignore_folder/` and verify `QLIB_DATA_DIR` and `DATA_RESULTS_DIR` before running experiments.
