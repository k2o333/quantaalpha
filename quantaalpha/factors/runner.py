import gc
import pickle
import sys
from pathlib import Path
from typing import List
import json
import os
import numpy as np
import pandas as pd
import yaml
from pandarallel import pandarallel

from quantaalpha.core.conf import RD_AGENT_SETTINGS
from quantaalpha.core.utils import cache_with_pickle, multiprocessing_wrapper
from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS

pandarallel.initialize(verbose=1)

from quantaalpha.components.runner import CachedRunner
from quantaalpha.core.exception import FactorEmptyError
from quantaalpha.log import logger
from quantaalpha.factors.experiment import QlibFactorExperiment

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
    h5_result: pd.DataFrame | pd.Series,
    parquet_result: pd.DataFrame | pd.Series,
    *,
    rtol: float = 1e-9,
    atol: float = 1e-12,
) -> dict[str, float | int]:
    """Assert H5-fed and parquet-fed backtest metric results are equivalent."""

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
    if isinstance(result, pd.Series):
        return result
    if "value" in result.columns:
        return result["value"]
    if result.shape[1] == 1:
        return result.iloc[:, 0]
    raise ValueError(f"unsupported backtest result schema for parity: {list(result.columns)}")


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

    def calculate_information_coefficient(
        self, concat_feature: pd.DataFrame, SOTA_feature_column_size: int, new_feature_columns_size: int
    ) -> pd.DataFrame:
        res = pd.Series(index=range(SOTA_feature_column_size * new_feature_columns_size))
        for col1 in range(SOTA_feature_column_size):
            for col2 in range(SOTA_feature_column_size, SOTA_feature_column_size + new_feature_columns_size):
                res.loc[col1 * new_feature_columns_size + col2 - SOTA_feature_column_size] = concat_feature.iloc[
                    :, col1
                ].corr(concat_feature.iloc[:, col2])
        return res

    def deduplicate_new_factors(self, SOTA_feature: pd.DataFrame, new_feature: pd.DataFrame) -> pd.DataFrame:
        # calculate the IC between each column of SOTA_feature and new_feature
        # if the IC is larger than a threshold, remove the new_feature column
        # return the new_feature

        concat_feature = pd.concat([SOTA_feature, new_feature], axis=1)
        IC_max = (
            concat_feature.groupby("datetime")
            .parallel_apply(
                lambda x: self.calculate_information_coefficient(x, SOTA_feature.shape[1], new_feature.shape[1])
            )
            .mean()
        )
        IC_max.index = pd.MultiIndex.from_product([range(SOTA_feature.shape[1]), range(new_feature.shape[1])])
        IC_max = IC_max.unstack().max(axis=0)
        return new_feature.iloc[:, IC_max[IC_max < 0.99].index]

    @cache_with_pickle(CachedRunner.get_cache_key, CachedRunner.assign_cached_result)
    def develop(self, exp: QlibFactorExperiment, use_local: bool = True) -> QlibFactorExperiment:
        
        """
        Generate the experiment by processing and combining factor data,
        then passing the combined data to Docker or local environment for backtest results.
        """
        parquet_runtime_combined_factors = None

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
                            env['PYTHONPATH'] = str(project_root) + os.pathsep + env.get('PYTHONPATH', '')
                            subprocess.check_output(
                                [sys.executable, str(ws.workspace_path / 'factor.py')],
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
            
            if new_factors.empty:
                raise FactorEmptyError("No valid factor data found to merge.")

            # Combine the SOTA factor and new factors if SOTA factor exists
            if SOTA_factor is not None and not SOTA_factor.empty:
                new_factors = self.deduplicate_new_factors(SOTA_factor, new_factors)
                if new_factors.empty:
                    raise FactorEmptyError("No valid factor data found to merge.")
                combined_factors = pd.concat([SOTA_factor, new_factors], axis=1).dropna()
            else:
                combined_factors = new_factors

            if (
                str(os.environ.get("QUANTAALPHA_FACTOR_CODER_RUNTIME", "")).strip().lower() == "dual_h5_parquet"
                and parquet_runtime_new_factors is not None
                and not parquet_runtime_new_factors.empty
            ):
                parquet_runtime_combined_factors, parquet_runtime_compared_columns = (
                    _prepare_parquet_runtime_combined_factors(combined_factors, parquet_runtime_new_factors)
                )
                combined_for_compare = combined_factors.loc[parquet_runtime_combined_factors.index]
                for column in parquet_runtime_compared_columns:
                    from quantaalpha.factors.coder.runtime_data import assert_factor_frame_parity

                    assert_factor_frame_parity(
                        combined_for_compare[[column]],
                        parquet_runtime_combined_factors[[column]],
                        factor_name=str(column),
                    )
                from quantaalpha.continuous.artifact_policy import runtime_parity_artifacts_enabled

                if runtime_parity_artifacts_enabled():
                    parity_path = exp.experiment_workspace.workspace_path / "factor_runtime_combined_parity.json"
                    parity_path.write_text(
                        json.dumps(
                            {
                                "rows": int(len(parquet_runtime_combined_factors)),
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
                
            if len(combined_factors.columns) >= 2:
                pd.set_option('display.width', 1000)
                logger.info(f"Factor correlation: \n\n{combined_factors.corr()}\n")

            combined_factors = self._apply_combined_quality_gate(combined_factors)
            if combined_factors.empty:
                raise FactorEmptyError("No valid factor data remained after combined quality gate.")

            # Sort and nest the combined factors under 'feature'
            combined_factors = combined_factors.sort_index()
            combined_factors = combined_factors.loc[:, ~combined_factors.columns.duplicated(keep="last")]
            new_columns = pd.MultiIndex.from_product([["feature"], combined_factors.columns])
            combined_factors.columns = new_columns
            if parquet_runtime_combined_factors is not None and not parquet_runtime_combined_factors.empty:
                parquet_runtime_combined_factors = parquet_runtime_combined_factors.sort_index()
                parquet_runtime_combined_factors = parquet_runtime_combined_factors.loc[
                    combined_factors.index,
                    combined_factors.columns.get_level_values(1),
                ]
                parquet_runtime_combined_factors.columns = new_columns
            
            logger.info(f"Factor values this round: \n\n{combined_factors.tail()}\n\n")

            # Save the combined factors to the workspace (parquet format for qlib compatibility)
            parquet_path = exp.experiment_workspace.workspace_path / "combined_factors_df.parquet"
            combined_factors.to_parquet(parquet_path, engine="pyarrow")
            logger.info(f"Saved combined factors to {parquet_path}")


        # Run backtest (local or Docker). Config name must match factor_template files (e.g. conf_baseline.yaml).
        config_name = "conf_baseline.yaml" if len(exp.based_experiments) == 0 else "conf_combined_factors.yaml"
        factor_count = 0
        if hasattr(exp, "sub_workspace_list") and exp.sub_workspace_list is not None:
            factor_count = sum(1 for workspace in exp.sub_workspace_list if workspace is not None)
        workspace_path = getattr(exp.experiment_workspace, "workspace_path", "<unknown>")
        backend = str(getattr(self, "_backtest_backend", os.environ.get("QUANTAALPHA_BACKTEST_BACKEND", "qlib")) or "qlib").strip().lower()
        logger.info(
            f"Execute factor backtest (Use {'Local' if use_local else 'Docker container'}): "
            f"{config_name}; workspace={workspace_path}; factor_count={factor_count}; backend={backend}"
        )

        if backend in {"noqlib", "vnpy"}:
            result = self._develop_noqlib(exp, config_name, backend=backend)
            if (
                parquet_runtime_combined_factors is not None
                and str(os.environ.get("QUANTAALPHA_FACTOR_CODER_RUNTIME", "")).strip().lower() == "dual_h5_parquet"
            ):
                parquet_path = exp.experiment_workspace.workspace_path / "combined_factors_df.parquet"
                h5_combined_backup = pd.read_parquet(parquet_path)
                try:
                    parquet_runtime_combined_factors.to_parquet(parquet_path, engine="pyarrow")
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
                    h5_combined_backup.to_parquet(parquet_path, engine="pyarrow")
            exp.result = result
            return exp
        if backend != "qlib":
            raise ValueError(f"unsupported factor mining backtest backend: {backend}")
        
        # Ensure workspace and config are ready (execute() does not call before_execute()).
        exp.experiment_workspace.before_execute()
        logger.info(f"Backtest workspace ready: workspace={workspace_path}; config={config_name}")
        
        # execute() returns (result_df, execute_qlib_log) or (None, execute_qlib_log)
        result_tuple = exp.experiment_workspace.execute(
            qlib_config_name=config_name,
            run_env={}
        )
        logger.info(f"Backtest execution finished: workspace={workspace_path}; config={config_name}")
        
        # Unpack tuple; take first element (DataFrame)
        result = result_tuple[0] if isinstance(result_tuple, tuple) else result_tuple

        # rdagent QlibFBWorkspace.execute() returns pd.Series (via .iloc[:, 0]).
        # Normalize to DataFrame for consistent downstream consumption.
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

    def _develop_noqlib(self, exp: QlibFactorExperiment, config_name: str, backend: str = "noqlib") -> pd.DataFrame:
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
            market = market_provider.load_market_data()
            expression_engine = NoQlibExpressionEngine(market)
        features = self._load_noqlib_template_features(
            config=qlib_cfg,
            expression_engine=expression_engine,
            workspace_path=workspace_path,
        )
        labels = expression_engine.compute_label(noqlib_cfg.get("dataset", {}).get("label", "Ref($close, -2)/Ref($close, -1) - 1"))
        # Free expression engine — features/labels are computed
        del expression_engine
        if backend == "vnpy":
            del market_frame
        gc.collect()
        dataset = NoQlibDatasetBuilder(noqlib_cfg).build(features, labels)
        # Free raw feature/label frames — dataset owns the data now
        del features, labels
        gc.collect()
        prediction = NoQlibModelRunner(noqlib_cfg).fit_predict(dataset)
        label_for_signal = dataset.raw_labels if dataset.raw_labels is not None else dataset.combined[dataset.label_column]
        metrics = signal_metrics(prediction, label_for_signal)
        if backend == "vnpy":
            market = market_provider.load_market_data()
        portfolio_metrics, _daily_report, _positions = NoQlibTopkDropoutBacktester(noqlib_cfg, market).run(prediction)
        # Free large intermediates after backtest
        del prediction, dataset, market
        gc.collect()
        metrics.update(portfolio_metrics)
        result = pd.DataFrame({"value": metrics})
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
                "segments": dataset_cfg.get("segments", {}),
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

    def _load_noqlib_template_features(self, *, config: dict, expression_engine, workspace_path: Path) -> pd.DataFrame:
        handler = config.get("data_handler_config", {})
        data_loader = handler.get("data_loader", {})
        frames: list[pd.DataFrame] = []
        for loader_cfg in _iter_loader_configs(data_loader):
            class_name = str(loader_cfg.get("class", ""))
            kwargs = loader_cfg.get("kwargs", {})
            if class_name.endswith("QlibDataLoader"):
                raw_config = kwargs.get("config", {})
                feature_cfg = raw_config.get("feature", [])
                if len(feature_cfg) >= 2:
                    expressions, names = feature_cfg[0], feature_cfg[1]
                    factor_defs = [
                        {"factor_id": str(name), "factor_name": str(name), "factor_expression": str(expr)}
                        for expr, name in zip(expressions, names)
                    ]
                    frames.append(expression_engine.compute(factor_defs))
            elif class_name.endswith("StaticDataLoader"):
                static_path = workspace_path / str(kwargs.get("config", "combined_factors_df.parquet"))
                frame = pd.read_parquet(static_path)
                if isinstance(frame.columns, pd.MultiIndex):
                    if "feature" in frame.columns.get_level_values(0):
                        frame = frame["feature"]
                    else:
                        frame.columns = [str(col[-1]) for col in frame.columns]
                frames.append(frame)
        if not frames:
            raise ValueError("noqlib factor-template features are empty")
        combined = pd.concat(frames, axis=1)
        combined = combined.loc[:, ~combined.columns.duplicated(keep="last")]
        return combined.sort_index()

    def _validate_factor_frame(self, df: pd.DataFrame) -> pd.DataFrame | None:
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
                logger.warning(
                    f"Skipping factor {col}: valid_ratio={valid_ratio:.3f}, nan_ratio={nan_ratio:.3f}."
                )
                continue
            if unique_count < self.MIN_UNIQUE_VALUES:
                logger.warning(f"Skipping factor {col}: unique non-null values={unique_count}.")
                continue
            valid_columns.append(series.to_frame(name=col))
        if not valid_columns:
            return None
        return pd.concat(valid_columns, axis=1)

    def _apply_combined_quality_gate(self, df: pd.DataFrame) -> pd.DataFrame:
        cleaned = df.replace([np.inf, -np.inf], np.nan)
        column_nan_ratio = cleaned.isna().mean()
        keep_columns = column_nan_ratio[column_nan_ratio <= self.MAX_NAN_RATIO].index.tolist()
        dropped_columns = sorted(set(cleaned.columns) - set(keep_columns))
        for col in dropped_columns:
            logger.warning(
                f"Dropping factor {col} from combined dataframe: nan_ratio={float(column_nan_ratio[col]):.3f}."
            )
        cleaned = cleaned.loc[:, keep_columns]
        if cleaned.empty:
            return cleaned
        cleaned = cleaned.dropna(how="any")
        keep_columns = [col for col in cleaned.columns if cleaned[col].nunique() >= self.MIN_UNIQUE_VALUES]
        cleaned = cleaned.loc[:, keep_columns]
        return self._prune_correlated_candidates(cleaned)

    def _prune_correlated_candidates(self, df: pd.DataFrame) -> pd.DataFrame:
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
                logger.warning(
                    f"Dropping factor {right} from combined dataframe: "
                    f"pre_backtest_correlation={float(value):.3f} with {left}."
                )
        if not dropped:
            return df
        keep_columns = [col for col in df.columns if col not in dropped]
        return df.loc[:, keep_columns]

    def process_factor_data(self, exp_or_list: List[QlibFactorExperiment] | QlibFactorExperiment) -> pd.DataFrame:
        """
        Process and combine factor data from experiment implementations.

        Args:
            exp (ASpecificExp): The experiment containing factor data.

        Returns:
            pd.DataFrame: Combined factor data without NaN values.
        """
        if isinstance(exp_or_list, QlibFactorExperiment):
            exp_or_list = [exp_or_list]
        factor_dfs = []
        parquet_factor_dfs = []

        # Collect all exp's dataframes
        for exp in exp_or_list:
            valid_implementations = [
                implementation
                for implementation in exp.sub_workspace_list
                if implementation is not None and "factor.py" in getattr(implementation, "code_dict", {})
            ]
            if not valid_implementations:
                continue
            # Iterate over sub-implementations and execute them to get each factor data
            message_and_df_list = multiprocessing_wrapper(
                [(implementation.execute, ("All",)) for implementation in valid_implementations],
                n=RD_AGENT_SETTINGS.multi_proc_n,
            )
            for idx, (message, df) in enumerate(message_and_df_list):
                # Check if factor generation was successful
                if df is not None and "datetime" in df.index.names:
                    # Convert Series to DataFrame if needed
                    if isinstance(df, pd.Series):
                        # Get factor name from the corresponding workspace (order should match)
                        if idx < len(valid_implementations):
                            factor_name = getattr(valid_implementations[idx].target_task, 'factor_name', None)
                            if factor_name:
                                df = df.to_frame(name=factor_name)
                            else:
                                df = df.to_frame(name=df.name if df.name else f'factor_{idx}')
                        else:
                            df = df.to_frame(name=df.name if df.name else f'factor_{idx}')
                    time_diff = df.index.get_level_values("datetime").to_series().diff().dropna().unique()
                    if pd.Timedelta(minutes=1) not in time_diff:
                        validated_df = self._validate_factor_frame(df)
                        if validated_df is not None:
                            factor_dfs.append(validated_df)
                            if (
                                str(os.environ.get("QUANTAALPHA_FACTOR_CODER_RUNTIME", "")).strip().lower()
                                == "dual_h5_parquet"
                                and idx < len(valid_implementations)
                            ):
                                parquet_path = valid_implementations[idx].workspace_path / "result.parquet"
                                if parquet_path.exists():
                                    from quantaalpha.factors.coder.runtime_data import (
                                        assert_factor_frame_parity,
                                        read_parquet_factor_result,
                                    )

                                    factor_name = str(valid_implementations[idx].target_task.factor_name)
                                    parquet_df = read_parquet_factor_result(parquet_path, factor_name=factor_name)
                                    assert_factor_frame_parity(validated_df[[factor_name]], parquet_df, factor_name=factor_name)
                                    parquet_validated = self._validate_factor_frame(parquet_df)
                                    if parquet_validated is not None:
                                        parquet_factor_dfs.append(parquet_validated)

        # Combine all successful factor data
        if factor_dfs:
            self._last_parquet_runtime_factors = pd.concat(parquet_factor_dfs, axis=1) if parquet_factor_dfs else None
            return pd.concat(factor_dfs, axis=1)
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
        "admission_profile_path",
        "admission_profile",
        "admission_profile_hash",
        "admitted_fields",
        "optional_fields",
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
