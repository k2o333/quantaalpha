"""
内存探查工具 - 用于检测 main.py 运行时的内存泄漏和残留数据

使用方法:
    1. 在 main.py 中导入并初始化 MemoryInspector
    2. 在关键位置调用 inspect() 方法检查内存
    3. 或者使用装饰器自动监控函数内存

示例:
    from utils.memory_inspector import MemoryInspector
    
    inspector = MemoryInspector()
    
    # 在数据保存后检查
    storage_manager.save_data(...)
    inspector.inspect(label="after_save")
"""

import gc
import sys
import tracemalloc
import threading
import time
import logging
from typing import Dict, List, Any, Optional, Callable
from collections import defaultdict
import weakref

logger = logging.getLogger(__name__)


class MemorySnapshot:
    """内存快照，用于对比分析"""
    
    def __init__(self, label: str = ""):
        self.label = label
        self.timestamp = time.time()
        self.objects = self._capture_objects()
        self.top_types = self._get_top_types()
        
    def _capture_objects(self) -> Dict[str, int]:
        """捕获当前内存中的对象统计"""
        gc.collect()  # 强制垃圾回收
        
        type_counts = defaultdict(int)
        type_sizes = defaultdict(int)
        
        for obj in gc.get_objects():
            try:
                obj_type = type(obj).__name__
                type_counts[obj_type] += 1
                
                # 估算大小（粗略）
                try:
                    size = sys.getsizeof(obj)
                    type_sizes[obj_type] += size
                except:
                    pass
            except:
                pass
                
        return {
            'counts': dict(type_counts),
            'sizes': dict(type_sizes),
            'total_objects': sum(type_counts.values()),
            'total_size': sum(type_sizes.values())
        }
    
    def _get_top_types(self, top_n: int = 20) -> List[tuple]:
        """获取占用内存最多的类型"""
        sizes = self.objects['sizes']
        return sorted(sizes.items(), key=lambda x: x[1], reverse=True)[:top_n]
    
    def diff(self, other: 'MemorySnapshot') -> Dict[str, Any]:
        """与另一个快照对比"""
        diff_counts = {}
        diff_sizes = {}
        
        all_types = set(self.objects['counts'].keys()) | set(other.objects['counts'].keys())
        
        for obj_type in all_types:
            count_diff = self.objects['counts'].get(obj_type, 0) - other.objects['counts'].get(obj_type, 0)
            size_diff = self.objects['sizes'].get(obj_type, 0) - other.objects['sizes'].get(obj_type, 0)
            
            if count_diff != 0:
                diff_counts[obj_type] = count_diff
            if size_diff != 0:
                diff_sizes[obj_type] = size_diff
        
        return {
            'time_diff': self.timestamp - other.timestamp,
            'count_diff': diff_counts,
            'size_diff': diff_sizes,
            'total_objects_diff': self.objects['total_objects'] - other.objects['total_objects'],
            'total_size_diff': self.objects['total_size'] - other.objects['total_size']
        }


class DataLeakDetector:
    """数据泄漏检测器 - 专门检测下载数据是否被正确释放"""
    
    def __init__(self):
        self._tracked_objects = weakref.WeakSet()
        self._snapshots = []
        
    def track_data(self, data: List[Dict[str, Any]], label: str = ""):
        """跟踪一个数据对象"""
        # 创建弱引用
        ref = weakref.ref(data)
        self._tracked_objects.add(data)
        
        self._snapshots.append({
            'label': label,
            'timestamp': time.time(),
            'data_id': id(data),
            'data_len': len(data),
            'weak_ref': ref
        })
        
        logger.debug(f"[DataLeakDetector] 开始跟踪数据: {label}, id={id(data)}, len={len(data)}")
    
    def check_leaks(self) -> List[Dict[str, Any]]:
        """检查是否有数据未被释放"""
        gc.collect()
        
        leaks = []
        for snapshot in self._snapshots:
            ref = snapshot['weak_ref']
            if ref() is not None:
                # 对象还存在
                leaks.append({
                    'label': snapshot['label'],
                    'data_id': snapshot['data_id'],
                    'original_len': snapshot['data_len'],
                    'alive_since': time.time() - snapshot['timestamp']
                })
        
        return leaks
    
    def get_report(self) -> str:
        """生成泄漏报告"""
        leaks = self.check_leaks()
        
        if not leaks:
            return "[DataLeakDetector] ✓ 所有数据都已正确释放"
        
        report = ["[DataLeakDetector] ⚠ 发现未释放的数据:"]
        for leak in leaks:
            report.append(
                f"  - {leak['label']}: id={leak['data_id']}, "
                f"原始大小={leak['original_len']}, "
                f"存活时间={leak['alive_since']:.1f}s"
            )
        
        return "\n".join(report)


