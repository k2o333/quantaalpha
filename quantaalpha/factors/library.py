"""
Factor library manager: save experiment output to unified JSON factor library.
Called from quantaalpha/pipeline/loop.py feedback step.
"""

from __future__ import annotations

import json
import hashlib
import logging
import os
import tempfile
import fcntl
import struct
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from quantaalpha.factors.status_rules import update_factor_status

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Tag enumeration constants for factor classification
# ----------------------------------------------------------------------
# category: investment style / factor category
CATEGORY_TAGS = ["momentum", "reversal", "value", "quality", "liquidity"]

# data_dependency: what data the factor primarily uses
DATA_DEPENDENCY_TAGS = ["price_volume", "financial", "alternative"]

# market_environment: market regime suitability
MARKET_ENVIRONMENT_TAGS = ["bull", "bear", "sideways", "high_vol"]

# time_horizon: investment holding period
TIME_HORIZON_TAGS = ["short_term", "intraday", "medium_term"]

# All valid tag keys and their allowed values (for validation)
TAG_DEFINITIONS = {
    "category": CATEGORY_TAGS,
    "data_dependency": DATA_DEPENDENCY_TAGS,
    "market_environment": MARKET_ENVIRONMENT_TAGS,
    "time_horizon": TIME_HORIZON_TAGS,
}

# Default empty tags structure for new factor entries
DEFAULT_TAGS = {
    "category": [],
    "data_dependency": [],
    "market_environment": [],
    "time_horizon": [],
}

DEFAULT_FACTOR_CACHE_DIR = os.environ.get(
    "FACTOR_CACHE_DIR",
    "data/results/factor_cache",
)
AUDIT_TRAIL_LIMIT = 200


