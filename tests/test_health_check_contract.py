# ruff: noqa: D100,D101,D102,D103,D212,D403,D415
"""
quantaalpha health_check 契约测试。

验证健康检查返回结构化 dict 包含所有必需检查项。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quantaalpha.app.utils import health_check as health_module
from quantaalpha.app.utils.health_check import health_check


class TestHealthCheckContract:
    """health_check() 返回值契约测试。"""

    def test_returns_dict_with_overall_pass(self):
        """health_check() 应返回包含 overall_pass 的 dict。"""
        result = health_check()
        assert isinstance(result, dict)
        assert "overall_pass" in result
        assert "checks" in result

    def test_checks_contain_all_required_names(self):
        """checks 应包含所有五个检查项。"""
        result = health_check()
        checks = result["checks"]
        required = {"docker", "ports", "data_capability", "factor_library", "llm_provider"}
        assert set(checks.keys()) >= required, f"missing checks: {required - set(checks.keys())}"

    def test_each_check_has_status_and_reason(self):
        """每个检查项应包含 status 和 reason。"""
        result = health_check()
        for name, check in result["checks"].items():
            assert "status" in check, f"'{name}' missing 'status'"
            assert "reason" in check, f"'{name}' missing 'reason'"
            assert isinstance(check["status"], str)
            assert isinstance(check["reason"], str)

    def test_data_capability_check(self):
        """data_capability 检查应报告 config 发现状态。"""
        result = health_check()
        dc = result["checks"]["data_capability"]
        assert dc["status"] in ("ok", "missing")

    def test_factor_library_check(self):
        """factor_library 检查应报告库状态。"""
        result = health_check()
        fl = result["checks"]["factor_library"]
        assert fl["status"] in ("ok", "missing", "degraded")

    def test_llm_provider_check(self):
        """llm_provider 检查应报告配置状态。"""
        result = health_check()
        lp = result["checks"]["llm_provider"]
        assert lp["status"] in ("configured", "missing", "skipped")

    def test_repo_root_points_to_aspipeline_repo(self):
        """仓库根路径应指向 aspipe_v4，而不是 quantaalpha package 目录。"""
        paths = health_module._resolve_roots()
        assert paths["repo_root"].name == "aspipe_v4"
        assert paths["quantaalpha_root"].name == "quantaalpha"
