"""
路径解析单元测试 - resolve_path 和 resolve_workspace_paths.

测试覆盖：
- resolve_path 基础功能（相对/绝对路径、Path 对象、无 project_root）
- resolve_workspace_paths 完整配置解析
- 路径冲突检测
- 原始 dict 不被修改
- monitoring_output_path 优先级逻辑
"""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from quantaalpha.continuous.paths import resolve_path, resolve_workspace_paths


# =============================================================================
# resolve_path 基础测试
# =============================================================================


class TestResolvePath(unittest.TestCase):
    """resolve_path 函数的单元测试。"""

    def test_relative_path_resolved(self):
        """相对路径应基于 project_root 解析为绝对路径。"""
        p = resolve_path("log/continuous/mining", "/home/quan/testdata/aspipe_v4")
        self.assertEqual(str(p), "/home/quan/testdata/aspipe_v4/log/continuous/mining")
        self.assertTrue(p.is_absolute())

    def test_absolute_path_unchanged(self):
        """绝对路径应保持原样，不受 project_root 影响。"""
        p = resolve_path("/custom/log/dir", "/home/quan/testdata/aspipe_v4")
        self.assertEqual(str(p), "/custom/log/dir")

    def test_no_project_root_uses_cwd(self):
        """不提供 project_root 时应使用 cwd 解析。"""
        p = resolve_path("log/test")
        self.assertTrue(p.is_absolute())
        # 应包含 cwd 的路径
        self.assertIn(str(Path.cwd().resolve()), str(p))

    def test_path_object_input(self):
        """resolve_path 应同时支持 str 和 Path 对象作为输入。"""
        p = resolve_path(Path("log/test"), Path("/home/quan"))
        self.assertEqual(str(p), "/home/quan/log/test")
        self.assertTrue(p.is_absolute())

    def test_path_object_with_project_root_str(self):
        """Path 对象输入 + str 类型 project_root 应正常工作。"""
        p = resolve_path(Path("data/factorlib"), "/home/quan/project")
        self.assertEqual(str(p), "/home/quan/project/data/factorlib")


# =============================================================================
# resolve_workspace_paths 完整测试
# =============================================================================


