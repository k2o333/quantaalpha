import io
import json
import os
import re
import shutil
import sys
from pathlib import Path

import pandas as pd
import polars as pl

# render it with jinja
from jinja2 import Environment, StrictUndefined

from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS
from quantaalpha.utils.env import QTDockerEnv
from quantaalpha.log import logger


def generate_data_folder_from_qlib(use_local: bool = True):
    template_path = Path(__file__).parent / "data_template"
    qtde = QTDockerEnv(is_local=use_local)
    qtde.prepare()
    
    # Use current Python so subprocess finds installed packages (e.g. qlib)
    python_exe = sys.executable
    logger.info(f"Generating factor data in {'local' if use_local else 'Docker'}")
    execute_log = qtde.run(
        local_path=str(template_path),
        entry=f'{python_exe} generate.py',
    )

    # Check that file was generated
    daily_pv_all = Path(__file__).parent / "data_template" / "daily_pv_all.h5"
    daily_pv_debug = Path(__file__).parent / "data_template" / "daily_pv_debug.h5"
    
    assert daily_pv_all.exists(), "daily_pv_all.h5 is not generated."
    assert daily_pv_debug.exists(), "daily_pv_debug.h5 is not generated."

    # Create data dir and copy files
    logger.info("Copying generated data files to workspace")
    Path(FACTOR_COSTEER_SETTINGS.data_folder).mkdir(parents=True, exist_ok=True)
    shutil.copy(
        daily_pv_all,
        Path(FACTOR_COSTEER_SETTINGS.data_folder) / "daily_pv.h5",
    )
    shutil.copy(
        Path(__file__).parent / "data_template" / "README.md",
        Path(FACTOR_COSTEER_SETTINGS.data_folder) / "README.md",
    )

    Path(FACTOR_COSTEER_SETTINGS.data_folder_debug).mkdir(parents=True, exist_ok=True)
    shutil.copy(
        daily_pv_debug,
        Path(FACTOR_COSTEER_SETTINGS.data_folder_debug) / "daily_pv.h5",
    )
    shutil.copy(
        Path(__file__).parent / "data_template" / "README.md",
        Path(FACTOR_COSTEER_SETTINGS.data_folder_debug) / "README.md",
    )
    
    logger.info("Data preparation done")


