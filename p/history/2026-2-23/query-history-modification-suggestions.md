# 查询历史记录方案 - 修改建议清单

## 文档说明

本文档针对 `query-history-tracking-solution.md` 方案提出修改建议，每个建议都包含：
- 问题位置
- 原代码分析
- 问题描述与原因
- 实际影响
- 修复方案

---

## 一、必须修复的问题

### 问题 1：`date_range` 日期展开缺陷

#### 问题位置
`QueryHistoryManager.get_queried_dates()` 方法，原方案第 364-369 行

#### 原代码
```python
elif query_type == "date_range":
    # 日期范围，需要展开
    start, end = parts[1], parts[2]
    # 简单处理：只记录起始和结束
    dates.add(start)
    dates.add(end)
```

#### 为什么有问题
当查询键为 `date_range:20260101:20260107` 时，代码只返回起始日期 `20260101` 和结束日期 `20260107`，中间的 5 天（`20260102` 到 `20260106`）被完全遗漏。

这是一个**功能性错误**，不是性能问题或边缘情况。

#### 实际影响场景

**场景描述**：
1. 用户请求 2026-01-01 到 2026-01-07 共 7 天的数据
2. API 返回 0 条记录（可能这些日期确实没有数据）
3. `QueryHistoryManager` 记录查询键：`date_range:20260101:20260107`
4. 用户第二次运行程序
5. `detect_gaps()` 调用 `get_queried_dates()` 获取已查询日期
6. `get_queried_dates()` 只返回 `{'20260101', '20260107'}`
7. 系统判断 `20260102` 到 `20260106` 为"缺口"
8. **重新请求这 5 天的数据** → 无效重复请求

**数据对比**：

| 日期 | 是否已查询 | `get_queried_dates()` 返回 | 系统判断 |
|------|-----------|---------------------------|----------|
| 20260101 | ✅ 是 | ✅ 包含 | 已覆盖 |
| 20260102 | ✅ 是 | ❌ 遗漏 | **误判为缺口** |
| 20260103 | ✅ 是 | ❌ 遗漏 | **误判为缺口** |
| 20260104 | ✅ 是 | ❌ 遗漏 | **误判为缺口** |
| 20260105 | ✅ 是 | ❌ 遗漏 | **误判为缺口** |
| 20260106 | ✅ 是 | ❌ 遗漏 | **误判为缺口** |
| 20260107 | ✅ 是 | ✅ 包含 | 已覆盖 |

#### 修复方案
```python
elif query_type == "date_range":
    from datetime import timedelta
    start, end = parts[1], parts[2]
    # 展开日期范围内的所有日期
    start_dt = datetime.strptime(start, "%Y%m%d")
    end_dt = datetime.strptime(end, "%Y%m%d")
    current = start_dt
    while current <= end_dt:
        dates.add(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
```

#### 修复后效果
| 日期 | 是否已查询 | `get_queried_dates()` 返回 | 系统判断 |
|------|-----------|---------------------------|----------|
| 20260101 | ✅ 是 | ✅ 包含 | 已覆盖 |
| 20260102 | ✅ 是 | ✅ 包含 | 已覆盖 |
| 20260103 | ✅ 是 | ✅ 包含 | 已覆盖 |
| 20260104 | ✅ 是 | ✅ 包含 | 已覆盖 |
| 20260105 | ✅ 是 | ✅ 包含 | 已覆盖 |
| 20260106 | ✅ 是 | ✅ 包含 | 已覆盖 |
| 20260107 | ✅ 是 | ✅ 包含 | 已覆盖 |

---

## 二、强烈建议添加的功能

### 问题 2：缺少过期检查机制

#### 问题位置
`QueryHistoryManager.has_queried()` 方法，整个方法缺少过期检查逻辑

#### 原代码行为
```python
def has_queried(self, interface_name: str, params, interface_config) -> bool:
    query_key = self.generate_query_key(params, interface_config)
    if not query_key:
        return False
    
    data = self._load_history(interface_name)
    return query_key in data.get("records", {})  # 只检查是否存在
```

