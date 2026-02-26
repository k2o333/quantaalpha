#!/usr/bin/env python3
"""
检查cyq_perf接口配置和修改是否生效
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app4'))

from app4.core.config_loader import ConfigLoader
from app4.core.params_builder import ParamsBuilder, DownloadScenario

def check_interface_config():
    """检查接口配置"""
    config_dir = os.path.join(os.path.dirname(__file__), 'app4', 'config')
    config_loader = ConfigLoader(config_dir=config_dir)

    # 获取所有接口
    interfaces = config_loader.get_available_interfaces()
    print(f"可用接口数量: {len(interfaces)}")
    print(f"cyq_perf 接口是否存在: {'cyq_perf' in interfaces}")

    if 'cyq_perf' in interfaces:
        print("\ncyq_perf接口配置:")
        config = config_loader.get_interface_config('cyq_perf')
        print(f"  API名称: {config.get('api_name')}")
        print(f"  描述: {config.get('description')}")
        print(f"  分页模式: {config.get('pagination', {}).get('mode')}")
        print(f"  参数配置: {list(config.get('parameters', {}).keys())}")
        for param_name, param_config in config.get('parameters', {}).items():
            if param_config.get('is_date_anchor'):
                print(f"  日期锚定参数: {param_name} -> {param_config}")

    return config_loader

def test_params_builder():
    """测试参数构建器"""
    config_dir = os.path.join(os.path.dirname(__file__), 'app4', 'config')
    config_loader = ConfigLoader(config_dir=config_dir)
    cyq_perf_config = config_loader.get_interface_config('cyq_perf')

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
    print(f"\n测试cyq_perf场景检测:")
    scenario = builder._detect_scenario(
        ts_code=args.ts_code,
        user_provided_dates=args.user_provided_dates,
        start_date=args.start_date,
        end_date=args.end_date
    )

    print(f"  检测到的场景: {scenario}")
    print(f"  预期场景: {DownloadScenario.DATE_ANCHOR_RANGE}")
    print(f"  检测结果: {'✓ 正确' if scenario == DownloadScenario.DATE_ANCHOR_RANGE else '✗ 错误'}")

    if scenario == DownloadScenario.DATE_ANCHOR_RANGE:
        # 测试参数构建
        result = builder.build(args)
        print(f"\n构建结果:")
        print(f"  场景: {result.scenario}")
        print(f"  是否需要股票循环: {result.requires_stock_loop}")
        print(f"  日期锚定参数: {result.date_anchor_param}")
        print(f"  内部参数: {result.params}")

        # 测试参数列表构建
        params_list, context = builder.build_params_list(result, [])
        print(f"\n参数列表生成:")
        print(f"  生成数量: {len(params_list)}")
        if params_list:
            print(f"  前3个参数: {params_list[:3]}")

        # 检查参数格式是否正确
        if params_list and all('trade_date' in p for p in params_list[:3]):
            print("  ✓ 参数格式正确")
        else:
            print("  ✗ 参数格式错误")

    # 测试其他接口是否不受影响
    print(f"\n测试其他接口是否不受影响:")

    # 模拟top10_holders接口配置
    top10_holders_config = {
        'api_name': 'top10_holders',
        'name': 'top10_holders',
        'pagination': {
            'enabled': True,
            'mode': 'stock_loop'
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
                'is_date_anchor': True
            }
        }
    }

    builder_stock_loop = ParamsBuilder(top10_holders_config)
    scenario_stock_loop = builder_stock_loop._detect_scenario(
        ts_code=args.ts_code,
        user_provided_dates=args.user_provided_dates,
        start_date=args.start_date,
        end_date=args.end_date
    )

    print(f"  top10_holders场景: {scenario_stock_loop}")
    print(f"  预期(应不受影响): {DownloadScenario.STOCK_LOOP_DATE_ANCHOR}")
    print(f"  检测结果: {'✓ 正确' if scenario_stock_loop == DownloadScenario.STOCK_LOOP_DATE_ANCHOR else '✗ 错误'}")

if __name__ == "__main__":
    print("检查cyq_perf接口修复...")
    config_loader = check_interface_config()
    test_params_builder()
    print("\n✓ 检查完成")