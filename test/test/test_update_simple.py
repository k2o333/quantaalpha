"""
增量更新模块简单测试
无需 pytest，直接运行
"""
import os
import sys
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from update import (
    UpdateOptions,
    DateCalculator,
    InterfaceSelector,
    UpdateReporter,
    CheckpointManager,
    DateRange,
    InterfaceUpdateResult,
    UpdateStatus,
    ReportFormat,
)
from unittest.mock import Mock

def test_date_range():
    """测试 DateRange"""
    print("测试 DateRange...")
    
    # 基本创建
    dr = DateRange(start_date='20230101', end_date='20231231')
    assert dr.start_date == '20230101'
    assert dr.end_date == '20231231'
    print("  ✓ 日期范围创建成功")
    
    # 空范围检测
    dr_empty = DateRange(start_date='20231231', end_date='20230101')
    assert dr_empty.is_empty() is True
    print("  ✓ 空范围检测正确")
    
    # 天数计算（包含首尾）
    dr_days = DateRange(start_date='20230101', end_date='20230110')
    assert dr_days.days_between() == 10  # 包含首尾：1-10号共10天
    print("  ✓ 天数计算正确（包含首尾）")

def test_update_options():
    """测试 UpdateOptions"""
    print("测试 UpdateOptions...")
    
    # 默认选项
    options = UpdateOptions()
    assert options.force is False
    assert options.dry_run is False
    assert options.report_format == ReportFormat.MARKDOWN
    print("  ✓ 默认选项正确")
    
    # 自定义选项
    options2 = UpdateOptions(
        interfaces=['daily', 'daily_basic'],
        force=True,
        dry_run=True
    )
    assert options2.interfaces == ['daily', 'daily_basic']
    assert options2.force is True
    print("  ✓ 自定义选项正确")

def test_checkpoint_manager():
    """测试 CheckpointManager"""
    print("测试 CheckpointManager...")
    
    config = {'enabled': False}
    manager = CheckpointManager(config)
    
    # 测试接口完成追踪
    manager.record_interface_complete('daily', True)
    assert manager.is_interface_completed('daily') is True
    print("  ✓ 接口完成追踪正确")
    
    # 测试失败接口追踪
    manager.record_interface_complete('daily_basic', False, 'Network error')
    assert manager.is_interface_failed('daily_basic') is True
    print("  ✓ 失败接口追踪正确")
    
    # 测试获取恢复列表
    all_interfaces = ['daily', 'daily_basic', 'moneyflow']
    resume_list = manager.get_resume_interfaces(all_interfaces)
    assert 'daily' not in resume_list
    assert 'daily_basic' in resume_list  # 失败的也需要重新运行
    assert 'moneyflow' in resume_list
    print("  ✓ 恢复列表获取正确")

def test_update_reporter():
    """测试 UpdateReporter"""
    print("测试 UpdateReporter...")
    
    reporter = UpdateReporter()
    reporter.record_update_start()
    
    # 添加结果
    reporter.record_interface_result(
        InterfaceUpdateResult('daily', UpdateStatus.SUCCESS, record_count=100)
    )
    reporter.record_interface_result(
        InterfaceUpdateResult('daily_basic', UpdateStatus.SUCCESS, record_count=200)
    )
    reporter.record_interface_result(
        InterfaceUpdateResult('moneyflow', UpdateStatus.FAILED, error_message='Error')
    )
    
    reporter.record_update_end()
    
    # 获取摘要
    summary = reporter.get_summary()
    assert summary.total == 3
    assert summary.success == 2
    assert summary.failed == 1
    assert summary.total_records == 300
    print("  ✓ 报告摘要正确")
    
    # 生成 Markdown 报告
    report = reporter.generate_report(ReportFormat.MARKDOWN)
    assert 'daily' in report
    assert '成功' in report or 'SUCCESS' in report
    print("  ✓ Markdown 报告生成成功")
    
    # 生成 JSON 报告
    report_json = reporter.generate_report(ReportFormat.JSON)
    assert 'daily' in report_json
    assert '"success": 2' in report_json
    print("  ✓ JSON 报告生成成功")

