"""
缺口检测功能单元测试
测试 CoverageManager.detect_gaps() 方法
"""
import sys
import os
import json

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app4.core.coverage_manager import CoverageManager, DateRange
from unittest.mock import Mock, MagicMock
import polars as pl


def test_no_gaps_complete_coverage():
    """测试：完全覆盖，无缺口"""
    print("\n[Test] 完全覆盖，无缺口")

    # 创建 mock 对象
    storage_manager = Mock()
    config_loader = Mock()
    downloader = Mock()

    # 已有数据覆盖所有交易日
    existing_dates = {'20250901', '20250902', '20250903'}

    # 创建 coverage_manager 并注入已有日期
    cm = CoverageManager(storage_manager, config_loader, downloader, cache_size=10)
    cm._existing_dates_cache['test_interface'] = existing_dates

    # 期望日期
    target_range = DateRange('20250901', '20250903')
    trade_calendar = [
        {'cal_date': '20250901', 'is_open': 1},
        {'cal_date': '20250902', 'is_open': 1},
        {'cal_date': '20250903', 'is_open': 1},
    ]

    # 执行检测
    gaps = cm.detect_gaps('test_interface', target_range, trade_calendar)

    # 验证结果
    assert len(gaps) == 0, f"期望无缺口，实际发现 {len(gaps)} 个缺口"
    print("  ✓ 通过：正确识别无缺口")


def test_single_gap():
    """测试：单个缺口"""
    print("\n[Test] 单个缺口")

    storage_manager = Mock()
    config_loader = Mock()
    downloader = Mock()

    # 已有数据缺失中间一天
    existing_dates = {'20250901', '20250903'}

    cm = CoverageManager(storage_manager, config_loader, downloader, cache_size=10)
    cm._existing_dates_cache['test_interface'] = existing_dates

    target_range = DateRange('20250901', '20250903')
    trade_calendar = [
        {'cal_date': '20250901', 'is_open': 1},
        {'cal_date': '20250902', 'is_open': 1},
        {'cal_date': '20250903', 'is_open': 1},
    ]

    gaps = cm.detect_gaps('test_interface', target_range, trade_calendar)

    assert len(gaps) == 1, f"期望1个缺口，实际发现 {len(gaps)} 个缺口"
    assert gaps[0].start_date == '20250902', f"缺口开始日期错误"
    assert gaps[0].end_date == '20250902', f"缺口结束日期错误"
    print("  ✓ 通过：正确识别单个缺口")


def test_multiple_gaps():
    """测试：多个缺口"""
    print("\n[Test] 多个缺口")

    storage_manager = Mock()
    config_loader = Mock()
    downloader = Mock()

    # 已有数据有多个断点
    existing_dates = {'20250901', '20250905', '20250910'}

    cm = CoverageManager(storage_manager, config_loader, downloader, cache_size=10)
    cm._existing_dates_cache['test_interface'] = existing_dates

    target_range = DateRange('20250901', '20250910')
    trade_calendar = [
        {'cal_date': f'2025090{i}', 'is_open': 1}
        for i in range(1, 11)
    ]

    gaps = cm.detect_gaps('test_interface', target_range, trade_calendar)

    assert len(gaps) == 2, f"期望2个缺口，实际发现 {len(gaps)} 个缺口"
    assert gaps[0].start_date == '20250902' and gaps[0].end_date == '20250904'
    assert gaps[1].start_date == '20250906' and gaps[1].end_date == '20250909'
    print("  ✓ 通过：正确识别多个缺口")


def test_min_gap_days_filter():
    """测试：最小缺口天数过滤"""
    print("\n[Test] 最小缺口天数过滤")

    storage_manager = Mock()
    config_loader = Mock()
    downloader = Mock()

    # 已有数据有单日缺口
    existing_dates = {'20250901', '20250903', '20250905'}

    cm = CoverageManager(storage_manager, config_loader, downloader, cache_size=10)
    cm._existing_dates_cache['test_interface'] = existing_dates

    target_range = DateRange('20250901', '20250905')
    trade_calendar = [
        {'cal_date': f'2025090{i}', 'is_open': 1}
        for i in range(1, 6)
    ]

    # min_gap_days=2，过滤掉单日缺口
    gaps = cm.detect_gaps('test_interface', target_range, trade_calendar, min_gap_days=2)

    assert len(gaps) == 0, f"期望过滤后无缺口，实际发现 {len(gaps)} 个缺口"
    print("  ✓ 通过：正确过滤小缺口")


def test_max_gaps_limit():
    """测试：最大缺口数量限制"""
    print("\n[Test] 最大缺口数量限制")

    storage_manager = Mock()
    config_loader = Mock()
    downloader = Mock()

    # 模拟大量小缺口（超过限制）
    existing_dates = set()
    for i in range(1, 100, 2):  # 每隔一天有数据
        existing_dates.add(f'202509{i:02d}')

    cm = CoverageManager(storage_manager, config_loader, downloader, cache_size=10)
    cm._existing_dates_cache['test_interface'] = existing_dates

    target_range = DateRange('20250901', '20250999')
    trade_calendar = [
        {'cal_date': f'202509{i:02d}', 'is_open': 1}
        for i in range(1, 100)
    ]

    # max_gaps=10，超过则返回完整范围
    gaps = cm.detect_gaps('test_interface', target_range, trade_calendar, max_gaps=10)

    assert len(gaps) == 1, f"期望合并为1个范围，实际为 {len(gaps)} 个"
    assert gaps[0].start_date == target_range.start_date
    assert gaps[0].end_date == target_range.end_date
    print("  ✓ 通过：正确合并过多缺口")


