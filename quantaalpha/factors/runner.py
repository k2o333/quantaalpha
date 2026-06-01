from __future__ import annotations

import gc
import ast
import pickle
import sys
from datetime import timedelta
from pathlib import Path
from typing import List
import json
import os
import numpy as np
import pandas as pd
import polars as pl
import yaml

from quantaalpha.core.conf import RD_AGENT_SETTINGS
from quantaalpha.core.utils import cache_with_pickle, multiprocessing_wrapper
from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS

from quantaalpha.components.runner import CachedRunner
from quantaalpha.core.exception import FactorEmptyError
from quantaalpha.factors.experiment import QlibFactorExperiment
from quantaalpha.factors.runner_polars import (
    KEY_COLUMNS,
    clean_factor_values,
    ensure_polars_factor_frame,
    factor_value_columns,
    join_factor_frames,
    metrics_to_polars,
    prepare_parquet_runtime_combined_factors,
    to_feature_storage_frame,
)
from quantaalpha.log import logger

DIRNAME = Path(__file__).absolute().resolve().parent
DIRNAME_local = Path.cwd()

# class QlibFactorExpWorkspace:

#     def prepare():
#         # create a folder;
#         # copy template
#         # place data inside the folder `combined_factors`
#         #
#     def execute():
#         de = DockerEnv()
#         de.run(local_path=self.ws_path, entry="qrun conf.yaml")

# TODO: supporting multiprocessing and keep previous results


def assert_backtest_result_parity(
    h5_result: pd.DataFrame | pd.Series | pl.DataFrame,
    parquet_result: pd.DataFrame | pd.Series | pl.DataFrame,
    *,
    rtol: float = 1e-9,
    atol: float = 1e-12,
) -> dict[str, float | int]:
    """Assert H5-fed and parquet-fed backtest metric results are equivalent."""

    if isinstance(h5_result, pl.DataFrame) or isinstance(parquet_result, pl.DataFrame):
        left = _metric_rows(h5_result)
        right = _metric_rows(parquet_result)
        common = sorted(set(left) & set(right))
        if not common:
            raise AssertionError("backtest parity has no common metrics")
        diffs = []
        for metric in common:
            left_value = left[metric]
            right_value = right[metric]
            if (left_value is None) != (right_value is None):
                raise AssertionError(f"backtest parity NaN mismatch for {metric}")
            if left_value is None:
                continue
            diff = abs(float(left_value) - float(right_value))
            diffs.append(diff)
            if not np.allclose([float(left_value)], [float(right_value)], rtol=rtol, atol=atol, equal_nan=True):
                raise AssertionError(f"backtest parity metric mismatch for {metric}: diff={diff}")
        return {
            "metric_count": int(len(common)),
            "max_abs_diff": float(max(diffs)) if diffs else 0.0,
            "rtol": float(rtol),
            "atol": float(atol),
        }

    import pandas as pd

    left = _metric_series(h5_result)
    right = _metric_series(parquet_result)
    common = left.index.intersection(right.index)
    if common.empty:
        raise AssertionError("backtest parity has no common metrics")
    left = left.loc[common].astype(float)
    right = right.loc[common].astype(float)
    diffs = (left - right).abs()
    comparable = ~(left.isna() | right.isna())
    nan_mismatch = left.isna() != right.isna()
    if bool(nan_mismatch.any()):
        metric = str(nan_mismatch[nan_mismatch].index[0])
        raise AssertionError(f"backtest parity NaN mismatch for {metric}")
    if not np.allclose(left[comparable], right[comparable], rtol=rtol, atol=atol, equal_nan=True):
        metric = str(diffs[comparable].idxmax())
        raise AssertionError(f"backtest parity metric mismatch for {metric}: diff={float(diffs[metric])}")
    return {
        "metric_count": int(len(common)),
        "max_abs_diff": float(diffs[comparable].max()) if bool(comparable.any()) else 0.0,
        "rtol": float(rtol),
        "atol": float(atol),
    }


def _metric_series(result: pd.DataFrame | pd.Series) -> pd.Series:
    import pandas as pd

    if isinstance(result, pd.Series):
        return result
    if "value" in result.columns:
        return result["value"]
    if result.shape[1] == 1:
        return result.iloc[:, 0]
    raise ValueError(f"unsupported backtest result schema for parity: {list(result.columns)}")


def _metric_rows(result: pd.DataFrame | pd.Series | pl.DataFrame) -> dict[str, float | None]:
    if isinstance(result, pl.DataFrame):
        if {"metric", "value"} <= set(result.columns):
            return {str(row["metric"]): (None if row["value"] is None else float(row["value"])) for row in result.select(["metric", "value"]).to_dicts()}
        if "value" in result.columns:
            return {str(idx): (None if value is None else float(value)) for idx, value in enumerate(result.get_column("value").to_list())}
        if result.width == 1:
            column = result.columns[0]
            return {str(idx): (None if value is None else float(value)) for idx, value in enumerate(result.get_column(column).to_list())}
        raise ValueError(f"unsupported polars backtest result schema for parity: {result.columns}")
    import pandas as pd

    series = _metric_series(result)
    return {str(index): (None if pd.isna(value) else float(value)) for index, value in series.items()}