class MemoryInspector:
    """
    内存探查器 - 主类
    
    功能:
    1. 在关键位置捕获内存快照
    2. 对比快照发现内存增长
    3. 检测数据对象是否被正确释放
    4. 生成内存使用报告
    """
    
    def __init__(self, enable_tracemalloc: bool = False):
        self.snapshots: List[MemorySnapshot] = []
        self.leak_detector = DataLeakDetector()
        self.enable_tracemalloc = enable_tracemalloc
        
        if enable_tracemalloc:
            tracemalloc.start()
            logger.info("[MemoryInspector] tracemalloc 已启动")
    
    def inspect(self, label: str = "", check_leaks: bool = True) -> MemorySnapshot:
        """
        捕获内存快照并分析
        
        Args:
            label: 快照标签，用于识别检查点
            check_leaks: 是否检查数据泄漏
        """
        snapshot = MemorySnapshot(label)
        self.snapshots.append(snapshot)
        
        # 打印当前内存状态
        logger.info(f"\n{'='*60}")
        logger.info(f"[MemoryInspector] 检查点: {label}")
        logger.info(f"{'='*60}")
        logger.info(f"总对象数: {snapshot.objects['total_objects']:,}")
        logger.info(f"总内存占用: {snapshot.objects['total_size'] / 1024 / 1024:.2f} MB")
        
        # 显示占用最多的类型
        logger.info("\nTop 10 内存占用类型:")
        for obj_type, size in snapshot.top_types[:10]:
            count = snapshot.objects['counts'].get(obj_type, 0)
            logger.info(f"  {obj_type}: {count:,} 个, {size / 1024 / 1024:.2f} MB")
        
        # 与上一个快照对比
        if len(self.snapshots) > 1:
            prev = self.snapshots[-2]
            diff = snapshot.diff(prev)
            
            logger.info(f"\n与上一个检查点 '{prev.label}' 对比:")
            logger.info(f"  时间间隔: {diff['time_diff']:.2f}s")
            logger.info(f"  对象数变化: {diff['total_objects_diff']:+,.0f}")
            logger.info(f"  内存变化: {diff['total_size_diff'] / 1024 / 1024:+.2f} MB")
            
            # 显示增长最多的类型
            if diff['size_diff']:
                logger.info("\n增长最多的类型:")
                sorted_diffs = sorted(
                    diff['size_diff'].items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:5]
                for obj_type, size_diff in sorted_diffs:
                    if size_diff > 0:
                        logger.info(f"  {obj_type}: +{size_diff / 1024 / 1024:.2f} MB")
        
        # 检查数据泄漏
        if check_leaks:
            leak_report = self.leak_detector.get_report()
            if "⚠" in leak_report:
                logger.warning(f"\n{leak_report}")
            else:
                logger.info(f"\n{leak_report}")
        
        # tracemalloc 详细分析
        if self.enable_tracemalloc:
            self._print_tracemalloc_stats()
        
        logger.info(f"{'='*60}\n")
        
        return snapshot
    
    def track_data(self, data: List[Dict[str, Any]], label: str = ""):
        """跟踪一个数据对象，检查是否被正确释放"""
        self.leak_detector.track_data(data, label)
    
    def _print_tracemalloc_stats(self):
        """打印 tracemalloc 统计"""
        current, peak = tracemalloc.get_traced_memory()
        logger.info(f"\n[tracemalloc] 当前内存: {current / 1024 / 1024:.2f} MB")
        logger.info(f"[tracemalloc] 峰值内存: {peak / 1024 / 1024:.2f} MB")
        
        # Top 10 内存分配点
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')[:10]
        
        logger.info("\nTop 10 内存分配点:")
        for stat in top_stats:
            logger.info(f"  {stat.traceback.format()[-1]}")
            logger.info(f"    大小: {stat.size / 1024:.2f} KB, 次数: {stat.count}")
    
    def get_memory_report(self) -> str:
        """生成完整的内存报告"""
        if not self.snapshots:
            return "没有内存快照"
        
        lines = ["="*60, "内存使用报告", "="*60, ""]
        
        # 总体趋势
        first = self.snapshots[0]
        last = self.snapshots[-1]
        total_diff = last.diff(first)
        
        lines.append(f"总监控时间: {total_diff['time_diff']:.2f}s")
        lines.append(f"总对象数变化: {total_diff['total_objects_diff']:+,.0f}")
        lines.append(f"总内存变化: {total_diff['total_size_diff'] / 1024 / 1024:+.2f} MB")
        lines.append("")
        
        # 每个检查点的详情
        lines.append("检查点详情:")
        for i, snapshot in enumerate(self.snapshots):
            lines.append(f"\n{i+1}. {snapshot.label}")
            lines.append(f"   对象数: {snapshot.objects['total_objects']:,}")
            lines.append(f"   内存: {snapshot.objects['total_size'] / 1024 / 1024:.2f} MB")
            
            if i > 0:
                diff = snapshot.diff(self.snapshots[i-1])
                lines.append(f"   变化: {diff['total_size_diff'] / 1024 / 1024:+.2f} MB")
        
        # 泄漏检测
        lines.append("\n" + "="*60)
        lines.append(self.leak_detector.get_report())
        
        return "\n".join(lines)


