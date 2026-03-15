"""
Offset 集成测试

测试目标：
6. 非 date_anchor 多日窗口在非原子 offset 下会保存脏数据
7. 非 date_anchor 多日窗口在原子 offset 下不保存当前窗口
8. date_anchor 单日窗口在原子 offset 下实现单日原子

测试场景：
- 测试6: 非 date_anchor 多日窗口 + 非原子 offset = 脏数据
- 测试7: 非 date_anchor 多日窗口 + 原子 offset = 窗口原子
- 测试8: date_anchor 单日窗口 + 原子 offset = 单日原子（最重要）
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import unittest
from unittest.mock import Mock, MagicMock
from typing import Dict, Any, List
from collections import defaultdict

from app4.core.pagination import PaginationComposer, PaginationContext
from app4.core.pagination_executor import PaginationExecutor


class TestOffsetIntegration(unittest.TestCase):
    """Offset 集成测试"""

    def setUp(self):
        """测试初始化"""
        self.executor = PaginationExecutor()

    # =========================================================================
    # 测试6: 非 date_anchor 多日窗口在非原子 offset 下会保存脏数据
    # =========================================================================
    def test_multi_day_window_non_atomic_saves_dirty_data(self):
        """
        测试6: 非 date_anchor 多日窗口在非原子 offset 下会保存脏数据
        
        输入场景：
        - 一个窗口覆盖多个日期
        - API 返回数据顺序跨越多个日期
        - offset 第 2 页失败
        - commit_on_success = false
        
        断言：
        - 存储层收到的数据包含前几页
        - 其中至少一个日期数据不完整
        """
        # 模拟存储
        saved_data = defaultdict(list)
        
        def save_callback(interface_name: str, data: List[Dict]) -> None:
            saved_data[interface_name].extend(data)
        
        # 模拟 make_request：第1页成功，第2页失败
        # 关键：limit=3，第1页返回3条数据（满页），触发第二页请求
        def make_request(interface_config: Dict, params: Dict) -> List[Dict]:
            offset = params.get("offset", 0)
            limit = params.get("limit", 3)
            
            if offset == 0:
                # 第1页：返回满页数据（limit条），触发下一页请求
                return [
                    {"ts_code": "000001.SZ", "trade_date": "20250101", "close": 10.0},
                    {"ts_code": "000002.SZ", "trade_date": "20250101", "close": 20.0},
                    {"ts_code": "000001.SZ", "trade_date": "20250102", "close": 10.1},
                ]
            else:
                # 第2页失败
                raise RuntimeError("API error on page 2")
        
        interface_config = {
            "name": "test_multi_day",
            "api_name": "test_multi_day",
            "pagination": {
                "mode": "reverse_date_range",
                "time_range": {
                    "enabled": True,
                    "window": "2d",
                },
                "offset": {
                    "enabled": True,
                    "limit": 3,  # 关键：limit设为3，确保第一页满页
                    "commit_on_success": False,  # 非原子
                },
            },
        }
        
        trade_calendar = [
            {"cal_date": "20250101", "is_open": 1},
            {"cal_date": "20250102", "is_open": 1},
        ]
        
        context = PaginationContext(
            interface_config=interface_config,
            trade_calendar=trade_calendar,
        )
        
        # 执行
        base_params = {"start_date": "20250101", "end_date": "20250102"}
        
        with self.assertRaises(RuntimeError):
            self.executor.execute(
                interface_config=interface_config,
                base_params=base_params,
                context=context,
                make_request=make_request,
                save_callback=save_callback,
            )
        
        # 验证：保存了第1页数据（脏数据）
        self.assertIn("test_multi_day", saved_data)
        saved = saved_data["test_multi_day"]
        self.assertEqual(len(saved), 3)
        
        # 验证：20250102 只有1条数据，不完整
        dates_20250102 = [r for r in saved if r["trade_date"] == "20250102"]
        self.assertEqual(len(dates_20250102), 1)  # 只有1条，应该有更多股票
        
        print("✓ 测试6通过: 非 date_anchor 多日窗口 + 非原子 offset 会保存脏数据")

    # =========================================================================
    # 测试7: 非 date_anchor 多日窗口在原子 offset 下不保存当前窗口
    # =========================================================================
    def test_multi_day_window_atomic_no_save_on_failure(self):
        """
        测试7: 非 date_anchor 多日窗口在原子 offset 下不保存当前窗口
        
        输入场景：
        - 同上
        - commit_on_success = true
        
        断言：
        - 当前窗口零保存
        - buffer / queue 中没有该窗口数据
        """
        saved_data = defaultdict(list)
        
        def save_callback(interface_name: str, data: List[Dict]) -> None:
            saved_data[interface_name].extend(data)
        
        # 关键：limit=2，第一页返回2条（满页），触发第二页请求
        def make_request(interface_config: Dict, params: Dict) -> List[Dict]:
            offset = params.get("offset", 0)
            if offset == 0:
                return [
                    {"ts_code": "000001.SZ", "trade_date": "20250101", "close": 10.0},
                    {"ts_code": "000002.SZ", "trade_date": "20250102", "close": 20.0},
                ]
            raise RuntimeError("API error on page 2")
        
        interface_config = {
            "name": "test_atomic_window",
            "api_name": "test_atomic_window",
            "pagination": {
                "mode": "reverse_date_range",
                "time_range": {
                    "enabled": True,
                    "window": "2d",
                },
                "offset": {
                    "enabled": True,
                    "limit": 2,  # 关键：limit=2
                    "commit_on_success": True,  # 原子模式
                },
            },
        }
        
        trade_calendar = [
            {"cal_date": "20250101", "is_open": 1},
            {"cal_date": "20250102", "is_open": 1},
        ]
        
        context = PaginationContext(
            interface_config=interface_config,
            trade_calendar=trade_calendar,
        )
        
        base_params = {"start_date": "20250101", "end_date": "20250102"}
        
        with self.assertRaises(RuntimeError):
            self.executor.execute(
                interface_config=interface_config,
                base_params=base_params,
                context=context,
                make_request=make_request,
                save_callback=save_callback,
            )
        
        # 验证：当前窗口零保存
        self.assertEqual(len(saved_data["test_atomic_window"]), 0)
        
        print("✓ 测试7通过: 非 date_anchor 多日窗口 + 原子 offset 不保存失败窗口")

    # =========================================================================
    # 测试8: date_anchor 单日窗口在原子 offset 下实现单日原子（最重要）
    # =========================================================================
    def test_date_anchor_single_day_atomic(self):
        """
        测试8: date_anchor 单日窗口在原子 offset 下实现单日原子
        
        输入场景：
        - trade_date.is_date_anchor = true
        - 连续 3 个交易日任务
        - 第 2 天 offset 第 2 页失败
        
        断言：
        - 第 1 天完整保存
        - 第 2 天完全不保存
        - 第 3 天如果未执行则无数据，若执行成功则完整保存
        - 不会出现"第 2 天只保存了部分股票"的情况
        """
        saved_data = defaultdict(list)
        request_log = []
        
        def save_callback(interface_name: str, data: List[Dict]) -> None:
            saved_data[interface_name].extend(data)
        
        def make_request(interface_config: Dict, params: Dict) -> List[Dict]:
            trade_date = params.get("trade_date")
            offset = params.get("offset", 0)
            request_log.append({"trade_date": trade_date, "offset": offset})
            
            if trade_date == "20250101":
                # 第1天：成功返回所有数据（2页）
                if offset == 0:
                    return [
                        {"ts_code": "000001.SZ", "trade_date": "20250101", "close": 10.0},
                        {"ts_code": "000002.SZ", "trade_date": "20250101", "close": 20.0},
                    ]
                else:
                    return [
                        {"ts_code": "000003.SZ", "trade_date": "20250101", "close": 30.0},
                    ]
            elif trade_date == "20250102":
                # 第2天：第1页成功（满页），第2页失败
                if offset == 0:
                    # 关键：返回 limit 条数据（满页），触发第二页请求
                    return [
                        {"ts_code": "000001.SZ", "trade_date": "20250102", "close": 10.1},
                        {"ts_code": "000002.SZ", "trade_date": "20250102", "close": 20.1},
                    ]
                else:
                    raise RuntimeError("API error on 20250102 page 2")
            elif trade_date == "20250103":
                # 第3天：成功
                if offset == 0:
                    return [
                        {"ts_code": "000001.SZ", "trade_date": "20250103", "close": 10.2},
                        {"ts_code": "000002.SZ", "trade_date": "20250103", "close": 20.2},
                    ]
                return []
            
            return []
        
        interface_config = {
            "name": "daily",
            "api_name": "daily",
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
                "offset": {
                    "enabled": True,
                    "limit": 2,  # 每页2条
                    "commit_on_success": True,  # 原子模式
                },
            },
        }
        
        trade_calendar = [
            {"cal_date": "20250101", "is_open": 1},
            {"cal_date": "20250102", "is_open": 1},
            {"cal_date": "20250103", "is_open": 1},
        ]
        
        context = PaginationContext(
            interface_config=interface_config,
            trade_calendar=trade_calendar,
        )
        
        base_params = {"start_date": "20250101", "end_date": "20250103"}
        
        # 执行（会抛出异常，因为第2天失败）
        with self.assertRaises(RuntimeError):
            self.executor.execute(
                interface_config=interface_config,
                base_params=base_params,
                context=context,
                make_request=make_request,
                save_callback=save_callback,
            )
        
        # 验证：第1天完整保存（reverse 模式下先执行 20250103）
        # reverse 顺序：20250103 -> 20250102 -> 20250101
        saved = saved_data["daily"]
        
        # 由于是 reverse 顺序，第3天先执行并成功保存
        day3_data = [r for r in saved if r["trade_date"] == "20250103"]
        self.assertEqual(len(day3_data), 2, "第3天应完整保存")
        
        # 第2天失败，不应保存
        day2_data = [r for r in saved if r["trade_date"] == "20250102"]
        self.assertEqual(len(day2_data), 0, "第2天失败后不应保存任何数据")
        
        # 第1天（因为第2天失败，执行停止，第1天未执行）
        day1_data = [r for r in saved if r["trade_date"] == "20250101"]
        # 在顺序执行模式下，第2天失败后不会继续执行第1天
        self.assertEqual(len(day1_data), 0, "第1天未执行")
        
        # 验证请求顺序
        requested_dates = [r["trade_date"] for r in request_log]
        self.assertEqual(requested_dates[0], "20250103", "reverse 模式应先请求 20250103")
        self.assertEqual(requested_dates[2], "20250102", "然后请求 20250102")
        
        print("✓ 测试8通过: date_anchor + 原子 offset 实现单日原子")
        print(f"  - 第3天完整保存: {len(day3_data)} 条")
        print(f"  - 第2天零保存: {len(day2_data)} 条")
        print(f"  - 第1天未执行: {len(day1_data)} 条")

    def test_date_anchor_atomic_all_success(self):
        """
        测试8b: date_anchor 所有日期都成功时完整保存
        """
        saved_data = defaultdict(list)
        
        def save_callback(interface_name: str, data: List[Dict]) -> None:
            saved_data[interface_name].extend(data)
        
        def make_request(interface_config: Dict, params: Dict) -> List[Dict]:
            trade_date = params.get("trade_date")
            offset = params.get("offset", 0)
            
            if offset == 0:
                return [
                    {"ts_code": "000001.SZ", "trade_date": trade_date, "close": 10.0},
                    {"ts_code": "000002.SZ", "trade_date": trade_date, "close": 20.0},
                ]
            return []
        
        interface_config = {
            "name": "daily",
            "api_name": "daily",
            "parameters": {
                "trade_date": {"is_date_anchor": True}
            },
            "pagination": {
                "mode": "reverse_date_range",
                "time_range": {
                    "enabled": True,
                    "window": "1d",
                    "reverse": True,
                },
                "offset": {
                    "enabled": True,
                    "limit": 100,
                    "commit_on_success": True,
                },
            },
        }
        
        trade_calendar = [
            {"cal_date": "20250101", "is_open": 1},
            {"cal_date": "20250102", "is_open": 1},
            {"cal_date": "20250103", "is_open": 1},
        ]
        
        context = PaginationContext(
            interface_config=interface_config,
            trade_calendar=trade_calendar,
        )
        
        base_params = {"start_date": "20250101", "end_date": "20250103"}
        
        result = self.executor.execute(
            interface_config=interface_config,
            base_params=base_params,
            context=context,
            make_request=make_request,
            save_callback=save_callback,
        )
        
        # 所有3天都完整保存
        saved = saved_data["daily"]
        self.assertEqual(len(saved), 6)  # 3天 * 2条
        
        # 每天都有2条数据
        for date in ["20250101", "20250102", "20250103"]:
            day_data = [r for r in saved if r["trade_date"] == date]
            self.assertEqual(len(day_data), 2)
        
        print("✓ 测试8b通过: date_anchor 所有日期都成功时完整保存")


if __name__ == "__main__":
    unittest.main()