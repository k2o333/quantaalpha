# Aspipe V4 重构方案 (App2) - 高内聚低耦合与稳妥演进版

## 一、 核心设计理念

本方案旨在 `/home/quan/testdata/aspipe_v4/app2` 构建一个全新的、生产级的数据下载系统。

### 1.1 核心原则
1.  **显式依赖 (Explicit Dependencies)**: 拒绝全局变量 (`from config import *`)。所有依赖（配置、数据库连接、API客户端）必须通过构造函数注入。
2.  **接口隔离 (Interface Segregation)**: 定义清晰的抽象基类 (ABC)，使得组件可替换、可测试。
3.  **防御性编程 (Defensive Programming)**: 假设网络会断、API会限流、数据会缺。
4.  **稳妥演进 (Safe Evolution)**: **不直接删除旧逻辑**。将旧逻辑封装为“遗留适配器 (Legacy Adapter)”，在新系统失败时作为兜底 (Fallback) 机制。

### 1.2 架构分层
系统采用 **六边形架构 (Hexagonal Architecture)** 的简化版：

*   **Domain (领域层)**: 定义核心实体 (如 `Stock`, `DailyBar`) 和接口 (`IDownloader`)。不依赖外部库。
*   **Application (应用层)**: 编排业务流程 (`DownloadService`, `Scheduler`)。
*   **Infrastructure (基础设施层)**: 具体实现 (`TuShareClient`, `ParquetStorage`, `FileConfigLoader`)。
*   **Interface (接口层)**: CLI 入口 (`main.py`)。

---

## 二、 详细目录结构 (App2)

```text
/home/quan/testdata/aspipe_v4/app2/
├── __init__.py
├── main.py                     # [入口] 唯一入口，负责组装组件 (Composition Root)
├── container.py                # [容器] 简单的依赖注入容器，管理单例和对象创建
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

---

## 三、 关键模块设计与“稳妥”机制

### 3.1 统一配置 (Unified Config)
不再散落在多个文件，使用单例配置对象。

```python
# app2/config/settings.py
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class TushareConfig:
    token: str
    timeout: int = 30
    retries: int = 3

@dataclass
class AppConfig:
    tushare: TushareConfig
    data_dir: str
    fallback_enabled: bool = True  # 核心稳妥开关
    # ...
```

### 3.2 依赖注入容器 (IoC Container)
在 `main.py` 启动时，`container.py` 负责把所有组件串联起来。

```python
# app2/container.py
class Container:
    def __init__(self, config: AppConfig):
        self.config = config
        self.storage = ParquetStorage(config.data_dir)
        self.tushare_client = TuShareClient(config.tushare)
        self.legacy_bridge = LegacyBridge(config) if config.fallback_enabled else None
```

### 3.3 韧性下载管理器 (Resilient Download Manager)
这是实现“稳妥”的核心。它尝试使用新策略，如果失败，则切回旧逻辑。

```python
# app2/services/download_manager.py
class DownloadManager:
    def __init__(self, strategy_factory, legacy_bridge, logger):
        self.factory = strategy_factory
        self.legacy = legacy_bridge
        self.logger = logger

    def download(self, interface_name: str, **kwargs):
        try:
            # 1. 尝试使用新架构策略
            strategy = self.factory.get_strategy(interface_name)
            self.logger.info(f"Using Strategy: {strategy.__class__.__name__}")
            return strategy.execute(**kwargs)
        except Exception as e:
            self.logger.error(f"New strategy failed for {interface_name}: {e}")
            
            # 2. 稳妥机制：回退到旧系统
            if self.legacy:
                self.logger.warning(f"Falling back to Legacy implementation for {interface_name}")
                return self.legacy.download(interface_name, **kwargs)
            else:
                raise e # 如果禁用了回退，则直接报错
```

### 3.4 遗留桥接器 (Legacy Bridge)
将 `/home/quan/testdata/aspipe_v4/app` 中的关键逻辑（或其副本）封装起来。

```python
# app2/services/legacy_bridge.py
import sys
import os

class LegacyBridge:
    def __init__(self, config):
        # 动态添加旧路径到 sys.path 以便通过 import 调用，或者使用 subprocess 调用
        self.old_app_path = "/home/quan/testdata/aspipe_v4/app"
    
    def download(self, interface: str, **kwargs):
        # 这里可以使用 subprocess 调用旧的 main.py 
        # 或者 import 旧的 downloader 类（需要小心路径污染）
        pass
```

---

## 四、 实施路线图 (Step-by-Step)

### Phase 1: 骨架搭建 (Skeleton)
1.  创建 `app2` 目录结构。
2.  实现 `Config` 和 `Container`。
3.  **验证点**: 运行 `python app2/main.py --help` 能打印出参数，且配置加载正确。

### Phase 2: 基础设施迁移 (Infrastructure)
1.  移植 `TuShareClient`: 重写 `TuShareDownloader`，移除动态代理，改为显式方法，并加入更清晰的限流逻辑。
2.  移植 `Storage`: 实现标准的 `ParquetStorage`。
3.  **验证点**: 编写单元测试，验证 `TuShareClient` 可以获取数据，`Storage` 可以写文件。

### Phase 3: 策略与调度 (Strategy & Scheduler)
1.  实现 `BaseStrategy`。
2.  实现 `DailyStrategy` (覆盖日线数据)。
3.  实现 `Scheduler` 替代 `download_scheduler.py`。
4.  **验证点**: 能够使用新架构下载 `daily` 数据。

### Phase 4: 稳妥回退机制 (Fallback)
1.  实现 `LegacyBridge`。
2.  在 `DownloadManager` 中集成 `try...catch...fallback`。
3.  **验证点**: 人为制造新策略的异常（如断网或代码错误），验证系统是否自动切换到旧逻辑并成功下载。

### Phase 5: 全面切换
1.  完善剩余接口的策略 (`financial`, `holders` 等)。
2.  更新 `CLAUDE.md` 和 `README.md` 指向新的 `app2`。

---

## 五、 质量保证措施

1.  **单元测试**: 每个 `Strategy` 和 `Service` 必须有对应的 pytest 测试。
2.  **类型检查**: 代码必须通过 `mypy` 检查 (利用 Python Type Hints)。
3.  **日志记录**: 所有的回退 (Fallback) 操作必须记录 WARN 级别日志，以便后续分析消除。

这个方案通过**隔离新旧代码**和**自动降级机制**，保证了重构过程中的系统稳定性，同时实现了代码质量的飞跃。
