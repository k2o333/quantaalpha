# App4 项目简化统一索引方案

## 1. 概述

本方案采用**极简设计**，通过**统一总索引文件 + YAML配置驱动**的方式管理所有接口的数据索引。核心原则：**任何数据下载都会更新总索引，基于总索引判断需要下载的记录**，避免复杂的分层检查和缓存逻辑。

## 2. 核心设计原则

### 2.1 极简性
- 单一索引：所有接口使用一个总索引文件
- 配置驱动：索引结构完全由YAML配置定义
- 直接决策：基于总索引直接判断下载需求

### 2.2 可靠性
- 原子更新：增量更新时保证总索引的原子性
- 一致性：索引与数据始终保持同步
- 可恢复：支持从所有parquet文件全量重建索引

### 2.3 高效性
- 一次判断：读取总索引后直接确定下载范围
- 增量更新：只更新新增的记录，不重复处理
- 零缓存：简化逻辑，避免缓存一致性问题

## 3. 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                    Downloader                            │
│  - 基于总索引判断下载需求                                   │
│  - 执行数据下载                                           │
│  - 调用 UnifiedIndexManager 更新索引                      │
└────────────────────┬────────────────────────────────────┘
                      │
                      ▼
          ┌──────────────────┐
          │ UnifiedIndexManager│
          │  - 总索引读写      │
          │  - 增量更新        │
          │  - 全量重建        │
          └──────────────────┘
                      ▲
                      │
          ┌──────────────────┐
          │  ConfigLoader    │
          │  - YAML配置解析   │
          │  - 索引字段定义    │
          └──────────────────┘
```

## 4. 总索引设计

### 4.1 总索引文件结构
```yaml
# 存储位置：../data/unified_index.parquet
# 文件结构：
{
  "interface_name": "daily",           # 接口名称
  "ts_code": "000001.SZ",              # 股票代码（如果适用）
  "trade_date": "20230101",            # 交易日期（或日期范围）
  "period": "202301",                   # 报告期（如果适用）
  "file_path": "../data/daily/daily_20230101_20230105_xxx.parquet",
  "update_time": 1704105600000,         # 更新时间戳
  "checksum": "abc123...",              # 数据校验和
  "record_count": 1000,                # 记录数量
  "file_size": 2048000                 # 文件大小
}
```

### 4.2 YAML配置定义索引结构
```yaml
# app4/config/interfaces/daily.yaml
name: daily
description: "日线行情"

# 索引配置
index:
  enabled: true
  primary_keys: ["ts_code", "trade_date"]  # 主键字段
  date_field: "trade_date"                  # 日期字段
  ts_field: "ts_code"                       # 股票代码字段（可选）
  period_field: null                        # 报告期字段（可选）

# 输出配置
output:
  primary_key: ["ts_code", "trade_date"]
  columns:
    ts_code: {type: string, required: true}
    trade_date: {type: date, format: "%Y%m%d", required: true}
    open: {type: float}
    high: {type: float}
    low: {type: float}
    close: {type: float}
    volume: {type: int}