class TestResolveWorkspacePaths(unittest.TestCase):
    """resolve_workspace_paths 函数的单元测试。"""

    def test_full_workspace_resolution(self):
        """完整配置应正确解析所有路径为绝对路径。"""
        raw = {
            "workspace": {
                "project_root": "/home/quan/testdata/aspipe_v4",
                "log_root": "log",
                "runs_dir": "continuous/runs",
                "monitoring_output_path": "monitoring",
            },
            "mining": {
                "log_root": "continuous/mining",
                "state": {
                    "pool_save_path": "continuous/trajectory_pool.json",
                },
            },
            "factor": {
                "library_path": "data/factorlib/all_factors_library.json",
            },
        }
        resolved = resolve_workspace_paths(raw)

        # 验证所有路径都是绝对路径
        for key, value in resolved.items():
            self.assertTrue(
                Path(value).is_absolute(),
                f"{key} 应为绝对路径，实际为: {value}",
            )

        # 验证具体路径值
        self.assertEqual(
            resolved["mining_log_root"],
            "/home/quan/testdata/aspipe_v4/log/continuous/mining",
        )
        self.assertEqual(
            resolved["runs_dir"],
            "/home/quan/testdata/aspipe_v4/log/continuous/runs",
        )
        self.assertEqual(
            resolved["pool_save_path"],
            "/home/quan/testdata/aspipe_v4/log/continuous/trajectory_pool.json",
        )
        self.assertEqual(
            resolved["factor_library_path"],
            "/home/quan/testdata/aspipe_v4/data/factorlib/all_factors_library.json",
        )
        self.assertEqual(
            resolved["monitoring_output_path"],
            "/home/quan/testdata/aspipe_v4/log/monitoring",
        )

    def test_empty_config_uses_defaults(self):
        """空配置应使用所有默认值，且结果都是绝对路径。"""
        resolved = resolve_workspace_paths({})

        # 所有值都应为绝对路径
        self.assertTrue(Path(resolved["log_root"]).is_absolute())
        self.assertTrue(Path(resolved["mining_log_root"]).is_absolute())
        self.assertTrue(Path(resolved["runs_dir"]).is_absolute())
        self.assertTrue(Path(resolved["pool_save_path"]).is_absolute())
        self.assertTrue(Path(resolved["factor_library_path"]).is_absolute())
        self.assertTrue(Path(resolved["monitoring_output_path"]).is_absolute())

        # 默认值应包含预期的相对路径片段
        self.assertIn("log", resolved["log_root"])
        self.assertIn("continuous", resolved["mining_log_root"])
        self.assertIn("continuous", resolved["runs_dir"])
        self.assertIn("trajectory_pool.json", resolved["pool_save_path"])

    def test_nested_relative_paths(self):
        """project_root 为相对路径时，也应正确解析为绝对路径。"""
        resolved = resolve_workspace_paths({
            "workspace": {"project_root": ".", "log_root": "my_logs"}
        })

        self.assertTrue(Path(resolved["log_root"]).is_absolute())
        self.assertTrue(resolved["log_root"].endswith("my_logs"))

    def test_path_conflict_detection(self):
        """当 runs_dir 与 mining_log_root 存在包含关系时，应抛出 ValueError。"""
        with self.assertRaises(ValueError) as ctx:
            resolve_workspace_paths({
                "workspace": {
                    "project_root": "/test",
                    "log_root": "log",
                    "runs_dir": "continuous/mining/runs",  # 嵌套在 mining_log_root 下
                },
                "mining": {
                    "log_root": "continuous/mining",
                },
            })

        # 错误信息应包含"路径冲突"
        self.assertIn("路径冲突", str(ctx.exception))

    def test_original_dict_not_mutated(self):
        """resolve_workspace_paths 不应修改传入的原始 dict。"""
        raw = {
            "workspace": {
                "project_root": "/test",
                "log_root": "my_log",
            },
            "mining": {
                "log_root": "mining_log",
                "state": {"pool_save_path": "pool.json"},
            },
            "factor": {"library_path": "lib.json"},
        }
        original = copy.deepcopy(raw)
        resolve_workspace_paths(raw)
        self.assertEqual(raw, original)

    def test_monitoring_output_from_workspace(self):
        """workspace.monitoring_output_path 应优先于 factor.monitoring_output_path。"""
        resolved = resolve_workspace_paths({
            "workspace": {
                "project_root": "/test",
                "log_root": "log",
                "monitoring_output_path": "custom_monitor",
            },
            "factor": {
                "monitoring_output_path": "old_monitor",
            },
        })

        self.assertEqual(
            resolved["monitoring_output_path"],
            "/test/log/custom_monitor",
        )

    def test_monitoring_output_fallback_to_factor(self):
        """无 workspace.monitoring_output_path 时应 fallback 到 factor 段。"""
        resolved = resolve_workspace_paths({
            "workspace": {"project_root": "/test", "log_root": "log"},
            "factor": {"monitoring_output_path": "old_monitor"},
        })

        self.assertEqual(
            resolved["monitoring_output_path"],
            "/test/log/old_monitor",
        )

    def test_monitoring_default_value(self):
        """workspace 和 factor 均未配置 monitoring 时应使用默认值 'monitoring'。"""
        resolved = resolve_workspace_paths({
            "workspace": {"project_root": "/test", "log_root": "log"},
        })

        self.assertEqual(
            resolved["monitoring_output_path"],
            "/test/log/monitoring",
        )

    def test_absolute_path_in_config(self):
        """配置中直接写绝对路径时，不应拼接 project_root。"""
        resolved = resolve_workspace_paths({
            "workspace": {
                "project_root": "/home/quan/project",
                "log_root": "/custom/log",  # 绝对路径
            },
            "mining": {
                "log_root": "continuous/mining",  # 相对于 log_root
            },
        })

        self.assertEqual(resolved["log_root"], "/custom/log")
        # mining_log_root 应相对于 /custom/log
        self.assertEqual(
            resolved["mining_log_root"],
            "/custom/log/continuous/mining",
        )

    def test_returned_keys_complete(self):
        """返回值应包含所有预期的键。"""
        resolved = resolve_workspace_paths({})

        expected_keys = {
            "project_root",
            "log_root",
            "mining_log_root",
            "runs_dir",
            "pool_save_path",
            "factor_library_path",
            "monitoring_output_path",
        }
        self.assertEqual(set(resolved.keys()), expected_keys)


if __name__ == "__main__":
    unittest.main()
