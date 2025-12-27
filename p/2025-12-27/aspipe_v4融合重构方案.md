# aspipe_v4 融合重构方案

## 一、项目现状分析

### 1.1 代码结构概览

```
aspipe_v4/app/
├── main.py                          # 主入口（437行）
├── enhanced_main_downloader.py      # 增强版下载器
├── score_based_downloader.py        # 积分管理下载器
├── config.py                        # 基础配置（token、积分）
├── config_adapter.py                # 配置适配器
├── download_config.py               # 简单布尔开关配置
├── enhanced_download_config.py      # 详细配置（优先级、重试、限流）
├── score_config.py                  # 积分配置
│
├── tushare_api.py                   # TuShare主下载器（Facade模式）
├── download_scheduler.py            # 下载调度器
├── date_range_downloader.py         # 日期范围下载器（遗留）
├── task_queue_manager.py            # 任务队列管理
├── storage_worker.py                # 存储工作线程
├── global_rate_limiter.py           # 全局限流器
├── parallel_downloader.py           # 并行下载器
│
├── download_strategies.py           # 下载策略
├── strategy_factory.py              # 策略工厂
│
├── interfaces/                      # 12个接口模块
│   ├── base.py
│   ├── basic_data.py
│   ├── daily_data.py
│   ├── financial_data.py
│   ├── market_flow.py
│   ├── holders_data.py
│   ├── holders_data_downloader.py
│   ├── technical_factors.py
│   ├── cyq_chips.py
│   ├── market_structure.py
│   └── research_data.py
│
├── cache_manager.py                 # 缓存管理
├── cache_key_generator.py           # 缓存键生成
├── cache_monitor.py                 # 缓存监控
├── stock_list_manager.py            # 股票列表管理器
├── error_handler.py                 # 错误处理
├── parameter_adapters.py            # 参数适配器
└── utils/                           # 工具函数
```

### 1.2 main.py参数功能清单（必须保留）

| 参数 | 功能 | 关联代码 | 优先级 |
|------|------|----------|--------|
| `--start_date` | 起始日期 | download_all_data_from_date | **必须保留** |
| `--end_date` | 结束日期 | download_all_data_from_date | **必须保留** |
| `--use_legacy` | 传统下载方式 | download_with_legacy_method | **必须保留** |
| `--holders-data` | 股东数据下载 | holders_data、stk_rewards、top10_holders | **必须保留** |
| `--pro-bar-only` | 仅pro_bar下载 | pro_bar接口 | **必须保留** |
| `--tscode-historical` | 全历史数据下载 | DownloadScheduler(tscode_historical模式) | **必须保留** |

### 1.3 现有问题汇总

#### 问题1：配置系统碎片化

**现状**：存在4套独立配置
- `config.py`：基础配置（token、积分、代理）
- `download_config.py`：简单布尔开关
- `enhanced_download_config.py`：详细配置（优先级、重试、限流）
- `config_adapter.py`：配置适配层

**影响**：
- 配置分散，维护困难
- 容易出现不一致
- 新开发者难以理解

#### 问题2：入口点过多

**现状**：3个独立入口
- `main.py`：主入口
- `enhanced_main_downloader.py`：功能重复
- `score_based_downloader.py`：功能重复

**影响**：
- 代码重复
- 功能重叠
- CLI调用混乱

#### 问题3：Facade模式过度使用

**现状**：`TuShareDownloader`使用`__getattr__`动态委托到12个接口模块

```python
class TuShareDownloader:
    def __getattr__(self, name):
        # 动态委托到各接口模块
        # basic_data、daily_data、financial_data等
```

**影响**：
- IDE无法追踪方法调用
- 类型推断困难
- 调试复杂
- 类型检查工具失效

#### 问题4：策略模式混乱

**现状**：两套策略系统
- `download_strategies.py`：下载策略实现
- `strategy_factory.py`：策略工厂

**依赖链**：
```
DownloadScheduler
  → download_strategies.get_strategy
    → strategy_factory.get_strategy
```

