# aspipe_v4 重构结构对比摘要

## 1. 重构核心目标
本次重构旨在解决 `app` 目录下存在的配置碎片化、入口冗余、接口逻辑分散等问题。我们将采用**六边形架构**在 `app2` 目录中重新构建系统，实现高内聚、低耦合。

## 2. 结构对比

### 2.1 整体架构

| 维度 | 重构前 (Current `app`) | 重构后 (Target `app2`) |
| :--- | :--- | :--- |
| **架构模式** | 混合模式 (Facade + 脚本式) | **六边形架构** (Domain/Infra/App) |
| **依赖管理** | 全局导入，紧耦合 | **依赖注入容器** (`Container`) |
| **入口点** | 3个 (`main.py`, `enhanced_*.py`, `score_*.py`) | **1个** (`main.py`) |
| **配置源** | 4套分散 (`config.py`, `*_config.py`) | **1套统一** (`config/settings.py`) |

### 2.2 关键模块映射

#### A. 接口层 (Interface Layer)
*   **Before**: 逻辑严重分散。
    *   `app/interfaces/*.py`: 12个分类文件，过度封装。
    *   `app/tushare_api.py`: 混杂了部分直接实现。
    *   `app/score_based_downloader.py`: 独立且重复的接口实现。
*   **After**: 统一收敛。
    *   `app2/infrastructure/tushare/client.py`: **通用客户端**，动态分发请求，移除冗余包装。
    *   `app2/infrastructure/tushare/adapters.py`: 统一处理参数适配。

#### B. 业务逻辑层 (Application Layer)
*   **Before**: 逻辑散落在下载器类中。
    *   `DateRangeDownloader`: 包含业务调度逻辑。
    *   `DownloadScheduler`: 复杂的调度实现。
*   **After**: 清晰的服务层。
    *   `app2/application/download_service.py`: 编排下载、存储、缓存流程。
    *   `app2/domain/interfaces.py`: 定义抽象接口，解耦具体实现。

#### C. 基础设施层 (Infrastructure Layer)
*   **Before**: 缓存和存储逻辑耦合在业务代码中。
    *   `cache_*.py`: 3个缓存相关文件。
    *   `data_storage.py`: 全局函数式存储。
*   **After**: 独立的实现类。
    *   `app2/infrastructure/cache/manager.py`: 统一缓存管理。
    *   `app2/infrastructure/storage/parquet.py`: 具体的存储实现。

## 3. 目录结构演变

### Before (`app/`)
```text
app/
├── main.py (主入口)
├── score_based_downloader.py (冗余入口)
├── tushare_api.py (核心Facade)
├── interfaces/ (12个分散文件)
├── *_config.py (4个配置文件)
└── ...
```

### After (`app2/`)
```text
app2/
├── main.py                         # 唯一入口 (CLI适配)
├── container/
│   └── container.py                # 依赖注入容器
├── config/
│   ├── settings.py                 # 强类型配置定义
│   └── loader.py                   # 配置加载器
├── domain/                         # 核心抽象
│   └── interfaces.py               # 接口定义 (IDownloader, IStorage)
├── infrastructure/                 # 具体实现
│   ├── tushare/
│   │   └── client.py               # 统一的 Tushare 客户端
│   ├── storage/
│   └── cache/
└── application/                    # 业务流程
    └── download_service.py         # 下载服务编排
```

## 4. 总结
重构后的 `app2` 将不再维护 `interfaces/` 下的大量样板代码，而是通过一个智能的 `client.py` 统一处理 API 调用。所有业务逻辑被封装在 `application/` 层，通过 `container` 进行组装，彻底解决了原有系统逻辑分散和配置混乱的问题。