class FactorLibraryManager:
    """Manage unified factor library (CRUD) with locking and audit support."""

    _lock_dir = Path(tempfile.gettempdir()) / "quantaalpha_locks"

    def __init__(self, library_path: str):
        self.library_path = Path(library_path)
        self.data = self._load()
        self._dirty = False
        self._dirty_factor_ids = set()
        self._last_save_time = None

    def _acquire_lock(self):
        self.library_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self.library_path.parent / f".{self.library_path.name}.lock"
        lock_fd = open(lock_file, "w")
        try:
            os.chmod(lock_file, 0o664)
        except OSError:
            logger.debug("Unable to chmod lock file %s", lock_file, exc_info=True)
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        return lock_fd

    def _release_lock(self, lock_fd):
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
        lock_fd.close()

    def _load(self) -> dict:
        return self._load_from_disk()

    def _load_from_disk(self) -> dict:
        if self.library_path.exists():
            try:
                with open(self.library_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return self._normalize_library_data(data)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Factor library file corrupted, recreating: {e}")
        return self._normalize_library_data(
            {
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat(),
                    "total_factors": 0,
                    "version": "1.1",
                },
                "factors": {},
            }
        )

    def _save(self):
        """Persist factor library to disk. Only writes when _dirty is True."""
        if not self._dirty:
            logger.debug("No changes to persist, skipping save")
            return

        self.library_path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = self._acquire_lock()
        try:
            merged_data = self._merge_library_data(
                self._load_from_disk(), self.data, now=datetime.now()
            )
            fd, tmp_path_str = tempfile.mkstemp(
                dir=str(self.library_path.parent),
                prefix=f".{self.library_path.name}.",
                suffix=".tmp",
            )
            tmp_path = Path(tmp_path_str)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(merged_data, f, ensure_ascii=False, indent=2, default=str)
            os.chmod(tmp_path, 0o664)
            os.replace(tmp_path, self.library_path)
            self.data = merged_data

            # Clear dirty state after successful save
            saved_count = len(self._dirty_factor_ids)
            self._dirty = False
            self._dirty_factor_ids.clear()
            self._last_save_time = datetime.now()

            logger.debug(f"Factor library saved ({saved_count} factors modified)")
        except Exception as e:
            # Preserve dirty state on failure for retry
            logger.error(f"Failed to save factor library: {e}")
            raise
        finally:
            self._release_lock(lock_fd)

    def _merge_library_data(
        self, base_data: dict[str, Any], current_data: dict[str, Any], *, now: datetime
    ) -> dict[str, Any]:
        merged = self._normalize_library_data(base_data)
        current = self._normalize_library_data(current_data)
        merged["factors"].update(current.get("factors", {}))
        merged_metadata = merged.setdefault("metadata", {})
        current_metadata = current.get("metadata", {})
        merged_metadata.update(
            {
                "created_at": merged_metadata.get("created_at")
                or current_metadata.get("created_at")
                or now.isoformat(),
                "last_updated": now.isoformat(),
                "total_factors": len(merged["factors"]),
                "version": "1.1",
            }
        )
        merged_metadata["audit_trail"] = self._merge_audit_entries(
            merged_metadata.get("audit_trail", []),
            current_metadata.get("audit_trail", []),
        )
        return merged

    @staticmethod
    def _merge_audit_entries(existing: list[dict], incoming: list[dict]) -> list[dict]:
        deduped = {}
        for entry in list(existing or []) + list(incoming or []):
            if not isinstance(entry, dict):
                continue
            key = (
                entry.get("timestamp"),
                entry.get("factor_id"),
                entry.get("old_status"),
                entry.get("new_status"),
                entry.get("trigger"),
            )
            deduped[key] = entry
        merged_entries = list(deduped.values())
        merged_entries.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
        return merged_entries[:AUDIT_TRAIL_LIMIT]

    def _append_audit_entry(
        self,
        *,
        factor_id: str,
        factor_name: str,
        old_status: str,
        new_status: str,
        reason: str,
        trigger: str,
        timestamp: str,
    ) -> None:
        metadata = self.data.setdefault("metadata", {})
        audit_trail = list(metadata.get("audit_trail", []))
        audit_trail.append(
            {
                "timestamp": timestamp,
                "factor_id": factor_id,
                "factor_name": factor_name,
                "old_status": old_status,
                "new_status": new_status,
                "reason": reason,
                "trigger": trigger,
            }
        )
        audit_trail.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
        metadata["audit_trail"] = audit_trail[:AUDIT_TRAIL_LIMIT]

    def add_factors_from_experiment(
        self,
        experiment,
        experiment_id: str = "unknown",
        round_number: int = 0,
        hypothesis: Optional[str] = None,
        feedback: Any = None,
        initial_direction: Optional[str] = None,
        user_initial_direction: Optional[str] = None,
        planning_direction: Optional[str] = None,
        evolution_phase: str = "original",
        trajectory_id: str = "",
        parent_trajectory_ids: Optional[list] = None,
    ):
        """Extract factors from a QlibFactorExperiment and write to library."""
        if experiment is None:
            logger.warning("experiment is None, skip saving factors")
            return
        backtest_results = self._extract_backtest_results(experiment)
        feedback_dict = self._extract_feedback(feedback)
        sub_tasks = getattr(experiment, "sub_tasks", []) or []
        sub_workspaces = getattr(experiment, "sub_workspace_list", []) or []

        for idx, task in enumerate(sub_tasks):
            factor_name = getattr(
                task, "factor_name", getattr(task, "name", f"factor_{idx}")
            )
            factor_expr = getattr(task, "factor_expression", "")
            factor_desc = getattr(
                task, "factor_description", getattr(task, "description", "")
            )
            factor_form = getattr(task, "factor_formulation", "")

            factor_id = hashlib.md5(
                f"{factor_name}_{factor_expr}".encode()
            ).hexdigest()[:16]

            code = ""
            cache_location = {}
            if idx < len(sub_workspaces):
                ws = sub_workspaces[idx]
                code_dict = getattr(ws, "code_dict", {})
                code = "\n".join(
                    f"File: {fname}\n\n{content}"
                    for fname, content in code_dict.items()
                )
                ws_path = getattr(ws, "workspace_path", None)
                if ws_path:
                    ws_path = Path(ws_path)
                    workspace_suffix = ""
                    for part in ws_path.parts:
                        if part.startswith("workspace_"):
                            workspace_suffix = part.replace("workspace_", "")
                            break
                    h5_file = ws_path / "result.h5"
                    cache_location = {
                        "workspace_suffix": workspace_suffix,
                        "workspace_path": str(ws_path.parent),
                        "factor_dir": ws_path.name,
                    }
                    if h5_file.exists():
                        cache_location["result_h5_path"] = str(h5_file)
                    else:
                        logger.warning(
                            f"result.h5 missing for {factor_name} ({h5_file}), will recompute from expression in backtest"
                        )

            factor_entry = {
                "factor_id": factor_id,
                "factor_name": factor_name,
                "factor_expression": factor_expr,
                "factor_implementation_code": code,
                "factor_description": factor_desc,
                "factor_formulation": factor_form,
                "cache_location": cache_location,
                "metadata": {
                    "experiment_id": experiment_id,
                    "round_number": round_number,
                    "evolution_phase": evolution_phase,
                    "trajectory_id": trajectory_id,
                    "parent_trajectory_ids": parent_trajectory_ids or [],
                    "hypothesis": str(hypothesis) if hypothesis else "",
                    "initial_direction": initial_direction or "",
                    "planning_direction": planning_direction or "",
                    "created_at": datetime.now().isoformat(),
                },
                "backtest_results": backtest_results,
                "feedback": feedback_dict,
            }
            factor_entry = self._normalize_factor_entry(factor_entry)

            multi_period_result = backtest_results.get("multi_period_validation")
            if isinstance(multi_period_result, dict):
                factor_entry = self.apply_validation_result(
                    factor_entry,
                    validation_result={
                        "status": "success",
                        "period_results": multi_period_result.get("period_results", []),
                        "summary": multi_period_result.get("summary", {}),
                    },
                    persist=False,
                )

            self.data["factors"][factor_id] = factor_entry
            self._dirty = True
            self._dirty_factor_ids.add(factor_id)

            if factor_expr and cache_location.get("result_h5_path"):
                self._sync_h5_to_md5_cache(
                    factor_expr, cache_location["result_h5_path"]
                )

        self._save()
        logger.info(
            f"Saved {len(sub_tasks)} factors to {self.library_path} (backtest_results: {len(backtest_results)} metrics)"
        )

    @staticmethod
    def _sync_h5_to_md5_cache(
        factor_expression: str, h5_path: str, cache_dir: Optional[str] = None
    ) -> bool:
        """Sync factor values from result.h5 to MD5 cache dir (.pkl). Returns True on success."""
        cache_dir = Path(cache_dir or DEFAULT_FACTOR_CACHE_DIR)
        h5_file = Path(h5_path)

        if not h5_file.exists():
            return False

        md5_key = hashlib.md5(factor_expression.encode()).hexdigest()
        pkl_file = cache_dir / f"{md5_key}.pkl"

        if pkl_file.exists():
            return True

        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            result = pd.read_hdf(str(h5_file))
            result.to_pickle(pkl_file)
            logger.debug(f"Synced factor cache -> {pkl_file.name}")
            return True
        except Exception as e:
            logger.debug(f"Sync factor cache failed [{h5_path}]: {e}")
            return False

    @staticmethod
    def check_cache_status(library_path: str, cache_dir: Optional[str] = None) -> dict:
        """Check cache status for each factor in library. Returns:
        {
            "total": int,
            "h5_cached": int,
            "md5_cached": int,
            "need_compute": int,
            "factors": [ { "factor_id", "factor_name", "status" }, ... ]
        }
        """
        cache_dir = Path(cache_dir or DEFAULT_FACTOR_CACHE_DIR)

        with open(library_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        factors = data.get("factors", {})
        total = len(factors)
        h5_cached = 0
        md5_cached = 0
        need_compute = 0
        details = []

        for fid, finfo in factors.items():
            expr = finfo.get("factor_expression", "")
            cloc = finfo.get("cache_location", {})
            h5_path = cloc.get("result_h5_path", "")

            status = "need_compute"
            # Check h5 cache
            if h5_path and Path(h5_path).exists():
                status = "h5_cached"
                h5_cached += 1
            # Check MD5 cache
            elif expr:
                md5_key = hashlib.md5(expr.encode()).hexdigest()
                if (cache_dir / f"{md5_key}.pkl").exists():
                    status = "md5_cached"
                    md5_cached += 1

            if status == "need_compute":
                need_compute += 1

            details.append(
                {
                    "factor_id": fid,
                    "factor_name": finfo.get("factor_name", fid),
                    "status": status,
                }
            )

        return {
            "total": total,
            "h5_cached": h5_cached,
            "md5_cached": md5_cached,
            "need_compute": need_compute,
            "factors": details,
        }

    @staticmethod
    def warm_cache_from_json(
        library_path: str, cache_dir: Optional[str] = None
    ) -> dict:
        """Walk factor library JSON and sync all available result.h5 to MD5 cache dir. Returns:
        { "total": int, "synced": int, "skipped": int, "failed": int,
          "already_cached": int, "no_source": int }
        """
        cache_dir_path = Path(cache_dir or DEFAULT_FACTOR_CACHE_DIR)

        with open(library_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        factors = data.get("factors", {})
        synced = 0
        skipped = 0
        failed = 0
        already_cached = 0
        no_source = 0

        for fid, finfo in factors.items():
            expr = finfo.get("factor_expression", "")
            cloc = finfo.get("cache_location", {})
            h5_path = cloc.get("result_h5_path", "")

            if not expr or not h5_path:
                no_source += 1
                skipped += 1
                continue

            md5_key = hashlib.md5(expr.encode()).hexdigest()
            pkl_file = cache_dir_path / f"{md5_key}.pkl"

            if pkl_file.exists():
                already_cached += 1
                skipped += 1
                continue

            if not Path(h5_path).exists():
                failed += 1
                continue

            try:
                cache_dir_path.mkdir(parents=True, exist_ok=True)
                result = pd.read_hdf(str(h5_path))
                result.to_pickle(pkl_file)
                synced += 1
            except Exception:
                failed += 1

        return {
            "total": len(factors),
            "synced": synced,
            "skipped": skipped,
            "failed": failed,
            "already_cached": already_cached,
            "no_source": no_source,
        }

    def _normalize_library_data(self, data: dict) -> dict:
        data = data or {}
        metadata = data.setdefault("metadata", {})
        metadata.setdefault("created_at", datetime.now().isoformat())
        metadata.setdefault("last_updated", datetime.now().isoformat())
        metadata["version"] = "1.1"
        metadata.setdefault("audit_trail", [])
        data.setdefault("factors", {})
        normalized_factors = {}
        for factor_id, factor_entry in data["factors"].items():
            normalized = self._normalize_factor_entry(factor_entry)
            normalized_factors[normalized.get("factor_id", factor_id)] = normalized
        data["factors"] = normalized_factors
        metadata["total_factors"] = len(normalized_factors)
        return data

    def _normalize_factor_entry(self, factor_entry: dict[str, Any]) -> dict[str, Any]:
        entry = dict(factor_entry or {})
        entry.setdefault("factor_id", "")
        entry.setdefault("factor_name", "")
        entry.setdefault("factor_expression", "")
        entry.setdefault("metadata", {})
        entry.setdefault("backtest_results", {})
        entry.setdefault("feedback", {})
        # Tags field: 4-dimension classification labels
        entry.setdefault("tags", dict(DEFAULT_TAGS))
        # Ensure tags has all required keys with list values (migration-safe)
        if "tags" in entry and entry["tags"] is not None:
            for tag_key, default_value in DEFAULT_TAGS.items():
                entry["tags"].setdefault(tag_key, list(default_value))
                if not isinstance(entry["tags"][tag_key], list):
                    entry["tags"][tag_key] = list(entry["tags"][tag_key])
        else:
            entry["tags"] = dict(DEFAULT_TAGS)
        entry["metadata"].setdefault("version", "1.1")
        entry.setdefault(
            "evaluation",
            {
                "status": "pending_validation",
                "last_validated": datetime.now().isoformat(),
                "stability_score": None,
                "period_results": [],
                "validation_summary": "",
                "consecutive_failures": 0,
            },
        )
        entry["evaluation"].setdefault("status", "pending_validation")
        entry["evaluation"].setdefault("last_validated", datetime.now().isoformat())
        entry["evaluation"].setdefault("stability_score", None)
        entry["evaluation"].setdefault("period_results", [])
        entry["evaluation"].setdefault("validation_summary", "")
        entry["evaluation"].setdefault("consecutive_failures", 0)
        entry.setdefault("data_requirements", {})
        entry["data_requirements"].setdefault(
            "dimensions", self._infer_dimensions(entry)
        )
        entry["data_requirements"].setdefault("fields", self._infer_fields(entry))

        # Infer tags from expression using shared inference engine
        # This is the "three-point convergence" for tag inference safety net
        expr = entry.get("factor_expression", "")
        if expr:
            from quantaalpha.factors.tag_inference import infer_tags_from_expression
            inferred = infer_tags_from_expression(expr)
            # Merge: fill in empty tag slots, don't override existing values
            for tag_key, tag_values in inferred.items():
                existing = entry["tags"].get(tag_key, [])
                if isinstance(existing, list) and not existing:
                    entry["tags"][tag_key] = tag_values

        return entry

    def apply_validation_result(
        self,
        factor_entry: dict[str, Any],
        validation_result: dict[str, Any],
        *,
        now: datetime | None = None,
        config: dict[str, Any] | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        previous_entry = self.get_factor(factor_entry.get("factor_id", "")) or self._normalize_factor_entry(factor_entry)
        previous_status = previous_entry.get("evaluation", {}).get("status")
        updated = update_factor_status(
            factor_entry=factor_entry,
            validation_result=validation_result,
            now=now,
            config=config,
        )
        if persist:
            factor_id = updated.get("factor_id")
            if factor_id:
                self.data["factors"][factor_id] = updated
                self._dirty = True
                self._dirty_factor_ids.add(factor_id)
                new_status = updated.get("evaluation", {}).get("status")
                if previous_status != new_status:
                    summary = validation_result.get("summary", validation_result)
                    self._append_audit_entry(
                        factor_id=factor_id,
                        factor_name=updated.get("factor_name", factor_id),
                        old_status=previous_status or "pending_validation",
                        new_status=new_status or "unknown",
                        reason=summary.get("validation_summary", ""),
                        trigger="apply_validation_result",
                        timestamp=(now or datetime.now()).isoformat(),
                    )
                self._save()
        return updated

    def select_revalidation_candidates(
        self,
        *,
        days: int | None = None,
        status: str | None = None,
        factor_ids: list[str] | None = None,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        selected = []
        now = now or datetime.now()
        factor_id_set = {
            fid.strip() for fid in (factor_ids or []) if fid and fid.strip()
        }
        for factor_id, factor_entry in self.data.get("factors", {}).items():
            entry = self._normalize_factor_entry(factor_entry)
            evaluation = entry["evaluation"]
            if factor_id_set and factor_id not in factor_id_set:
                continue
            if status and evaluation.get("status") != status:
                continue
            if days is not None:
                last_validated = evaluation.get("last_validated")
                if last_validated:
                    try:
                        validated_at = datetime.fromisoformat(str(last_validated))
                    except ValueError:
                        validated_at = now - timedelta(days=days + 1)
                    if (now - validated_at).days < days:
                        continue
            selected.append(entry)
        return selected

    @staticmethod
    def _infer_dimensions(factor_entry: dict[str, Any]) -> list[str]:
        expr = str(factor_entry.get("factor_expression", ""))
        dimensions = ["price_volume"]
        if any(token in expr.lower() for token in ("roe", "roa", "profit", "margin")):
            dimensions.append("financial")
        return dimensions

    @staticmethod
    def _infer_fields(factor_entry: dict[str, Any]) -> list[str]:
        expr = str(factor_entry.get("factor_expression", ""))
        fields = []
        for token in (
            "$close",
            "$open",
            "$high",
            "$low",
            "$volume",
            "$amount",
            "$roe",
            "$roa",
            "$net_profit_margin",
        ):
            if token.lower() in expr.lower():
                fields.append(token)
        return fields

    @staticmethod
    def _extract_backtest_results(experiment) -> dict:
        """Extract backtest metrics from experiment.result (pandas Series) as dict."""
        result = getattr(experiment, "result", None)
        if result is None:
            return {}
        if isinstance(result, pd.Series):
            out = {}
            for key, val in result.items():
                # NaN/Inf -> None for JSON
                if isinstance(val, (float, np.floating)):
                    if np.isnan(val) or np.isinf(val):
                        out[str(key)] = None
                    else:
                        out[str(key)] = round(float(val), 8)
                else:
                    out[str(key)] = val
            return out

        if isinstance(result, pd.DataFrame):
            try:
                return {
                    str(k): round(float(v), 8)
                    if isinstance(v, (float, np.floating)) and not np.isnan(v)
                    else None
                    for k, v in result.iloc[:, 0].items()
                }
            except Exception:
                pass

        if isinstance(result, dict):
            return result

        return {}

    @staticmethod
    def _extract_feedback(feedback) -> dict:
        """Convert feedback object to serializable dict."""
        if feedback is None:
            return {}
        if isinstance(feedback, dict):
            return feedback

        out = {}
        for attr in [
            "observations",
            "hypothesis_evaluation",
            "decision",
            "reason",
            "new_hypothesis",
            "feedback_str",
        ]:
            val = getattr(feedback, attr, None)
            if val is not None:
                out[attr] = str(val) if not isinstance(val, (bool, int, float)) else val
        if not out:
            out["raw"] = str(feedback)
        return out

    def get_summary(self) -> dict:
        """Return library-level summary statistics."""
        factors = self.data.get("factors", {})
        status_counts: dict[str, int] = {}
        evolution_counts: dict[str, int] = {}
        total_validated = 0
        total_active = 0
        stability_scores = []
        latest_validated = None
        for fid, entry in factors.items():
            eval_data = entry.get("evaluation", {})
            status = eval_data.get("status", "pending_validation")
            status_counts[status] = status_counts.get(status, 0) + 1
            evolution = entry.get("metadata", {}).get("evolution_phase", "original")
            evolution_counts[evolution] = evolution_counts.get(evolution, 0) + 1
            if eval_data.get("last_validated"):
                total_validated += 1
                validated_at = eval_data.get("last_validated")
                if latest_validated is None or str(validated_at) > str(latest_validated):
                    latest_validated = validated_at
            if status == "active":
                total_active += 1
            score = eval_data.get("stability_score")
            if score is not None:
                stability_scores.append(float(score))

        avg_stability = (
            float(sum(stability_scores)) / len(stability_scores)
            if stability_scores
            else None
        )
        return {
            "total_factors": len(factors),
            "status_distribution": status_counts,
            "status_counts": status_counts,
            "evolution_counts": evolution_counts,
            "total_validated": total_validated,
            "total_active": total_active,
            "active_count": status_counts.get("active", 0),
            "degraded_count": status_counts.get("degraded", 0),
            "stale_count": status_counts.get("stale", 0),
            "last_validated": latest_validated,
            "avg_stability_score": round(avg_stability, 6)
            if avg_stability is not None
            else None,
            "last_updated": self.data.get("metadata", {}).get("last_updated"),
            "version": self.data.get("metadata", {}).get("version"),
        }

    def get_audit_trail(
        self,
        factor_id: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Return persisted audit trail entries."""
        since_dt = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since)
            except ValueError:
                pass

        entries = []
        for entry in self.data.get("metadata", {}).get("audit_trail", []):
            if factor_id and entry.get("factor_id") != factor_id:
                continue
            timestamp = entry.get("timestamp")
            if timestamp:
                try:
                    updated_dt = datetime.fromisoformat(str(timestamp))
                    if since_dt and updated_dt < since_dt:
                        continue
                    entries.append(entry)
                except ValueError:
                    pass

        entries.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
        return entries[:limit]

    def upsert_factor(
        self,
        factor_entry: dict[str, Any],
        *,
        now: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Atomically upsert a single factor entry with write lock."""
        factor_id = factor_entry.get("factor_id")
        if not factor_id:
            return factor_entry
        self.data["factors"][factor_id] = self._normalize_factor_entry(factor_entry)
        self._dirty = True
        self._dirty_factor_ids.add(factor_id)
        self._save()
        return self.data["factors"][factor_id]

    def batch_upsert(
        self,
        factor_entries: List[Dict[str, Any]],
        *,
        now: Optional[datetime] = None,
    ) -> int:
        """
        Batch upsert multiple factor entries, triggering only one disk write.

        More efficient than calling upsert_factor() in a loop because:
        1. Only one _load_from_disk + merge + json.dump cycle
        2. Only acquires/releases lock once

        Args:
            factor_entries: List of factor entry dicts to upsert
            now: Optional time override

        Returns:
            Number of factors successfully upserted
        """
        count = 0
        for entry in factor_entries:
            factor_id = entry.get("factor_id")
            if not factor_id:
                continue
            self.data["factors"][factor_id] = self._normalize_factor_entry(entry)
            self._dirty = True
            self._dirty_factor_ids.add(factor_id)
            count += 1

        if self._dirty:
            self._save()

        logger.info(f"Batch upsert: {count} factors persisted in single write")
        return count

    def flush(self):
        """Explicitly persist any pending changes. Public interface for _save()."""
        if self._dirty:
            self._save()
        else:
            logger.debug("flush() called but nothing to save")

    def get_factor(self, factor_id: str) -> Optional[dict[str, Any]]:
        """Get a single factor by ID."""
        entry = self.data.get("factors", {}).get(factor_id)
        if entry:
            return self._normalize_factor_entry(entry)
        return None

    def list_factor_ids(self, status: Optional[str] = None) -> list[str]:
        """List all factor IDs, optionally filtered by status."""
        factors = self.data.get("factors", {})
        if status is None:
            return list(factors.keys())
        return [
            fid
            for fid, entry in factors.items()
            if entry.get("evaluation", {}).get("status") == status
        ]

    def check_redundancy(
        self,
        new_factor_expression: str,
        correlation_threshold: float = 0.85,
        max_comparisons: int = 50,
    ) -> Dict[str, Any]:
        """
        Check if a new factor expression is redundant with existing factors.

        Method:
        1. Expression string similarity pre-filter (fast elimination of obvious non-matches)
        2. Factor value cross-section correlation check (if factor values available)

        Args:
            new_factor_expression: The factor expression to check
            correlation_threshold: Similarity threshold (0-1)
            max_comparisons: Maximum number of comparisons (to limit computation)

        Returns:
            {
                "is_redundant": bool,
                "most_similar_factor_id": str or None,
                "max_similarity": float,
                "method": "expression" | "value" | None,
                "comparisons_made": int,
            }
        """
        import re

        result: Dict[str, Any] = {
            "is_redundant": False,
            "most_similar_factor_id": None,
            "max_similarity": 0.0,
            "method": None,
            "comparisons_made": 0,
        }

        try:
            active_factors = self.select_revalidation_candidates(status="active")
        except Exception:
            # fail-open: if we can't query the library, don't block admission
            return result

        if not active_factors:
            return result

        # Limit comparison count
        candidates = active_factors[:max_comparisons]
        result["comparisons_made"] = len(candidates)

        # Stage 1: Expression string similarity
        new_normalized = self._normalize_expression_for_comparison(new_factor_expression)

        max_sim = 0.0
        most_similar_id = None

        for factor in candidates:
            existing_expr = factor.get("factor_expression", "")
            existing_normalized = self._normalize_expression_for_comparison(existing_expr)

            similarity = self._expression_similarity(new_normalized, existing_normalized)

            if similarity > max_sim:
                max_sim = similarity
                most_similar_id = factor.get("factor_id")

        result["max_similarity"] = max_sim
        result["most_similar_factor_id"] = most_similar_id
        result["method"] = "expression"

        # Expression identical
        if max_sim >= 0.99:
            result["is_redundant"] = True
            return result

        # Expression highly similar (above threshold)
        if max_sim >= correlation_threshold:
            result["is_redundant"] = True
            return result

        return result

    def _normalize_expression_for_comparison(self, expr: str) -> str:
        """
        Normalize expression for comparison.

        Removes whitespace, unifies case, replaces numeric parameters with placeholders.
        """
        import re

        if not expr:
            return ""

        normalized = expr.strip().lower()
        # Remove extra whitespace
        normalized = re.sub(r"\s+", "", normalized)
        return normalized

    def _expression_similarity(self, expr_a: str, expr_b: str) -> float:
        """
        Calculate similarity between two normalized expressions.

        Uses set-based Jaccard similarity + edit distance hybrid:
        - Split expression into token sets by operators
        - Calculate Jaccard coefficient
        - For short expressions, supplement with edit distance

        Returns:
            Similarity value 0.0 ~ 1.0
        """
        import re

        if not expr_a or not expr_b:
            return 0.0

        if expr_a == expr_b:
            return 1.0

        # Tokenize: split by operators and parentheses
        def tokenize(expr: str) -> set:
            return set(re.findall(r"[a-z_]+|\$[a-z_]+|\d+", expr))

        tokens_a = tokenize(expr_a)
        tokens_b = tokenize(expr_b)

        if not tokens_a and not tokens_b:
            return 1.0
        if not tokens_a or not tokens_b:
            return 0.0

        # Jaccard coefficient
        intersection = len(tokens_a & tokens_b)
        union = len(tokens_a | tokens_b)
        jaccard = intersection / union if union > 0 else 0.0

        # For short expressions, supplement with structured comparison
        # Remove numeric parameters and compare skeleton
        def skeleton(expr: str) -> str:
            return re.sub(r"\d+", "N", expr)

        skel_a = skeleton(expr_a)
        skel_b = skeleton(expr_b)

        if skel_a == skel_b:
            # Only parameters differ — highly similar
            return max(jaccard, 0.90)

        return jaccard