#### 问题5：遗留系统维护

**现状**：
- `date_range_downloader.py`：传统下载方式
- `download_with_legacy_method`：遗留函数
- `download_with_legacy_fallback`：回退逻辑

#### 问题6：缓存系统过度设计

**现状**：3个缓存组件
- `cache_manager.py`：缓存管理
- `cache_key_generator.py`：缓存键生成
- `cache_monitor.py`：缓存监控

**问题**：功能重叠、配置复杂

#### 问题7：多层适配器嵌套

**现状**：`parameter_adapters.py`包含多个适配器
- DailyDataParameterAdapter
- FinancialDataParameterAdapter
- ...

**问题**：增加调用开销，维护复杂

## 二、融合重构目标

### 2.1 总体目标

1. **配置统一化**：合并为单一配置源，采用显式依赖注入
2. **入口单一化**：统一CLI入口，保留所有功能
3. **架构清晰化**：简化Facade模式，采用接口隔离
4. **代码精简**：移除冗余代码，引入稳妥回退机制
5. **向后兼容**：确保现有工作流不受影响
6. **高内聚低耦合**：采用六边形架构，实现组件可替换

### 2.2 具体指标

| 指标 | 当前 | 目标 |
|------|------|------|
| 配置文件数量 | 4 | 1 |
| 入口点数量 | 3 | 1 |
| 主文件代码行数 | 437 | <300 |
| 缓存组件数量 | 3 | 1-2 |
| 策略组件数量 | 2 | 1 |
| 依赖注入 | 全局导入 | 构造函数注入 |

## 三、融合重构方案

### 3.1 第一阶段：配置统一化与依赖注入

#### 3.1.1 目标

合并4套配置为1套统一的配置系统，采用显式依赖注入

#### 3.1.2 方案设计

**新配置结构**：

```python
# config/unified_config.py

from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum
import os
import json
from dotenv import load_dotenv

class Priority(Enum):
    HIGH = 1
    MEDIUM = 2
    LOW = 3

@dataclass
class RateLimit:
    calls_per_minute: int = 100
    burst_size: int = 10

@dataclass
class InterfaceConfig:
    enabled: bool = True
    priority: Priority = Priority.MEDIUM
    max_retries: int = 3
    rate_limit: Optional[RateLimit] = None
    cache_ttl: int = 3600
    download_strategy: str = "default"
    adapter: str = "default"

@dataclass
class CacheConfig:
    enabled: bool = True
    dir: str = "cache"
    max_size_gb: float = 10.0
    default_ttl: int = 3600

@dataclass
class TaskQueueConfig:
    max_workers: int = 4
    max_queue_size: int = 1000
    priority_levels: int = 3

@dataclass
class TushareConfig:
    token: str
    points: int
    proxy_url: str = ""
    timeout: int = 30
    retries: int = 3

@dataclass
class AppConfig:
    """统一配置类"""
    tushare: TushareConfig
    interfaces: Dict[str, InterfaceConfig]
    cache: CacheConfig
    task_queue: TaskQueueConfig
    fallback_enabled: bool = True  # 核心稳妥开关

class ConfigLoader:
    """配置加载器 - 实现显式依赖注入"""

    @staticmethod
    def load_from_env() -> AppConfig:
        load_dotenv('/home/quan/testdata/aspipe_v4/.env')

        # 基础配置
        tushare_config = TushareConfig(
            token=os.getenv('tushare_token') or os.getenv('tushare2_token'),
            points=int(os.getenv('tushare_points', '120')),
            proxy_url=os.getenv('PROXY_URL', ''),
            timeout=int(os.getenv('TUSHARE_TIMEOUT', '30')),
            retries=int(os.getenv('TUSHARE_RETRIES', '3'))
        )

        # 接口配置
        interfaces = ConfigLoader._load_interface_configs()

        # 缓存配置
        cache_config = CacheConfig(
            enabled=True,
            dir='cache',
            max_size_gb=10.0,
            default_ttl=3600
        )

        # 任务队列配置
        task_queue_config = TaskQueueConfig(
            max_workers=4,
            max_queue_size=1000,
            priority_levels=3
        )

        return AppConfig(
            tushare=tushare_config,
            interfaces=interfaces,
            cache=cache_config,
            task_queue=task_queue_config,
            fallback_enabled=os.getenv('FALLBACK_ENABLED', 'true').lower() == 'true'
        )

    @staticmethod
    def _load_interface_configs() -> Dict[str, InterfaceConfig]:
        # 加载接口配置，兼容新旧格式
        configs = {}

        # 默认配置
        default_configs = {
            'daily': InterfaceConfig(enabled=True, priority=Priority.HIGH),
            'daily_basic': InterfaceConfig(enabled=True, priority=Priority.HIGH),
            'moneyflow': InterfaceConfig(enabled=True, priority=Priority.MEDIUM),
            'stock_basic': InterfaceConfig(enabled=True, priority=Priority.HIGH),
            # ... 其他接口
        }

        return default_configs
```

