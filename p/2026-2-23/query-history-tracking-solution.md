# 查询历史记录方案 - 解决"已查询但返回0条记录"的重复请求问题

> **版本说明**：本文档已根据代码评审意见修订，主要改进包括：
> - 修复 `date_range` 日期展开缺陷
> - 添加 TTL 过期检查机制
> - 优化为批量写入模式
> - 添加功能开关配置

## 问题分析

### 现象
- 第一次下载：请求全部 30 个交易日，其中 18 天有数据返回，12 天返回 0 条记录
- 第二次运行：`detect_gaps()` 只检查"已有数据的日期"，12 天被误判为"缺口"，重新请求

### 根本原因
`coverage_manager.py` 的 `detect_gaps()` 方法：
```python
existing_dates = self._get_existing_dates_cached(interface_name)
missing_dates = expected_dates - existing_dates
```

`existing_dates` 只包含有数据的日期，**不包含"已查询但返回0条"的日期**。

### 影响范围

| 分页模式 | 场景描述 | 问题表现 |
|---------|---------|---------|
| `reverse_date_range` 普通模式 | 按日期窗口请求 | 空窗口被重复请求 |
| `is_date_anchor` 模式 | 按单个日期锚定值请求（如 `ann_date=20260112`） | 空日期被重复请求 |
| `stock_loop` 模式 | 按股票+日期组合请求 | 某股票某日无数据被重复请求 |
| `period_range` 模式 | 按报告期请求（如 `period=20260331`） | 空报告期被重复请求 |

---

## 解决方案

### 核心思路
引入**查询历史记录（Query History）**机制，记录所有已执行过的查询参数，无论是否有数据返回。

### 设计原则
1. **轻量级**：不改变现有数据存储结构
2. **通用性**：支持所有分页模式
3. **可维护**：易于清理、查询、调试
4. **最小侵入**：尽量复用现有代码
5. **过期检查**：支持 TTL，处理数据补发场景
6. **批量写入**：优化 I/O 性能

---

## 方案详细设计

### 1. 数据结构

#### 查询记录文件位置
```
data/{interface_name}/.query_history.json
```

#### 记录格式
```json
{
  "interface_name": "dividend",
  "records": {
    "date:20260112": {
      "query_type": "date",
      "date_value": "20260112",
      "queried_at": "2026-02-25T16:13:35",
      "result_count": 0
    },
    "anchor:ann_date:20260112": {
      "query_type": "anchor",
      "anchor_param": "ann_date",
      "anchor_value": "20260112",
      "queried_at": "2026-02-25T16:13:35",
      "result_count": 0
    },
    "period:end_date:20260331": {
      "query_type": "period",
      "period_field": "end_date",
      "period_value": "20260331",
      "queried_at": "2026-02-25T16:13:00",
      "result_count": 150
    },
    "stock_date:000001.SZ:20260112": {
      "query_type": "stock_date",
      "ts_code": "000001.SZ",
      "date_value": "20260112",
      "queried_at": "2026-02-25T16:13:35",
      "result_count": 0
    },
    "stock_period:000001.SZ:20260331": {
      "query_type": "stock_period",
      "ts_code": "000001.SZ",
      "period_value": "20260331",
      "queried_at": "2026-02-25T16:13:00",
      "result_count": 4
    },
    "date_range:20260101:20260107": {
      "query_type": "date_range",
      "start_date": "20260101",
      "end_date": "20260107",
      "queried_at": "2026-02-25T16:13:00",
      "result_count": 0
    }
  },
  "last_updated": "2026-02-25T16:13:48"
}
```

### 2. 查询键（Query Key）生成规则

| 场景 | 查询键格式 | 示例 |
|-----|-----------|------|
| 日期范围查询（单日） | `date:{date}` | `date:20260112` |
| 日期范围查询（多日窗口） | `date_range:{start}:{end}` | `date_range:20260101:20260107` |
| 日期锚点查询 | `anchor:{param}:{value}` | `anchor:ann_date:20260112` |
| 报告期查询 | `period:{field}:{value}` | `period:end_date:20260331` |
| 股票+日期 | `stock_date:{ts_code}:{date}` | `stock_date:000001.SZ:20260112` |
| 股票+报告期 | `stock_period:{ts_code}:{period}` | `stock_period:000001.SZ:20260331` |

