"""
Date Anchor 分页组合测试

测试目标：
4. `reverse_date_range + is_date_anchor` 会拆成逐日请求
5. 非 date_anchor 接口继续按窗口生成请求

测试场景：
- 测试4: reverse_date_range + is_date_anchor 会拆成逐日请求
- 测试5: 非 date_anchor 接口继续按窗口生成请求
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import unittest
from typing import Dict, Any, List

from app4.core.pagination import (
    PaginationComposer,
    PaginationContext,
    migrate_legacy_config,
    create_context_with_legacy_support,
)


class TestDateAnchorComposer(unittest.TestCase):
    """Date Anchor 分页组合测试"""

    # =========================================================================
    # 测试4: reverse_date_range + is_date_anchor 会拆成逐日请求
    # =========================================================================
    def test_date_anchor_splits_into_daily_requests(self):
        """
        测试4: reverse_date_range + is_date_anchor 会拆成逐日请求
        
        输入场景：
        - start_date=20250101, end_date=20250103
        - trade_date.is_date_anchor = true
        
        断言：
        - 生成 3 个请求
        - 每个请求只包含一个 trade_date
        - 不再带原始 start_date/end_date
        - 顺序符合 reverse 语义
        """
        interface_config = {
            "name": "daily",
            "api_name": "daily",
            "parameters": {
                "trade_date": {
                    "type": "string",
                    "required": False,
                    "description": "交易日期",
                    "is_date_anchor": True,
                }
            },
            "pagination": {
                "mode": "reverse_date_range",
                "time_range": {
                    "enabled": True,
                    "window": "1d",
                    "reverse": True,
                },
            },
        }
        
        # 模拟交易日历
        trade_calendar = [
            {"cal_date": "20250101", "is_open": 1},
            {"cal_date": "20250102", "is_open": 1},
            {"cal_date": "20250103", "is_open": 1},
            {"cal_date": "20250104", "is_open": 0},  # 非交易日
            {"cal_date": "20250105", "is_open": 1},
        ]
        
        context = PaginationContext(
            interface_config=interface_config,
            trade_calendar=trade_calendar,
        )
        
        composer = PaginationComposer(context)
        base_params = {"start_date": "20250101", "end_date": "20250103"}
        
        params_list = list(composer.compose(base_params))
        
        # 验证：生成3个请求（对应3个交易日）
        self.assertEqual(len(params_list), 3)
        
        # 验证：每个请求只包含一个 trade_date
        for params in params_list:
            self.assertIn("trade_date", params)
            self.assertNotIn("start_date", params)
            self.assertNotIn("end_date", params)
        
        # 验证：顺序符合 reverse 语义（从后往前）
        dates = [p["trade_date"] for p in params_list]
        self.assertEqual(dates, ["20250103", "20250102", "20250101"])
        
        print("✓ 测试4通过: date_anchor 正确拆分成逐日请求，顺序符合 reverse 语义")

    def test_date_anchor_uses_trading_days_only(self):
        """
        测试4b: date_anchor 只使用交易日，跳过非交易日
        """
        interface_config = {
            "name": "daily",
            "parameters": {
                "trade_date": {
                    "type": "string",
                    "is_date_anchor": True,
                }
            },
            "pagination": {
                "mode": "reverse_date_range",
                "time_range": {
                    "enabled": True,
                    "window": "1d",
                    "reverse": True,
                },
            },
        }
        
        # 包含周末的交易日历
        trade_calendar = [
            {"cal_date": "20260220", "is_open": 1},  # 周五
            {"cal_date": "20260221", "is_open": 0},  # 周六
            {"cal_date": "20260222", "is_open": 0},  # 周日
            {"cal_date": "20260223", "is_open": 1},  # 周一
        ]
        
        context = PaginationContext(
            interface_config=interface_config,
            trade_calendar=trade_calendar,
        )
        
        composer = PaginationComposer(context)
        base_params = {"start_date": "20260220", "end_date": "20260223"}
        
        params_list = list(composer.compose(base_params))
        
        # 只生成2个请求（周五和周一）
        self.assertEqual(len(params_list), 2)
        
        dates = [p["trade_date"] for p in params_list]
        # reverse 顺序：周一在前，周五在后
        self.assertEqual(dates, ["20260223", "20260220"])
        
        print("✓ 测试4b通过: date_anchor 只使用交易日，跳过非交易日")

    # =========================================================================
    # 测试5: 非 date_anchor 接口继续按窗口生成请求
    # =========================================================================
    def test_non_date_anchor_uses_window_mode(self):
        """
        测试5: 非 date_anchor 接口继续按窗口生成请求
        
        输入场景：
        - window_size_days = 30
        - 未配置 is_date_anchor
        
        断言：
        - 生成的是按窗口切分的 start_date/end_date
        - 不会错误拆成逐日请求
        """
        interface_config = {
            "name": "repurchase",
            "api_name": "repurchase",
            "parameters": {
                "ann_date": {
                    "type": "string",
                    "required": False,
                    # 注意：没有 is_date_anchor
                }
            },
            "pagination": {
                "mode": "reverse_date_range",
                "time_range": {
                    "enabled": True,
                    "window": "30d",
                    "reverse": True,
                },
            },
        }
        
        # 模拟60天的交易日历
        trade_calendar = []
        for i in range(1, 61):
            day = f"2025{str(i).zfill(4)}"
            trade_calendar.append({"cal_date": day, "is_open": 1})
        
        context = PaginationContext(
            interface_config=interface_config,
            trade_calendar=trade_calendar,
        )
        
        composer = PaginationComposer(context)
        base_params = {"start_date": "20250001", "end_date": "20250060"}
        
        params_list = list(composer.compose(base_params))
        
        # 验证：生成的请求数量少于日期数量（因为按窗口切分）
        self.assertLess(len(params_list), 60)
        
        # 验证：每个请求包含 start_date/end_date（窗口范围）
        for params in params_list:
            self.assertIn("start_date", params)
            self.assertIn("end_date", params)
            # 不应该有 trade_date 锚定
            self.assertNotIn("trade_date", params)
        
        print(f"✓ 测试5通过: 非 date_anchor 接口按窗口切分（{len(params_list)} 个窗口）")

    def test_non_date_anchor_respects_window_size(self):
        """
        测试5b: 验证窗口大小正确应用
        """
        interface_config = {
            "name": "suspend_d",
            "parameters": {},
            "pagination": {
                "mode": "reverse_date_range",
                "time_range": {
                    "enabled": True,
                    "window": "10d",
                    "reverse": True,
                },
            },
        }
        
        # 25个交易日
        trade_calendar = [
            {"cal_date": f"202501{str(i).zfill(2)}", "is_open": 1}
            for i in range(1, 26)
        ]
        
        context = PaginationContext(
            interface_config=interface_config,
            trade_calendar=trade_calendar,
        )
        
        composer = PaginationComposer(context)
        base_params = {"start_date": "20250101", "end_date": "20250125"}
        
        params_list = list(composer.compose(base_params))
        
        # 25天按10天窗口切分，应该是3个窗口
        self.assertEqual(len(params_list), 3)
        
        # 验证窗口大小
        first_window = params_list[0]
        start = int(first_window["start_date"])
        end = int(first_window["end_date"])
        window_size = end - start + 1
        self.assertLessEqual(window_size, 10)
        
        print("✓ 测试5b通过: 窗口大小正确应用")

    # =========================================================================
    # 辅助测试: migrate_legacy_config
    # =========================================================================
    def test_migrate_legacy_config_preserves_mode(self):
        """测试 migrate_legacy_config 保留 mode 字段"""
        old_config = {
            "pagination": {
                "mode": "reverse_date_range",
                "window_size_days": 1,
            }
        }
        
        new_config = migrate_legacy_config(old_config)
        
        self.assertEqual(new_config.get("mode"), "reverse_date_range")
        print("✓ migrate_legacy_config 正确保留 mode 字段")

    def test_is_date_anchor_interface_detection(self):
        """测试 _is_date_anchor_interface 方法"""
        # date_anchor 接口
        date_anchor_config = {
            "name": "daily",
            "parameters": {
                "trade_date": {"is_date_anchor": True}
            },
            "pagination": {"mode": "reverse_date_range"},
        }
        context = PaginationContext(interface_config=date_anchor_config)
        composer = PaginationComposer(context)
        self.assertTrue(composer._is_date_anchor_interface())
        
        # 非 date_anchor 接口
        non_anchor_config = {
            "name": "repurchase",
            "parameters": {
                "ann_date": {"type": "string"}
            },
            "pagination": {"mode": "reverse_date_range"},
        }
        context = PaginationContext(interface_config=non_anchor_config)
        composer = PaginationComposer(context)
        self.assertFalse(composer._is_date_anchor_interface())
        
        print("✓ _is_date_anchor_interface 检测正确")


if __name__ == "__main__":
    unittest.main()
