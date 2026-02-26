# 空查询追踪方案（最终版）

> 基于评审意见改进，整合采纳的优化建议

---

## 一、方案概述

### 核心思路
**只记录"空查询"**（返回0条记录的查询），并添加过期检查机制。

### 与原方案对比

| 对比项 | 原方案 | 最终方案 |
|--------|--------|----------|
| 存储内容 | 所有查询 | 仅空查询 |
| 存储量 | 大 | 小 |
| I/O 性能 | 每次写入 | 批量写入 |
| 处理数据更新 | ❌ | ✅ TTL过期检查 |
| 查询键生成 | 60+ 行 | 简化版 |

---

## 二、数据结构

### 文件位置
```
data/{interface_name}/.empty_queries.json
```

### 记录格式
```json
{
  "anchor:ann_date:20260112": "2026-02-25T16:13:35",
  "date:20260114": "2026-02-25T16:13:36",
  "period:end_date:20260331": "2026-02-25T16:13:00",
  "stock_date:000001.SZ:20260119": "2026-02-25T16:13:37"
}
```

**简化说明**：只存储 `{query_key: queried_at}`，不再存储详细信息，按需解析。

---

## 三、查询键生成规则

| 场景 | 查询键格式 | 示例 |
|-----|-----------|------|
| 日期锚点（is_date_anchor） | `anchor:{param}:{value}` | `anchor:ann_date:20260112` |
| 单日期查询 | `date:{date}` | `date:20260114` |
| 报告期查询 | `period:{field}:{value}` | `period:end_date:20260331` |
| 股票+日期 | `stock_date:{ts_code}:{date}` | `stock_date:000001.SZ:20260112` |
| 股票+报告期 | `stock_period:{ts_code}:{period}` | `stock_period:000001.SZ:20260331` |

**注意**：多日范围（`date_range`）不记录，原因：
1. 实际场景中 `window_size_days` 通常为 1
2. 展开多日范围增加复杂度和存储
3. 如需支持，可在后续版本添加

---

## 四、核心实现

### 1. EmptyQueryTracker 类