#### 为什么有问题
当前设计假设：**一旦记录了查询历史，该日期就永远不需要再查询**。

这个假设在以下场景中不成立：

| 场景 | 描述 | 问题 |
|------|------|------|
| **数据补发** | 公司可能在数日后补发公告，原本空的日期现在有数据了 | 用户无法获取新数据 |
| **数据更正** | API 可能更正历史数据 | 用户获取的是旧数据 |
| **API 更新** | 数据源可能更新历史记录 | 用户错过更新 |
| **用户强制刷新** | 用户希望重新检查某些日期 | 无法实现 |

#### 实际影响案例

**案例：分红数据补发**

```
Day 1 (2026-02-01):
- 用户下载 dividend 接口，ann_date=20260115
- API 返回 0 条记录
- QueryHistoryManager 记录: {"anchor:ann_date:20260115": {"queried_at": "2026-02-01T10:00:00", "result_count": 0}}

Day 30 (2026-03-03):
- 公司补发了 ann_date=20260115 的分红公告
- 用户再次运行程序
- has_queried() 返回 True（因为记录存在）
- 系统跳过该日期
- 用户永远无法获取这条新数据
```

#### 为什么需要过期检查

过期检查机制的核心思想是：**空查询记录有"保质期"，超过一定时间后需要重新验证**。

这与缓存系统的 TTL（Time To Live）概念一致：
- 有效期内的记录：信任查询结果，跳过重复请求
- 过期的记录：重新查询，获取最新数据

#### 修复方案

**步骤 1：添加配置项**

```yaml
# app4/config/settings.yaml
query_history:
  enabled: true
  ttl_days: 30  # 空查询记录有效期（天），超过则重新检查
  batch_size: 100
```

**步骤 2：修改 `__init__` 方法**

```python
def __init__(
    self, 
    data_dir: str = "data", 
    ttl_days: int = 30,
    batch_size: int = 100,
    enabled: bool = True
):
    self.data_dir = Path(data_dir)
    self.ttl_days = ttl_days      # 新增：过期天数
    self.batch_size = batch_size  # 新增：批量写入阈值
    self.enabled = enabled        # 新增：功能开关
    self._cache: Dict[str, Dict[str, Any]] = {}
    self._lock = threading.RLock()
```

**步骤 3：修改 `has_queried()` 方法**

```python
def has_queried(
    self,
    interface_name: str,
    params: Dict[str, Any],
    interface_config: Dict[str, Any]
) -> bool:
    """检查是否已查询过（未过期）"""
    if not self.enabled:
        return False
    
    query_key = self.generate_query_key(params, interface_config)
    if not query_key:
        return False
    
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
                return False  # 需要重新查询
        except Exception as e:
            logger.warning(f"Failed to parse queried_at: {e}")
    
    return True
```

**步骤 4：修改 `get_queried_dates()` 方法**

```python
def get_queried_dates(self, interface_name: str) -> Set[str]:
    """获取已查询过的日期集合（排除过期记录）"""
    if not self.enabled:
        return set()
    
    from datetime import timedelta
    data = self._load_history(interface_name)
    dates = set()
    cutoff = datetime.now() - timedelta(days=self.ttl_days)
    
    for key, record in data.get("records", {}).items():
        # 检查是否过期
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
        elif query_type == "date_range":
            # 展开日期范围
            start, end = parts[1], parts[2]
            start_dt = datetime.strptime(start, "%Y%m%d")
            end_dt = datetime.strptime(end, "%Y%m%d")
            current = start_dt
            while current <= end_dt:
                dates.add(current.strftime("%Y%m%d"))
                current += timedelta(days=1)
    
    return dates
```

---

## 三、性能优化建议

### 问题 3：每次请求都写文件

#### 问题位置
`QueryHistoryManager.record_query()` 方法，原方案第 314-315 行

