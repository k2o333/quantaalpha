# 性能监控增强实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 增强性能监控能力，提供详细的P50/P90/P99统计，提升系统可观测性

**Architecture:** PerformanceMonitor类收集和分析性能指标，生成可视化报告

**Tech Stack:** Python, 数据统计, Markdown报告生成

---

### Task 1: 创建PerformanceMonitor类

**Files:**
- Create: `app4/core/performance_monitor.py`

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

运行: `pytest test_performance_monitor.py::test_performance_monitor_initialization -v`
Expected: FAIL with file not found

**Step 3: Write minimal implementation**

```python
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
```

**Step 4: Run test to verify it passes**

运行: `pytest test_performance_monitor.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app4/core/performance_monitor.py
git commit -m "feat: implement PerformanceMonitor class"
```

### Task 2: 集成性能监控到Downloader

**Files:**
- Modify: `app4/core/downloader.py`

**Step 1: Write the failing test**

```python
# test_downloader_performance_monitor.py
from app4.core.downloader import GenericDownloader
from app4.core.config_loader import ConfigLoader

def test_downloader_performance_monitor():
    """测试Downloader中的性能监控集成"""
    config_loader = ConfigLoader('app4/config')
    downloader = GenericDownloader(config_loader)

    # 验证性能监控器已初始化
    assert hasattr(downloader, 'performance_monitor')
    assert downloader.performance_monitor is not None
```

**Step 2: Run test to verify it fails**

运行: `pytest test_downloader_performance_monitor.py::test_downloader_performance_monitor -v`
Expected: FAIL with attribute not found

**Step 3: Write minimal implementation**

在 `app4/core/downloader.py` 中的 `GenericDownloader` 类初始化方法中添加性能监控器:

```python
# 在__init__方法中添加
def __init__(self, config_loader, max_workers=4,
             trade_calendar_cache=None, stock_list_cache=None):
    # ... 现有初始化代码 ...

    # 初始化性能监控器
    from app4.core.performance_monitor import PerformanceMonitor
    self.performance_monitor = PerformanceMonitor()

    # ... 其余初始化代码 ...
```

在 `_make_request` 方法中添加性能指标记录:

```python
def _make_request(self, interface_config, params):
    start_time = time.time()
    retry_count = 0

    # ... 请求逻辑，包含重试 ...
    # 这里是原有的请求代码

    duration = time.time() - start_time

    # 记录指标
    self.performance_monitor.record_request(
        interface=interface_config['name'],
        duration=duration,
        record_count=len(data) if data else 0,
        retry_count=retry_count,
        window_start=params.get('start_date'),
        window_end=params.get('end_date')
    )

    return data
```

**Step 4: Run test to verify it passes**

运行: `pytest test_downloader_performance_monitor.py::test_downloader_performance_monitor -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app4/core/downloader.py
git commit -m "feat: integrate PerformanceMonitor with downloader"
```

### Task 3: 在main.py中生成性能报告

**Files:**
- Modify: `app4/main.py`

**Step 1: Write the failing test**

此任务集成到现有main.py，不需要单独测试

**Step 2: Write minimal implementation**

修改 `app4/main.py` 文件，在执行完成后生成性能报告:

```python
# 在main函数的最后添加性能报告生成
def main():
    # ... 现有执行逻辑 ...

    # 执行下载任务
    for interface_name in interfaces:
        # ... 现有接口处理逻辑 ...

    # 生成性能报告
    import os
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    performance_file = os.path.join(log_dir, f"performance_report_{timestamp}.md")
    downloader.performance_monitor.save_report(performance_file)

    logger.info(f"性能报告已生成: {performance_file}")
```

**Step 3: Commit**

```bash
git add app4/main.py
git commit -m "feat: generate performance reports in main entry point"
```