#### 3.1.3 依赖注入容器

```python
# container.py

class Container:
    """依赖注入容器 - 管理单例和对象创建"""

    def __init__(self, config: AppConfig):
        self.config = config
        self.storage = ParquetStorage(config.cache.dir)
        self.tushare_client = TuShareClient(config.tushare)
        self.cache_manager = CacheManager(config.cache)
        self.legacy_bridge = LegacyBridge(config) if config.fallback_enabled else None
        self.download_manager = DownloadManager(
            strategy_factory=StrategyFactory(config),
            legacy_bridge=self.legacy_bridge,
            cache_manager=self.cache_manager,
            logger=get_logger()
        )
```

### 3.2 第二阶段：入口整合与架构优化

#### 3.2.1 目标

合并3个入口为1个统一入口，采用六边形架构

#### 3.2.2 六边形架构设计

```
aspipe_v4/app/
├── __init__.py
├── main.py                     # [接口层] 唯一入口，负责组装组件
├── container.py                # [容器] 依赖注入容器
├── config/                     # [配置]
│   ├── __init__.py
│   ├── settings.py             # 定义强类型的配置类 (dataclass)
│   └── loader.py               # 负责从 env/yaml/cli 加载配置
├── domain/                     # [领域] 核心接口定义
│   ├── __init__.py
│   ├── interfaces.py           # 定义 IDataSource, IStorage, ILogger 等抽象基类
│   └── models.py               # 数据模型定义
├── infrastructure/             # [设施] 具体技术实现
│   ├── __init__.py
│   ├── tushare_api/            # TuShare 具体实现
│   │   ├── client.py           # 封装 tushare pro_api
│   │   └── rate_limiter.py     # 限流器实现
│   ├── storage/
│   │   └── parquet_storage.py  # Parquet 文件存储实现
│   └── logging/
│       └── logger.py           # 结构化日志实现
├── services/                   # [服务] 业务逻辑
│   ├── __init__.py
│   ├── download_manager.py     # 核心下载协调器
│   ├── strategies/             # 下载策略 (策略模式)
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── daily.py            # 日线下载策略
│   │   ├── financial.py        # 财务数据策略
│   │   └── static.py
│   └── legacy_bridge.py        # [稳妥关键] 封装旧版逻辑的适配器
└── legacy/                     # [旧代码] 从 app/ 迁移过来的核心旧代码快照 (隔离修改)
    ├── __init__.py
    └── original_impl.py        # 仅作备份和 Fallback 调用，不做新开发
```

#### 3.2.3 领域层接口定义

```python
# domain/interfaces.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import pandas as pd

class IDataSource(ABC):
    """数据源接口 - 实现接口隔离"""

    @abstractmethod
    def download(self, **kwargs) -> pd.DataFrame:
        pass

class IStorage(ABC):
    """存储接口 - 实现接口隔离"""

    @abstractmethod
    def save(self, data: pd.DataFrame, filename: str) -> bool:
        pass

class ILogger(ABC):
    """日志接口 - 实现接口隔离"""

    @abstractmethod
    def info(self, message: str):
        pass

    @abstractmethod
    def error(self, message: str):
        pass

    @abstractmethod
    def warning(self, message: str):
        pass
```