```python
# app4/core/empty_query_tracker.py

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Set, Any, Optional
import threading

logger = logging.getLogger(__name__)


class EmptyQueryTracker:
    """
    空查询追踪器 - 只记录返回0条记录的查询
    
    特性：
    1. 只记录空查询，减少存储开销
    2. TTL过期检查，处理数据补发场景
    3. 批量写入，优化 I/O 性能
    4. 线程安全
    """
    
    def __init__(
        self, 
        data_dir: str = "data",
        ttl_days: int = 30,
        batch_size: int = 50
    ):
        """
        Args:
            data_dir: 数据目录
            ttl_days: 空查询记录有效期（天），超过后重新检查
            batch_size: 批量写入阈值
        """
        self.data_dir = Path(data_dir)
        self.ttl_days = ttl_days
        self.batch_size = batch_size
        
        # 内存缓存: {interface_name: {query_key: queried_at}}
        self._cache: Dict[str, Dict[str, str]] = {}
        self._pending: Dict[str, Dict[str, str]] = {}  # 待写入记录
        self._lock = threading.RLock()
        self._dirty: Set[str] = set()  # 需要保存的接口
    
    def _get_file_path(self, interface_name: str) -> Path:
        """获取空查询记录文件路径"""
        return self.data_dir / interface_name / ".empty_queries.json"
    
    def _load(self, interface_name: str) -> Dict[str, str]:
        """从文件加载空查询记录"""
        with self._lock:
            if interface_name in self._cache:
                return self._cache[interface_name]
            
            file_path = self._get_file_path(interface_name)
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self._cache[interface_name] = data
                        return data
                except Exception as e:
                    logger.warning(f"加载空查询记录失败 {interface_name}: {e}")
            
            self._cache[interface_name] = {}
            return self._cache[interface_name]
    
    def _save(self, interface_name: str):
        """保存到文件"""
        with self._lock:
            file_path = self._get_file_path(interface_name)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self._cache[interface_name], f, ensure_ascii=False)
                self._dirty.discard(interface_name)
            except Exception as e:
                logger.warning(f"保存空查询记录失败 {interface_name}: {e}")
    
    def _flush_pending(self, interface_name: str):
        """将待写入记录合并到缓存"""
        with self._lock:
            if interface_name not in self._pending:
                return
            
            pending = self._pending[interface_name]
            if not pending:
                return
            
            # 确保缓存已加载
            self._load(interface_name)
            
            # 合并到缓存
            self._cache[interface_name].update(pending)
            self._pending[interface_name].clear()
            self._dirty.add(interface_name)
            
            # 达到批量阈值时保存
            if len(self._cache[interface_name]) >= self.batch_size:
                self._save(interface_name)
    
    def generate_query_key(
        self, 
        params: Dict[str, Any], 
        interface_config: Dict[str, Any]
    ) -> Optional[str]:
        """
        根据请求参数生成查询键
        
        Args:
            params: 请求参数
            interface_config: 接口配置
            
        Returns:
            查询键，无法生成时返回 None
        """
        # 1. 检查日期锚点接口
        param_defs = interface_config.get("parameters", {})
        for param_name, param_def in param_defs.items():
            if param_def.get("is_date_anchor", False) and param_name in params:
                anchor_value = params.get(param_name)
                if anchor_value:
                    return f"anchor:{param_name}:{anchor_value}"
        
        # 2. 处理股票维度
        ts_code = params.get("ts_code")
        if ts_code:
            # 报告期模式
            period_field = params.get("_period_field", "period")
            period_value = params.get(period_field) or params.get("period")
            if period_value:
                return f"stock_period:{ts_code}:{period_value}"
            
            # 日期模式（单日）
            start_date = params.get("start_date")
            end_date = params.get("end_date")
            if start_date and end_date and start_date == end_date:
                return f"stock_date:{ts_code}:{start_date}"
            
            return None  # 多日范围不记录
        
        # 3. 处理报告期模式（无股票维度）
        period_field = params.get("_period_field", "period")
        period_value = params.get(period_field) or params.get("period")
        if period_value:
            return f"period:{period_field}:{period_value}"
        
        # 4. 处理单日期模式
        start_date = params.get("start_date")
        end_date = params.get("end_date")
        if start_date and end_date and start_date == end_date:
            return f"date:{start_date}"
        
        # 5. 其他场景不记录（多日范围等）
        return None
    
    def record_empty(
        self, 
        interface_name: str, 
        params: Dict[str, Any], 
        interface_config: Dict[str, Any]
    ):
        """
        记录空查询
        
        Args:
            interface_name: 接口名称
            params: 请求参数
            interface_config: 接口配置
        """
        query_key = self.generate_query_key(params, interface_config)
        if not query_key:
            return
        
        with self._lock:
            if interface_name not in self._pending:
                self._pending[interface_name] = {}
            
            self._pending[interface_name][query_key] = datetime.now().isoformat()
            self._flush_pending(interface_name)
        
        logger.debug(f"记录空查询 {interface_name}: {query_key}")
    
    def is_empty_queried(
        self, 
        interface_name: str, 
        params: Dict[str, Any], 
        interface_config: Dict[str, Any]
    ) -> bool:
        """
        检查是否已查询过且为空（未过期）
        
        Returns:
            True: 已查询且为空，应跳过
            False: 未查询或已过期，应重新查询
        """
        query_key = self.generate_query_key(params, interface_config)
        if not query_key:
            return False
        
        with self._lock:
            records = self._load(interface_name)
            queried_at = records.get(query_key)
            
            if not queried_at:
                return False
            
            # 检查是否过期
            try:
                queried_time = datetime.fromisoformat(queried_at)
                age_days = (datetime.now() - queried_time).days
                
                if age_days > self.ttl_days:
                    logger.info(
                        f"空查询记录已过期 ({age_days}天)，重新检查: {query_key}"
                    )
                    # 删除过期记录
                    del records[query_key]
                    self._dirty.add(interface_name)
                    self._save(interface_name)
                    return False
                
                return True
            except Exception:
                return False
    
    def get_empty_queried_dates(self, interface_name: str) -> Set[str]:
        """
        获取已查询过且为空的日期集合（未过期）
        
        用于 detect_gaps() 合并到已覆盖日期
        
        Returns:
            日期字符串集合
        """
        with self._lock:
            records = self._load(interface_name)
            dates = set()
            cutoff = datetime.now() - timedelta(days=self.ttl_days)
            
            for key, queried_at in records.items():
                try:
                    queried_time = datetime.fromisoformat(queried_at)
                    if queried_time < cutoff:
                        continue
                    
                    # 解析日期
                    parts = key.split(":")
                    query_type = parts[0]
                    
                    if query_type == "date":
                        dates.add(parts[1])
                    elif query_type == "anchor":
                        dates.add(parts[2])
                    elif query_type == "stock_date":
                        dates.add(parts[2])
                    # period 和 stock_period 不包含日期，跳过
                    
                except Exception:
                    continue
            
            return dates
    
    def get_empty_queried_periods(
        self, 
        interface_name: str, 
        period_field: str = "period"
    ) -> Set[str]:
        """
        获取已查询过且为空的报告期集合（未过期）
        
        Returns:
            报告期字符串集合
        """
        with self._lock:
            records = self._load(interface_name)
            periods = set()
            cutoff = datetime.now() - timedelta(days=self.ttl_days)
            
            for key, queried_at in records.items():
                try:
                    queried_time = datetime.fromisoformat(queried_at)
                    if queried_time < cutoff:
                        continue
                    
                    parts = key.split(":")
                    query_type = parts[0]
                    
                    if query_type == "period" and parts[1] == period_field:
                        periods.add(parts[2])
                    elif query_type == "stock_period":
                        periods.add(parts[2])
                        
                except Exception:
                    continue
            
            return periods
    
    def clear(self, interface_name: str):
        """清除接口的空查询记录"""
        with self._lock:
            self._cache.pop(interface_name, None)
            self._pending.pop(interface_name, None)
            self._dirty.discard(interface_name)
            
            file_path = self._get_file_path(interface_name)
            if file_path.exists():
                file_path.unlink()
    
    def flush_all(self):
        """刷新所有待写入记录到文件"""
        with self._lock:
            for interface_name in list(self._pending.keys()):
                self._flush_pending(interface_name)
            
            for interface_name in self._dirty:
                self._save(interface_name)
    
    def prune_expired(self, interface_name: str = None) -> int:
        """
        清理过期记录
        
        Args:
            interface_name: 指定接口，None 则清理所有
            
        Returns:
            清理的记录数
        """
        cutoff = datetime.now() - timedelta(days=self.ttl_days)
        total_pruned = 0
        
        with self._lock:
            interfaces = [interface_name] if interface_name else list(self._cache.keys())
            
            for iface in interfaces:
                if iface not in self._cache:
                    continue
                
                records = self._cache[iface]
                original_count = len(records)
                
                self._cache[iface] = {
                    k: v for k, v in records.items()
                    if datetime.fromisoformat(v) >= cutoff
                }
                
                pruned = original_count - len(self._cache[iface])
                if pruned > 0:
                    self._dirty.add(iface)
                    self._save(iface)
                    total_pruned += pruned
                    logger.info(f"清理过期空查询记录 {iface}: {pruned}条")
        
        return total_pruned
```

