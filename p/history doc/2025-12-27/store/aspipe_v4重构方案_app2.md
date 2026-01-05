# aspipe_v4 重构方案 (app2 独立重写版)

## 一、核心原则

根据最新要求，本项目将在 `app2` 目录下进行**完全独立的代码重写**。不依赖 `app` 目录下的旧代码，不进行渐进式迁移，不保留非必要的抽象和向后兼容层。

**核心原则：**
1.  **零依赖 (Greenfield):** `app2` 是一个全新的起点。
2.  **无包袱 (No Legacy):** 不实现 `ConfigAdapter`，不实现 `LegacyBridge`，不兼容旧配置格式。
3.  **直接实现 (Direct Implementation):** 优先使用显式、具体的代码，拒绝过度设计（Over-engineering）。
4.  **现代架构 (Modern Architecture):** 直接采用六边形架构 + 依赖注入。

## 二、目录结构 (app2/)

```
app2/
├── __init__.py
├── main.py                     # 唯一入口
├── container.py                # 依赖注入容器 (Wiring)
├── config/                     # 配置模块
│   ├── __init__.py
│   ├── settings.py             # AppConfig 数据类定义
│   └── loader.py               # 负责从环境变量加载配置
├── domain/                     # 领域层 (接口定义)
│   ├── __init__.py
│   └── interfaces.py           # IDataSource, IStorage, ILogger
├── infrastructure/             # 基础设施层 (具体实现)
│   ├── __init__.py
│   ├── tushare_api/            # TuShare 客户端
│   │   ├── client.py           # 显式定义的 Client
│   │   └── rate_limiter.py     # 限流器
│   ├── storage/                # 存储实现
│   │   └── parquet_storage.py  # Parquet 存储
│   └── logging/
│       └── logger.py
├── services/                   # 应用服务层
│   ├── __init__.py
│   ├── download_manager.py     # 下载协调器
│   └── strategies/             # 下载策略
│       ├── __init__.py
│       ├── base.py
│       ├── daily.py
│       ├── financial.py
│       └── static.py
└── utils/                      # 通用工具
    └── date_utils.py
```

## 三、关键组件设计

### 3.1 统一配置 (Configuration)

摒弃旧的四套配置，直接使用单一、强类型的配置对象。

```python
# app2/config/settings.py
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class TushareConfig:
    token: str
    points: int = 2000
    proxy_url: Optional[str] = None

@dataclass
class StorageConfig:
    data_dir: str = "data"
    cache_dir: str = "cache"

@dataclass
class AppConfig:
    tushare: TushareConfig
    storage: StorageConfig
    # 接口特定的简单配置，如是否启用
    interfaces: Dict[str, bool] 
```

### 3.2 TuShare 客户端 (Infrastructure)

完全移除 `__getattr__` 动态代理，所有方法必须显式定义。这提供了最佳的代码提示和可维护性。

```python
# app2/infrastructure/tushare_api/client.py
import tushare as ts

class TuShareClient:
    def __init__(self, token: str):
        self.pro = ts.pro_api(token)

    def daily(self, **kwargs):
        return self.pro.daily(**kwargs)

    def daily_basic(self, **kwargs):
        return self.pro.daily_basic(**kwargs)
        
    def income(self, **kwargs):
        return self.pro.income(**kwargs)
        
    # ... 显式列出所有需要的接口 ...
```

### 3.3 策略模式 (Services)

移除复杂的 `StrategyFactory` 和参数适配器，使用简单的策略注册表。

```python
# app2/services/strategies/base.py
class BaseStrategy(ABC):
    def __init__(self, client: TuShareClient, storage: IStorage):
        self.client = client
        self.storage = storage

    @abstractmethod
    def download(self, **kwargs):
        pass

# app2/services/download_manager.py
class DownloadManager:
    def __init__(self, strategies: Dict[str, BaseStrategy]):
        self.strategies = strategies

    def run(self, interface_name: str, **kwargs):
        strategy = self.strategies.get(interface_name)
        if not strategy:
            raise ValueError(f"No strategy found for {interface_name}")
        
        data = strategy.download(**kwargs)
        # 存储逻辑直接由 Strategy 或 Manager 显式处理，不再隐含
```

### 3.4 缓存与存储 (Storage)

合并原有的 `cache_manager`, `cache_key_generator`, `storage_worker`。
在 `app2` 中，缓存和持久化存储可以统一视为 `IStorage` 的不同实现，或者由 `DownloadManager` 统一控制 "先查缓存，再下载，最后存盘" 的流程。

## 四、实施计划 (快速通道)

由于不需要考虑兼容性和迁移，进度可以大幅加快。

### 阶段 1: 骨架搭建 (1-2天)
1. 创建 `app2` 目录结构。
2. 实现 `config/settings.py` 和 `config/loader.py`。
3. 实现 `container.py` (简单的依赖组装)。
4. 实现 `main.py` (CLI 参数解析)。

### 阶段 2: 核心基础设施 (2-3天)
1. 实现 `infrastructure/tushare_api/client.py` (显式定义所有 API 方法)。
2. 实现 `infrastructure/storage/parquet_storage.py` (读写 Parquet)。
3. 实现基础的 `infrastructure/logging`。

### 阶段 3: 业务逻辑与策略 (3-4天)
1. 实现 `services/strategies/` 下的核心策略 (Daily, Financial, Static)。
2. 实现 `services/download_manager.py`。
3. 将策略注册到 Container 中。

### 阶段 4: 集成与验证 (2天)
1. 运行 `main.py` 测试关键流程 (如下载日线数据)。
2. 验证数据落地格式。

**预计总工期：** 约 8-10 个工作日 (大幅短于原计划的 39 天)。

## 五、与原调整建议的对比 (Explicit Over Implicit)

| 特性 | 原调整建议 (app) | 本方案 (app2) | 原因 |
| :--- | :--- | :--- | :--- |
| **配置** | `ConfigAdapter` 兼容新旧 | `AppConfig` 仅支持新格式 | 无需兼容旧代码 |
| **API 调用** | `__getattr__` 兜底 | 全显式方法 | 更好的 IDE 支持和调试 |
| **回退机制** | `LegacyBridge` (Subprocess) | **无** | 相信新代码质量，失败即报错 |
| **策略工厂** | 复杂的动态注册/缓存 | 简单的字典/Map | 减少过度抽象 |
| **缓存键** | 复杂的 Key 生成器 | 简单确定的规则 | 简单即美 |

## 六、总结

在 `app2` 进行重写是最高效的路径。我们完全丢弃了历史包袱，能够直接采用最佳实践。所有的组件都将是**显式**且**类型安全**的。这不仅加快了开发速度，也为未来的维护打下了坚实基础。