# /home/quan/testdata/aspipe_v4/app4/core/performance_monitor.py

import time
import json
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class RequestMetric:
    """请求指标"""
    interface: str
    duration: float
    record_count: int
    retry_count: int
    window_start: str = None
    window_end: str = None
    timestamp: float = 0.0

class PerformanceMonitor:
    """增强性能监控器"""

    def __init__(self):
        self.metrics: List[RequestMetric] = []
        self.start_time = time.time()

    def record_request(self, interface: str, duration: float,
                      record_count: int, retry_count: int,
                      window_start: str = None, window_end: str = None):
        """记录请求指标"""
        metric = RequestMetric(
            interface=interface,
            duration=duration,
            record_count=record_count,
            retry_count=retry_count,
            window_start=window_start,
            window_end=window_end,
            timestamp=time.time()
        )
        self.metrics.append(metric)

    def get_summary(self) -> Dict[str, Any]:
        """获取汇总统计"""
        if not self.metrics:
            return {}

        # 按接口分组
        by_interface = {}
        for metric in self.metrics:
            if metric.interface not in by_interface:
                by_interface[metric.interface] = []
            by_interface[metric.interface].append(metric)

        summary = {}

        for interface, metrics in by_interface.items():
            durations = [m.duration for m in metrics]
            record_counts = [m.record_count for m in metrics]
            retry_counts = [m.retry_count for m in metrics]

            # 计算分布统计
            durations_sorted = sorted(durations)
            record_counts_sorted = sorted(record_counts)

            summary[interface] = {
                'total_requests': len(metrics),
                'total_records': sum(record_counts),
                'total_time': sum(durations),
                # 平均数
                'avg_duration': sum(durations) / len(durations),
                'avg_records': sum(record_counts) / len(record_counts),
                'avg_retries': sum(retry_counts) / len(retry_counts),
                # P50/P90/P99
                'p50_duration': self._percentile(durations_sorted, 0.5),
                'p90_duration': self._percentile(durations_sorted, 0.9),
                'p99_duration': self._percentile(durations_sorted, 0.99),
                'p50_records': self._percentile(record_counts_sorted, 0.5),
                'p90_records': self._percentile(record_counts_sorted, 0.9),
                # 成功率
                'success_rate': len([m for m in metrics if m.record_count > 0]) / len(metrics) * 100,
            }

        return summary

    def _percentile(self, sorted_values: List[float], percentile: float) -> float:
        """计算百分位数"""
        if not sorted_values:
            return 0.0

        index = int(len(sorted_values) * percentile)
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]

    def save_report(self, filepath: str):
        """保存详细报告"""
        summary = self.get_summary()

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("# 性能监控报告\n\n")
            f.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"总运行时间: {time.time() - self.start_time:.2f}秒\n")
            f.write(f"总请求数: {len(self.metrics)}\n\n")

            for interface, stats in summary.items():
                f.write(f"## 接口: {interface}\n")
                f.write(f"- 请求次数: {stats['total_requests']}\n")
                f.write(f"- 总记录数: {stats['total_records']}\n")
                f.write(f"- 总耗时: {stats['total_time']:.2f}秒\n")
                f.write(f"- 成功率: {stats['success_rate']:.1f}%\n")
                f.write(f"- 平均请求时间: {stats['avg_duration']:.2f}秒\n")
                f.write(f"- P50/P90/P99: {stats['p50_duration']:.2f}/{stats['p90_duration']:.2f}/{stats['p99_duration']:.2f}秒\n")
                f.write(f"- 平均记录数: {stats['avg_records']:.0f}条\n\n")

        logger.info(f"性能报告已保存: {filepath}")