def prepare_data_folder_from_standard_frame(noqlib_config: dict) -> bool:
    """Materialize coder H5 source data from an App5 standard-frame config."""

    workspace_root = Path(__file__).resolve().parents[4]
    project_root = Path(noqlib_config.get("project_root") or workspace_root).expanduser().resolve()
    if not (project_root / "docs" / "01-govern").exists():
        project_root = workspace_root
    logger.info(f"Preparing App5 standard-frame coder data with project_root={project_root}")
    standard_frame_cfg = dict(noqlib_config.get("standard_frame") or {})
    optional_fields = standard_frame_cfg.get("optional_fields") or ()
    admitted_fields = standard_frame_cfg.get("admitted_fields") or ()
    if not admitted_fields and standard_frame_cfg.get("admission_profile_path"):
        from quantaalpha.backtest.mining_admission import load_mining_admission_profile

        profile_path = Path(str(standard_frame_cfg["admission_profile_path"]))
        if not profile_path.is_absolute():
            profile_path = project_root / profile_path
        profile_name = str(standard_frame_cfg.get("admission_profile") or "expanded_app5_v1")
        profile = load_mining_admission_profile(profile_path, profile_name)
        admitted_fields = [field.identity() for field in profile.fields]
        standard_frame_cfg["admitted_fields"] = admitted_fields
        standard_frame_cfg["admission_profile"] = profile.name
        standard_frame_cfg["admission_profile_hash"] = profile.version_hash()
    if not optional_fields and not admitted_fields:
        return False

    from quantaalpha.backtest.standard_frame import App5StandardFrameBuilder, request_from_mapping

    storage_root = Path(noqlib_config.get("app5_storage_root") or standard_frame_cfg.get("storage_root") or "data")
    if not storage_root.is_absolute():
        storage_root = project_root / storage_root
    payload = {
        **standard_frame_cfg,
        "storage_root": str(storage_root),
    }
    use_backtest_universe = _factor_coder_uses_backtest_universe(noqlib_config)
    if use_backtest_universe and not payload.get("instruments") and noqlib_config.get("instruments"):
        payload["instruments"] = tuple(str(item) for item in noqlib_config["instruments"])
    if use_backtest_universe and not payload.get("instruments") and noqlib_config.get("instruments_path"):
        instruments_path = Path(noqlib_config["instruments_path"])
        if not instruments_path.is_absolute():
            instruments_path = project_root / instruments_path
        if instruments_path.exists():
            payload["instruments"] = tuple(
                line.strip().split()[0]
                for line in instruments_path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            )
    request = request_from_mapping(payload)
    request_hash = request.identity_hash()

    data_root = Path(FACTOR_COSTEER_SETTINGS.data_folder)
    debug_root = Path(FACTOR_COSTEER_SETTINGS.data_folder_debug)
    if not data_root.is_absolute():
        data_root = project_root / data_root
    if not debug_root.is_absolute():
        debug_root = project_root / debug_root
    workspace_data_root = workspace_root / Path(FACTOR_COSTEER_SETTINGS.data_folder)
    workspace_debug_root = workspace_root / Path(FACTOR_COSTEER_SETTINGS.data_folder_debug)
    default_data_root = workspace_root / "git_ignore_folder" / "factor_implementation_source_data"
    default_debug_root = workspace_root / "git_ignore_folder" / "factor_implementation_source_data_debug"
    data_roots = tuple(dict.fromkeys([data_root, workspace_data_root, default_data_root]))
    debug_roots = tuple(dict.fromkeys([debug_root, workspace_debug_root, default_debug_root]))

    marker_path = data_root / ".standard_frame_source.json"
    required_columns = sorted(
        {
            str(item["feature_name"])
            for item in optional_fields
            if isinstance(item, dict) and item.get("feature_name")
        }
        | {
            str(item["base"]["feature_name"])
            for item in admitted_fields
            if isinstance(item, dict) and isinstance(item.get("base"), dict) and item["base"].get("feature_name")
        }
    )
    coder_runtime = str(
        noqlib_config.get("factor_coder_runtime")
        or os.environ.get("QUANTAALPHA_FACTOR_CODER_RUNTIME", "")
    ).strip().lower()
    need_h5_oracle = coder_runtime not in {"parquet_only", "parquet", "polars_parquet"}
    if marker_path.exists():
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            marker_columns = set(marker.get("columns") or [])
            all_targets_ready = True
            for candidate_data_root, candidate_debug_root in zip(data_roots, debug_roots):
                if (
                    not (candidate_data_root / "standard_frame.parquet").exists()
                    or not (candidate_debug_root / "standard_frame.parquet").exists()
                ):
                    all_targets_ready = False
                    break
                if need_h5_oracle and (
                    not (candidate_data_root / "daily_pv.h5").exists()
                    or not (candidate_debug_root / "daily_pv.h5").exists()
                ):
                    all_targets_ready = False
                    break
                if need_h5_oracle and not set(required_columns).issubset(pd.read_hdf(candidate_debug_root / "daily_pv.h5", key="data", stop=1).columns):
                    all_targets_ready = False
                    break
            if (
                marker.get("request_hash") == request_hash
                and set(required_columns).issubset(marker_columns)
                and all_targets_ready
            ):
                return True
        except (json.JSONDecodeError, OSError, ValueError, TypeError):
            pass

    result = App5StandardFrameBuilder(storage_root=storage_root).build(request)
    source_manifest = result.manifest
    frame = result.frame.sort(["datetime", "instrument"])
    del result
    if frame.is_empty():
        raise ValueError("standard-frame coder data source is empty")

    # Only write H5 oracle when the coder runtime needs it (saves a full
    # Polars→Pandas conversion per write — up to ~4 GB for large frames).
    import gc as _gc

    def _write_runtime_data(target_root: Path, source_frame, *, write_h5: bool) -> None:
        from quantaalpha.factors.coder.runtime_data import write_standard_frame_runtime_data

        target_root.mkdir(parents=True, exist_ok=True)
        write_standard_frame_runtime_data(
            frame=source_frame,
            target_root=target_root,
            source_manifest=source_manifest,
            write_h5_oracle=write_h5,
        )
        (target_root / "README.md").write_text(
            "# How to read files.\n"
            "Use `polars.scan_parquet(\"standard_frame.parquet\")` for the primary runtime path.\n"
            "Use `pd.read_hdf(\"daily_pv.h5\", key=\"data\")` only for the temporary H5 oracle path.\n\n"
            "# Data\n"
            "This H5 file was materialized from the governed App5 standard-frame request. "
            "The parquet file is the target factor-coder runtime data contract. "
            "Columns are prompt-visible only when admitted by the data-admission allowlist.\n",
            encoding="utf-8",
        )

    def _copy_runtime_artifacts(primary_root: Path, target_root: Path) -> None:
        """Copy already-written artifacts instead of re-materializing the frame."""
        target_root.mkdir(parents=True, exist_ok=True)
        for filename in ("standard_frame.parquet", "standard_frame_manifest.json", "daily_pv.h5", "README.md"):
            src = primary_root / filename
            dst = target_root / filename
            if src.exists() and not dst.exists():
                shutil.copy2(str(src), str(dst))
            elif src.exists() and dst.exists() and src.stat().st_mtime > dst.stat().st_mtime:
                shutil.copy2(str(src), str(dst))

    debug_frame = frame.head(min(frame.height, 100_000))
    row_count = frame.height
    columns = frame.columns

    # Write primary roots, copy to secondary roots to avoid repeat materialization.
    data_roots_list = list(data_roots)
    if data_roots_list:
        _write_runtime_data(data_roots_list[0], frame, write_h5=need_h5_oracle)
        for secondary_root in data_roots_list[1:]:
            _copy_runtime_artifacts(data_roots_list[0], secondary_root)

    debug_roots_list = list(debug_roots)
    if debug_roots_list:
        _write_runtime_data(debug_roots_list[0], debug_frame, write_h5=need_h5_oracle)
        for secondary_root in debug_roots_list[1:]:
            _copy_runtime_artifacts(debug_roots_list[0], secondary_root)

    # Free large frames explicitly before writing the marker
    del debug_frame, frame
    _gc.collect()

    marker_payload = {
        "request_hash": request_hash,
        "rows": row_count,
        "columns": columns,
        "manifest": source_manifest,
    }
    marker_path.write_text(json.dumps(marker_payload, ensure_ascii=True, indent=2, sort_keys=True, default=str), encoding="utf-8")
    logger.info(f"Materialized factor coder data from App5 standard frame: rows={row_count} columns={columns} data_root={data_root}")
    return True