def memory_monitor(interval: float = 5.0, label_prefix: str = "auto"):
    """
    装饰器：自动监控函数内存使用
    
    示例:
        @memory_monitor(interval=2.0)
        def download_data():
            ...
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            inspector = MemoryInspector()
            stop_event = threading.Event()
            
            def monitor_loop():
                count = 0
                while not stop_event.is_set():
                    time.sleep(interval)
                    if not stop_event.is_set():
                        count += 1
                        inspector.inspect(label=f"{label_prefix}_{count}")
            
            # 启动监控线程
            monitor_thread = threading.Thread(target=monitor_loop)
            monitor_thread.start()
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                stop_event.set()
                monitor_thread.join(timeout=1)
                
                # 最终报告
                logger.info("\n" + inspector.get_memory_report())
        
        return wrapper
    return decorator


# 便捷函数：快速检查内存
def quick_inspect(label: str = ""):
    """快速检查当前内存状态"""
    gc.collect()
    
    # 统计主要类型
    type_counts = defaultdict(int)
    type_sizes = defaultdict(int)
    
    for obj in gc.get_objects():
        try:
            obj_type = type(obj).__name__
            type_counts[obj_type] += 1
            try:
                type_sizes[obj_type] += sys.getsizeof(obj)
            except:
                pass
        except:
            pass
    
    total_size = sum(type_sizes.values())
    
    logger.info(f"\n[QuickInspect] {label}")
    logger.info(f"  总对象数: {sum(type_counts.values()):,}")
    logger.info(f"  总内存: {total_size / 1024 / 1024:.2f} MB")
    
    # 显示列表和字典数量（数据的主要载体）
    list_count = type_counts.get('list', 0)
    dict_count = type_counts.get('dict', 0)
    logger.info(f"  list 数量: {list_count:,}")
    logger.info(f"  dict 数量: {dict_count:,}")
    
    return {
        'total_objects': sum(type_counts.values()),
        'total_size': total_size,
        'list_count': list_count,
        'dict_count': dict_count
    }