def test_interface_selector():
    """测试 InterfaceSelector"""
    print("测试 InterfaceSelector...")
    
    # 创建模拟配置加载器 - 使用一个类来模拟
    class MockConfigLoader:
        def __init__(self):
            self.global_config = {
                'groups': {
                    'daily': ['daily', 'daily_basic'],
                },
                'update': {
                    'excluded_interfaces': ['trade_cal'],
                    'update_order': ['daily', 'daily_basic']
                }
            }
        
        def get_available_interfaces(self):
            return ['daily', 'daily_basic', 'moneyflow', 'trade_cal']
    
    config_loader = MockConfigLoader()
    selector = InterfaceSelector(config_loader)
    
    # 测试选择所有接口 - 注意要排除被配置排除的接口
    options = UpdateOptions()
    interfaces = selector.select_interfaces(options)
    # 由于 trade_cal 在 excluded_interfaces 中，应该被排除
    assert 'trade_cal' not in interfaces, f"trade_cal 应该被排除，但在: {interfaces}"
    assert 'daily' in interfaces, f"daily 应该在接口列表中: {interfaces}"
    print("  ✓ 选择所有接口正确")
    
    # 测试按接口选择
    options2 = UpdateOptions(interfaces=['daily'])
    interfaces2 = selector.select_interfaces(options2)
    assert interfaces2 == ['daily'], f"接口选择错误: {interfaces2}"
    print("  ✓ 按接口选择正确")
    
    # 测试按组选择
    options3 = UpdateOptions(groups=['daily'])
    interfaces3 = selector.select_interfaces(options3)
    assert set(interfaces3) == {'daily', 'daily_basic'}, f"组选择错误: {interfaces3}"
    print("  ✓ 按组选择正确")
    
    # 测试排除
    options4 = UpdateOptions(exclude=['moneyflow'])
    interfaces4 = selector.select_interfaces(options4)
    # 注意 trade_cal 也在排除列表中
    assert 'moneyflow' not in interfaces4, f"moneyflow 应该被排除: {interfaces4}"
    print("  ✓ 排除规则正确")

def test_date_calculator():
    """测试 DateCalculator"""
    print("测试 DateCalculator...")
    
    # 创建模拟组件
    config_loader = Mock()
    config_loader.global_config = {
        'update': {
            'default_strategy': {
                'start_date': '20000101',
                'lookback_days': 7
            },
            'special_interfaces': {
                'trade_cal': {
                    'start_date': '19900101',
                    'date_column': 'cal_date'
                }
            }
        }
    }
    storage_manager = Mock()
    
    calculator = DateCalculator(config_loader, storage_manager)
    
    # 测试强制日期范围
    date_range = calculator.calculate_update_range(
        'daily',
        forced_start='20230101',
        forced_end='20231231'
    )
    assert date_range.start_date == '20230101'
    assert date_range.end_date == '20231231'
    print("  ✓ 强制日期范围正确")
    
    # 测试获取日期列
    assert calculator._get_interface_date_column('trade_cal') == 'cal_date'
    # 对于没有特殊配置的接口，在没有完整接口配置的情况下使用默认值
    assert calculator._get_interface_date_column('daily') == 'trade_date'
    print("  ✓ 日期列获取正确")
    
    # 测试获取默认起始日期
    assert calculator._get_default_start_date('trade_cal') == '19900101'
    assert calculator._get_default_start_date('daily') == '20000101'
    print("  ✓ 默认起始日期正确")

def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始运行增量更新模块测试")
    print("=" * 60)
    
    try:
        test_date_range()
        test_update_options()
        test_checkpoint_manager()
        test_update_reporter()
        test_interface_selector()
        test_date_calculator()
        
        print("\n" + "=" * 60)
        print("所有测试通过！")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    exit(run_all_tests())