#### 原代码
```python
def record_query(self, interface_name: str, params, interface_config, result_count: int = 0):
    # ... 构建 record ...
    
    data["records"][query_key] = record
    self._save_history(interface_name, data)  # 每次都写文件
    
    logger.debug(f"Recorded query for {interface_name}: {query_key}")
```

#### 为什么有问题
每次 API 请求完成后，都会触发一次文件写入操作：
1. 序列化整个 `data` 对象为 JSON
2. 打开文件
3. 写入磁盘
4. 关闭文件

**性能测算**：

假设典型场景：
- 5000 只股票
- 每只股票 100 个交易日
- 每个交易日 1 次请求

计算：
- 总请求数：5000 × 100 = 500,000 次
- 每次文件写入耗时：约 5ms（保守估计）
- 总 I/O 耗时：500,000 × 5ms = 2,500 秒 ≈ **42 分钟**

**并发场景问题**：
- 多线程同时写入同一文件
- 文件锁竞争
- 潜在的数据损坏风险

#### 修复方案：批量写入 + 内存缓存

```python
class QueryHistoryManager:
    def __init__(
        self, 
        data_dir: str = "data",
        ttl_days: int = 30,
        batch_size: int = 100,
        enabled: bool = True
    ):
        self.data_dir = Path(data_dir)
        self.ttl_days = ttl_days
        self.batch_size = batch_size
        self.enabled = enabled
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._pending: Dict[str, Set[str]] = {}  # 新增：待写入缓冲
        self._dirty: Dict[str, bool] = {}        # 新增：脏标记
        self._lock = threading.RLock()
    
    def record_query(
        self,
        interface_name: str,
        params: Dict[str, Any],
        interface_config: Dict[str, Any],
        result_count: int = 0
    ) -> None:
        """记录一次查询（批量写入优化版）"""
        if not self.enabled:
            return
        
        query_key = self.generate_query_key(params, interface_config)
        if not query_key:
            return
        
        with self._lock:
            data = self._load_history(interface_name)
            
            # 构建记录
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
            
            # 添加到待写入缓冲
            if interface_name not in self._pending:
                self._pending[interface_name] = set()
            self._pending[interface_name].add(query_key)
            
            # 达到阈值时才写入文件
            if len(self._pending[interface_name]) >= self.batch_size:
                self._save_history(interface_name, data)
                self._pending[interface_name].clear()
                self._dirty[interface_name] = False
        
        logger.debug(f"Recorded query for {interface_name}: {query_key} (count={result_count})")
    
    def flush(self, interface_name: str = None):
        """
        强制刷新待写入数据到文件
        
        应在程序退出前调用，确保所有数据持久化
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
```

#### 优化效果对比

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 写文件次数 | 500,000 | 5,000 | **100倍** |
| I/O 总耗时 | 42 分钟 | 25 秒 | **100倍** |
| 内存占用 | 低 | 略高（缓冲区） | 可接受 |

---

### 问题 4：缺少功能开关检查

#### 问题位置
`CoverageManager.detect_gaps()` 集成代码

#### 原代码
```python
if self.query_history_manager:
    queried_dates = self.query_history_manager.get_queried_dates(interface_name)
```

#### 为什么有问题
- 只检查 `query_history_manager` 是否存在
- 没有检查 `enabled` 配置
- 用户无法通过配置禁用功能

#### 修复方案

```python
# CoverageManager.detect_gaps()
if self.query_history_manager and self.query_history_manager.enabled:
    queried_dates = self.query_history_manager.get_queried_dates(interface_name)
    logger.info(f"已查询（含空结果）: {len(queried_dates)} 天")
```

---

## 四、其他问题修复

### 问题 5：缺少 `timedelta` 导入

#### 问题位置
文件开头导入区域

#### 原代码
```python
from datetime import datetime
```

#### 为什么有问题
`prune_old_records()` 方法使用了 `timedelta`：
```python
cutoff = datetime.now() - timedelta(days=days)  # NameError: timedelta is not defined
```

#### 修复方案
```python
from datetime import datetime, timedelta
```