```

## 5. 核心实现

### 5.1 UnifiedIndexManager - 统一索引管理器

```python
import os
import threading
import hashlib
import time
from typing import List, Dict, Any, Optional, Set
import polars as pl
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class UnifiedIndexManager:
    """统一索引管理器 - 负责总索引文件的读写和更新"""
    
    def __init__(self, storage_dir: str = "../data", config_loader=None):
        self.storage_dir = Path(storage_dir)
        self.config_loader = config_loader
        
        # 总索引文件路径
        self.index_path = self.storage_dir / "unified_index.parquet"
        
        # 线程安全锁
        self._lock = threading.RLock()
        
        # 确保存储目录存在
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def get_index_config(self, interface_name: str) -> Dict[str, Any]:
        """从YAML配置获取索引配置"""
        if not self.config_loader:
            return {}
        
        interface_config = self.config_loader.get_interface_config(interface_name)
        return interface_config.get('index', {})
    
    def load_index(self) -> pl.DataFrame:
        """加载总索引文件"""
        try:
            if self.index_path.exists():
                index_df = pl.read_parquet(self.index_path)
                logger.debug(f"Loaded unified index with {len(index_df)} records")
                return index_df
            else:
                # 创建空索引
                empty_index = pl.DataFrame(schema=self._get_index_schema())
                logger.info("Created new empty unified index")
                return empty_index
        except Exception as e:
            logger.error(f"Failed to load unified index: {e}")
            # 返回空索引
            return pl.DataFrame(schema=self._get_index_schema())
    
    def save_index(self, index_df: pl.DataFrame):
        """保存总索引文件（原子写入）"""
        try:
            with self._lock:
                # 临时文件
                temp_path = self.index_path.with_suffix('.tmp.parquet')
                
                # 写入临时文件
                index_df.write_parquet(temp_path, compression='snappy')
                
                # 原子重命名
                temp_path.rename(self.index_path)
                
                logger.info(f"Saved unified index with {len(index_df)} records")
        except Exception as e:
            logger.error(f"Failed to save unified index: {e}")
            if temp_path.exists():
                temp_path.unlink()
            raise
    
    def _get_index_schema(self) -> Dict[str, pl.DataType]:
        """获取索引文件的Schema"""
        return {
            "interface_name": pl.String,
            "ts_code": pl.String,
            "trade_date": pl.String,
            "period": pl.String,
            "file_path": pl.String,
            "update_time": pl.Int64,
            "checksum": pl.String,
            "record_count": pl.Int64,
            "file_size": pl.Int64
        }
    
    def add_records(self, interface_name: str, file_path: str, df: pl.DataFrame):
        """
        添加新记录到总索引
        
        Args:
            interface_name: 接口名称
            file_path: 数据文件路径
            df: 数据DataFrame
        """
        try:
            index_config = self.get_index_config(interface_name)
            primary_keys = index_config.get('primary_keys', ['trade_date'])
            date_field = index_config.get('date_field', 'trade_date')
            ts_field = index_config.get('ts_field', 'ts_code')
            period_field = index_config.get('period_field', 'period')
            
            if df.is_empty():
                return
            
            # 获取文件信息
            file_stat = os.path.getmtime(file_path) if os.path.exists(file_path) else time.time()
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            
            # 计算校验和
            checksum = hashlib.md5(df.head(10).to_string().encode()).hexdigest()
            
            # 生成索引记录
            index_records = []
            
            for row in df.iter_rows(named=True):
                record = {
                    "interface_name": interface_name,
                    "ts_code": row.get(ts_field, ""),
                    "trade_date": str(row.get(date_field, "")),
                    "period": str(row.get(period_field, "")) if period_field and period_field in row else "",
                    "file_path": str(file_path),
                    "update_time": int(file_stat * 1000),
                    "checksum": checksum,
                    "record_count": len(df),
                    "file_size": file_size
                }
                index_records.append(record)
            
            # 加载现有索引
            existing_index = self.load_index()
            
            # 移除相同接口和文件的旧记录
            existing_index = existing_index.filter(
                ~(pl.col("interface_name") == interface_name) & 
                ~(pl.col("file_path") == str(file_path))
            )
            
            # 添加新记录
            new_records_df = pl.DataFrame(index_records, schema=self._get_index_schema())
            updated_index = pl.concat([existing_index, new_records_df])
            
            # 保存更新后的索引
            self.save_index(updated_index)
            
            logger.info(f"Added {len(index_records)} records to unified index for {interface_name}")
            
        except Exception as e:
            logger.error(f"Failed to add records to unified index: {e}")
            raise
    
    def get_existing_records(self, interface_name: str, 
                           start_date: Optional[str] = None, 
                           end_date: Optional[str] = None,
                           ts_codes: Optional[List[str]] = None,
                           period: Optional[str] = None) -> Set[tuple]:
        """
        获取已存在的记录
        
        Returns:
            Set of tuples: 根据 primary_keys 组成的记录标识
        """
        try:
            index_df = self.load_index()
            
            # 过滤接口
            interface_df = index_df.filter(pl.col("interface_name") == interface_name)
            
            if interface_df.is_empty():
                return set()
            
            # 日期范围过滤
            if start_date:
                interface_df = interface_df.filter(pl.col("trade_date") >= start_date)
            if end_date:
                interface_df = interface_df.filter(pl.col("trade_date") <= end_date)
            
            # 股票代码过滤
            if ts_codes:
                interface_df = interface_df.filter(pl.col("ts_code").is_in(ts_codes))
            
            # 报告期过滤
            if period:
                interface_df = interface_df.filter(pl.col("period") == period)
            
            # 获取索引配置
            index_config = self.get_index_config(interface_name)
            primary_keys = index_config.get('primary_keys', ['trade_date'])
            
            # 生成记录标识
            existing_records = set()
            for row in interface_df.iter_rows(named=True):
                record_key = tuple(row.get(key, "") for key in primary_keys)
                existing_records.add(record_key)
            
            logger.debug(f"Found {len(existing_records)} existing records for {interface_name}")
            return existing_records
            
        except Exception as e:
            logger.error(f"Failed to get existing records: {e}")
            return set()
    
    def rebuild_from_data_files(self) -> Dict[str, Any]:
        """
        从所有数据文件重建总索引
        
        Returns:
            Dict: 重建结果统计
        """
        result = {
            'success': True,
            'total_interfaces': 0,
            'total_files': 0,
            'total_records': 0,
            'errors': []
        }
        
        try:
            logger.info("Starting full index rebuild from data files...")
            
            # 创建空的索引DataFrame
            all_records = []
            
            # 遍历所有接口目录
            for interface_dir in self.storage_dir.iterdir():
                if not interface_dir.is_dir() or interface_dir.name == '__pycache__':
                    continue
                
                interface_name = interface_dir.name
                index_config = self.get_index_config(interface_name)
                
                if not index_config.get('enabled', True):
                    continue
                
                logger.info(f"Rebuilding index for {interface_name}...")
                
                # 获取所有parquet文件
                parquet_files = list(interface_dir.glob("*.parquet"))
                
                if not parquet_files:
                    continue
                
                interface_records = 0
                
                for file_path in parquet_files:
                    try:
                        # 读取数据文件
                        df = pl.read_parquet(file_path)
                        
                        if df.is_empty():
                            continue
                        
                        # 添加到索引
                        self.add_records(interface_name, str(file_path), df)
                        interface_records += len(df)
                        result['total_files'] += 1
                        
                    except Exception as e:
                        error_msg = f"Failed to process {file_path}: {e}"
                        logger.error(error_msg)
                        result['errors'].append(error_msg)
                        continue
                
                if interface_records > 0:
                    result['total_interfaces'] += 1
                    result['total_records'] += interface_records
                    logger.info(f"Rebuilt {interface_name}: {interface_records} records from {len(parquet_files)} files")
            
            # 重新保存索引
            final_index = self.load_index()
            self.save_index(final_index)
            
            logger.info(f"Index rebuild completed: {result['total_interfaces']} interfaces, "
                       f"{result['total_files']} files, {result['total_records']} records")
            
        except Exception as e:
            logger.error(f"Failed to rebuild index: {e}")
            result['success'] = False
            result['errors'].append(str(e))
        
        return result
    
    def get_download_plan(self, interface_name: str, 
                         start_date: Optional[str] = None,
                         end_date: Optional[str] = None,
                         ts_codes: Optional[List[str]] = None,
                         period: Optional[str] = None) -> Dict[str, Any]:
        """
        获取下载计划，确定需要下载的记录
        
        Returns:
            Dict: 包含已存在记录和需要下载的记录信息
        """
        try:
            # 获取已存在的记录
            existing_records = self.get_existing_records(
                interface_name, start_date, end_date, ts_codes, period
            )
            
            # 获取索引配置
            index_config = self.get_index_config(interface_name)
            primary_keys = index_config.get('primary_keys', ['trade_date'])
            
            # 生成所有需要的记录标识
            needed_records = set()
            
            # 这里需要根据不同的分页模式生成记录
            # 简化示例：日期范围模式
            if start_date and end_date:
                from datetime import datetime, timedelta
                start_dt = datetime.strptime(start_date, '%Y%m%d')
                end_dt = datetime.strptime(end_date, '%Y%m%d')
                current_dt = start_dt
                
                while current_dt <= end_dt:
                    date_str = current_dt.strftime('%Y%m%d')
                    
                    if ts_codes:
                        for ts_code in ts_codes:
                            record_key = tuple(ts_code if key == 'ts_code' else date_str for key in primary_keys)
                            needed_records.add(record_key)
                    else:
                        record_key = tuple(date_str for key in primary_keys)
                        needed_records.add(record_key)
                    
                    current_dt += timedelta(days=1)
            
            # 计算需要下载的记录
            missing_records = needed_records - existing_records
            coverage_ratio = len(existing_records) / len(needed_records) if needed_records else 0
            
            return {
                'total_needed': len(needed_records),
                'existing_count': len(existing_records),
                'missing_count': len(missing_records),
                'coverage_ratio': coverage_ratio,
                'should_skip': len(missing_records) == 0,
                'existing_records': existing_records,
                'missing_records': missing_records
            }
            
        except Exception as e:
            logger.error(f"Failed to get download plan: {e}")
            return {
                'total_needed': 0,
                'existing_count': 0,
                'missing_count': 0,
                'coverage_ratio': 0,
                'should_skip': False,
                'existing_records': set(),
                'missing_records': set()
            }