#### 3.2.4 韧性下载管理器

```python
# services/download_manager.py

class DownloadManager:
    """韧性下载管理器 - 实现稳妥回退机制"""

    def __init__(self, strategy_factory, legacy_bridge, cache_manager, logger):
        self.factory = strategy_factory
        self.legacy = legacy_bridge
        self.cache = cache_manager
        self.logger = logger

    def download(self, interface_name: str, **kwargs):
        try:
            # 1. 尝试使用新架构策略
            strategy = self.factory.get_strategy(interface_name)
            self.logger.info(f"Using Strategy: {strategy.__class__.__name__}")
            
            # 检查缓存
            cache_key = self.cache.generate_key(interface_name, **kwargs)
            cached_data = self.cache.get(cache_key)
            if cached_data is not None:
                self.logger.info(f"Cache hit for {interface_name}")
                return cached_data
            
            # 执行下载
            result = strategy.execute(**kwargs)
            
            # 缓存结果
            self.cache.set(cache_key, result)
            
            return result
        except Exception as e:
            self.logger.error(f"New strategy failed for {interface_name}: {e}")

            # 2. 稳妥机制：回退到旧系统
            if self.legacy:
                self.logger.warning(f"Falling back to Legacy implementation for {interface_name}")
                return self.legacy.download(interface_name, **kwargs)
            else:
                raise e # 如果禁用了回退，则直接报错
```

### 3.3 第三阶段：Facade模式重构与策略简化

#### 3.3.1 TuShare客户端重构

```python
# infrastructure/tushare_api/client.py

class TuShareClient:
    """TuShare客户端 - 移除动态代理，改为显式方法"""

    def __init__(self, config: TushareConfig):
        self.config = config
        self.pro = ts.pro_api(config.token)
        self.logger = get_logger()
        self.last_call_times = {}
        
        # 显式初始化各接口
        self.basic = BasicDataDownloader(self.pro)
        self.daily = DailyDataDownloader(self.pro)
        self.financial = FinancialDataDownloader(self.pro)
        # ... 其他接口

    def stock_basic(self, **kwargs) -> pd.DataFrame:
        """显式方法 - 不再使用__getattr__动态委托"""
        return self._call_with_retry(self.pro.stock_basic, **kwargs)

    def daily(self, **kwargs) -> pd.DataFrame:
        """显式方法 - 不再使用__getattr__动态委托"""
        return self._call_with_retry(self.pro.daily, **kwargs)

    def _call_with_retry(self, api_func, **kwargs):
        """带重试和限流的API调用"""
        # 实现重试和限流逻辑
        pass
```

#### 3.3.2 策略系统简化

```python
# services/strategies/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any
import pandas as pd

class IDownloadStrategy(ABC):
    """下载策略接口"""

    @abstractmethod
    def execute(self, **kwargs) -> pd.DataFrame:
        pass

class BaseStrategy(IDownloadStrategy):
    """基础策略实现"""

    def __init__(self, client, config):
        self.client = client
        self.config = config

    def execute(self, **kwargs) -> pd.DataFrame:
        # 基础执行逻辑
        pass
```

### 3.4 第四阶段：遗留桥接器与稳妥机制

#### 3.4.1 遗留桥接器

```python
# services/legacy_bridge.py

import subprocess
import sys
import os
from typing import Dict, Any

class LegacyBridge:
    """遗留桥接器 - 封装旧版逻辑的适配器"""

    def __init__(self, config):
        self.config = config
        self.old_app_path = "/home/quan/testdata/aspipe_v4/app"
        self.logger = get_logger()

    def download(self, interface: str, **kwargs):
        """通过subprocess调用旧系统"""
        try:
            # 构建命令行参数
            cmd = [
                sys.executable,
                f"{self.old_app_path}/main.py",
                # 根据接口和参数构建命令
            ]
            
            # 执行旧系统
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                self.logger.info(f"Legacy download succeeded for {interface}")
                return self._parse_legacy_result(result.stdout)
            else:
                self.logger.error(f"Legacy download failed for {interface}: {result.stderr}")
                raise Exception(f"Legacy download failed: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"Legacy download timed out for {interface}")
            raise
        except Exception as e:
            self.logger.error(f"Legacy download error for {interface}: {e}")
            raise

    def _parse_legacy_result(self, output: str):
        """解析旧系统输出"""
        # 实现结果解析逻辑
        pass
```

