#!/usr/bin/env python3
"""
完整测试cyq_perf接口修复：params_builder和pagination两处修改
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app4'))

from app4.core.config_loader import ConfigLoader
from app4.core.params_builder import ParamsBuilder, DownloadScenario
from app4.core.pagination import PaginationComposer, PaginationContext

def test_params_builder_fix():
    """测试params_builder.py的修复"""
    print("=== 测试params_builder.py修复 ===")

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
    print("测试cyq_perf场景检测:")
    scenario = builder._detect_scenario(
        ts_code=args.ts_code,
        user_provided_dates=args.user_provided_dates,
        start_date=args.start_date,
        end_date=args.end_date
    )

    print(f"  检测到的场景: {scenario}")
    print(f"  预期场景: {DownloadScenario.DATE_ANCHOR_RANGE}")
    scenario_ok = scenario == DownloadScenario.DATE_ANCHOR_RANGE
    print(f"  检测结果: {'✓ 正确' if scenario_ok else '✗ 错误'}")

    if scenario_ok:
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
        params_format_ok = params_list and all('trade_date' in p for p in params_list[:3])
        print(f"  参数格式检查: {'✓ 正确' if params_format_ok else '✗ 错误'}")
    else:
        params_format_ok = False

    return scenario_ok and params_format_ok

def test_pagination_fix():
    """测试pagination.py的修复"""
    print("\n=== 测试pagination.py修复 ===")

    config_dir = os.path.join(os.path.dirname(__file__), 'app4', 'config')
    config_loader = ConfigLoader(config_dir=config_dir)
    cyq_perf_config = config_loader.get_interface_config('cyq_perf')

    context = PaginationContext(
        interface_config=cyq_perf_config,
        user_provided_dates=True
    )

    # 创建composer
    composer = PaginationComposer(context)

    # 检查配置
    is_date_anchor = composer._is_date_anchor_interface()
    pagination_mode = composer.config.get("mode", "")
    print(f"cyq_perf配置检查:")
    print(f"  分页模式: {pagination_mode}")
    print(f"  是否日期锚定接口: {is_date_anchor}")

    expected_mode = "reverse_date_range"
    expected_date_anchor = True
    config_ok = (pagination_mode == expected_mode and is_date_anchor == expected_date_anchor)
    print(f"  配置检查: {'✓ 正确' if config_ok else '✗ 错误'}")

    # 测试参数流转换
    print(f"\n测试_apply_date_anchor_range方法...")
    params_stream = [{'start_date': '20260205', 'end_date': '20260207'}]
    print(f"  输入参数流: {params_stream}")

    result = list(composer._apply_date_anchor_range(params_stream))
    print(f"  输出参数数量: {len(result)}")
    print(f"  输出参数: {result}")

    method_ok = len(result) == 3 and all('trade_date' in p for p in result)
    print(f"  方法执行检查: {'✓ 正确' if method_ok else '✗ 错误'}")

    # 测试compose方法（模拟更新模式的路径）
    print(f"\n测试PaginationComposer.compose()方法（模拟更新模式）...")
    base_params = {'start_date': '20260205', 'end_date': '20260210'}
    print(f"  输入参数: {base_params}")

    compose_result = list(composer.compose(base_params))
    print(f"  输出参数数量: {len(compose_result)}")
    print(f"  输出参数示例: {compose_result[:3]}")

    compose_ok = len(compose_result) == 6 and all('trade_date' in p for p in compose_result)
    print(f"  compose方法检查: {'✓ 正确' if compose_ok else '✗ 错误'}")

    return config_ok and method_ok and compose_ok

def test_backward_compatibility():
    """测试其他接口是否不受影响"""
    print("\n=== 测试向后兼容性（其他接口不应受影响） ===")

    config_dir = os.path.join(os.path.dirname(__file__), 'app4', 'config')
    config_loader = ConfigLoader(config_dir=config_dir)

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

    class MockArgs:
        def __init__(self):
            self.start_date = '20260101'
            self.end_date = '20260220'
            self.ts_code = None
            self.user_provided_dates = True

    args = MockArgs()

    scenario_stock_loop = builder_stock_loop._detect_scenario(
        ts_code=args.ts_code,
        user_provided_dates=args.user_provided_dates,
        start_date=args.start_date,
        end_date=args.end_date
    )

    print(f"  top10_holders场景: {scenario_stock_loop}")
    print(f"  预期(应不受影响): {DownloadScenario.STOCK_LOOP_DATE_ANCHOR}")
    compatibility_ok = scenario_stock_loop == DownloadScenario.STOCK_LOOP_DATE_ANCHOR
    print(f"  兼容性检查: {'✓ 正确' if compatibility_ok else '✗ 错误'}")

    return compatibility_ok

if __name__ == "__main__":
    print("完整测试cyq_perf接口修复...")

    params_ok = test_params_builder_fix()
    pagination_ok = test_pagination_fix()
    compat_ok = test_backward_compatibility()

    print(f"\n=== 总结 ===")
    print(f"params_builder修复: {'✓' if params_ok else '✗'}")
    print(f"pagination修复: {'✓' if pagination_ok else '✗'}")
    print(f"向后兼容性: {'✓' if compat_ok else '✗'}")

    if params_ok and pagination_ok and compat_ok:
        print(f"\n✓ 所有测试通过！cyq_perf接口修复完整实施。")
        print(f"  - 普通模式：通过params_builder.py路径正常工作")
        print(f"  - 更新模式：通过pagination.py路径正常工作")
        print(f"  - 其他接口：不受影响")
    else:
        print(f"\n✗ 部分测试失败！")
        sys.exit(1)