```

### 5.2 SimplifiedDownloader - 简化的下载器

```python
import logging
from typing import List, Dict, Any, Optional
from .unified_index import UnifiedIndexManager

logger = logging.getLogger(__name__)

class SimplifiedDownloader:
    """简化的下载器 - 基于总索引的智能下载"""
    
    def __init__(self, config_loader=None, storage_manager=None):
        self.config_loader = config_loader
        self.storage_manager = storage_manager
        
        # 初始化统一索引管理器
        self.index_manager = UnifiedIndexManager(
            storage_dir=storage_manager.storage_dir,
            config_loader=config_loader
        )
    
    def should_download(self, interface_name: str, 
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None,
                       ts_codes: Optional[List[str]] = None,
                       period: Optional[str] = None) -> bool:
        """
        判断是否需要下载
        
        基于总索引直接判断，避免复杂的多层检查
        """
        try:
            # 获取下载计划
            plan = self.index_manager.get_download_plan(
                interface_name, start_date, end_date, ts_codes, period
            )
            
            if plan['should_skip']:
                logger.info(f"Skipping {interface_name}: {plan['existing_count']}/{plan['total_needed']} records already exist")
                return False
            
            coverage_ratio = plan['coverage_ratio']
            if coverage_ratio >= 0.95:  # 95%阈值
                logger.info(f"Skipping {interface_name}: {coverage_ratio:.1%} coverage, {plan['missing_count']} records missing")
                return False
            
            logger.info(f"Downloading {interface_name}: {plan['missing_count']} records needed, {coverage_ratio:.1%} already exists")
            return True
            
        except Exception as e:
            logger.error(f"Failed to determine download need for {interface_name}: {e}")
            return True  # 失败时默认下载
    
    def save_data_with_index(self, interface_name: str, data: List[Dict[str, Any]], file_path: str):
        """
        保存数据并更新索引
        
        确保任何数据下载都会更新总索引
        """
        try:
            # 1. 保存数据文件
            df = pl.DataFrame(data)
            df.write_parquet(file_path, compression='snappy')
            
            # 2. 更新总索引
            self.index_manager.add_records(interface_name, file_path, df)
            
            logger.info(f"Saved {len(data)} records for {interface_name} and updated unified index")
            
        except Exception as e:
            logger.error(f"Failed to save data with index: {e}")
            raise