def test_cache_functionality():
    """测试：缓存功能"""
    print("\n[Test] 缓存功能")

    storage_manager = Mock()
    config_loader = Mock()
    config_loader.get_interface_config.return_value = {
        'duplicate_detection': {'date_column': 'trade_date'}
    }
    downloader = Mock()

    # 模拟存储返回数据
    df = pl.DataFrame({'trade_date': ['20250901', '20250902']})
    storage_manager.read_interface_data.return_value = df

    cm = CoverageManager(storage_manager, config_loader, downloader, cache_size=10)

    # 第一次调用，应该读取存储
    dates1 = cm._get_existing_dates_cached('test_interface')
    assert storage_manager.read_interface_data.call_count == 1

    # 第二次调用，应该使用缓存
    dates2 = cm._get_existing_dates_cached('test_interface')
    assert storage_manager.read_interface_data.call_count == 1  # 没有增加
    assert dates1 == dates2

    print("  ✓ 通过：缓存功能正常")


def test_lru_cache_eviction():
    """测试：LRU缓存淘汰"""
    print("\n[Test] LRU缓存淘汰")

    storage_manager = Mock()
    config_loader = Mock()
    config_loader.get_interface_config.return_value = {
        'duplicate_detection': {'date_column': 'trade_date'}
    }
    downloader = Mock()

    df = pl.DataFrame({'trade_date': ['20250901']})
    storage_manager.read_interface_data.return_value = df

    # 小缓存，只能存2个
    cm = CoverageManager(storage_manager, config_loader, downloader, cache_size=2)

    # 填充缓存
    cm._get_existing_dates_cached('interface1')
    cm._get_existing_dates_cached('interface2')

    assert len(cm._existing_dates_cache) == 2

    # 访问第一个，使其变为最近使用
    cm._get_existing_dates_cached('interface1')

    # 添加第三个，应该淘汰interface2
    cm._get_existing_dates_cached('interface3')

    assert 'interface1' in cm._existing_dates_cache
    assert 'interface2' not in cm._existing_dates_cache
    assert 'interface3' in cm._existing_dates_cache

    print("  ✓ 通过：LRU淘汰机制正常")


def test_detect_date_column():
    """测试：智能日期列检测"""
    print("\n[Test] 智能日期列检测")

    storage_manager = Mock()
    config_loader = Mock()
    downloader = Mock()

    cm = CoverageManager(storage_manager, config_loader, downloader, cache_size=10)

    # 测试1: duplicate_detection 配置
    config1 = {'duplicate_detection': {'date_column': 'custom_date'}}
    assert cm._detect_date_column(config1) == 'custom_date'
    print("  ✓ 从 duplicate_detection 检测日期列")

    # 测试2: output.sort_by
    config2 = {'output': {'sort_by': ['report_date', 'ts_code']}}
    assert cm._detect_date_column(config2) == 'report_date'
    print("  ✓ 从 output.sort_by 检测日期列")

    # 测试3: fields 中的常见日期字段
    config3 = {'fields': {'ts_code': 'string', 'report_date': 'string', 'value': 'float'}}
    assert cm._detect_date_column(config3) == 'report_date'
    print("  ✓ 从 fields 检测日期列")

    # 测试4: 无日期字段
    config4 = {'fields': {'ts_code': 'string', 'name': 'string'}}
    assert cm._detect_date_column(config4) is None
    print("  ✓ 无日期字段时返回 None")


def test_report_rc_scenario():
    """测试：report_rc 真实场景"""
    print("\n[Test] report_rc 真实场景")

    storage_manager = Mock()
    config_loader = Mock()
    downloader = Mock()

    # 模拟 report_rc 配置
    report_rc_config = {
        'output': {
            'sort_by': ['report_date'],
            'primary_key': ['ts_code', 'report_date', 'org_name', 'report_title']
        },
        'pagination': {
            'enabled': True,
            'mode': 'reverse_date_range'
        },
        'fields': {
            'ts_code': 'string',
            'report_date': 'string',
            'org_name': 'string'
        }
    }
    config_loader.get_interface_config.return_value = report_rc_config

    # 模拟已有数据
    df = pl.DataFrame({
        'report_date': ['20250815', '20250816', '20250820']
    })
    storage_manager.read_interface_data.return_value = df

    cm = CoverageManager(storage_manager, config_loader, downloader, cache_size=10)

    # 测试日期列检测
    date_col = cm._detect_date_column(report_rc_config)
    assert date_col == 'report_date', f"应检测到 report_date，实际是 {date_col}"
    print("  ✓ 正确检测到 report_date 列")

    # 测试读取已有日期
    dates = cm._get_existing_dates_from_storage('report_rc')
    assert len(dates) == 3, f"应有3个日期，实际有 {len(dates)} 个"
    assert '20250815' in dates
    print("  ✓ 正确读取已有日期数据")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("缺口检测功能单元测试")
    print("=" * 60)

    tests = [
        test_no_gaps_complete_coverage,
        test_single_gap,
        test_multiple_gaps,
        test_min_gap_days_filter,
        test_max_gaps_limit,
        test_cache_functionality,
        test_lru_cache_eviction,
        test_detect_date_column,
        test_report_rc_scenario,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    # 输出 metrics
    metrics = {
        "total_tests": len(tests),
        "passed": passed,
        "failed": failed,
        "success_rate": passed / len(tests) if tests else 0
    }

    with open("test_gap_detection.metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
