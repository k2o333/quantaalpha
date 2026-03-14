# quantaalpha

LLM-driven alpha factor mining framework for quantitative trading research.

---

## Responsibility

- Generate trading factor hypotheses using LLM
- Construct factor expressions from natural language hypotheses
- Calculate factor values using Qlib data
- Run backtests to evaluate factor performance
- Manage factor library (storage, retrieval, deduplication)
- Support evolution-based factor optimization (mutation, crossover)

---

## External Interfaces

### CLI Commands

```bash
quantaalpha mine --direction "[direction]" --config_path configs/experiment.yaml
quantaalpha backtest -c configs/backtest.yaml --factor-source custom --factor-json factors.json
quantaalpha health_check
quantaalpha collect_info
```

### Programmatic Entry Points

| Entry Point | Module | Description |
|-------------|--------|-------------|
| `quantaalpha.pipeline.factor_mining.main()` | `pipeline/factor_mining.py` | Factor mining main loop |
| `quantaalpha.pipeline.factor_backtest.main()` | `pipeline/factor_backtest.py` | Standalone backtest |
| `quantaalpha.backtest.run_backtest.main()` | `backtest/run_backtest.py` | CLI backtest entry |

### Factor Library API

```python
from quantaalpha.factors.library import FactorLibraryManager

manager = FactorLibraryManager("data/factorlib/all_factors_library.json")
manager.add_factors_from_experiment(experiment, ...)
FactorLibraryManager.check_cache_status(library_path)
FactorLibraryManager.warm_cache_from_json(library_path)
```

---

## Key Data Structures

### AlphaAgentLoop (5-Step Workflow)

| Step | Method | Output Type |
|------|--------|-------------|
| 1 | `factor_propose()` | `AlphaAgentHypothesis` |
| 2 | `factor_construct()` | `QlibFactorExperiment` |
| 3 | `factor_calculate()` | `QlibFactorExperiment` with sub_workspace_list |
| 4 | `factor_backtest()` | `QlibFactorExperiment` with result |
| 5 | `feedback()` | `HypothesisFeedback` |

### Core Classes

| Class | Module | Purpose |
|-------|--------|---------|
| `AlphaAgentLoop` | `pipeline/loop.py` | Main workflow orchestrator |
| `EvolutionController` | `pipeline/evolution/controller.py` | Evolution phase management |
| `EvolutionConfig` | `pipeline/evolution/controller.py` | Evolution parameters |
| `StrategyTrajectory` | `pipeline/evolution/controller.py` | Factor evolution trajectory |
| `FactorLibraryManager` | `factors/library.py` | Factor library CRUD |
| `Trace` | `core/proposal.py` | Hypothesis history tracking |
| `QlibFactorExperiment` | `factors/experiment.py` | Experiment container with sub_tasks |

### Evolution Phases

- `ORIGINAL`: Initial exploration from planning directions
- `MUTATION`: Orthogonal exploration from parent trajectories
- `CROSSOVER`: Hybrid strategies from multiple parents

### Configuration Classes

| Class | Prefix | Purpose |
|-------|--------|---------|
| `AlphaAgentFactorBasePropSetting` | `QLIB_FACTOR_` | Main factor mining settings |
| `FactorBasePropSetting` | `QLIB_FACTOR_` | Traditional RD Loop mode |
| `LLMSettings` | - | LLM API configuration |
| `RDAgentSettings` | - | Workspace and cache settings |

---

## Dependencies

### Python Packages

| Package | Purpose |
|---------|---------|
| `rdagent==0.8.0` | RD-agent framework (pinned) |
| `pyqlib` | Quantitative research framework |
| `openai` | LLM API client |
| `langchain-community` | LLM tooling |
| `pandas`, `numpy` | Data processing |
| `pydantic-settings` | Configuration management |
| `tables` | HDF5 factor storage |
| `docker` | Container-based backtest (optional) |

### External Services

- **LLM API**: OpenAI-compatible endpoint (required for factor generation)
- **Qlib Data**: Local data files in `QLIB_DATA_DIR`

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `WORKSPACE_PATH` | `data/results/workspace` | Working directory |
| `QLIB_DATA_DIR` | - | Qlib data directory |
| `DATA_RESULTS_DIR` | `data/results` | Output directory |
| `FACTOR_LIBRARY_SUFFIX` | - | Custom factor library name |
| `USE_LOCAL` | `True` | Local vs Docker backtest |
| `CHAT_MODEL` | `gpt-4-turbo` | LLM model name |
| `openai_base_url` | - | LLM API endpoint |

---

## Constraints

1. **LLM Required**: Factor generation requires a working OpenAI-compatible API
2. **Qlib Data**: Must have Qlib data initialized before backtest
3. **Python Version**: Compatible with Python 3.9+
4. **SOTA Factor Merge Disabled**: Current implementation uses only new factors per round (not merged with historical SOTA)
5. **Evolution Mode**: Requires `evolution.enabled=true` in config; not default
6. **Planning Optional**: Planning phase is disabled by default

---

## Known Risks

1. **LLM Rate Limiting**: Long-running mining may hit API rate limits; built-in retry with exponential backoff
2. **Memory Growth**: Large factor experiments can consume significant memory during parallel execution
3. **JSON Parse Failures**: LLM responses may fail JSON parsing; handled with retry and `robust_json_parse()`
4. **Factor Expression Errors**: Invalid factor expressions may fail during calculation; captured in `CoderError`
5. **Parallel Evolution Deadlock**: File lock disabled during evolution mode to avoid cross-process deadlocks
6. **SOTA Factor Not Merged**: `runner.py` has SOTA factor merge disabled (`if False:`); factors are not accumulated across rounds

---

## Test Entry Points

### CLI Test

```bash
# Health check
quantaalpha health_check

# Dry-run backtest
python -m quantaalpha.backtest.run_backtest -c configs/backtest.yaml --dry-run

# Quick mine test (few steps)
quantaalpha mine --direction "momentum reversal" --step_n 5
```

### Programmatic Test

```python
# Test factor mining loop
from quantaalpha.pipeline.loop import AlphaAgentLoop
from quantaalpha.pipeline.settings import ALPHA_AGENT_FACTOR_PROP_SETTING

loop = AlphaAgentLoop(
    ALPHA_AGENT_FACTOR_PROP_SETTING,
    potential_direction="test direction",
    stop_event=None,
    use_local=True,
)
loop.run(step_n=5)

# Test backtest runner
from quantaalpha.backtest.runner import BacktestRunner
runner = BacktestRunner("configs/backtest.yaml")
runner.run(factor_source="alpha158_20")
```

### Test Files

- `/home/quan/testdata/aspipe_v4/backtest/start/backtest_alpha101.py` - Alpha101 backtest examples
- `/home/quan/testdata/aspipe_v4/backtest/qa/` - Qlib-based backtest tests

---

## Related Docs

- `docs/06-references/factormining-mvp-requirements.txt` - MVP requirements
- `docs/07-technical/quantaalpha-factor-mining-flow.md` - Detailed flow documentation
- `docs/drafts/2026-03-14-quantaalpha-structure.md` - Module structure overview