### 3. 新增模块：QueryHistoryManager

```python
# app4/core/query_history.py

import json
import os
import logging
from datetime import datetime, timedelta  # 【修复】添加 timedelta 导入
from typing import Dict, Any, Optional, Set
from pathlib import Path
import threading

logger = logging.getLogger(__name__)


class QueryHistoryManager:
    """
    查询历史管理器 - 记录已执行的查询，避免重复请求
    
    支持的查询类型：
    - date: 单日期查询
    - date_range: 日期范围查询
    - anchor: 日期锚点查询（is_date_anchor）
    - period: 报告期查询
    - stock_date: 股票+日期组合
    - stock_period: 股票+报告期组合
    
    特性：
    - TTL 过期检查：超过 ttl_days 的记录会被重新查询
    - 批量写入：减少 I/O 次数，提升性能
    - 线程安全：使用 RLock 保护并发访问
    """
    
    def __init__(
        self, 
        data_dir: str = "data",
        ttl_days: int = 30,        # 【新增】过期天数
        batch_size: int = 100,     # 【新增】批量写入阈值
        enabled: bool = True       # 【新增】功能开关
    ):
        """
        初始化查询历史管理器
        
        Args:
            data_dir: 数据存储目录
            ttl_days: 记录有效期（天），超过此天数的记录会被重新查询
            batch_size: 批量写入阈值，达到此数量才写入文件
            enabled: 是否启用功能
        """
        self.data_dir = Path(data_dir)
        self.ttl_days = ttl_days
        self.batch_size = batch_size
        self.enabled = enabled
        
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._pending: Dict[str, Set[str]] = {}  # 【新增】待写入缓冲
        self._dirty: Dict[str, bool] = {}        # 【新增】脏标记
        self._lock = threading.RLock()
    
    def _get_history_file(self, interface_name: str) -> Path:
        """获取接口的查询历史文件路径"""
        return self.data_dir / interface_name / ".query_history.json"
    
    def _load_history(self, interface_name: str) -> Dict[str, Any]:
        """加载查询历史"""
        with self._lock:
            if interface_name in self._cache:
                return self._cache[interface_name]
            
            history_file = self._get_history_file(interface_name)
            if history_file.exists():
                try:
                    with open(history_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self._cache[interface_name] = data
                        return data
                except Exception as e:
                    logger.warning(f"Failed to load query history for {interface_name}: {e}")
            
            # 创建新的空记录
            data = {
                "interface_name": interface_name,
                "records": {},
                "last_updated": None
            }
            self._cache[interface_name] = data
            return data
    
    def _save_history(self, interface_name: str, data: Dict[str, Any]) -> None:
        """保存查询历史"""
        with self._lock:
            history_file = self._get_history_file(interface_name)
            history_file.parent.mkdir(parents=True, exist_ok=True)
            
            data["last_updated"] = datetime.now().isoformat()
            
            try:
                with open(history_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"Failed to save query history for {interface_name}: {e}")
    
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
        # 检查是否是日期锚点接口
        param_defs = interface_config.get("parameters", {})
        date_anchor_param = None
        for param_name, param_def in param_defs.items():
            if param_def.get("is_date_anchor", False) and param_name in params:
                date_anchor_param = param_name
                break
        
        # 日期锚点模式
        if date_anchor_param:
            anchor_value = params.get(date_anchor_param)
            if anchor_value:
                return f"anchor:{date_anchor_param}:{anchor_value}"
        
        # 股票+日期/报告期模式
        ts_code = params.get("ts_code")
        period_field = params.get("_period_field", "period")
        period_value = params.get(period_field) or params.get("period")
        
        if ts_code:
            # 检查是报告期还是日期
            if period_value and len(period_value) == 8 and period_value.endswith(("0331", "0630", "0930", "1231")):
                return f"stock_period:{ts_code}:{period_value}"
            elif period_value:
                return f"stock_period:{ts_code}:{period_value}"
            else:
                # 尝试从 start_date/end_date 获取日期
                start_date = params.get("start_date")
                end_date = params.get("end_date")
                if start_date and end_date and start_date == end_date:
                    return f"stock_date:{ts_code}:{start_date}"
        
        # 报告期模式（无股票维度）
        if period_value and not ts_code:
            return f"period:{period_field}:{period_value}"
        
        # 日期范围模式
        start_date = params.get("start_date")
        end_date = params.get("end_date")
        
        if start_date and end_date:
            # 检查是否有时间窗口信息
            time_window = params.get("_time_window")
            if time_window:
                window_start, window_end = time_window
                return f"date_range:{window_start}:{window_end}"
            elif start_date == end_date:
                return f"date:{start_date}"
            else:
                # 大范围查询，不记录（可能导致误判）
                return None
        
        return None
    
    def record_query(
        self,
        interface_name: str,
        params: Dict[str, Any],
        interface_config: Dict[str, Any],
        result_count: int = 0
    ) -> None:
        """
        记录一次查询（批量写入优化版）
        
        Args:
            interface_name: 接口名称
            params: 请求参数
            interface_config: 接口配置
            result_count: 返回记录数
        """
        if not self.enabled:
            return
        
        query_key = self.generate_query_key(params, interface_config)
        if not query_key:
            return
        
        with self._lock:
            data = self._load_history(interface_name)
            
            record = {
                "query_key": query_key,
                "queried_at": datetime.now().isoformat(),
                "result_count": result_count
            }
            
            # 解析查询类型和值
            parts = query_key.split(":")
            record["query_type"] = parts[0]
            
            if record["query_type"] == "anchor":
                record["anchor_param"] = parts[1]
                record["anchor_value"] = parts[2]
            elif record["query_type"] == "period":
                record["period_field"] = parts[1]
                record["period_value"] = parts[2]
            elif record["query_type"] == "date":
                record["date_value"] = parts[1]
            elif record["query_type"] == "date_range":
                record["start_date"] = parts[1]
                record["end_date"] = parts[2]
            elif record["query_type"] == "stock_date":
                record["ts_code"] = parts[1]
                record["date_value"] = parts[2]
            elif record["query_type"] == "stock_period":
                record["ts_code"] = parts[1]
                record["period_value"] = parts[2]
            
            # 更新内存缓存
            data["records"][query_key] = record
            self._cache[interface_name] = data
            self._dirty[interface_name] = True
            
            # 【优化】添加到待写入缓冲
            if interface_name not in self._pending:
                self._pending[interface_name] = set()
            self._pending[interface_name].add(query_key)
            
            # 【优化】达到阈值时才写入文件
            if len(self._pending[interface_name]) >= self.batch_size:
                self._save_history(interface_name, data)
                self._pending[interface_name].clear()
                self._dirty[interface_name] = False
        
        logger.debug(f"Recorded query for {interface_name}: {query_key} (count={result_count})")
    
    def has_queried(
        self,
        interface_name: str,
        params: Dict[str, Any],
        interface_config: Dict[str, Any]
    ) -> bool:
        """
        检查是否已查询过（未过期）
        
        Args:
            interface_name: 接口名称
            params: 请求参数
            interface_config: 接口配置
            
        Returns:
            True 表示已查询且未过期，应跳过
            False 表示未查询或已过期，应重新查询
        """
        if not self.enabled:
            return False
        
        query_key = self.generate_query_key(params, interface_config)
        if not query_key:
            return False
        
        with self._lock:
            data = self._load_history(interface_name)
            record = data.get("records", {}).get(query_key)
            
            if not record:
                return False
            
            # 【新增】检查是否过期
            queried_at = record.get("queried_at")
            if queried_at:
                try:
                    queried_time = datetime.fromisoformat(queried_at)
                    age_days = (datetime.now() - queried_time).days
                    
                    if age_days > self.ttl_days:
                        logger.info(
                            f"Query record expired ({age_days} > {self.ttl_days} days), "
                            f"will recheck: {query_key}"
                        )
                        # 删除过期记录
                        del data["records"][query_key]
                        self._save_history(interface_name, data)
                        return False
                except Exception as e:
                    logger.warning(f"Failed to parse queried_at: {e}")
            
            return True
    
    def get_queried_dates(self, interface_name: str) -> Set[str]:
        """
        获取已查询过的日期集合（排除过期记录）
        
        【修复】date_range 现在会正确展开所有日期
        
        Args:
            interface_name: 接口名称
            
        Returns:
            已查询的日期集合（YYYYMMDD 格式）
        """
        if not self.enabled:
            return set()
        
        with self._lock:
            data = self._load_history(interface_name)
            dates = set()
            cutoff = datetime.now() - timedelta(days=self.ttl_days)
            
            for key, record in data.get("records", {}).items():
                # 【新增】检查是否过期
                queried_at = record.get("queried_at")
                if queried_at:
                    try:
                        queried_time = datetime.fromisoformat(queried_at)
                        if queried_time < cutoff:
                            continue  # 跳过过期记录
                    except Exception:
                        pass
                
                # 解析日期
                parts = key.split(":")
                query_type = parts[0]
                
                if query_type == "date":
                    dates.add(parts[1])
                elif query_type == "anchor":
                    dates.add(parts[2])
                elif query_type == "stock_date":
                    dates.add(parts[2])
                elif query_type == "date_range":
                    # 【修复】展开日期范围内的所有日期
                    start, end = parts[1], parts[2]
                    start_dt = datetime.strptime(start, "%Y%m%d")
                    end_dt = datetime.strptime(end, "%Y%m%d")
                    current = start_dt
                    while current <= end_dt:
                        dates.add(current.strftime("%Y%m%d"))
                        current += timedelta(days=1)
            
            return dates
    
    def get_queried_periods(
        self, 
        interface_name: str, 
        period_field: str = "period"
    ) -> Set[str]:
        """
        获取已查询过的报告期集合（排除过期记录）
        
        Args:
            interface_name: 接口名称
            period_field: 报告期字段名
            
        Returns:
            已查询的报告期集合
        """
        if not self.enabled:
            return set()
        
        with self._lock:
            data = self._load_history(interface_name)
            periods = set()
            cutoff = datetime.now() - timedelta(days=self.ttl_days)
            
            for key, record in data.get("records", {}).items():
                # 检查是否过期
                queried_at = record.get("queried_at")
                if queried_at:
                    try:
                        queried_time = datetime.fromisoformat(queried_at)
                        if queried_time < cutoff:
                            continue
                    except Exception:
                        pass
                
                parts = key.split(":")
                query_type = parts[0]
                
                if query_type == "period" and parts[1] == period_field:
                    periods.add(parts[2])
                elif query_type == "stock_period":
                    periods.add(parts[2])
            
            return periods
    
    def flush(self, interface_name: str = None):
        """
        【新增】强制刷新待写入数据到文件
        
        应在程序退出前调用，确保所有数据持久化
        
        Args:
            interface_name: 指定接口名称，None 则刷新所有
        """
        with self._lock:
            interfaces = [interface_name] if interface_name else list(self._dirty.keys())
            for iface in interfaces:
                if self._dirty.get(iface) and iface in self._cache:
                    self._save_history(iface, self._cache[iface])
                    self._dirty[iface] = False
                    if iface in self._pending:
                        self._pending[iface].clear()
                    logger.debug(f"Flushed query history for {iface}")
    
    def clear_history(self, interface_name: str) -> None:
        """清除接口的查询历史"""
        with self._lock:
            history_file = self._get_history_file(interface_name)
            if history_file.exists():
                history_file.unlink()
            self._cache.pop(interface_name, None)
            self._pending.pop(interface_name, None)
            self._dirty.pop(interface_name, None)
    
    def prune_old_records(self, interface_name: str = None, days: int = None) -> int:
        """
        清理过期的查询记录
        
        Args:
            interface_name: 接口名称，None 则清理所有接口
            days: 保留天数，None 则使用 ttl_days
            
        Returns:
            清理的记录数
        """
        if days is None:
            days = self.ttl_days
        
        cutoff = datetime.now() - timedelta(days=days)
        total_pruned = 0
        
        with self._lock:
            interfaces = [interface_name] if interface_name else list(self._cache.keys())
            
            for iface in interfaces:
                if iface not in self._cache:
                    continue
                
                data = self._load_history(iface)
                original_count = len(data.get("records", {}))
                
                data["records"] = {
                    k: v for k, v in data.get("records", {}).items()
                    if datetime.fromisoformat(v.get("queried_at", "2000-01-01")) >= cutoff
                }
                
                pruned = original_count - len(data["records"])
                if pruned > 0:
                    self._save_history(iface, data)
                    total_pruned += pruned
                    logger.info(f"Pruned {pruned} old query records for {iface}")
        
        return total_pruned
```