```

## 6. 集成使用

### 6.1 在StorageManager中集成

```python
class StorageManager:
    def __init__(self, storage_dir: str = "../data", config_loader=None):
        self.storage_dir = storage_dir
        self.config_loader = config_loader
        
        # 初始化统一索引管理器
        self.index_manager = UnifiedIndexManager(storage_dir, config_loader)
    
    def save_data(self, interface_name: str, data: List[Dict[str, Any]], file_path: str):
        """保存数据并更新索引"""
        # 原有的数据保存逻辑
        df = pl.DataFrame(data)
        df.write_parquet(file_path, compression='snappy')
        
        # 更新统一索引
        self.index_manager.add_records(interface_name, file_path, df)
```

### 6.2 在Downloader中集成

```python
class GenericDownloader:
    def __init__(self, config_loader=None, storage_manager=None):
        self.config_loader = config_loader
        self.storage_manager = storage_manager
        self.index_manager = storage_manager.index_manager
    
    def download_interface(self, interface_name: str, **params):
        """下载接口数据"""
        # 1. 检查是否需要下载
        if not self.index_manager.should_download(interface_name, **params):
            return
        
        # 2. 下载数据
        data = self._fetch_data(interface_name, **params)
        
        # 3. 保存数据并更新索引
        file_path = self._generate_file_path(interface_name, **params)
        self.storage_manager.save_data(interface_name, data, file_path)