### 3.5 第五阶段：缓存系统简化

```python
# infrastructure/storage/cache_manager.py

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Optional
import time
import threading
import pandas as pd

class CacheManager:
    """缓存管理器（简化版）- 合并原有三个组件"""

    def __init__(self, config):
        self.config = config
        self.cache_dir = Path(config.dir)
        self.max_size = config.max_size_gb * 1024 * 1024 * 1024
        self.default_ttl = config.default_ttl
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        path = self._key_to_path(key)
        if not path.exists():
            return None

        # 检查是否过期
        if self._is_expired(path):
            self._remove(path)  # 清理过期文件
            return None

        # 读取数据
        return self._load(path)

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存"""
        ttl = ttl or self.default_ttl
        path = self._key_to_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        # 写入数据
        self._save(path, value, ttl)

        # 清理过期缓存
        self._cleanup()

    def generate_key(self, interface: str, **params) -> str:
        """生成缓存键 - 合并cache_key_generator功能"""
        # 标准化参数
        sorted_params = sorted(params.items())
        param_str = json.dumps(sorted_params, sort_keys=True)

        # 生成哈希
        key = f"{interface}_{hashlib.md5(param_str.encode()).hexdigest()}"
        return key

    def get_stats(self) -> dict:
        """获取缓存统计 - 合并cache_monitor功能"""
        with self._lock:
            total_size = 0
            file_count = 0
            expired_count = 0

            for path in self.cache_dir.rglob("*"):
                if path.is_file():
                    file_count += 1
                    size = path.stat().st_size
                    total_size += size
                    if self._is_expired(path):
                        expired_count += 1

            return {
                "total_size_mb": total_size / (1024 * 1024),
                "file_count": file_count,
                "expired_count": expired_count,
                "hit_rate": self._calculate_hit_rate()
            }

    def _key_to_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.parquet"

    def _is_expired(self, path: Path) -> bool:
        """检查是否过期"""
        if not path.exists():
            return True
            
        # 检查TTL
        mtime = path.stat().st_mtime
        return time.time() - mtime > self.default_ttl

    def _load(self, path: Path) -> Any:
        """加载缓存数据"""
        try:
            return pd.read_parquet(path)
        except Exception as e:
            self.logger.error(f"Failed to load cache {path}: {e}")
            return None

    def _save(self, path: Path, value: Any, ttl: int):
        """保存缓存数据"""
        try:
            if isinstance(value, pd.DataFrame):
                value.to_parquet(path)
            else:
                # 对于非DataFrame数据，使用pickle
                import pickle
                with open(path, 'wb') as f:
                    pickle.dump(value, f)
        except Exception as e:
            self.logger.error(f"Failed to save cache {path}: {e}")

    def _cleanup(self):
        """清理过期缓存"""
        # 实现清理逻辑
        pass

    def _calculate_hit_rate(self) -> float:
        """计算命中率"""
        return 0.0
```

## 四、详细实施计划

### 4.1 阶段一：配置统一化与依赖注入（第1-2周）

| 任务 | 负责人 | 工时 | 验收标准 |
|------|--------|------|----------|
| 创建config/目录结构 | - | 1天 | 目录结构完成 |
| 实现AppConfig类 | - | 2天 | 配置加载正常 |
| 实现ConfigLoader | - | 2天 | 支持多种配置源 |
| 实现Container | - | 2天 | 依赖注入正常 |
| 更新所有导入 | - | 2天 | 无导入错误 |