### 4. 集成点修改

#### 4.1 CoverageManager 集成

```python
# app4/core/coverage_manager.py

class CoverageManager:
    def __init__(
        self,
        storage_manager: StorageManager,
        config_loader: ConfigLoader,
        downloader=None,
        cache_size: int = 128,
        query_history_manager: Optional[QueryHistoryManager] = None,
    ):
        # ... 现有初始化 ...
        self.query_history_manager = query_history_manager
    
    def detect_gaps(
        self,
        interface_name: str,
        target_range: DateRange,
        trade_calendar: List[Dict[str, Any]],
        min_gap_days: int = 1,
        max_gaps: int = 50,
    ) -> List[DateRange]:
        """检测缺失的日期段 - 增强版"""
        logger.info(f"检测缺口: {interface_name} ({target_range})")
        
        # 1. 获取已有数据的日期
        existing_dates = self._get_existing_dates_cached(interface_name)
        logger.info(f"已有数据: {len(existing_dates)} 天")
        
        # 2. 【修改】获取已查询过但无数据的日期（带 enabled 检查）
        queried_dates = set()
        if self.query_history_manager and self.query_history_manager.enabled:
            queried_dates = self.query_history_manager.get_queried_dates(interface_name)
            logger.info(f"已查询（含空结果）: {len(queried_dates)} 天")
        
        # 3. 合并：已有数据日期 + 已查询日期
        covered_dates = existing_dates | queried_dates
        
        # 4. 计算期望日期集合（只包含交易日）
        expected_dates = set()
        for day in trade_calendar:
            cal_date = day.get("cal_date")
            is_open = day.get("is_open", 0)
            if cal_date and is_open == 1:
                if target_range.start_date <= cal_date <= target_range.end_date:
                    expected_dates.add(cal_date)
        
        logger.info(f"期望交易日: {len(expected_dates)} 天")
        
        # 5. 快速路径检查
        if covered_dates >= expected_dates:
            logger.info("数据已完整覆盖（含空查询记录），无需下载")
            return []
        
        # 6. 找出缺失日期
        missing_dates = expected_dates - covered_dates
        # ... 后续逻辑不变 ...
```

