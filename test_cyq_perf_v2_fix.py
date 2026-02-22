#!/usr/bin/env python3
"""
测试cyq_perf接口在更新模式下的修复
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app4'))

from app4.core.config_loader import ConfigLoader
from app4.core.pagination import PaginationComposer, PaginationContext

def test_pagination_compose():
    """测试PaginationComposer的compose方法"""
    config_dir = os.path.join(os.path.dirname(__file__), 'app4', 'config')
    config_loader = ConfigLoader(config_dir=config_dir)

    # 获取cyq_perf配置
    cyq_perf_config = config_loader.get_interface_config('cyq_perf')

    # 创建pagination context
    context = PaginationContext(
        interface_config=cyq_perf_config,
        user_provided_dates=True
    )

    # 创建composer
    composer = PaginationComposer(context)

    # 模拟用户提供的参数
    base_params = {
        'start_date': '20260205',
        'end_date': '20260210'
    }

    print("测试PaginationComposer.compose()方法...")
    print(f"输入参数: {base_params}")

    # 执行compose方法
    result_params = list(composer.compose(base_params))

    print(f"输出参数数量: {len(result_params)}")
    print(f"输出参数示例: {result_params[:3]}")  # 显示前3个

    # 检查参数格式是否正确
    if result_params and all('trade_date' in p for p in result_params):
        print("✓ 参数格式正确：包含trade_date字段")
        print("✓ PaginationComposer修复成功")
        return True
    else:
        print("✗ 参数格式错误")
        return False

def test_is_date_anchor_interface():
    """测试_is_date_anchor_interface方法"""
    config_dir = os.path.join(os.path.dirname(__file__), 'app4', 'config')
    config_loader = ConfigLoader(config_dir=config_dir)
    cyq_perf_config = config_loader.get_interface_config('cyq_perf')

    context = PaginationContext(
        interface_config=cyq_perf_config,
        user_provided_dates=True
    )

    composer = PaginationComposer(context)

    is_date_anchor = composer._is_date_anchor_interface()
    pagination_mode = composer.config.get("mode", "")

    print(f"\ncyq_perf配置检查:")
    print(f"  分页模式: {pagination_mode}")
    print(f"  是否日期锚定接口: {is_date_anchor}")

    expected_mode = "reverse_date_range"
    expected_date_anchor = True

    if pagination_mode == expected_mode and is_date_anchor == expected_date_anchor:
        print("✓ 配置检查正确")
        return True
    else:
        print(f"✗ 配置检查错误: 期望模式'{expected_mode}', 实际'{pagination_mode}' 或 日期锚定期望{expected_date_anchor}, 实际{is_date_anchor}")
        return False

def test_date_anchor_range_method():
    """测试新增的_apply_date_anchor_range方法"""
    config_dir = os.path.join(os.path.dirname(__file__), 'app4', 'config')
    config_loader = ConfigLoader(config_dir=config_dir)
    cyq_perf_config = config_loader.get_interface_config('cyq_perf')

    context = PaginationContext(
        interface_config=cyq_perf_config,
        user_provided_dates=True
    )

    composer = PaginationComposer(context)

    # 测试参数流
    params_stream = [{'start_date': '20260205', 'end_date': '20260207'}]

    print(f"\n测试_apply_date_anchor_range方法...")
    print(f"输入参数流: {params_stream}")

    result = list(composer._apply_date_anchor_range(params_stream))

    print(f"输出参数数量: {len(result)}")
    print(f"输出参数: {result}")

    # 检查结果
    if len(result) == 3 and all('trade_date' in p for p in result):
        print("✓ _apply_date_anchor_range方法工作正常")
        return True
    else:
        print("✗ _apply_date_anchor_range方法存在问题")
        return False

if __name__ == "__main__":
    print("测试cyq_perf接口在更新模式下的修复...")

    success1 = test_is_date_anchor_interface()
    success2 = test_date_anchor_range_method()
    success3 = test_pagination_compose()

    if success1 and success2 and success3:
        print("\n✓ 所有测试通过！PaginationComposer修复已成功实施。")
    else:
        print("\n✗ 测试失败！需要进一步调试。")
        sys.exit(1)