### 4.2 阶段二：架构重构（第3-5周）

| 任务 | 负责人 | 工时 | 验收标准 |
|------|--------|------|----------|
| 创建domain/目录结构 | - | 1天 | 接口定义完成 |
| 创建infrastructure/目录结构 | - | 1天 | 基础实现完成 |
| 创建services/目录结构 | - | 1天 | 服务类完成 |
| 实现TuShareClient | - | 3天 | 显式方法正常 |
| 实现DownloadManager | - | 3天 | 稳妥机制正常 |
| 实现LegacyBridge | - | 2天 | 回退功能正常 |

### 4.3 阶段三：策略与缓存（第6-7周）

| 任务 | 负责人 | 工时 | 验收标准 |
|------|--------|------|----------|
| 实现策略系统 | - | 3天 | 策略执行正常 |
| 实现缓存系统 | - | 2天 | 缓存功能正常 |
| 集成策略与缓存 | - | 2天 | 整体功能正常 |

### 4.4 阶段四：入口整合与测试（第8-9周）

| 任务 | 负责人 | 工时 | 验收标准 |
|------|--------|------|----------|
| 重构main.py | - | 2天 | 代码<300行 |
| 移除旧入口 | - | 1天 | 文件删除 |
| 测试所有参数 | - | 3天 | 参数功能正常 |
| 性能测试 | - | 2天 | 性能不下降 |

## 五、风险评估与稳妥机制

### 5.1 风险清单

| 风险 | 可能性 | 影响 | 应对措施 |
|------|--------|------|----------|
| 配置迁移导致数据丢失 | 低 | 高 | 备份旧配置，逐步迁移 |
| CLI参数不兼容 | 中 | 高 | 保留所有参数，添加废弃警告 |
| 性能下降 | 中 | 中 | 性能测试，基准对比 |
| 测试覆盖不足 | 高 | 中 | 增加集成测试 |
| 回滚困难 | 中 | 高 | 保留版本标签，可快速回滚 |

### 5.2 稳妥机制

1. **回退开关**：通过`fallback_enabled`配置控制是否启用回退机制
2. **渐进式迁移**：先实现新架构，保留旧逻辑作为回退
3. **监控日志**：记录所有回退操作，便于分析和优化

## 六、验证方案

### 6.1 测试类型

| 测试类型 | 覆盖范围 | 工具 |
|----------|----------|------|
| 单元测试 | 核心函数 | pytest |
| 集成测试 | CLI参数 | pytest + subprocess |
| 性能测试 | 下载速度 | timeit |
| 回归测试 | 现有功能 | pytest |

### 6.2 验证用例

```python
# tests/test_fused_refactor.py

import pytest
from main import main
import subprocess

class TestCLIParameters:
    """CLI参数测试"""

    def test_start_date(self):
        """测试start_date参数"""
        result = subprocess.run([
            'python', 'main.py',
            '--start_date', '20240101',
            '--dry_run', 'true'
        ], capture_output=True, text=True)
        assert result.returncode == 0

    def test_end_date(self):
        """测试end_date参数"""
        result = subprocess.run([
            'python', 'main.py',
            '--start_date', '20240101',
            '--end_date', '20240131'
        ], capture_output=True, text=True)
        assert result.returncode == 0

    def test_holders_data(self):
        """测试holders_data参数"""
        result = subprocess.run([
            'python', 'main.py',
            '--holders-data'
        ], capture_output=True, text=True)
        assert result.returncode == 0

    def test_tscode_historical(self):
        """测试tscode_historical参数"""
        result = subprocess.run([
            'python', 'main.py',
            '--tscode-historical'
        ], capture_output=True, text=True)
        assert result.returncode == 0


class TestConfigMigration:
    """配置迁移测试"""

    def test_old_config_compatibility(self):
        """测试旧配置兼容"""
        from config.loader import ConfigLoader
        config = ConfigLoader.load_from_env()
        assert config.tushare.token is not None

    def test_new_config_loading(self):
        """测试新配置加载"""
        from config.loader import ConfigLoader
        config = ConfigLoader.load_from_env()
        assert config.interfaces is not None
```

