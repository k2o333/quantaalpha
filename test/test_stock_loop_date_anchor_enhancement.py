#!/usr/bin/env python3
"""
测试 stock_loop 模式日期参数增强功能

测试场景：
1. 接口支持 start_date/end_date 参数 - 直接透传命令行参数
2. 接口使用日期锚定参数 - 在命令行日期范围内按窗口遍历
3. 接口未配置日期参数 - 保持原有行为（全历史下载）
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app4.core.config_loader import ConfigLoader
from app4.core.pagination import ParameterGenerator, PaginationContext


class TestStockLoopDateAnchorEnhancement(unittest.TestCase):
    """测试 stock_loop 日期锚定参数增强功能"""

    def setUp(self):
        """测试前准备"""
        # 创建一个简单的 ConfigLoader 实例用于测试，不加载实际配置文件
        self.config_loader = ConfigLoader.__new__(ConfigLoader)
        self.config_loader.interface_configs = {}
        self.config_loader.global_config = {}

    def test_validate_date_anchor_parameters_single_valid(self):
        """测试单个有效日期锚定参数"""
        interface_config = {
            'name': 'test_interface',
            'parameters': {
                'period': {
                    'type': 'string',
                    'is_date_anchor': True
                },
                'ts_code': {
                    'type': 'string'
                }
            }
        }
        
        result = self.config_loader._validate_date_anchor_parameters(interface_config)
        self.assertTrue(result)

    def test_validate_date_anchor_parameters_multiple_warning(self):
        """测试多个日期锚定参数 - 应该警告但通过验证"""
        interface_config = {
            'name': 'test_interface',
            'parameters': {
                'period': {
                    'type': 'string',
                    'is_date_anchor': True
                },
                'ann_date': {
                    'type': 'string',
                    'is_date_anchor': True
                }
            }
        }
        
        with patch('app4.core.config_loader.logger') as mock_logger:
            result = self.config_loader._validate_date_anchor_parameters(interface_config)
            self.assertTrue(result)
            mock_logger.warning.assert_called_once()

    def test_validate_date_anchor_parameters_invalid_start_date(self):
        """测试将 start_date 标记为日期锚定参数 - 应该通过"""
        interface_config = {
            'name': 'test_interface',
            'parameters': {
                'start_date': {
                    'type': 'string',
                    'is_date_anchor': True
                }
            }
        }
        
        result = self.config_loader._validate_date_anchor_parameters(interface_config)
        self.assertTrue(result)

    def test_validate_date_anchor_parameters_invalid_end_date(self):
        """测试将 end_date 标记为日期锚定参数 - 应该通过"""
        interface_config = {
            'name': 'test_interface',
            'parameters': {
                'end_date': {
                    'type': 'string',
                    'is_date_anchor': True
                }
            }
        }
        
        result = self.config_loader._validate_date_anchor_parameters(interface_config)
        self.assertTrue(result)

    def test_generate_date_points_period_type(self):
        """测试 period 类型日期点生成"""
        interface_config = {
            'name': 'test_interface',
            'pagination': {
                'enabled': True,
                'mode': 'stock_loop',
                'window_size_days': 90
            }
        }
        
        context = PaginationContext(interface_config=interface_config)
        param_gen = ParameterGenerator(context)
        
        date_points = param_gen._generate_date_points_by_type('20230101', '20231231', 'period', 90)
        
        # 验证季度末日期
        expected_quarters = ['20230331', '20230630', '20230930', '20231231']
        self.assertEqual(date_points, expected_quarters)

    def test_generate_date_points_trade_date_type_with_calendar(self):
        """测试 trade_date 类型日期点生成（有交易日历）"""
        interface_config = {
            'name': 'test_interface',
            'pagination': {
                'enabled': True,
                'mode': 'stock_loop'
            }
        }
        
        # 模拟交易日历
        trade_calendar = [
            {'cal_date': '20230103', 'is_open': 1},
            {'cal_date': '20230104', 'is_open': 1},
            {'cal_date': '20230105', 'is_open': 1},
            {'cal_date': '20230106', 'is_open': 0},  # 非交易日
            {'cal_date': '20230109', 'is_open': 1}
        ]
        
        context = PaginationContext(interface_config=interface_config, trade_calendar=trade_calendar)
        param_gen = ParameterGenerator(context)
        
        date_points = param_gen._generate_date_points_by_type('20230101', '20230110', 'trade_date', 2)
        
        # 验证只包含交易日
        expected = ['20230103', '20230104', '20230105', '20230109']
        self.assertEqual(date_points, expected)

    def test_generate_date_points_ann_date_type_windowed(self):
        """测试 ann_date 类型按窗口大小生成日期点"""
        interface_config = {
            'name': 'test_interface',
            'pagination': {
                'enabled': True,
                'mode': 'stock_loop'
            }
        }
        
        # 模拟交易日历
        trade_calendar = [
            {'cal_date': '20230103', 'is_open': 1},
            {'cal_date': '20230104', 'is_open': 1},
            {'cal_date': '20230105', 'is_open': 1},
            {'cal_date': '20230106', 'is_open': 1},
            {'cal_date': '20230109', 'is_open': 1}
        ]
        
        context = PaginationContext(interface_config=interface_config, trade_calendar=trade_calendar)
        param_gen = ParameterGenerator(context)
        
        date_points = param_gen._generate_date_points_by_type('20230101', '20230110', 'ann_date', 3)
        
        # 验证按3天窗口生成
        expected = ['20230105', '20230109']  # 每个窗口的最后一个交易日
        self.assertEqual(date_points, expected)

    def test_generate_stock_date_anchor_params(self):
        """测试生成股票循环+日期锚定参数"""
        interface_config = {
            'name': 'test_interface',
            'pagination': {
                'enabled': True,
                'mode': 'stock_loop',
                'window_size_days': 90
            }
        }
        
        stock_list = [
            {'ts_code': '000001.SZ', 'list_date': '20100101'},
            {'ts_code': '000002.SZ', 'list_date': '20110101'}
        ]
        
        context = PaginationContext(interface_config=interface_config, stock_list=stock_list)
        param_gen = ParameterGenerator(context)
        
        base_params = {
            'start_date': '20230101',
            'end_date': '20231231',
            '_date_anchor_param': 'period'
        }
        
        generated_params = list(param_gen.generate_stock_date_anchor_params(base_params))
        
        # 验证生成的参数数量：2只股票 × 4个季度 = 8个参数组合
        self.assertEqual(len(generated_params), 8)
        
        # 验证第一个参数组合
        first_params, first_stock = generated_params[0]
        self.assertEqual(first_stock['ts_code'], '000001.SZ')
        self.assertEqual(first_params['ts_code'], '000001.SZ')
        self.assertEqual(first_params['period'], '20230331')
        self.assertNotIn('_date_anchor_param', first_params)
        self.assertNotIn('start_date', first_params)
        self.assertNotIn('end_date', first_params)

    def test_generate_stock_date_anchor_params_missing_required(self):
        """测试缺少必需参数时的错误处理"""
        interface_config = {
            'name': 'test_interface',
            'pagination': {
                'enabled': True,
                'mode': 'stock_loop'
            }
        }
        
        stock_list = [{'ts_code': '000001.SZ', 'list_date': '20100101'}]
        context = PaginationContext(interface_config=interface_config, stock_list=stock_list)
        param_gen = ParameterGenerator(context)
        
        # 缺少 _date_anchor_param
        base_params = {
            'start_date': '20230101',
            'end_date': '20231231'
        }
        
        with patch('app4.core.pagination.logger') as mock_logger:
            generated_params = list(param_gen.generate_stock_date_anchor_params(base_params))
            self.assertEqual(len(generated_params), 0)
            mock_logger.error.assert_called_once()

    def test_generate_stock_date_anchor_params_with_existing_checker(self):
        """测试带有存在性检查的参数生成"""
        interface_config = {
            'name': 'test_interface',
            'pagination': {
                'enabled': True,
                'mode': 'stock_loop'
            }
        }
        
        stock_list = [
            {'ts_code': '000001.SZ', 'list_date': '20100101'},
            {'ts_code': '000002.SZ', 'list_date': '20110101'}
        ]
        
        context = PaginationContext(interface_config=interface_config, stock_list=stock_list)
        param_gen = ParameterGenerator(context)
        
        # 模拟交易日历
        trade_calendar = [
            {'cal_date': '20230103', 'is_open': 1},
            {'cal_date': '20230104', 'is_open': 1},
            {'cal_date': '20230105', 'is_open': 1}
        ]
        
        context_with_calendar = PaginationContext(
            interface_config=interface_config, 
            stock_list=stock_list,
            trade_calendar=trade_calendar
        )
        param_gen_with_calendar = ParameterGenerator(context_with_calendar)
        
        base_params = {
            'start_date': '20230101',
            'end_date': '20230105',
            '_date_anchor_param': 'trade_date'
        }
        
        # 模拟存在性检查 - 第一只股票已存在，第二只不存在
        def mock_existing_checker(interface_name, ts_code):
            return ts_code == '000001.SZ'
        
        with patch('app4.core.pagination.logger') as mock_logger:
            generated_params = list(param_gen_with_calendar.generate_stock_date_anchor_params(
                base_params, 
                existing_stocks_checker=mock_existing_checker
            ))
            
            # 应该只为第二只股票生成3个交易日的参数
            self.assertEqual(len(generated_params), 3)
            # 验证所有生成的参数都属于第二只股票
            for params, stock in generated_params:
                self.assertEqual(stock['ts_code'], '000002.SZ')
                self.assertEqual(params['ts_code'], '000002.SZ')
                self.assertIn('trade_date', params)
                self.assertNotIn('_date_anchor_param', params)


if __name__ == '__main__':
    unittest.main()