---

## 五、集成修改

### 1. CoverageManager 集成

```python
# app4/core/coverage_manager.py

from .empty_query_tracker import EmptyQueryTracker

class CoverageManager:
    def __init__(
        self,
        storage_manager: StorageManager,
        config_loader: ConfigLoader,
        downloader=None,
        cache_size: int = 128,
        empty_query_tracker: Optional[EmptyQueryTracker] = None,
    ):
        # ... 现有初始化 ...
        self.empty_query_tracker = empty_query_tracker
    
    def detect_gaps(
        self,
        interface_name: str,
        target_range: DateRange,
        trade_calendar: List[Dict[str, Any]],
        min_gap_days: int = 1,
        max_gaps: int = 50,
    ) -> List[DateRange]:
        """检测缺失的日期段"""
        logger.info(f"检测缺口: {interface_name} ({target_range})")
        
        # 1. 获取已有数据的日期
        existing_dates = self._get_existing_dates_cached(interface_name)
        logger.info(f"已有数据: {len(existing_dates)} 天")
        
        # 2. 获取已查询过但无数据的日期
        empty_queried_dates = set()
        if self.empty_query_tracker:
            empty_queried_dates = self.empty_query_tracker.get_empty_queried_dates(
                interface_name
            )
            if empty_queried_dates:
                logger.info(f"已查询（空结果）: {len(empty_queried_dates)} 天")
        
        # 3. 合并覆盖日期
        covered_dates = existing_dates | empty_queried_dates
        
        # 4. 计算期望交易日
        expected_dates = set()
        for day in trade_calendar:
            cal_date = day.get("cal_date")
            is_open = day.get("is_open", 0)
            if cal_date and is_open == 1:
                if target_range.start_date <= cal_date <= target_range.end_date:
                    expected_dates.add(cal_date)
        
        logger.info(f"期望交易日: {len(expected_dates)} 天")
        
        # 5. 检查完整覆盖
        if covered_dates >= expected_dates:
            logger.info("数据已完整覆盖（含空查询记录），无需下载")
            return []
        
        # 6. 计算缺失日期
        missing_dates = expected_dates - covered_dates
        # ... 后续逻辑不变 ...
```

