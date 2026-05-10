"""
Factor workflow with session control
"""

from typing import Any, Optional

import fire

from quantaalpha.pipeline.settings import FACTOR_BACK_TEST_PROP_SETTING
from quantaalpha.pipeline.loop import BacktestLoop
from quantaalpha.backtest.runner import BacktestRunner


def main(path=None, step_n=None, factor_path=None):
    """
    Auto R&D Evolving loop for fintech factors.

    You can continue running session by

    .. code-block:: python

        quantaalpha backtest --factor_path "/path/to/factor_file.csv"

    """
    if path is None:
        model_loop = BacktestLoop(
            FACTOR_BACK_TEST_PROP_SETTING, factor_path=factor_path
        )
    else:
        model_loop = BacktestLoop.load(path)
    model_loop.run(step_n=step_n)


def run_real_backtest(
    config_path: str,
    library_path: str,
    factor_ids: Optional[str] = None,
    status_filter: Optional[str] = None,
    output_name: Optional[str] = None,
    skip_uncached: bool = False,
    backend: Optional[str] = None,
) -> dict:
    """
    Run backtest on factors from a factor library JSON file.

    This function provides internal integration between the factor library
    and the backtest runner, exposing real backtest results for consumption.

    Args:
        config_path: Path to backtest YAML config
        library_path: Path to factor library JSON file
        factor_ids: Comma-separated list of factor IDs to backtest (optional)
        status_filter: Only backtest factors with this evaluation status (optional)
        output_name: Output name prefix for results (optional)
        skip_uncached: Skip factors without precomputed cache (default False)

    Returns:
        Dict with 'metrics', 'factors_backtested', and 'library_path'
    """
    factor_id_list = None
    if factor_ids:
        factor_id_list = [fid.strip() for fid in factor_ids.split(",") if fid.strip()]

    if backend is None:
        runner = BacktestRunner(config_path)
    else:
        from quantaalpha.backtest.facade import BacktestFacade

        runner = BacktestFacade(config_path, backend=backend)
    result = runner.run_from_library(
        library_path=library_path,
        factor_ids=factor_id_list,
        status_filter=status_filter,
        output_name=output_name,
        skip_uncached=skip_uncached,
    )
    return result


if __name__ == "__main__":
    fire.Fire(
        {
            "main": main,
            "run_real_backtest": run_real_backtest,
        }
    )
