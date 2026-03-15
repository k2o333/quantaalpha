# app4 - 数据下载与存储模块

**Status:** active
**Created:** 2026-03-14

---

## TL;DR

- `app4` is the config-driven downloader and storage system for Tushare data.
- Most behavior changes happen in `app4/core/`, `app4/update/`, or `app4/config/interfaces/*.yaml`.
- High-risk edits are pagination, storage, dedup, schema, and update semantics.

## Entrypoints

- CLI: `python app4/main.py`
- Main config: `app4/config/settings.yaml`
- Interface configs: `app4/config/interfaces/*.yaml`
- Core logic: `app4/core/`
- Update flow: `app4/update/`

## Validation

- Config validation: `python -c "from app4.core.config_loader import ConfigLoader; ConfigLoader().validate_config()"`
- Single-interface smoke test: `python app4/main.py --interface trade_cal --start_date 20240101 --end_date 20240131`
- Update preview: `python app4/main.py --update --update-dry-run`
- Targeted tests: `pytest test/ -v`

## Do Not Touch Blindly

- `pagination.py`
- `pagination_executor.py`
- `storage.py`
- `dedup.py`
- `schema_manager.py`

Read the relevant sections below and review `docs/00-governance/rules.md` first.

## Known Risks At A Glance

- large interfaces such as `stk_factor_pro` and `cyq_chips` can stress memory
- pagination mistakes can create silent gaps or duplicates
- write-path changes can corrupt datasets if not validated

---

## Responsibility

app4 是配置驱动的金融数据下载与存储模块，负责：

1. **数据下载**：从 Tushare API 获取 A 股市场数据
2. **数据处理**：数据类型转换、清洗、去重
3. **数据存储**：以 Parquet 格式持久化到本地文件系统
4. **增量更新**：智能检测数据缺口并增量补全
5. **并发调度**：任务调度与限流控制

---

## External Interfaces

### CLI 入口

```bash
python app4/main.py [options]
```

| 参数 | 说明 |
|------|------|
| `--interface <name>` | 指定接口名称（可多个） |
| `--group <name>` | 指定接口组 |
| `--start_date YYYYMMDD` | 起始日期 |
| `--end_date YYYYMMDD` | 结束日期 |
| `--update` | 启用增量更新模式 |
| `--update-interface <name>` | 指定更新接口 |
| `--update-force` | 强制更新（忽略现有数据） |
| `--ts_code <code>` | 指定股票代码 |
| `--concurrency <n>` | 并发数（默认 4） |
| `--log-level <level>` | 日志级别 |

### 外部 API

- **Tushare Pro API**：`http://api.tushare.pro`
- 需要配置 `TUSHARE_TOKEN` 环境变量
- 积分权限决定可访问的接口范围

---

## Key Data Structures

### AppComponents

组件容器，封装所有核心组件引用：

```python
@dataclass
class AppComponents:
    config_loader: ConfigLoader
    storage_manager: StorageManager
    downloader: GenericDownloader
    scheduler: TaskScheduler
    processor: DataProcessor
    cache_warmer: CacheWarmer
    trade_cal_cache: Any
    stock_list_cache: Any
```

### UpdateOptions

增量更新选项：

```python
@dataclass
class UpdateOptions:
    interfaces: List[str]        # 待更新接口列表
    start_date: Optional[str]    # 起始日期
    end_date: Optional[str]      # 结束日期
    force: bool                  # 强制更新
    dry_run: bool                # 预览模式
    gap_detection_enabled: bool  # 启用缺口检测
    ts_code: Optional[str]       # 指定股票代码
```

### PaginationContext

分页上下文，封装分页参数：

```python
class PaginationContext:
    interface_config: Dict[str, Any]  # 接口配置
    trade_calendar: List[Dict]        # 交易日历
    stock_list: List[Dict]            # 股票列表
    coverage_manager: CoverageManager # 覆盖率管理器
```

### PaginationExecutor 支持的分页模式

| 模式 | 说明 | 适用接口 |
|------|------|----------|
| `offset` | 偏移量分页 | stock_basic, stock_company |
| `date_range` | 日期范围 | trade_cal |
| `reverse_date_range` | 反向日期范围 | daily_basic, stk_factor_pro 等 |
| `stock_loop` | 股票循环 | stk_rewards, cyq_chips 等 |
| `period_range` | 报告期范围 | income_vip, balancesheet_vip 等 |
| `type_split` | 类型分割 | stock_hsgt |