#### 4.2 PaginationExecutor 集成

```python
# app4/core/pagination_executor.py

class PaginationExecutor:
    def __init__(
        self, 
        max_workers: int = 4,
        query_history_manager: Optional[QueryHistoryManager] = None
    ):
        self.max_workers = max_workers
        self.query_history_manager = query_history_manager
    
    def _execute_single_request(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any],
        make_request: Callable,
    ) -> List[Dict[str, Any]]:
        """执行单个请求 - 增强版"""
        # ... 现有 offset 分页逻辑 ...
        
        clean_params = {k: v for k, v in params.items() if not k.startswith("_")}
        data = make_request(interface_config, clean_params)
        
        # 【修改】记录查询历史（带 enabled 检查）
        if self.query_history_manager and self.query_history_manager.enabled:
            interface_name = interface_config.get("name", "")
            self.query_history_manager.record_query(
                interface_name,
                clean_params,
                interface_config,
                result_count=len(data) if data else 0
            )
        
        return data
```

#### 4.3 Downloader 初始化修改

```python
# app4/core/downloader.py

from .query_history import QueryHistoryManager

class Downloader:
    def __init__(self, ...):
        # ... 现有初始化 ...
        
        # 【修改】从配置读取参数
        query_history_config = self.global_config.get("query_history", {})
        self.query_history_manager = QueryHistoryManager(
            data_dir=self.global_config.get("storage", {}).get("base_dir", "data"),
            ttl_days=query_history_config.get("ttl_days", 30),
            batch_size=query_history_config.get("batch_size", 100),
            enabled=query_history_config.get("enabled", True)
        )
        
        # 注入到 coverage_manager 和 pagination_executor
        if self.coverage_manager:
            self.coverage_manager.query_history_manager = self.query_history_manager
        if self.pagination_executor:
            self.pagination_executor.query_history_manager = self.query_history_manager
    
    def close(self):
        """关闭时刷新待写入记录"""
        # ... 现有关闭逻辑 ...
        
        # 【新增】刷新查询历史
        if self.query_history_manager:
            self.query_history_manager.flush()
```

