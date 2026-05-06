# ruff: noqa: D100,D103,D212,D415
"""QuantaAlpha 环境健康检查。

QuantaAlpha 环境健康检查。

检查项目：
- Docker 可用性（可选）
- 端口占用（UI 端口）
- 数据能力配置可发现性
- 因子库 JSON/parquet 可读性
- LLM provider 配置状态
- 返回结构化 dict，供 Fire CLI 和 shell 脚本解析
"""

from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Any


def _resolve_roots() -> dict[str, Path]:
    """解析 quantaalpha 项目根和 aspipe_v4 仓库根。"""
    quantaalpha_root = Path(__file__).resolve().parents[3]
    repo_root = quantaalpha_root.parents[1]
    return {
        "quantaalpha_root": quantaalpha_root,
        "repo_root": repo_root,
    }


def _check_docker() -> dict[str, Any]:
    """检查 Docker 状态（非强制）。"""
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return {"status": "ok", "reason": "docker reachable"}
    except Exception as e:
        return {"status": "skipped", "reason": f"docker not available: {e}"}


def _check_ports(start_port: int = 19899, max_ports: int = 10) -> dict[str, Any]:
    """检查 UI 端口占用。"""
    free_ports: list[int] = []
    occupied_ports: list[int] = []
    for port in range(start_port, start_port + max_ports):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                occupied_ports.append(port)
            else:
                free_ports.append(port)

    if start_port in occupied_ports:
        return {
            "status": "warning",
            "reason": f"port {start_port} occupied",
            "free_ports": free_ports[:5],
        }
    return {"status": "ok", "reason": f"port {start_port} free", "free_ports": free_ports[:5]}


def _check_data_capability() -> dict[str, Any]:
    """检查数据能力配置可发现性。"""
    roots = _resolve_roots()
    repo_root = roots["repo_root"]
    quantaalpha_root = roots["quantaalpha_root"]
    config_candidates = [
        repo_root / "config" / "pipeline.yaml",
        repo_root / "config" / "factor_pool.yaml",
        quantaalpha_root / "configs" / "backtest.yaml",
        quantaalpha_root / "configs" / "experiment.yaml",
    ]
    found = [str(p) for p in config_candidates if p.exists()]
    if found:
        return {"status": "ok", "reason": f"{len(found)} config(s) found", "paths": found}
    return {"status": "missing", "reason": "no data capability config found in expected locations"}


def _check_factor_library() -> dict[str, Any]:
    """检查因子库 JSON/parquet 可读性。"""
    roots = _resolve_roots()
    repo_root = roots["repo_root"]
    quantaalpha_root = roots["quantaalpha_root"]
    library_candidates = [
        repo_root / "data" / "factor_pool",
        quantaalpha_root / "data" / "factorlib" / "parquet_store",
        quantaalpha_root / "data" / "factorlib" / "all_factors_library.json",
        quantaalpha_root / "data" / "factorlib" / "factors.json",
    ]
    result: dict[str, Any] = {"status": "missing", "reason": "no factor library found"}
    for candidate in library_candidates:
        if candidate.is_file() and candidate.suffix == ".json":
            result = {"status": "ok", "reason": f"factor library found: {candidate}"}
            break
        if candidate.is_dir():
            parquet_files = list(candidate.glob("*.parquet"))
            if parquet_files:
                try:
                    import polars as pl
                    schema = pl.read_parquet_schema(parquet_files[0])
                    key_cols = [c for c in schema if c in ("trade_date", "instrument", "factor_id")]
                    result = {
                        "status": "ok",
                        "reason": f"factor pool dir readable: {len(parquet_files)} parquet files, schema keys: {key_cols}",
                    }
                except Exception as e:
                    result = {
                        "status": "degraded",
                        "reason": f"factor pool dir found but unreadable: {e}",
                    }
                break
    return result


def _check_llm_provider() -> dict[str, Any]:
    """检查 LLM provider 配置状态（不调用付费 API）。"""
    llm_env_vars = [
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "ANTHROPIC_API_KEY",
        "LLM_PROVIDER",
        "LLM_MODEL",
    ]
    configured_vars = [v for v in llm_env_vars if os.environ.get(v)]
    if configured_vars:
        return {
            "status": "configured",
            "reason": f"{len(configured_vars)}/{len(llm_env_vars)} env vars set: {configured_vars}",
        }
    # 检查是否有 LLM 相关 Python 包
    try:
        import openai  # noqa: F401
        return {"status": "missing", "reason": f"openai installed but no API keys set; set {llm_env_vars}"}
    except ImportError:
        return {"status": "skipped", "reason": "LLM provider not configured (no keys, no openai package)"}


def health_check() -> dict[str, Any]:
    """
    统一健康检查入口。

    Returns:
        结构化 dict:
        {
            "overall_pass": true/false,
            "checks": {
                "docker": {...},
                "ports": {...},
                "data_capability": {...},
                "factor_library": {...},
                "llm_provider": {...},
            }
        }
    """
    checks: dict[str, dict[str, Any]] = {}

    checks["docker"] = _check_docker()
    checks["ports"] = _check_ports()
    checks["data_capability"] = _check_data_capability()
    checks["factor_library"] = _check_factor_library()
    checks["llm_provider"] = _check_llm_provider()

    hard_failures = [
        name
        for name, result in checks.items()
        if result.get("status") in ("missing", "degraded") and name not in ("docker", "llm_provider")
    ]
    overall_pass = len(hard_failures) == 0

    return {
        "overall_pass": overall_pass,
        "checks": checks,
    }