---

## Dependencies

### Python 包

```
polars>=0.20.0
pyarrow>=14.0.0
requests>=2.28.0
python-dotenv>=1.0.0
```

### 外部依赖

- **Tushare Pro API**：数据源
- **本地文件系统**：Parquet 数据存储

### 内部依赖

- `config/settings.yaml`：全局配置
- `config/interfaces/*.yaml`：接口配置
- `.env`：环境变量（TUSHARE_TOKEN, TUSHARE_POINTS）

---

## Constraints

### API 限制

- 每分钟最多 250 次请求（rate_limit 配置）
- 积分权限决定接口访问范围：
  - basic (120分)：基础接口
  - standard (2000分)：标准接口
  - advanced (5000分)：高级接口
  - professional (8000分)：专业接口

### 并发限制

- 默认最大并发数：4
- 队列最大容量：1000

### 存储限制

- 默认 Buffer 阈值：5000 条
- 小批次阈值：100 条（立即处理）
- 文件格式：Parquet

---

## Known Risks

### 内存管理

- **大数据量接口**：`stk_factor_pro`、`cyq_chips` 等接口数据量大，可能造成内存增长
- **缓解措施**：使用 Buffer 机制分批处理，避免全量数据驻留内存

### 重复数据

- **风险**：部分接口可能返回重复记录
- **缓解措施**：`_process_worker` 执行主键去重，`CoverageManager` 检测已存在数据

### 网络错误

- **风险**：API 请求失败导致数据缺失
- **缓解措施**：指数退避重试策略（最多 3 次），断点续传机制

### 积分限制

- **风险**：积分不足导致接口无权限
- **缓解措施**：`InterfaceSelector.filter_by_permission()` 过滤无权限接口

---

## Test Entry Points

### 单元测试

```bash
# 运行所有测试
pytest test/

# 运行特定测试
pytest test/test/test_config_loader.py
pytest test/test/test_coverage_manager.py
pytest test/test/test_storage_monitoring.py
pytest test/test/test_update_module.py
```

### 关键测试文件

| 文件 | 测试内容 |
|------|----------|
| `test/test/test_config_loader.py` | 配置加载器 |
| `test/test/test_coverage_manager.py` | 覆盖率管理器 |
| `test/test/test_storage_monitoring.py` | 存储监控 |
| `test/test/test_update_module.py` | 增量更新模块 |
| `test/test/test_schema_manager.py` | Schema 管理 |
| `test/test/test_pagination_combinable.py` | 分页组合 |
| `test/test/test_main_flow.py` | 主流程 |

### 集成测试

```bash
# 使用 --dry-run 预览更新
python app4/main.py --update --update-dry-run

# 测试单个接口
python app4/main.py --interface trade_cal --start_date 20240101 --end_date 20240131
```

---

## Core Components

### core/downloader.py - GenericDownloader

通用下载器，负责：
- API 请求与重试
- 分页执行协调
- 缓存管理（交易日历、股票列表）

### core/storage.py - StorageManager

存储管理器，负责：
- 数据 Buffer 管理
- 异步写入线程
- Parquet 文件生成

### core/processor.py - DataProcessor

数据处理器，负责：
- 类型转换
- 数据清洗
- 批次内去重

### core/coverage_manager.py - CoverageManager

覆盖率管理器，负责：
- 数据缺口检测
- 已存在数据判断
- 覆盖率计算

### core/pagination_executor.py - PaginationExecutor

分页执行器，负责：
- 分页参数组合
- 并发/顺序执行策略
- 请求执行与结果收集

### update/update_manager.py - UpdateManager

更新管理器，负责：
- 增量更新协调
- 断点续传
- 更新报告生成

---

## Configuration

### 全局配置路径

`app4/config/settings.yaml`

### 关键配置项

```yaml
concurrency:
  max_workers: 4
  max_queue_size: 1000

request:
  rate_limit: 250
  max_retries: 3
  timeout: 30

storage:
  base_dir: "/path/to/data"
  format: "parquet"
  batch_size: 10000

update:
  checkpoint:
    enabled: true
  fault_tolerance:
    skip_on_error: true
    max_consecutive_errors: 5
```

### 接口配置路径

`app4/config/interfaces/*.yaml`