---

## 五、修改优先级总结

| 优先级 | 问题 | 类型 | 影响 | 修复难度 |
|--------|------|------|------|----------|
| **P0** | date_range 展开缺陷 | 功能错误 | 中间日期被遗漏，导致重复请求 | 低 |
| **P1** | 过期检查机制 | 功能缺失 | 无法获取更新数据 | 中 |
| **P2** | 批量写入优化 | 性能问题 | I/O 瓶颈，42分钟 → 25秒 | 中 |
| **P2** | 配置开关检查 | 可配置性 | 无法禁用功能 | 低 |
| **P3** | 缺少 timedelta 导入 | 运行时错误 | 程序崩溃 | 极低 |

---

## 六、完整修改后的代码

### `app4/core/query_history.py`（完整版）

```python
# app4/core/query_history.py

import json
import os
import logging
from datetime import datetime, timedelta
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
        ttl_days: int = 30,
        batch_size: int = 100,
        enabled: bool = True
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
        self._pending: Dict[str, Set[str]] = {}  # 待写入缓冲
        self._dirty: Dict[str, bool] = {}        # 脏标记
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
        记录一次查询
        
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
            
            # 添加到待写入缓冲
            if interface_name not in self._pending:
                self._pending[interface_name] = set()
            self._pending[interface_name].add(query_key)
            
            # 达到阈值时才写入文件
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
            
            # 检查是否过期
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
                # 检查是否过期
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
                elif query_type == "date_range":
                    # 展开日期范围内的所有日期
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
        强制刷新待写入数据到文件
        
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

---

## 七、配置文件修改

### `app4/config/settings.yaml`

```yaml
# 在文件末尾添加

query_history:
  enabled: true                    # 是否启用查询历史记录
  ttl_days: 30                     # 记录有效期（天），超过则重新查询
  batch_size: 100                  # 批量写入阈值
  auto_prune: true                 # 程序启动时自动清理过期记录
  max_records_per_interface: 10000 # 每个接口最大记录数（可选）
```

---

## 八、集成修改

### `app4/core/coverage_manager.py`

```python
# 在 detect_gaps() 方法中修改

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
    
    # ... 后续逻辑不变 ...
```

### `app4/core/downloader.py`

```python
# 在 __init__ 方法中修改

from .query_history import QueryHistoryManager

class GenericDownloader:
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
        
        # 注入到 coverage_manager
        if self.coverage_manager:
            self.coverage_manager.query_history_manager = self.query_history_manager
```

---

## 九、测试用例

### `test/test_query_history.py`

```python
import pytest
from datetime import datetime, timedelta
from app4.core.query_history import QueryHistoryManager
import tempfile
import os