---

## 配置选项

```yaml
# app4/config/settings.yaml

query_history:
  enabled: true                    # 是否启用查询历史记录
  ttl_days: 30                     # 记录有效期（天），超过则重新查询
  batch_size: 100                  # 批量写入阈值
  auto_prune: true                 # 程序启动时自动清理过期记录
  max_records_per_interface: 10000 # 每个接口最大记录数（可选）
```

---

## 性能对比

### 批量写入优化效果

假设典型场景：
- 5000 只股票
- 每只股票 100 个交易日
- 每个交易日 1 次请求

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 写文件次数 | 500,000 | 5,000 | **100倍** |
| I/O 总耗时 | 42 分钟 | 25 秒 | **100倍** |
| 内存占用 | 低 | 略高（缓冲区） | 可接受 |

---

## 清理策略

### 自动清理
- 每次程序启动时检查并清理过期记录
- 超过 `max_records_per_interface` 时清理最旧记录

### 手动清理
```python
# 清除特定接口的查询历史
query_history_manager.clear_history("dividend")

# 清理 90 天前的记录
query_history_manager.prune_old_records("dividend", days=90)
```

### CLI 支持
```bash
# 清除指定接口的查询历史
python app4/main.py --clear-query-history --interface dividend

# 清理过期记录
python app4/main.py --prune-query-history --days 90
```

---

## 实施步骤

### 阶段 1: 核心模块（预计改动 3 个文件）
1. 新建 `app4/core/query_history.py`
2. 修改 `app4/core/coverage_manager.py` - 集成查询历史
3. 修改 `app4/core/pagination_executor.py` - 记录查询

### 阶段 2: 初始化集成（预计改动 2 个文件）
4. 修改 `app4/core/downloader.py` - 初始化并注入
5. 修改 `app4/main.py` - 添加 CLI 支持

### 阶段 3: 测试验证
6. 编写单元测试
7. 进行集成测试

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| 文件损坏导致记录丢失 | 低 | 内存缓存 + 定期保存 |
| 记录文件过大 | 低 | 自动清理 + 记录数限制 |
| 并发写入冲突 | 中 | 使用线程锁 |
| 查询键生成错误 | 中 | 充分的单元测试 |
| 数据补发后无法获取 | 低 | TTL 过期检查机制 |

---

## 回滚方案

如果出现问题，可以通过以下方式快速回滚：
1. 设置 `query_history.enabled: false` 禁用功能
2. 删除 `data/{interface}/.query_history.json` 文件
3. 功能禁用后系统恢复到原有行为