### 6.3 验收标准

1. **功能验收**：
   - 所有CLI参数正常工作
   - 下载功能正常
   - 缓存功能正常
   - 回退机制正常

2. **性能验收**：
   - 下载速度不降低（基准测试）
   - 内存使用不增加（基准测试）

3. **代码质量验收**：
   - 配置文件从4个减少到1个
   - 入口从3个减少到1个
   - 主文件代码行数<300行
   - 依赖注入实现

## 七、时间线

```
Week 1-2: 配置统一化与依赖注入
  ├── Day 1: 创建config/目录结构
  ├── Day 2-3: 实现AppConfig类
  ├── Day 4-5: 实现ConfigLoader
  ├── Day 6-7: 实现Container
  └── Day 8-10: 更新导入和测试

Week 3-5: 架构重构
  ├── Day 11-12: 创建domain/目录结构
  ├── Day 13-14: 创建infrastructure/目录结构
  ├── Day 15-16: 创建services/目录结构
  ├── Day 17-19: 实现TuShareClient
  ├── Day 20-21: 实现DownloadManager
  └── Day 22-23: 实现LegacyBridge

Week 6-7: 策略与缓存
  ├── Day 24-26: 实现策略系统
  ├── Day 27-28: 实现缓存系统
  └── Day 29-30: 集成策略与缓存

Week 8-9: 入口整合与测试
  ├── Day 31-32: 重构main.py
  ├── Day 33: 移除旧入口
  ├── Day 34-36: 测试所有参数
  └── Day 37-39: 性能测试和文档
```

**总工时**：39个工作日

## 八、保留与移除清单

### 8.1 保留功能清单

| 功能 | 关联文件 | 状态 |
|------|----------|------|
| CLI参数 | main.py | 保留 |
| 日期范围下载 | download_scheduler.py | 保留（重构） |
| 全历史下载 | download_scheduler.py (tscode_historical模式) | 保留（重构） |
| 股东数据下载 | holders_data.py | 保留（重构） |
| pro_bar下载 | daily_data.py (pro_bar) | 保留（重构） |
| 缓存功能 | cache_manager.py | 保留（简化） |
| 限流功能 | global_rate_limiter.py | 保留（重构） |
| 错误处理 | error_handler.py | 保留（重构） |
| 依赖注入 | container.py | 新增 |
| 接口隔离 | domain/interfaces.py | 新增 |
| 稳妥回退 | services/legacy_bridge.py | 新增 |

### 8.2 移除功能清单

| 功能 | 关联文件 | 移除原因 |
|------|----------|----------|
| enhanced_main_downloader.py | 独立入口 | 功能重复main.py |
| score_based_downloader.py | 独立入口 | 功能重复main.py |
| date_range_downloader.py | 遗留下载器 | 被download_scheduler替代 |
| download_with_legacy_method | 遗留函数 | 被download_scheduler替代 |
| download_with_legacy_fallback | 遗留函数 | 被download_scheduler替代 |
| cache_key_generator.py | 缓存组件 | 功能合并到cache_manager |
| cache_monitor.py | 缓存组件 | 功能合并到cache_manager |
| config_adapter.py | 配置适配器 | 功能合并到统一配置 |
| download_config.py | 配置文件 | 功能合并到统一配置 |
| enhanced_download_config.py | 配置文件 | 功能合并到统一配置 |
| parameter_adapters.py | 参数适配器 | 功能简化 |

## 九、总结

本融合重构方案结合了两个方案的优点：

1. **统一配置与依赖注入**：采用显式依赖注入，避免全局变量
2. **六边形架构**：实现高内聚低耦合的架构
3. **稳妥演进**：保留回退机制，确保系统稳定性
4. **接口隔离**：定义清晰的抽象基类，使组件可替换
5. **代码精简**：移除冗余代码，保留核心功能

通过此方案，我们能够在保持所有现有功能的前提下，实现代码架构的现代化和可维护性提升。