### 2. _check_period_existence 增强

```python
# app4/core/coverage_manager.py

def _check_period_existence(
    self, 
    interface_name: str, 
    params: Dict[str, Any]
) -> bool:
    """检查报告期是否存在 - 增强版"""
    period_field = params.get("_period_field", "period")
    period = params.get(period_field) or params.get("period")
    
    if not period:
        return False
    
    # 1. 检查是否有数据
    interface_config = self.config_loader.get_interface_config(interface_name)
    detection_config = interface_config.get("duplicate_detection", {})
    date_column = detection_config.get("date_column", period_field)
    
    # ... 原有数据检查逻辑 ...
    has_data = period in self._cache[cache_key]
    
    if has_data:
        return True
    
    # 2. 检查是否已查询且为空
    if self.empty_query_tracker:
        return self.empty_query_tracker.is_empty_queried(
            interface_name, params, interface_config
        )
    
    return False
```

### 3. Downloader 集成

```python
# app4/core/downloader.py

from .empty_query_tracker import EmptyQueryTracker

class GenericDownloader:
    def __init__(self, ...):
        # ... 现有初始化 ...
        
        # 初始化空查询追踪器
        coverage_config = self.global_config.get("coverage", {})
        self.empty_query_tracker = EmptyQueryTracker(
            data_dir=self.global_config.get("storage", {}).get("base_dir", "data"),
            ttl_days=coverage_config.get("empty_query_ttl_days", 30),
            batch_size=coverage_config.get("empty_query_batch_size", 50)
        )
        
        # 注入到 CoverageManager
        if self.coverage_manager:
            self.coverage_manager.empty_query_tracker = self.empty_query_tracker
    
    def _make_request(
        self, 
        interface_config: Dict[str, Any], 
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """发起 API 请求 - 增强版"""
        # ... 现有请求逻辑 ...
        
        converted_data = []  # 原有逻辑获取的数据
        
        # 记录空查询
        if self.empty_query_tracker and len(converted_data) == 0:
            interface_name = interface_config.get("name") or interface_config.get("api_name")
            if interface_name:
                self.empty_query_tracker.record_empty(
                    interface_name,
                    params,
                    interface_config
                )
        
        return converted_data
    
    def close(self):
        """关闭时刷新待写入记录"""
        if self.empty_query_tracker:
            self.empty_query_tracker.flush_all()
```

---

## 六、配置支持

```yaml
# app4/config/settings.yaml

coverage:
  # 空查询追踪配置
  empty_query_tracking_enabled: true  # 是否启用
  empty_query_ttl_days: 30            # 记录有效期（天）
  empty_query_batch_size: 50          # 批量写入阈值
```

---

## 七、CLI 支持

```bash
# 清除指定接口的空查询记录
python app4/main.py --clear-empty-queries --interface dividend

# 清理所有过期记录
python app4/main.py --prune-empty-queries
```

---

## 八、测试用例