def _factor_coder_uses_backtest_universe(noqlib_config: dict) -> bool:
    """Whether factor-coder standard-frame materialization should inherit backtest instruments."""
    scope = str(noqlib_config.get("factor_coder_universe_scope") or "backtest").strip().lower()
    if scope in {"all", "full", "full_market", "global"}:
        return False
    if scope in {"backtest", "instruments", "configured"}:
        return True
    raise ValueError(f"unsupported factor_coder_universe_scope: {scope}")


def get_file_desc(p: Path, variable_list=[]) -> str:
    """
    Get the description of a file based on its type.

    Parameters
    ----------
    p : Path
        The path of the file.

    Returns
    -------
    str
        The description of the file.
    """
    p = Path(p)

    JJ_TPL = Environment(undefined=StrictUndefined).from_string(
        """
{{file_name}}
```{{type_desc}}
{{content}}
```
"""
    )

    if p.name.endswith(".h5"):
        df = pd.read_hdf(p)
        # get df.head() as string with full width
        pd.set_option("display.max_columns", None)  # or 1000
        pd.set_option("display.max_rows", None)  # or 1000
        pd.set_option("display.max_colwidth", None)  # or 199

        if isinstance(df.index, pd.MultiIndex):
            df_info = f"MultiIndex names:, {df.index.names})\n"
        else:
            df_info = f"Index name: {df.index.name}\n"
        columns = df.dtypes.to_dict()
        filtered_columns = [f"{i, j}" for i, j in columns.items() if i in variable_list]
        if filtered_columns:
            df_info += "Related Data columns: \n"
            df_info += ",".join(filtered_columns)
        else:
            df_info += "Data columns: \n"
            df_info += ",".join(columns)
        df_info += "\n"
        if "REPORT_PERIOD" in df.columns:
            one_instrument = df.index.get_level_values("instrument")[0]
            df_on_one_instrument = df.loc[pd.IndexSlice[:, one_instrument], ["REPORT_PERIOD"]]
            df_info += f"""
A snapshot of one instrument, from which you can tell the distribution of the data:
{df_on_one_instrument.head(5)}
"""
        return JJ_TPL.render(
            file_name=p.name,
            type_desc="h5 info",
            content=df_info,
            )
    elif p.name.endswith(".parquet"):
        schema = pl.scan_parquet(str(p)).collect_schema()
        columns = {name: str(schema[name]) for name in schema.names()}
        filtered_columns = {name: dtype for name, dtype in columns.items() if name in variable_list}
        selected_columns = filtered_columns or columns
        df_info = "Data columns: \n"
        df_info += ",".join(f"{name}: {dtype}" for name, dtype in selected_columns.items())
        df_info += "\n"
        return JJ_TPL.render(
            file_name=p.name,
            type_desc="parquet schema",
            content=df_info,
        )
    elif p.name.endswith(".json"):
        content = p.read_text(encoding="utf-8")[:2000]
        return JJ_TPL.render(
            file_name=p.name,
            type_desc="json",
            content=content,
        )
    elif p.name.endswith(".md"):
        with open(p) as f:
            content = f.read()
            return JJ_TPL.render(
                file_name=p.name,
                type_desc="markdown",
                content=content,
            )
    else:
        raise NotImplementedError(
            f"file type {p.name} is not supported. Please implement its description function.",
        )


def get_data_folder_intro(
    fname_reg: str = ".*",
    flags=0,
    variable_mapping=None,
    use_local: bool = True,
) -> str:
    """
    Directly get the info of the data folder.
    It is for preparing prompting message.

    Parameters
    ----------
    fname_reg : str
        a regular expression to filter the file name.

    flags: str
        flags for re.match

    Returns
    -------
        str
            The description of the data folder.
    """

    if (
        not Path(FACTOR_COSTEER_SETTINGS.data_folder).exists()
        or not Path(FACTOR_COSTEER_SETTINGS.data_folder_debug).exists()
    ):
        # FIXME: (xiao) I think this is writing in a hard-coded way.
        # get data folder intro does not imply that we are generating the data folder.
        generate_data_folder_from_qlib(use_local=use_local)
    content_l = []
    
    for p in Path(FACTOR_COSTEER_SETTINGS.data_folder_debug).iterdir():
        if re.match(fname_reg, p.name, flags) is not None:
            if variable_mapping:
                content_l.append(get_file_desc(p, variable_mapping.get(p.stem, [])))
            else:
                content_l.append(get_file_desc(p))
    return "\n----------------- file splitter -------------\n".join(content_l)
