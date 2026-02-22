#!/usr/bin/env python3
"""
测试cyq_perf接口修复是否生效
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app4'))

from app4.core.params_builder import ParamsBuilder, DownloadScenario
from datetime import datetime

def test_cyq_perf_scenario_detection():
    """测试cyq_perf接口的场景检测逻辑"""

    # 模拟cyq_perf接口配置
    cyq_perf_config = {
        'api_name': 'cyq_perf',
        'name': 'cyq_perf',
        'description': '每日筹码及胜率',
        'pagination': {
            'enabled': True,
            'mode': 'reverse_date_range',  # 关键：reverse_date_range模式
            'window_size_days': 1,
            'empty_threshold_days': 90
        },
        'parameters': {
            'trade_date': {
                'description': '交易日期 YYYYMMDD',
                'required': False,
                'type': 'string',
                'is_date_anchor': True  # 关键：日期锚定参数
            },
            'ts_code': {
                'description': '股票代码',
                'required': False,
                'type': 'string'
            }
        }
    }

    builder = ParamsBuilder(cyq_perf_config)

    # 模拟传入的参数对象
    class MockArgs:
        def __init__(self):
            self.start_date = '20260205'
            self.end_date = '20260220'
            self.ts_code = None
            self.user_provided_dates = True  # 用户提供了日期

    args = MockArgs()

    # 测试场景检测
    scenario = builder._detect_scenario(
        ts_code=args.ts_code,
        user_provided_dates=args.user_provided_dates,
        start_date=args.start_date,
        end_date=args.end_date
    )

    print(f"检测到的场景: {scenario}")
    print(f"预期场景: {DownloadScenario.DATE_ANCHOR_RANGE}")

    if scenario == DownloadScenario.DATE_ANCHOR_RANGE:
        print("✓ 场景检测正确：识别为DATE_ANCHOR_RANGE")

        # 测试参数构建
        result = builder.build(args)
        print(f"构建结果场景: {result.scenario}")
        print(f"是否需要股票循环: {result.requires_stock_loop}")
        print(f"日期锚定参数: {result.date_anchor_param}")
        print(f"内部参数: {result.params}")

        # 测试参数列表构建
        stock_list = []  # 日期锚定范围模式不需要股票列表
        params_list, context = builder.build_params_list(result, stock_list)

        print(f"生成的参数列表: {params_list[:5]}...")  # 只显示前5个

        # 验证参数格式是否正确
        if params_list and len(params_list) > 0:
            first_param = params_list[0]
            expected_keys = ['trade_date']
            if all(key in first_param for key in expected_keys):
                print("✓ 参数格式正确：包含trade_date字段")
                print(f"  第一个参数: {first_param}")
            else:
                print(f"✗ 参数格式错误：期望{expected_keys}, 实际{list(first_param.keys())}")
        else:
            print("✗ 未生成任何参数")

        return True
    else:
        print(f"✗ 场景检测错误：期望{DownloadScenario.DATE_ANCHOR_RANGE}，实际得到{scenario}")
        return False

def test_other_interfaces_unchanged():
    """测试其他接口是否不受影响"""

    # 测试stock_loop + is_date_anchor的接口（如top10_holders）
    top10_holders_config = {
        'api_name': 'top10_holders',
        'name': 'top10_holders',
        'pagination': {
            'enabled': True,
            'mode': 'stock_loop'  # 关键：stock_loop模式
        },
        'parameters': {
            'ts_code': {
                'description': '股票代码',
                'required': False,
                'type': 'string'
            },
            'ann_date': {
                'description': '公告日期',
                'required': False,
                'type': 'string',
                'is_date_anchor': True  # 日期锚定参数
            }
        }
    }

    builder = ParamsBuilder(top10_holders_config)

    class MockArgs:
        def __init__(self):
            self.start_date = '20260101'
            self.end_date = '20260220'
            self.ts_code = None
            self.user_provided_dates = True

    args = MockArgs()

    scenario = builder._detect_scenario(
        ts_code=args.ts_code,
        user_provided_dates=args.user_provided_dates,
        start_date=args.start_date,
        end_date=args.end_date
    )

    print(f"\ntop10_holders场景检测: {scenario}")
    print(f"预期(不应受影响): {DownloadScenario.STOCK_LOOP_DATE_ANCHOR}")

    if scenario == DownloadScenario.STOCK_LOOP_DATE_ANCHOR:
        print("✓ stock_loop接口行为未受影响")
        return True
    else:
        print(f"✗ stock_loop接口行为被意外改变")
        return False

if __name__ == "__main__":
    print("测试cyq_perf接口修复...")

    success1 = test_cyq_perf_scenario_detection()
    success2 = test_other_interfaces_unchanged()

    if success1 and success2:
        print("\n✓ 所有测试通过！修复已成功实施。")
    else:
        print("\n✗ 测试失败！需要进一步调试。")
        sys.exit(1)