class TestQueryHistoryManager:
    
    def setup_method(self):
        """每个测试方法前创建临时目录"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = QueryHistoryManager(
            data_dir=self.temp_dir,
            ttl_days=30,
            batch_size=10,
            enabled=True
        )
    
    def teardown_method(self):
        """每个测试方法后清理临时目录"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_date_range_expansion(self):
        """测试 date_range 日期展开"""
        interface_config = {"parameters": {}}
        
        # 记录一个日期范围查询
        self.manager.record_query(
            "test_interface",
            {"_time_window": ("20260101", "20260107"), "start_date": "20260101", "end_date": "20260107"},
            interface_config,
            result_count=0
        )
        
        # 获取已查询日期
        dates = self.manager.get_queried_dates("test_interface")
        
        # 验证所有日期都被包含
        expected_dates = {"20260101", "20260102", "20260103", "20260104", "20260105", "20260106", "20260107"}
        assert dates == expected_dates, f"Expected {expected_dates}, got {dates}"
    
    def test_ttl_expiration(self):
        """测试 TTL 过期检查"""
        interface_config = {"parameters": {"ann_date": {"is_date_anchor": True}}}
        params = {"ann_date": "20260115"}
        
        # 手动插入一个过期记录
        self.manager._load_history("test_interface")
        old_time = (datetime.now() - timedelta(days=31)).isoformat()
        self.manager._cache["test_interface"]["records"]["anchor:ann_date:20260115"] = {
            "queried_at": old_time,
            "result_count": 0
        }
        self.manager._save_history("test_interface", self.manager._cache["test_interface"])
        
        # 验证过期记录返回 False
        result = self.manager.has_queried("test_interface", params, interface_config)
        assert result is False, "Expired record should return False"
    
    def test_batch_write(self):
        """测试批量写入"""
        interface_config = {"parameters": {"ann_date": {"is_date_anchor": True}}}
        
        # 记录 batch_size - 1 次查询
        for i in range(9):
            self.manager.record_query(
                "test_interface",
                {"ann_date": f"2026010{i}"},
                interface_config,
                result_count=0
            )
        
        # 此时不应写入文件
        history_file = self.manager._get_history_file("test_interface")
        assert not history_file.exists(), "File should not be written before batch_size"
        
        # 再记录一次，达到阈值
        self.manager.record_query(
            "test_interface",
            {"ann_date": "20260110"},
            interface_config,
            result_count=0
        )
        
        # 此时应该写入文件
        assert history_file.exists(), "File should be written after batch_size reached"
    
    def test_enabled_flag(self):
        """测试功能开关"""
        # 禁用功能
        self.manager.enabled = False
        
        interface_config = {"parameters": {"ann_date": {"is_date_anchor": True}}}
        params = {"ann_date": "20260115"}
        
        # 记录查询（应该被忽略）
        self.manager.record_query("test_interface", params, interface_config, result_count=0)
        
        # 检查是否已查询（应该返回 False）
        result = self.manager.has_queried("test_interface", params, interface_config)
        assert result is False, "Disabled manager should always return False"
        
        # 获取已查询日期（应该返回空集）
        dates = self.manager.get_queried_dates("test_interface")
        assert dates == set(), "Disabled manager should return empty set"
    
    def test_flush(self):
        """测试强制刷新"""
        interface_config = {"parameters": {"ann_date": {"is_date_anchor": True}}}
        
        # 记录查询（不达到 batch_size）
        self.manager.record_query(
            "test_interface",
            {"ann_date": "20260115"},
            interface_config,
            result_count=0
        )
        
        # 此时文件不应存在
        history_file = self.manager._get_history_file("test_interface")
        assert not history_file.exists()
        
        # 强制刷新
        self.manager.flush("test_interface")
        
        # 此时文件应该存在
        assert history_file.exists()
```

---

## 十、实施检查清单

### 阶段 1：核心修复（必须）

- [ ] 修复 `date_range` 展开问题
- [ ] 添加 `timedelta` 导入
- [ ] 添加 TTL 过期检查
- [ ] 添加 `enabled` 参数和检查

### 阶段 2：性能优化（建议）

- [ ] 实现批量写入机制
- [ ] 添加 `flush()` 方法
- [ ] 在程序退出前调用 `flush()`

### 阶段 3：测试验证

- [ ] 编写单元测试
- [ ] 测试 date_range 展开正确性
- [ ] 测试 TTL 过期逻辑
- [ ] 测试批量写入性能
- [ ] 测试功能开关

### 阶段 4：文档更新

- [ ] 更新 API 文档
- [ ] 更新配置说明
- [ ] 添加使用示例

---

## 十一、总结

本文档列出了对原方案的 5 处修改建议，按优先级分类：

| 优先级 | 数量 | 内容 |
|--------|------|------|
| P0（必须） | 1 | date_range 展开缺陷 |
| P1（强烈建议） | 1 | 过期检查机制 |
| P2（建议优化） | 2 | 批量写入、配置开关 |
| P3（小问题） | 1 | timedelta 导入 |

每个修改都详细说明了：
- 为什么需要修改
- 不修改会有什么影响
- 如何修改
- 修改后的效果

建议按照优先级顺序实施，P0 问题必须修复，否则方案无法正常工作。
