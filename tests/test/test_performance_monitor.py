# test_performance_monitor.py
from app4.core.performance_monitor import PerformanceMonitor, RequestMetric
import time

def test_performance_monitor_initialization():
    """测试性能监控器初始化"""
    monitor = PerformanceMonitor()

    assert len(monitor.metrics) == 0
    assert monitor.start_time > 0

def test_record_request():
    """测试记录请求指标"""
    monitor = PerformanceMonitor()

    # 记录一个指标
    monitor.record_request(
        interface='test_interface',
        duration=1.5,
        record_count=100,
        retry_count=0,
        window_start='20230101',
        window_end='20230131'
    )

    assert len(monitor.metrics) == 1
    metric = monitor.metrics[0]
    assert metric.interface == 'test_interface'
    assert metric.duration == 1.5
    assert metric.record_count == 100

def test_get_summary():
    """测试获取汇总统计"""
    monitor = PerformanceMonitor()

    # 添加多个指标
    for i in range(100):
        monitor.record_request(
            interface='test_interface',
            duration=i * 0.1,  # 0.0到9.9秒
            record_count=50 + i,
            retry_count=0
        )

    summary = monitor.get_summary()
    assert 'test_interface' in summary
    stats = summary['test_interface']
    assert stats['total_requests'] == 100
    assert stats['p90_duration'] >= 8.9  # P90应该是第90百分位