```python
# test/test_empty_query_tracker.py

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from app4.core.empty_query_tracker import EmptyQueryTracker


class TestEmptyQueryTracker:
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.tracker = EmptyQueryTracker(data_dir=self.temp_dir, ttl_days=1)
    
    def teardown_method(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_record_and_check_anchor_query(self):
        """测试日期锚点查询"""
        interface_config = {"parameters": {"ann_date": {"is_date_anchor": True}}}
        params = {"ann_date": "20260112"}
        
        # 初始未查询
        assert not self.tracker.is_empty_queried("test", params, interface_config)
        
        # 记录空查询
        self.tracker.record_empty("test", params, interface_config)
        
        # 已查询
        assert self.tracker.is_empty_queried("test", params, interface_config)
    
    def test_record_and_check_date_query(self):
        """测试单日期查询"""
        interface_config = {"parameters": {}}
        params = {"start_date": "20260112", "end_date": "20260112"}
        
        self.tracker.record_empty("test", params, interface_config)
        assert self.tracker.is_empty_queried("test", params, interface_config)
    
    def test_record_and_check_period_query(self):
        """测试报告期查询"""
        interface_config = {"parameters": {}}
        params = {"period": "20260331"}
        
        self.tracker.record_empty("test", params, interface_config)
        assert self.tracker.is_empty_queried("test", params, interface_config)
    
    def test_record_and_check_stock_date_query(self):
        """测试股票+日期查询"""
        interface_config = {"parameters": {}}
        params = {"ts_code": "000001.SZ", "start_date": "20260112", "end_date": "20260112"}
        
        self.tracker.record_empty("test", params, interface_config)
        assert self.tracker.is_empty_queried("test", params, interface_config)
    
    def test_expired_query(self):
        """测试过期检查"""
        interface_config = {"parameters": {"ann_date": {"is_date_anchor": True}}}
        params = {"ann_date": "20260112"}
        
        # 手动设置过期记录
        self.tracker._load("test")
        old_time = (datetime.now() - timedelta(days=2)).isoformat()
        self.tracker._cache["test"]["anchor:ann_date:20260112"] = old_time
        
        # 过期记录应返回 False
        assert not self.tracker.is_empty_queried("test", params, interface_config)
    
    def test_get_empty_queried_dates(self):
        """测试获取空查询日期集合"""
        interface_config = {"parameters": {"ann_date": {"is_date_anchor": True}}}
        
        # 记录多个空查询
        for date in ["20260101", "20260102", "20260103"]:
            self.tracker.record_empty(
                "test", 
                {"ann_date": date}, 
                interface_config
            )
        
        dates = self.tracker.get_empty_queried_dates("test")
        assert "20260101" in dates
        assert "20260102" in dates
        assert "20260103" in dates
    
    def test_multi_day_range_not_recorded(self):
        """测试多日范围不记录"""
        interface_config = {"parameters": {}}
        params = {"start_date": "20260101", "end_date": "20260107"}  # 7天范围
        
        self.tracker.record_empty("test", params, interface_config)
        
        # 多日范围不应记录
        assert not self.tracker.is_empty_queried("test", params, interface_config)
    
    def test_clear(self):
        """测试清除记录"""
        interface_config = {"parameters": {"ann_date": {"is_date_anchor": True}}}
        params = {"ann_date": "20260112"}
        
        self.tracker.record_empty("test", params, interface_config)
        assert self.tracker.is_empty_queried("test", params, interface_config)
        
        self.tracker.clear("test")
        assert not self.tracker.is_empty_queried("test", params, interface_config)
```

---

## 九、实施步骤

### 阶段 1：核心模块
1. 创建 `app4/core/empty_query_tracker.py`
2. 添加配置到 `app4/config/settings.yaml`

### 阶段 2：集成
3. 修改 `app4/core/coverage_manager.py`
   - `detect_gaps()` 合并空查询日期
   - `_check_period_existence()` 检查空查询记录
4. 修改 `app4/core/downloader.py`
   - 初始化 `EmptyQueryTracker`
   - `_make_request()` 记录空查询
   - `close()` 刷新待写入

### 阶段 3：CLI 和测试
5. 修改 `app4/main.py` 添加 CLI 命令
6. 编写单元测试
7. 集成测试

---

## 十、风险评估

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| 多日范围不记录 | 低 | 实际 `window_size_days` 通常为 1 |
| 文件损坏 | 低 | 内存缓存 + 批量写入 |
| 并发写入冲突 | 中 | 使用线程锁 |
| 过期检查失败 | 低 | try-catch 包裹，失败时返回 False |