def _prepare_parquet_runtime_combined_factors(
    h5_combined_factors: pd.DataFrame,
    parquet_runtime_new_factors: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    """Build a full combined factor frame with parquet-runtime values replacing new factor columns."""

    common_columns = [col for col in h5_combined_factors.columns if col in parquet_runtime_new_factors.columns]
    if not common_columns:
        raise AssertionError("parquet runtime combined parity has no common factor columns")

    common_index = h5_combined_factors.index.intersection(parquet_runtime_new_factors.index)
    if common_index.empty:
        raise AssertionError("parquet runtime combined parity has no common rows")

    parquet_combined = h5_combined_factors.loc[common_index].copy()
    parquet_replacement = parquet_runtime_new_factors.loc[common_index, common_columns]
    for column in common_columns:
        parquet_combined[column] = parquet_replacement[column]
    return parquet_combined, [str(col) for col in common_columns]


def compute_isolated_factor_signal_metrics(features: pd.DataFrame | pl.DataFrame, label: pd.Series | pd.DataFrame | pl.DataFrame) -> dict[str, dict[str, float] | dict[str, int]]:
    """Compute signal metrics for each factor column with its own values, not the combined model signal."""
    from quantaalpha.backtest.noqlib.signal_analysis import signal_metrics

    if not isinstance(features, pl.DataFrame):
        features = _pandas_factor_frame_to_polars(features)
    if not isinstance(label, pl.DataFrame):
        label = _pandas_factor_frame_to_polars(label, value_name="label")

    if isinstance(features, pl.DataFrame):
        factor_columns = [column for column in features.columns if column not in {"datetime", "instrument"}]
        isolated: dict[str, dict[str, float] | dict[str, int]] = {}
        metric_values: dict[str, list[float]] = {}
        for column in factor_columns:
            factor_frame = features.select(["datetime", "instrument", column]).rename({column: "pred"})
            metrics = signal_metrics(factor_frame, label)
            isolated[column] = metrics
            for metric_name, value in metrics.items():
                try:
                    metric_values.setdefault(metric_name, []).append(round(float(value), 12))
                except (TypeError, ValueError):
                    continue
        isolated["metric_unique_counts"] = {metric_name: len(set(values)) for metric_name, values in metric_values.items()}
        return isolated

    raise TypeError(f"unsupported isolated signal feature input type: {type(features).__name__}")


def _pandas_factor_frame_to_polars(frame: pd.DataFrame | pd.Series, *, value_name: str | None = None) -> pl.DataFrame:
    import pandas as pd

    if isinstance(frame, pd.Series):
        frame = frame.to_frame(name=value_name or frame.name or "value")
    else:
        frame = frame.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        if "feature" in frame.columns.get_level_values(0):
            frame = frame["feature"]
        else:
            frame.columns = [str(col[-1]) for col in frame.columns]
    if isinstance(frame.index, pd.MultiIndex) and {"datetime", "instrument"} <= set(frame.index.names):
        frame = frame.reset_index()
    if value_name and value_name not in frame.columns:
        value_columns = [column for column in frame.columns if column not in {"datetime", "instrument"}]
        if len(value_columns) == 1:
            frame = frame.rename(columns={value_columns[0]: value_name})
    return pl.from_pandas(frame).with_columns(
        pl.col("datetime").cast(pl.Datetime("ns"), strict=False),
        pl.col("instrument").cast(pl.Utf8),
    )


def compute_isolated_factor_portfolio_metrics(
    features: pd.DataFrame | pl.DataFrame,
    market: pd.DataFrame | pl.DataFrame,
    config: dict,
    backtester_cls,
) -> dict[str, dict[str, float]]:
    """Compute portfolio metrics for each factor column using that factor as the prediction signal."""
    if isinstance(features, pl.DataFrame):
        isolated: dict[str, dict[str, float]] = {}
        for column in factor_value_columns(features):
            prediction = features.select(["datetime", "instrument", pl.col(column).alias("score")]).drop_nulls("score")
            metrics, _report, _positions = backtester_cls(config, market).run(prediction)
            isolated[str(column)] = dict(metrics or {})
        return isolated

    factor_frame = _factor_feature_frame(features)
    isolated: dict[str, dict[str, float]] = {}
    for column in factor_frame.columns:
        prediction = factor_frame[column].rename(str(column)).dropna()
        metrics, _report, _positions = backtester_cls(config, market).run(prediction)
        isolated[str(column)] = dict(metrics or {})
    return isolated


def _factor_feature_frame(features: pd.DataFrame | pl.DataFrame) -> pd.DataFrame:
    import pandas as pd

    if isinstance(features, pl.DataFrame):
        value_columns = [column for column in features.columns if column not in {"datetime", "instrument"}]
        return features.select(["datetime", "instrument", *value_columns]).to_pandas().set_index(["datetime", "instrument"])
    if isinstance(features.columns, pd.MultiIndex):
        if "feature" in features.columns.get_level_values(0):
            return features["feature"]
        frame = features.copy()
        frame.columns = [str(col[-1]) for col in frame.columns]
        return frame
    return features.copy()


def _normalize_static_feature_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Restore feature names after polars reads pandas MultiIndex parquet columns as strings."""
    import pandas as pd

    if isinstance(frame.columns, pd.MultiIndex):
        if "feature" in frame.columns.get_level_values(0):
            return frame["feature"]
        frame = frame.copy()
        frame.columns = [str(col[-1]) for col in frame.columns]
        return frame

    restored_columns: list[str] = []
    changed = False
    for column in frame.columns:
        if isinstance(column, str) and column.startswith("(") and column.endswith(")"):
            try:
                parsed = ast.literal_eval(column)
            except (SyntaxError, ValueError):
                parsed = None
            if isinstance(parsed, tuple) and len(parsed) >= 2 and parsed[0] == "feature":
                restored_columns.append(str(parsed[-1]))
                changed = True
                continue
        restored_columns.append(str(column))
    if changed:
        frame = frame.copy()
        frame.columns = restored_columns
    return frame


class QlibFactorRunner(CachedRunner[QlibFactorExperiment]):
    MIN_VALID_RATIO = 0.6
    MAX_NAN_RATIO = 0.4
    MIN_UNIQUE_VALUES = 2
    MAX_PRE_BACKTEST_CORRELATION = 0.70
    """
    Docker run
    Everything in a folder
    - config.yaml
    - price-volume data dumper
    - `data.py` + Adaptor to Factor implementation
    - results in `mlflow`
    """

    def set_backtest_backend(self, backend: str | None) -> None:
        """Set the backend used by continuous mining backtest."""
        self._backtest_backend = str(backend or "qlib").strip().lower()

    def set_noqlib_config(self, config: dict | None) -> None:
        """Set no-qlib runtime options passed from continuous config."""
        self._noqlib_config = dict(config or {})

    def set_quality_overlay_config(self, config: dict | None) -> None:
        """Set quality overlay thresholds used by factor-value gates."""
        from quantaalpha.pipeline.quality_overlay_polars import load_quality_overlay_config

        self._quality_overlay_config = load_quality_overlay_config(config or {})

    def calculate_information_coefficient(self, concat_feature: pd.DataFrame, SOTA_feature_column_size: int, new_feature_columns_size: int) -> pd.DataFrame:
        import pandas as pd

        res = pd.Series(index=range(SOTA_feature_column_size * new_feature_columns_size))
        for col1 in range(SOTA_feature_column_size):
            for col2 in range(SOTA_feature_column_size, SOTA_feature_column_size + new_feature_columns_size):
                res.loc[col1 * new_feature_columns_size + col2 - SOTA_feature_column_size] = concat_feature.iloc[:, col1].corr(concat_feature.iloc[:, col2])
        return res

    def deduplicate_new_factors(self, SOTA_feature: pd.DataFrame | pl.DataFrame, new_feature: pd.DataFrame | pl.DataFrame) -> pd.DataFrame | pl.DataFrame:
        # calculate the IC between each column of SOTA_feature and new_feature
        # if the IC is larger than a threshold, remove the new_feature column
        # return the new_feature
        if isinstance(SOTA_feature, pl.DataFrame) or isinstance(new_feature, pl.DataFrame):
            if not isinstance(SOTA_feature, pl.DataFrame) or not isinstance(new_feature, pl.DataFrame):
                raise TypeError("polars factor dedup requires both SOTA and new factors to be polars DataFrames")
            return self._deduplicate_new_factors_polars(SOTA_feature, new_feature)

        import pandas as pd
        from pandarallel import pandarallel

        pandarallel.initialize(verbose=1)
        concat_feature = pd.concat([SOTA_feature, new_feature], axis=1)
        IC_max = concat_feature.groupby("datetime").parallel_apply(lambda x: self.calculate_information_coefficient(x, SOTA_feature.shape[1], new_feature.shape[1])).mean()
        IC_max.index = pd.MultiIndex.from_product([range(SOTA_feature.shape[1]), range(new_feature.shape[1])])
        IC_max = IC_max.unstack().max(axis=0)
        return new_feature.iloc[:, IC_max[IC_max < 0.99].index]

    def _deduplicate_new_factors_polars(self, sota_feature: pl.DataFrame, new_feature: pl.DataFrame) -> pl.DataFrame:
        sota_columns = factor_value_columns(sota_feature)
        new_columns = factor_value_columns(new_feature)
        if not sota_columns or not new_columns:
            return new_feature
        aligned = sota_feature.join(new_feature, on=list(KEY_COLUMNS), how="inner")
        if aligned.is_empty():
            return new_feature
        keep_columns: list[str] = []
        for new_column in new_columns:
            max_abs_corr = 0.0
            for sota_column in sota_columns:
                daily = (
                    aligned.select(["datetime", sota_column, new_column])
                    .drop_nulls([sota_column, new_column])
                    .group_by("datetime")
                    .agg(
                        pl.len().alias("rows"),
                        pl.corr(sota_column, new_column).abs().alias("corr"),
                    )
                    .filter(pl.col("rows") >= 2)
                    .drop_nulls("corr")
                )
                if daily.is_empty():
                    continue
                value = daily.get_column("corr").mean()
                if value is not None and np.isfinite(float(value)):
                    max_abs_corr = max(max_abs_corr, float(value))
            if max_abs_corr < 0.99:
                keep_columns.append(new_column)
        return new_feature.select([*KEY_COLUMNS, *keep_columns]) if keep_columns else new_feature.select(list(KEY_COLUMNS))

    @cache_with_pickle(CachedRunner.get_cache_key, CachedRunner.assign_cached_result)
    def develop(self, exp: QlibFactorExperiment, use_local: bool = True) -> QlibFactorExperiment:
        """
        Generate the experiment by processing and combining factor data,
        then passing the combined data to Docker or local environment for backtest results.
        """
        parquet_runtime_combined_factors = None
        backend = str(getattr(self, "_backtest_backend", os.environ.get("QUANTAALPHA_BACKTEST_BACKEND", "qlib")) or "qlib").strip().lower()

        if exp.based_experiments and exp.based_experiments[-1].result is None:
            exp.based_experiments[-1] = self.develop(exp.based_experiments[-1], use_local=use_local)

        if exp.based_experiments:
            SOTA_factor = None
            if len(exp.based_experiments) > 1:
                try:
                    SOTA_factor = self.process_factor_data(exp.based_experiments)
                except FactorEmptyError:
                    logger.warning("SOTA factors processing failed, continuing with new factors only.")
                    SOTA_factor = None

            # Process the new factors data
            try:
                new_factors = self.process_factor_data(exp)
                parquet_runtime_new_factors = getattr(self, "_last_parquet_runtime_factors", None)
            except FactorEmptyError as e:
                logger.error(f"Failed to process new factors: {e}")
                # Try manual factor execution
                logger.info("Attempting to manually execute factors...")
                for ws in exp.sub_workspace_list:
                    if ws is None or "factor.py" not in getattr(ws, "code_dict", {}):
                        continue
                    if not (ws.workspace_path / "result.h5").exists():
                        try:
                            # Ensure symlink exists
                            data_source = Path(FACTOR_COSTEER_SETTINGS.data_folder).absolute()
                            if not data_source.is_absolute():
                                data_source = Path(__file__).parent.parent.parent.parent.parent / FACTOR_COSTEER_SETTINGS.data_folder
                            daily_pv_link = ws.workspace_path / "daily_pv.h5"
                            if not daily_pv_link.exists() and (data_source / "daily_pv.h5").exists():
                                os.symlink(str(data_source / "daily_pv.h5"), str(daily_pv_link))

                            # Execute factor
                            import subprocess

                            env = os.environ.copy()
                            project_root = Path(__file__).parent.parent.parent.parent
                            env["PYTHONPATH"] = str(project_root) + os.pathsep + env.get("PYTHONPATH", "")
                            subprocess.check_output(
                                [sys.executable, str(ws.workspace_path / "factor.py")],
                                cwd=str(ws.workspace_path),
                                stderr=subprocess.STDOUT,
                                env=env,
                                timeout=1200,
                            )
                        except Exception as exec_e:
                            logger.warning(f"Failed to manually execute factor {ws.workspace_path}: {exec_e}")

                # Retry processing factor data
                try:
                    new_factors = self.process_factor_data(exp)
                    parquet_runtime_new_factors = getattr(self, "_last_parquet_runtime_factors", None)
                except FactorEmptyError:
                    raise FactorEmptyError("No valid factor data found to merge after manual execution attempt.")

            if new_factors.is_empty():
                raise FactorEmptyError("No valid factor data found to merge.")

            # Combine the SOTA factor and new factors if SOTA factor exists
            if SOTA_factor is not None and not SOTA_factor.is_empty():
                new_factors = self.deduplicate_new_factors(SOTA_factor, new_factors)
                if new_factors.is_empty():
                    raise FactorEmptyError("No valid factor data found to merge.")
                combined_factors = join_factor_frames([SOTA_factor, new_factors], how="inner").drop_nulls(subset=factor_value_columns(SOTA_factor) + factor_value_columns(new_factors))
            else:
                combined_factors = new_factors

            if str(os.environ.get("QUANTAALPHA_FACTOR_CODER_RUNTIME", "")).strip().lower() == "dual_h5_parquet" and parquet_runtime_new_factors is not None and not parquet_runtime_new_factors.is_empty():
                parquet_runtime_combined_factors, parquet_runtime_compared_columns = prepare_parquet_runtime_combined_factors(combined_factors, parquet_runtime_new_factors)
                for column in parquet_runtime_compared_columns:
                    from quantaalpha.factors.coder.runtime_data import assert_factor_frame_parity

                    assert_factor_frame_parity(
                        combined_factors.select([*KEY_COLUMNS, column]),
                        parquet_runtime_combined_factors.select([*KEY_COLUMNS, column]),
                        factor_name=str(column),
                    )
                from quantaalpha.continuous.artifact_policy import runtime_parity_artifacts_enabled

                if runtime_parity_artifacts_enabled():
                    parity_path = exp.experiment_workspace.workspace_path / "factor_runtime_combined_parity.json"
                    parity_path.write_text(
                        json.dumps(
                            {
                                "rows": int(parquet_runtime_combined_factors.height),
                                "columns": [str(col) for col in parquet_runtime_combined_factors.columns],
                                "compared_columns": parquet_runtime_compared_columns,
                                "status": "passed",
                            },
                            ensure_ascii=True,
                            indent=2,
                            sort_keys=True,
                        ),
                        encoding="utf-8",
                    )

            combined_factors = self._apply_combined_quality_gate(combined_factors)
            if combined_factors.is_empty():
                raise FactorEmptyError("No valid factor data remained after combined quality gate.")

            if len(factor_value_columns(combined_factors)) >= 2:
                logger.info(f"Cleaned factor correlation: \n\n{combined_factors.select(factor_value_columns(combined_factors)).corr()}\n")

            combined_factors = combined_factors.sort(list(KEY_COLUMNS))
            if parquet_runtime_combined_factors is not None and not parquet_runtime_combined_factors.is_empty():
                parquet_runtime_combined_factors = parquet_runtime_combined_factors.sort(list(KEY_COLUMNS))

            logger.info(f"Factor values this round: \n\n{combined_factors.tail()}\n\n")

            # Save the combined factors to the workspace (parquet format for qlib compatibility)
            parquet_path = exp.experiment_workspace.workspace_path / "combined_factors_df.parquet"
            to_feature_storage_frame(combined_factors).write_parquet(parquet_path)
            logger.info(f"Saved combined factors to {parquet_path}")

        # Run backtest (local or Docker). Config name must match factor_template files (e.g. conf_baseline.yaml).
        config_name = "conf_baseline.yaml" if len(exp.based_experiments) == 0 else "conf_combined_factors.yaml"
        factor_count = 0
        if hasattr(exp, "sub_workspace_list") and exp.sub_workspace_list is not None:
            factor_count = sum(1 for workspace in exp.sub_workspace_list if workspace is not None)
        workspace_path = getattr(exp.experiment_workspace, "workspace_path", "<unknown>")
        logger.info(f"Execute factor backtest (Use {'Local' if use_local else 'Docker container'}): {config_name}; workspace={workspace_path}; factor_count={factor_count}; backend={backend}")

        if backend in {"noqlib", "vnpy"}:
            result = self._develop_noqlib(exp, config_name, backend=backend)
            if parquet_runtime_combined_factors is not None and str(os.environ.get("QUANTAALPHA_FACTOR_CODER_RUNTIME", "")).strip().lower() == "dual_h5_parquet":
                parquet_path = exp.experiment_workspace.workspace_path / "combined_factors_df.parquet"
                h5_combined_backup = pl.read_parquet(parquet_path)
                try:
                    to_feature_storage_frame(parquet_runtime_combined_factors).write_parquet(parquet_path)
                    parquet_result = self._develop_noqlib(exp, config_name, backend=backend)
                    backtest_parity = assert_backtest_result_parity(result, parquet_result)
                    from quantaalpha.continuous.artifact_policy import runtime_parity_artifacts_enabled

                    if runtime_parity_artifacts_enabled():
                        (exp.experiment_workspace.workspace_path / "factor_runtime_backtest_parity.json").write_text(
                            json.dumps(backtest_parity, ensure_ascii=True, indent=2, sort_keys=True),
                            encoding="utf-8",
                        )
                    logger.info(f"Parquet runtime backtest parity passed: {backtest_parity}")
                finally:
                    h5_combined_backup.write_parquet(parquet_path)
            exp.result = result
            return exp
        if backend != "qlib":
            raise ValueError(f"unsupported factor mining backtest backend: {backend}")

        # Ensure workspace and config are ready (execute() does not call before_execute()).
        exp.experiment_workspace.before_execute()
        logger.info(f"Backtest workspace ready: workspace={workspace_path}; config={config_name}")

        # execute() returns (result_df, execute_qlib_log) or (None, execute_qlib_log)
        result_tuple = exp.experiment_workspace.execute(qlib_config_name=config_name, run_env={})
        logger.info(f"Backtest execution finished: workspace={workspace_path}; config={config_name}")

        # Unpack tuple; take first element (DataFrame)
        result = result_tuple[0] if isinstance(result_tuple, tuple) else result_tuple

        # rdagent QlibFBWorkspace.execute() returns pd.Series (via .iloc[:, 0]).
        # Normalize to DataFrame for consistent downstream consumption.
        import pandas as pd

        if isinstance(result, pd.Series):
            logger.info(f"Normalizing backtest result from Series to DataFrame (len={len(result)})")
            result = result.to_frame(name="value")

        if result is not None:
            logger.info(f"Backtesting results: \n{result.iloc[2:] if hasattr(result, 'iloc') else result}")
        else:
            logger.warning("Backtesting result is None. Check the execution logs above for errors.")
            if isinstance(result_tuple, tuple) and len(result_tuple) > 1:
                logger.info(f"Execution log: {result_tuple[1][:500]}...")

        exp.result = result

        return exp

    def _develop_noqlib(self, exp: QlibFactorExperiment, config_name: str, backend: str = "noqlib") -> pl.DataFrame:
        """Run the factor-template backtest without importing qlib."""
        from quantaalpha.backtest.noqlib.data_provider import NoQlibMarketDataProvider
        from quantaalpha.backtest.noqlib.dataset import NoQlibDatasetBuilder
        from quantaalpha.backtest.noqlib.expression_engine import NoQlibExpressionEngine
        from quantaalpha.backtest.noqlib.model import NoQlibModelRunner
        from quantaalpha.backtest.noqlib.portfolio import NoQlibTopkDropoutBacktester
        from quantaalpha.backtest.noqlib.signal_analysis import signal_metrics

        template_path = DIRNAME / "factor_template" / config_name
        with template_path.open("r", encoding="utf-8") as fh:
            qlib_cfg = yaml.safe_load(fh) or {}
        noqlib_cfg = self._factor_template_to_noqlib_config(qlib_cfg, backend=backend)
        workspace_path = exp.experiment_workspace.workspace_path

        market_provider = NoQlibMarketDataProvider(noqlib_cfg)
        if backend == "vnpy":
            from quantaalpha.backtest.vnpy.expression_engine import VnpyExpressionEngine

            market_frame = market_provider.load_market_frame()
            expression_engine = VnpyExpressionEngine(market_frame)
        else:
            market = market_provider.load_market_frame()
            expression_engine = NoQlibExpressionEngine(market)
        features = self._load_noqlib_template_features(
            config=qlib_cfg,
            expression_engine=expression_engine,
            workspace_path=workspace_path,
        )
        labels = expression_engine.compute_label(noqlib_cfg.get("dataset", {}).get("label", "Ref($close, -2)/Ref($close, -1) - 1"))
        isolated_factor_metrics = compute_isolated_factor_signal_metrics(features, labels)
        # Free expression engine — features/labels are computed
        del expression_engine
        if backend == "vnpy":
            del market_frame
        gc.collect()
        dataset = NoQlibDatasetBuilder(noqlib_cfg).build(features, labels)
        # Labels are no longer needed; features are kept for per-factor portfolio metrics.
        del labels
        gc.collect()
        prediction = NoQlibModelRunner(noqlib_cfg).fit_predict(dataset)
        label_for_signal = dataset.raw_labels if dataset.raw_labels is not None else dataset.combined.select(["datetime", "instrument", dataset.label_column])
        metrics = signal_metrics(prediction, label_for_signal)
        try:
            from quantaalpha.pipeline.quality_overlay_polars import compute_oos_rank_ic_metrics_polars, compute_tradability_metrics_polars

            overlay_cfg = getattr(self, "_quality_overlay_config", {}) or {}
            full_cfg = dict(overlay_cfg.get("full_backtest") or {})
            oos_cfg = dict(overlay_cfg.get("oos") or {})
            cost_rate = float(full_cfg.get("cost_rate", 0.001) or 0.0)
            n_groups = int(full_cfg.get("monotonicity_groups", 5) or 5)
            metrics.update(
                compute_tradability_metrics_polars(
                    prediction,
                    label_for_signal,
                    cost_rate=cost_rate,
                    n_groups=n_groups,
                )
            )
            metrics.update(
                compute_oos_rank_ic_metrics_polars(
                    prediction,
                    label_for_signal,
                    recent_trading_days=int(oos_cfg.get("recent_trading_days", 250) or 250),
                )
            )
        except Exception as exc:
            logger.warning(f"Failed to compute quality overlay noqlib metrics: {exc}")
        if backend == "vnpy":
            market = market_provider.load_market_frame()
        isolated_portfolio_metrics = compute_isolated_factor_portfolio_metrics(
            features,
            market=market,
            config=noqlib_cfg,
            backtester_cls=NoQlibTopkDropoutBacktester,
        )
        for factor_name, portfolio_metrics in isolated_portfolio_metrics.items():
            if isinstance(isolated_factor_metrics.get(factor_name), dict):
                isolated_factor_metrics[factor_name].update(portfolio_metrics)
            else:
                isolated_factor_metrics[factor_name] = portfolio_metrics
        setattr(exp, "_isolated_factor_metrics", isolated_factor_metrics)
        for task in getattr(exp, "sub_tasks", []) or []:
            factor_name = str(getattr(task, "factor_name", getattr(task, "name", "")) or "")
            factor_metrics = isolated_factor_metrics.get(factor_name)
            if isinstance(factor_metrics, dict):
                setattr(task, "isolated_backtest_metrics", factor_metrics)
        logger.info(f"metric_isolation: computed isolated factor metrics factor_count={len([key for key in isolated_factor_metrics if key != 'metric_unique_counts'])} unique_counts={isolated_factor_metrics.get('metric_unique_counts', {})}")
        portfolio_metrics, _daily_report, _positions = NoQlibTopkDropoutBacktester(noqlib_cfg, market).run(prediction)
        # Free large intermediates after backtest
        del prediction, dataset, features, market
        gc.collect()
        metrics.update(portfolio_metrics)
        result = metrics_to_polars(metrics)
        logger.info(f"{backend} backtesting results: \n{result}")
        return result

    def _factor_template_to_noqlib_config(self, qlib_cfg: dict, backend: str = "noqlib") -> dict:
        handler = qlib_cfg.get("data_handler_config", {})
        dataset_cfg = qlib_cfg.get("task", {}).get("dataset", {}).get("kwargs", {})
        model_cfg = qlib_cfg.get("task", {}).get("model", {})
        port_cfg = qlib_cfg.get("port_analysis_config", {})
        data_loader_cfg = handler.get("data_loader", {}).get("kwargs", {}).get("config", {})
        label_exprs = data_loader_cfg.get("label", [["Ref($close, -2)/Ref($close, -1) - 1"], ["LABEL0"]])[0]
        runtime_options = dict(getattr(self, "_noqlib_config", {}) or {})
        runtime_segments = runtime_options.pop("segments", None)
        if isinstance(runtime_options.get("standard_frame"), dict):
            runtime_options["standard_frame"] = _market_only_standard_frame_config(runtime_options["standard_frame"])
        workspace_root = Path(__file__).resolve().parents[4]
        noqlib_cfg = {
            "data": {
                "market": handler.get("instruments", qlib_cfg.get("market", "csi300")),
                "start_time": str(handler.get("start_time")),
                "end_time": str(handler.get("end_time")),
            },
            "dataset": {
                "label": str(label_exprs[0]),
                "segments": runtime_segments or dataset_cfg.get("segments", {}),
            },
            "model": {
                "type": "lgb",
                "params": dict(model_cfg.get("kwargs", {})),
            },
            "backtest": port_cfg,
            "backtest_runtime": {
                "backend": backend,
                "noqlib": {
                    "project_root": str(workspace_root),
                    "app5_storage_root": os.environ.get(
                        "QUANTAALPHA_NOQLIB_APP5_STORAGE_ROOT",
                        str(workspace_root / "data" / "app5"),
                    ),
                    "daily_interface": os.environ.get("QUANTAALPHA_NOQLIB_DAILY_INTERFACE", "daily"),
                    "benchmark_instruments": [str(port_cfg.get("backtest", {}).get("benchmark", "SH000300"))],
                },
            },
        }
        noqlib_cfg["backtest_runtime"]["noqlib"].update(runtime_options)
        # 当 benchmark_mode=mean 时，不需要指数行情数据，改为横截面均值 benchmark
        benchmark_mode = noqlib_cfg["backtest_runtime"]["noqlib"].get("benchmark_mode")
        if str(benchmark_mode).lower() == "mean":
            noqlib_cfg["backtest"]["backtest"]["benchmark"] = "mean"
            noqlib_cfg["backtest_runtime"]["noqlib"]["benchmark_instruments"] = []
        instruments = _resolve_noqlib_instruments(noqlib_cfg["backtest_runtime"]["noqlib"])
        if instruments:
            noqlib_cfg["backtest_runtime"]["noqlib"]["instruments"] = instruments
        return noqlib_cfg

    def _load_noqlib_template_features(self, *, config: dict, expression_engine, workspace_path: Path) -> pl.DataFrame:
        handler = config.get("data_handler_config", {})
        data_loader = handler.get("data_loader", {})
        frames: list[pl.DataFrame] = []
        for loader_cfg in _iter_loader_configs(data_loader):
            class_name = str(loader_cfg.get("class", ""))
            kwargs = loader_cfg.get("kwargs", {})
            if class_name.endswith("QlibDataLoader"):
                raw_config = kwargs.get("config", {})
                feature_cfg = raw_config.get("feature", [])
                if len(feature_cfg) >= 2:
                    expressions, names = feature_cfg[0], feature_cfg[1]
                    factor_defs = [{"factor_id": str(name), "factor_name": str(name), "factor_expression": str(expr)} for expr, name in zip(expressions, names)]
                    result = expression_engine.compute(factor_defs)
                    if not isinstance(result, pl.DataFrame):
                        raise TypeError(f"noqlib expression engine must return polars DataFrame, got {type(result).__name__}")
                    frames.append(ensure_polars_factor_frame(result))
            elif class_name.endswith("StaticDataLoader"):
                static_path = workspace_path / str(kwargs.get("config", "combined_factors_df.parquet"))
                frame = pl.read_parquet(static_path)
                frames.append(ensure_polars_factor_frame(frame))
        if not frames:
            raise ValueError("noqlib factor-template features are empty")
        return join_factor_frames(frames, how="inner")

    def _validate_factor_frame(self, df: pd.DataFrame | pl.DataFrame) -> pd.DataFrame | pl.DataFrame | None:
        if isinstance(df, pl.DataFrame):
            cleaned = clean_factor_values(df)
            keep_columns: list[str] = []
            for col in factor_value_columns(cleaned):
                stats = cleaned.select(
                    pl.len().alias("total"),
                    pl.col(col).is_null().mean().alias("nan_ratio"),
                    pl.col(col).drop_nulls().n_unique().alias("unique_count"),
                ).row(0, named=True)
                total = int(stats["total"])
                if total == 0:
                    logger.warning(f"Skipping factor {col}: empty output.")
                    continue
                nan_ratio = float(stats["nan_ratio"] or 0.0)
                valid_ratio = 1.0 - nan_ratio
                unique_count = int(stats["unique_count"] or 0)
                if valid_ratio < self.MIN_VALID_RATIO or nan_ratio > self.MAX_NAN_RATIO:
                    logger.warning(f"Skipping factor {col}: valid_ratio={valid_ratio:.3f}, nan_ratio={nan_ratio:.3f}.")
                    continue
                if unique_count < self.MIN_UNIQUE_VALUES:
                    logger.warning(f"Skipping factor {col}: unique non-null values={unique_count}.")
                    continue
                keep_columns.append(col)
            if not keep_columns:
                return None
            return cleaned.select([*KEY_COLUMNS, *keep_columns]).sort(list(KEY_COLUMNS))

        import pandas as pd

        valid_columns = []
        for col in df.columns:
            series = df[col].replace([np.inf, -np.inf], np.nan)
            total = len(series)
            if total == 0:
                logger.warning(f"Skipping factor {col}: empty output.")
                continue
            nan_ratio = float(series.isna().mean())
            valid_ratio = 1.0 - nan_ratio
            non_null = series.dropna()
            unique_count = int(non_null.nunique()) if not non_null.empty else 0
            if valid_ratio < self.MIN_VALID_RATIO or nan_ratio > self.MAX_NAN_RATIO:
                logger.warning(f"Skipping factor {col}: valid_ratio={valid_ratio:.3f}, nan_ratio={nan_ratio:.3f}.")
                continue
            if unique_count < self.MIN_UNIQUE_VALUES:
                logger.warning(f"Skipping factor {col}: unique non-null values={unique_count}.")
                continue
            valid_columns.append(series.to_frame(name=col))
        if not valid_columns:
            return None
        return pd.concat(valid_columns, axis=1)

    def _apply_combined_quality_gate(self, df: pd.DataFrame | pl.DataFrame) -> pd.DataFrame | pl.DataFrame:
        if isinstance(df, pl.DataFrame):
            from quantaalpha.pipeline.quality_overlay_polars import filter_pre_backtest_survivors_polars

            overlay_cfg = getattr(self, "_quality_overlay_config", None)
            if overlay_cfg is not None:
                pre_backtest_cfg = dict(overlay_cfg.get("pre_backtest") or {})
                filtered, diagnostics = filter_pre_backtest_survivors_polars(df, pre_backtest_cfg)
                self._last_pre_backtest_diagnostics = diagnostics
                for col, detail in diagnostics.items():
                    if not detail.get("passed"):
                        logger.warning(f"Dropping factor {col} from combined dataframe: pre_backtest_reasons={detail.get('failure_reasons')}, metrics={detail.get('metrics')}.")
                if filtered.is_empty():
                    return filtered
                return self._prune_correlated_candidates(filtered)

            cleaned = clean_factor_values(df)
            keep_columns: list[str] = []
            nan_stats = cleaned.select(*[pl.col(col).is_null().mean().alias(col) for col in factor_value_columns(cleaned)]).row(0, named=True)
            for col in factor_value_columns(cleaned):
                nan_ratio = float(nan_stats.get(col) or 0.0)
                if nan_ratio <= self.MAX_NAN_RATIO:
                    keep_columns.append(col)
                else:
                    logger.warning(f"Dropping factor {col} from combined dataframe: nan_ratio={nan_ratio:.3f}.")
            cleaned = cleaned.select([*KEY_COLUMNS, *keep_columns]) if keep_columns else cleaned.select(list(KEY_COLUMNS))
            if cleaned.is_empty() or not keep_columns:
                return cleaned
            cleaned = cleaned.drop_nulls(subset=keep_columns)
            keep_columns = [col for col in keep_columns if int(cleaned.select(pl.col(col).drop_nulls().n_unique()).item() or 0) >= self.MIN_UNIQUE_VALUES]
            return self._prune_correlated_candidates(cleaned.select([*KEY_COLUMNS, *keep_columns]))

        from quantaalpha.pipeline.quality_overlay import filter_pre_backtest_survivors

        overlay_cfg = getattr(self, "_quality_overlay_config", None)
        if overlay_cfg is not None:
            pre_backtest_cfg = dict(overlay_cfg.get("pre_backtest") or {})
            filtered, diagnostics = filter_pre_backtest_survivors(df, pre_backtest_cfg)
            self._last_pre_backtest_diagnostics = diagnostics
            for col, detail in diagnostics.items():
                if not detail.get("passed"):
                    logger.warning(f"Dropping factor {col} from combined dataframe: pre_backtest_reasons={detail.get('failure_reasons')}, metrics={detail.get('metrics')}.")
            if filtered.empty:
                return filtered
            return self._prune_correlated_candidates(filtered)

        cleaned = df.replace([np.inf, -np.inf], np.nan)
        column_nan_ratio = cleaned.isna().mean()
        keep_columns = column_nan_ratio[column_nan_ratio <= self.MAX_NAN_RATIO].index.tolist()
        dropped_columns = sorted(set(cleaned.columns) - set(keep_columns))
        for col in dropped_columns:
            logger.warning(f"Dropping factor {col} from combined dataframe: nan_ratio={float(column_nan_ratio[col]):.3f}.")
        cleaned = cleaned.loc[:, keep_columns]
        if cleaned.empty:
            return cleaned
        cleaned = cleaned.dropna(how="any")
        keep_columns = [col for col in cleaned.columns if cleaned[col].nunique() >= self.MIN_UNIQUE_VALUES]
        cleaned = cleaned.loc[:, keep_columns]
        return self._prune_correlated_candidates(cleaned)

    def _prune_correlated_candidates(self, df: pd.DataFrame | pl.DataFrame) -> pd.DataFrame | pl.DataFrame:
        if isinstance(df, pl.DataFrame):
            value_columns = factor_value_columns(df)
            if len(value_columns) < 2:
                return df
            corr = df.select(value_columns).corr()
            dropped: set[str] = set()
            for left_idx, left in enumerate(value_columns):
                if left in dropped:
                    continue
                for right_idx, right in enumerate(value_columns[left_idx + 1 :], start=left_idx + 1):
                    if right in dropped:
                        continue
                    value = corr.row(left_idx)[right_idx]
                    if value is None or not np.isfinite(float(value)) or float(value) <= self.MAX_PRE_BACKTEST_CORRELATION:
                        continue
                    dropped.add(right)
                    logger.warning(f"Dropping factor {right} from combined dataframe: pre_backtest_correlation={float(value):.3f} with {left}.")
            if not dropped:
                return df
            keep_columns = [col for col in value_columns if col not in dropped]
            return df.select([*KEY_COLUMNS, *keep_columns])

        import pandas as pd

        if df.shape[1] < 2:
            return df

        corr = df.corr().abs()
        dropped: set[str] = set()
        for left_idx, left in enumerate(corr.columns):
            if left in dropped:
                continue
            for right in corr.columns[left_idx + 1 :]:
                if right in dropped:
                    continue
                value = corr.loc[left, right]
                if pd.isna(value) or float(value) <= self.MAX_PRE_BACKTEST_CORRELATION:
                    continue
                dropped.add(right)
                logger.warning(f"Dropping factor {right} from combined dataframe: pre_backtest_correlation={float(value):.3f} with {left}.")
        if not dropped:
            return df
        keep_columns = [col for col in df.columns if col not in dropped]
        return df.loc[:, keep_columns]

    def process_factor_data(self, exp_or_list: List[QlibFactorExperiment] | QlibFactorExperiment) -> pl.DataFrame:
        """
        Process and combine factor data from experiment implementations.

        Args:
            exp (ASpecificExp): The experiment containing factor data.

        Returns:
            pl.DataFrame: Combined factor data with explicit datetime/instrument keys.
        """
        if isinstance(exp_or_list, QlibFactorExperiment):
            exp_or_list = [exp_or_list]
        factor_dfs: list[pl.DataFrame] = []
        parquet_factor_dfs: list[pl.DataFrame] = []

        # Collect all exp's dataframes
        for exp in exp_or_list:
            valid_implementations = [implementation for implementation in exp.sub_workspace_list if implementation is not None and "factor.py" in getattr(implementation, "code_dict", {})]
            if not valid_implementations:
                continue
            # Iterate over sub-implementations and execute them to get each factor data
            message_and_df_list = multiprocessing_wrapper(
                [(implementation.execute, ("All",)) for implementation in valid_implementations],
                n=RD_AGENT_SETTINGS.multi_proc_n,
            )
            for idx, (message, df) in enumerate(message_and_df_list):
                if df is None or idx >= len(valid_implementations):
                    continue
                factor_name = str(getattr(valid_implementations[idx].target_task, "factor_name", f"factor_{idx}"))
                try:
                    factor_frame = ensure_polars_factor_frame(df, factor_name=factor_name)
                except (TypeError, ValueError) as exc:
                    logger.warning(f"Skipping factor {factor_name}: invalid polars factor result: {exc}")
                    continue
                time_diffs = factor_frame.select(pl.col("datetime").sort().diff().drop_nulls().unique()).to_series().to_list()
                if timedelta(minutes=1) in set(time_diffs):
                    continue
                validated_df = self._validate_factor_frame(factor_frame)
                if isinstance(validated_df, pl.DataFrame) and not validated_df.is_empty():
                    factor_dfs.append(validated_df)
                    if str(os.environ.get("QUANTAALPHA_FACTOR_CODER_RUNTIME", "")).strip().lower() == "dual_h5_parquet":
                        parquet_path = valid_implementations[idx].workspace_path / "result.parquet"
                        if parquet_path.exists():
                            from quantaalpha.factors.coder.runtime_data import (
                                assert_factor_frame_parity,
                                read_parquet_factor_result,
                            )

                            parquet_df = read_parquet_factor_result(parquet_path, factor_name=factor_name)
                            assert_factor_frame_parity(
                                validated_df.select([*KEY_COLUMNS, factor_name]),
                                parquet_df,
                                factor_name=factor_name,
                            )
                            parquet_validated = self._validate_factor_frame(parquet_df)
                            if isinstance(parquet_validated, pl.DataFrame) and not parquet_validated.is_empty():
                                parquet_factor_dfs.append(parquet_validated)

        # Combine all successful factor data
        if factor_dfs:
            self._last_parquet_runtime_factors = join_factor_frames(parquet_factor_dfs, how="inner") if parquet_factor_dfs else None
            return join_factor_frames(factor_dfs, how="inner")
        else:
            self._last_parquet_runtime_factors = None
            raise FactorEmptyError("No valid factor data found to merge.")


def _iter_loader_configs(loader_config: dict) -> list[dict]:
    """Return leaf loader configs from qlib DataLoader or NestedDataLoader config."""
    class_name = str(loader_config.get("class", ""))
    kwargs = loader_config.get("kwargs", {})
    if class_name.endswith("NestedDataLoader"):
        return list(kwargs.get("dataloader_l", []))
    return [loader_config]


def _market_only_standard_frame_config(config: dict) -> dict:
    """Keep standard-frame keys needed by noqlib market and expression data."""
    keep = {
        "daily_interface",
        "adjustment",
        "include_markets",
        "exclude_markets",
        "materialized_cache_root",
    }
    return {key: value for key, value in config.items() if key in keep}


def _resolve_noqlib_instruments(noqlib_options: dict) -> list[str]:
    """Resolve no-qlib stock universe from config, file, or environment."""
    instruments = noqlib_options.get("instruments")
    if instruments:
        return [str(item) for item in instruments]
    instruments_csv = os.environ.get("QUANTAALPHA_NOQLIB_INSTRUMENTS")
    if instruments_csv:
        return [item.strip() for item in instruments_csv.split(",") if item.strip()]
    instruments_path = noqlib_options.get("instruments_path") or os.environ.get("QUANTAALPHA_NOQLIB_INSTRUMENTS_PATH")
    if not instruments_path:
        return []
    path = Path(instruments_path)
    if not path.is_absolute():
        workspace_root = Path(__file__).resolve().parents[4]
        project_root = Path(noqlib_options.get("project_root") or workspace_root).expanduser().resolve()
        if not (project_root / "docs" / "01-govern").exists():
            project_root = workspace_root
        path = project_root / path
    if not path.exists():
        raise FileNotFoundError(f"noqlib instruments_path not found: {path}")
    if path.suffix.lower() == ".json":
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("instruments", [])
        return [str(item) for item in data]
    instruments = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        instruments.append(stripped.split()[0])
    return instruments
