"""
Offset 原子性行为测试

测试目标：
1. 非原子 offset 异常时会产生部分保存
2. 原子 offset 异常时不保存当前窗口数据
3. 原子 offset 成功时只提交一次

测试场景：
- 测试1: 非原子 offset 异常时会产生部分保存
- 测试2: 原子 offset 异常时不保存当前窗口数据  
- 测试3: 原子 offset 成功时只提交一次
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import unittest
from unittest.mock import Mock, call
from typing import Dict, Any, List

from app4.core.pagination_executor import PaginationExecutor


class TestOffsetAtomicBehavior(unittest.TestCase):
    """Offset 原子性行为测试"""

    def setUp(self):
        """测试初始化"""
        self.executor = PaginationExecutor()
        self.interface_config = {"name": "test_interface"}

    # =========================================================================
    # 测试1: 非原子 offset 异常时会产生部分保存
    # =========================================================================
    def test_non_atomic_offset_saves_partial_data_on_exception(self):
        """
        测试1: 非原子 offset 异常时会产生部分保存
        
        输入场景：
        - 第 1 页返回数据
        - 第 2 页抛出异常
        - commit_on_success = false
        
        断言：
        - 已有页数据被回调或保存
        - 异常继续向上抛出
        """
        # 记录回调调用
        saved_data = []
        
        def save_callback(interface_name: str, data: List[Dict[str, Any]]) -> None:
            saved_data.append((interface_name, data))
        
        def make_request(_interface_config: Dict, params: Dict) -> List[Dict]:
            offset = params["offset"]
            if offset == 0:
                # 第1页返回数据
                return [{"id": 1, "trade_date": "20250101"}, {"id": 2, "trade_date": "20250101"}]
            else:
                # 第2页抛出异常
                raise RuntimeError("API error on page 2")
        
        params = {
            "_offset_pagination": {
                "enabled": True,
                "limit": 2,
                "commit_on_success": False,  # 非原子模式
            }
        }
        
        # 执行并捕获异常
        with self.assertRaises(RuntimeError) as context:
            self.executor._execute_single_request(
                self.interface_config,
                params,
                make_request,
                save_callback=save_callback,
            )
        
        # 验证：异常被正确抛出
        self.assertIn("API error on page 2", str(context.exception))
        
        # 验证：第1页数据已被保存（这是问题的根源！）
        self.assertEqual(len(saved_data), 1)
        self.assertEqual(saved_data[0][0], "test_interface")
        self.assertEqual(len(saved_data[0][1]), 2)
        print("✓ 测试1通过: 非原子 offset 异常时会保存部分数据（证实问题存在）")

    # =========================================================================
    # 测试2: 原子 offset 异常时不保存当前窗口数据
    # =========================================================================
    def test_atomic_offset_discards_partial_data_on_exception(self):
        """
        测试2: 原子 offset 异常时不保存当前窗口数据
        
        输入场景：
        - 第 1 页返回数据
        - 第 2 页抛出异常
        - commit_on_success = true
        
        断言：
        - on_data_ready 不被调用
        - save_callback 不被调用
        - 当前窗口没有任何数据落盘
        """
        # 记录回调调用
        on_data_ready_calls = []
        save_callback_calls = []
        
        def on_data_ready(data: List[Dict[str, Any]]) -> None:
            on_data_ready_calls.append(data)
        
        def save_callback(interface_name: str, data: List[Dict[str, Any]]) -> None:
            save_callback_calls.append((interface_name, data))
        
        def make_request(_interface_config: Dict, params: Dict) -> List[Dict]:
            offset = params["offset"]
            if offset == 0:
                return [{"id": 1, "trade_date": "20250101"}, {"id": 2, "trade_date": "20250101"}]
            else:
                raise RuntimeError("API error on page 2")
        
        params = {
            "_offset_pagination": {
                "enabled": True,
                "limit": 2,
                "commit_on_success": True,  # 原子模式
            }
        }
        
        # 执行并捕获异常
        with self.assertRaises(RuntimeError) as context:
            self.executor._execute_single_request(
                self.interface_config,
                params,
                make_request,
                on_data_ready=on_data_ready,
                save_callback=save_callback,
            )
        
        # 验证：异常被正确抛出
        self.assertIn("API error on page 2", str(context.exception))
        
        # 验证：当前窗口数据被丢弃，不保存
        self.assertEqual(len(on_data_ready_calls), 0, "on_data_ready 不应被调用")
        self.assertEqual(len(save_callback_calls), 0, "save_callback 不应被调用")
        print("✓ 测试2通过: 原子 offset 异常时不保存当前窗口数据")

    def test_atomic_offset_discards_partial_data_with_save_callback(self):
        """
        测试2b: 原子 offset 异常时，即使有 save_callback 也不保存
        
        这个测试验证在原子模式下，即使配置了 save_callback，
        失败的窗口也不会保存任何数据。
        """
        save_callback_calls = []
        
        def save_callback(interface_name: str, data: List[Dict[str, Any]]) -> None:
            save_callback_calls.append((interface_name, data))
        
        def make_request(_interface_config: Dict, params: Dict) -> List[Dict]:
            offset = params["offset"]
            if offset == 0:
                return [{"id": 1}, {"id": 2}]
            raise RuntimeError("boom")
        
        params = {
            "_offset_pagination": {
                "enabled": True,
                "limit": 2,
                "commit_on_success": True,
            }
        }
        
        with self.assertRaises(RuntimeError):
            self.executor._execute_single_request(
                self.interface_config,
                params,
                make_request,
                save_callback=save_callback,
            )
        
        # 原子模式下，即使有 save_callback 也不应保存
        self.assertEqual(len(save_callback_calls), 0)
        print("✓ 测试2b通过: 原子 offset 异常时，即使有 save_callback 也不保存")

    # =========================================================================
    # 测试3: 原子 offset 成功时只提交一次
    # =========================================================================
    def test_atomic_offset_commits_once_on_success(self):
        """
        测试3: 原子 offset 成功时只提交一次
        
        输入场景：
        - 多页成功
        - 最后一页不足 limit
        
        断言：
        - 所有页数据聚合后只提交一次
        - 提交总数正确
        """
        on_data_ready_calls = []
        
        def on_data_ready(data: List[Dict[str, Any]]) -> None:
            on_data_ready_calls.append(data)
        
        def make_request(_interface_config: Dict, params: Dict) -> List[Dict]:
            offset = params["offset"]
            limit = params["limit"]
            if offset == 0:
                # 第1页：满页
                return [{"id": i} for i in range(1, limit + 1)]
            elif offset == limit:
                # 第2页：满页
                return [{"id": i} for i in range(limit + 1, 2 * limit + 1)]
            else:
                # 第3页：不满页（结束）
                return [{"id": i} for i in range(2 * limit + 1, 2 * limit + 3)]
        
        params = {
            "_offset_pagination": {
                "enabled": True,
                "limit": 5,
                "commit_on_success": True,
            }
        }
        
        result = self.executor._execute_single_request(
            self.interface_config,
            params,
            make_request,
            on_data_ready=on_data_ready,
        )
        
        # 验证：返回总记录数
        self.assertEqual(result, 12)  # 5 + 5 + 2
        
        # 验证：只回调一次，包含所有数据
        self.assertEqual(len(on_data_ready_calls), 1)
        self.assertEqual(len(on_data_ready_calls[0]), 12)
        print("✓ 测试3通过: 原子 offset 成功时只提交一次，数据完整")

    def test_atomic_offset_commits_all_pages_in_single_batch(self):
        """
        测试3b: 验证原子模式下多页数据正确聚合
        """
        on_data_ready_calls = []
        
        def on_data_ready(data: List[Dict[str, Any]]) -> None:
            on_data_ready_calls.append(data)
        
        def make_request(_interface_config: Dict, params: Dict) -> List[Dict]:
            offset = params["offset"]
            if offset == 0:
                return [{"id": 1}, {"id": 2}]
            elif offset == 2:
                return [{"id": 3}]
            return []
        
        params = {
            "_offset_pagination": {
                "enabled": True,
                "limit": 2,
                "commit_on_success": True,
            }
        }
        
        result = self.executor._execute_single_request(
            self.interface_config,
            params,
            make_request,
            on_data_ready=on_data_ready,
        )
        
        self.assertEqual(result, 3)
        self.assertEqual(len(on_data_ready_calls), 1)
        self.assertEqual(on_data_ready_calls[0], [{"id": 1}, {"id": 2}, {"id": 3}])
        print("✓ 测试3b通过: 多页数据正确聚合后一次性提交")

    # =========================================================================
    # 测试: 非原子模式流式处理
    # =========================================================================
    def test_non_atomic_streaming_calls_callback_per_page(self):
        """
        测试: 非原子模式流式处理时每页都回调
        """
        on_data_ready_calls = []
        
        def on_data_ready(data: List[Dict[str, Any]]) -> None:
            on_data_ready_calls.append(data)
        
        def make_request(_interface_config: Dict, params: Dict) -> List[Dict]:
            offset = params["offset"]
            if offset == 0:
                return [{"id": 1}, {"id": 2}]
            elif offset == 2:
                return [{"id": 3}]
            return []
        
        params = {
            "_offset_pagination": {
                "enabled": True,
                "limit": 2,
                "commit_on_success": False,  # 非原子模式
            }
        }
        
        result = self.executor._execute_single_request(
            self.interface_config,
            params,
            make_request,
            on_data_ready=on_data_ready,
        )
        
        self.assertEqual(result, 3)
        # 非原子模式：每页都会回调
        self.assertEqual(len(on_data_ready_calls), 2)
        self.assertEqual(on_data_ready_calls[0], [{"id": 1}, {"id": 2}])
        self.assertEqual(on_data_ready_calls[1], [{"id": 3}])
        print("✓ 非原子模式流式处理测试通过: 每页都回调")


if __name__ == "__main__":
    unittest.main()