```

## 7. CLI命令

### 7.1 重建总索引

```python
def rebuild_unified_index(args):
    """重建统一总索引命令"""
    from app4.core.unified_index import UnifiedIndexManager
    from app4.core.config_loader import ConfigLoader
    
    config_loader = ConfigLoader()
    global_config = config_loader.get_global_config()
    storage_dir = global_config.get('storage', {}).get('base_dir', '../data')
    
    index_manager = UnifiedIndexManager(storage_dir, config_loader)
    
    print("Rebuilding unified index from all data files...")
    result = index_manager.rebuild_from_data_files()
    
    if result['success']:
        print(f"✓ Index rebuild successful")
        print(f"  - Total interfaces: {result['total_interfaces']}")
        print(f"  - Total files: {result['total_files']}")
        print(f"  - Total records: {result['total_records']}")
    else:
        print(f"✗ Index rebuild failed")
        for error in result['errors']:
            print(f"  - {error}")

### 7.2 检查覆盖率

```python
def check_coverage(args):
    """检查接口覆盖率命令"""
    from app4.core.unified_index import UnifiedIndexManager
    from app4.core.config_loader import ConfigLoader
    
    config_loader = ConfigLoader()
    global_config = config_loader.get_global_config()
    storage_dir = global_config.get('storage', {}).get('base_dir', '../data')
    
    index_manager = UnifiedIndexManager(storage_dir, config_loader)
    
    interface_name = args.interface
    start_date = args.start_date
    end_date = args.end_date
    
    plan = index_manager.get_download_plan(interface_name, start_date, end_date)
    
    print(f"Coverage analysis for {interface_name}:")
    print(f"  - Total needed: {plan['total_needed']} records")
    print(f"  - Existing: {plan['existing_count']} records")
    print(f"  - Missing: {plan['missing_count']} records")
    print(f"  - Coverage: {plan['coverage_ratio']:.1%}")
    print(f"  - Should skip: {plan['should_skip']}")
```

## 8. 使用示例

```bash
# 重建统一总索引
python app4/main.py rebuild-unified-index

# 检查接口覆盖率
python app4/main.py check-coverage --interface daily --start_date 20230101 --end_date 20230131

# 正常下载（会自动基于总索引判断）
python app4/main.py --interface daily --start_date 20230101 --end_date 20230131
```

## 9. 优势总结

1. **极简设计**：单一总索引文件，配置驱动，逻辑清晰
2. **高性能**：一次查询直接判断，避免多层检查和缓存
3. **高可靠**：原子更新，支持全量重建，数据一致性保证
4. **易维护**：YAML配置定义索引结构，代码与配置分离
5. **易扩展**：新增接口只需在YAML中定义索引配置

## 10. 实施计划

### 第一阶段：实现UnifiedIndexManager（1天）
- 实现总索引的读写操作
- 实现增量更新功能
- 实现全量重建功能

### 第二阶段：集成到现有组件（1天）
- 修改StorageManager集成索引更新
- 修改Downloader集成下载判断

### 第三阶段：测试和优化（1天）
- 功能测试和性能测试
- 边界情况处理

### 第四阶段：部署和监控（1天）
- 生产环境部署
- 添加监控和日志

这个简化方案避免了复杂的多层检查，通过单一总索引和YAML配置驱动，实现了高效、可靠的重复数据检测和智能下载功能。