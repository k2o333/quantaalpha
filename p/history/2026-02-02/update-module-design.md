# App4 增量更新模块设计方案

## 1. 设计目标

### 1.1 核心目标
- 将 `--update` 功能独立为可复用、可测试的模块
- 支持一键式全系统增量更新
- 提供清晰的更新报告和统计信息
- 保持与现有 App4 架构的兼容性

### 1.2 设计原则
- **单一职责**：更新模块只负责协调更新流程，不处理具体下载逻辑
- **配置驱动**：复用现有的接口配置，不硬编码接口信息
- **容错性**：单个接口失败不影响其他接口更新
- **可观测性**：提供详细的日志和更新报告

---

## 2. 架构设计

### 2.1 模块位置
```
app4/
├── main.py                    # 主入口，添加 --update 参数解析
├── core/                      # 现有核心模块
│   ├── config_loader.py
│   ├── downloader.py
│   ├── coverage_manager.py
│   └── ...
├── update/                    # 新增更新模块目录
│   ├── __init__.py
│   ├── update_manager.py      # 更新管理器（核心协调器）
│   ├── date_calculator.py     # 日期范围计算器
│   ├── update_reporter.py     # 更新报告生成器
│   └── interface_selector.py  # 接口选择器
└── config/
    └── settings.yaml          # 添加 update 配置段
```

### 2.2 模块职责划分

| 模块 | 职责 | 依赖 |
|------|------|------|
| `UpdateManager` | 协调整个更新流程，管理生命周期 | 所有其他模块 |
| `DateCalculator` | 计算每个接口的更新日期范围 | StorageManager, ConfigLoader |
| `UpdateReporter` | 收集统计信息，生成更新报告 | 无（纯数据处理） |
| `InterfaceSelector` | 根据配置和状态选择需要更新的接口 | ConfigLoader |

---

## 3. 核心组件设计

### 3.1 UpdateManager（更新管理器）

**职责**：
- 初始化更新环境
- 协调更新流程
- 管理更新生命周期
- 处理异常和回滚

**核心方法**：
```
class UpdateManager:
    - __init__(config_loader, storage_manager, downloader, ...)
    - run_update(options: UpdateOptions) -> UpdateResult
    - update_interface(interface_name: str) -> InterfaceUpdateResult
    - should_update_interface(interface_name: str) -> bool
    - get_update_statistics() -> UpdateStatistics
```

**工作流程**：
1. 初始化阶段：加载配置，验证环境
2. 规划阶段：确定需要更新的接口列表
3. 执行阶段：逐个接口执行更新
4. 报告阶段：生成更新报告

### 3.2 DateCalculator（日期计算器）

**职责**：
- 智能计算每个接口的更新日期范围
- 处理特殊接口的日期规则
- 检测现有数据的边界

**核心方法**：
```
class DateCalculator:
    - calculate_update_range(interface_name: str) -> DateRange
    - get_existing_data_range(interface_name: str) -> Optional[DateRange]
    - get_default_start_date(interface_name: str) -> str
    - is_update_needed(existing_range: DateRange, target_range: DateRange) -> bool
```

**日期计算策略**：

| 接口类型 | 起始日期策略 | 说明 |
|----------|-------------|------|
| 交易日历 | 1990-01-01 | 固定起始日期 |
| 股票基础信息 | 1990-01-01 | 固定起始日期 |
| 日线数据 | 2000-01-01 或最早上市日 | 可配置 |
| 财务数据 | 现有数据最新日期 | 增量更新 |
| 股东数据 | 现有数据最新日期 | 增量更新 |

### 3.3 UpdateReporter（更新报告器）

**职责**：
- 收集更新过程中的统计信息
- 生成结构化的更新报告
- 支持多种输出格式

**核心方法**：
```
class UpdateReporter:
    - record_interface_start(interface_name: str)
    - record_interface_success(interface_name: str, record_count: int)
    - record_interface_skip(interface_name: str, reason: str)
    - record_interface_failure(interface_name: str, error: Exception)
    - generate_report(format: ReportFormat = "markdown") -> str
    - get_summary() -> UpdateSummary
```

**报告内容**：
- 更新概览（总接口数、成功数、跳过数、失败数）
- 每个接口的详细结果
- 时间统计（开始时间、结束时间、耗时）
- 数据量统计（总记录数、新增记录数）
- 错误详情（如有）

### 3.4 InterfaceSelector（接口选择器）

**职责**：
- 根据配置和用户选项选择需要更新的接口
- 支持包含/排除特定接口或组
- 根据积分权限过滤

**核心方法**：
```
class InterfaceSelector:
    - select_interfaces(options: SelectionOptions) -> List[str]
    - filter_by_permission(interfaces: List[str], available_points: int) -> List[str]
    - filter_by_group(interfaces: List[str], group_name: str) -> List[str]
    - exclude_interfaces(interfaces: List[str], exclusions: List[str]) -> List[str]
```

---

## 4. 配置设计

### 4.1 settings.yaml 新增配置段

```yaml
update:
  enabled: true
  
  # 默认更新策略
  default_strategy:
    start_date: "20000101"  # 默认起始日期
    lookback_days: 7        # 回溯天数（处理可能的数据延迟）
  
  # 特殊接口配置
  special_interfaces:
    trade_cal:
      start_date: "19900101"
      update_frequency: "weekly"  # 更新频率
    stock_basic:
      start_date: "19900101"
      update_frequency: "daily"
    daily:
      start_date: "20000101"
    daily_basic:
      start_date: "20000101"
  
  # 排除接口（不自动更新）
  excluded_interfaces:
    - stock_basic      # 基础数据通常不需要频繁更新
    - trade_cal        # 交易日历更新频率低
  
  # 更新顺序（按依赖关系）
  update_order:
    - trade_cal
    - stock_basic
    - daily
    - daily_basic
    - moneyflow
    - income_vip
    - balancesheet_vip
    - cashflow_vip
    - fina_indicator_vip
  
  # 并发配置
  concurrency:
    max_parallel_interfaces: 1  # 同时更新的接口数（建议为1，避免API限制）
    retry_failed: true          # 失败时是否重试
    max_retries: 3
  
  # 报告配置
  reporting:
    enabled: true
    output_format: "markdown"   # markdown, json, html
    save_report: true
    report_dir: "log/update_reports/"
```

### 4.2 命令行参数设计

```bash
# 基础用法
python app4/main.py --update

# 指定特定接口
python app4/main.py --update --interface daily_basic

# 指定接口组
python app4/main.py --update --group daily

# 排除特定接口
python app4/main.py --update --exclude stock_basic,trade_cal

# 强制更新（忽略现有数据）
python app4/main.py --update --force

# 指定日期范围（覆盖智能计算）
python app4/main.py --update --start_date 20240101 --end_date 20241231

# 仅预览哪些接口需要更新（不实际执行）
python app4/main.py --update --dry-run

# 生成JSON格式报告
python app4/main.py --update --report-format json
```

---

## 5. 数据模型设计

### 5.1 核心数据类

```python
# 日期范围
@dataclass
class DateRange:
    start_date: str
    end_date: str
    
    def is_empty(self) -> bool:
        return self.start_date >= self.end_date

# 更新选项
@dataclass
class UpdateOptions:
    interfaces: Optional[List[str]] = None      # 指定接口，None表示全部
    exclude: List[str] = field(default_factory=list)  # 排除接口
    start_date: Optional[str] = None            # 强制起始日期
    end_date: Optional[str] = None              # 强制结束日期
    force: bool = False                         # 强制更新
    dry_run: bool = False                       # 预览模式
    report_format: str = "markdown"             # 报告格式

# 接口更新结果
@dataclass
class InterfaceUpdateResult:
    interface_name: str
    status: UpdateStatus                        # SUCCESS, SKIPPED, FAILED
    date_range: Optional[DateRange] = None
    record_count: int = 0
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    skip_reason: Optional[str] = None

# 更新结果
@dataclass
class UpdateResult:
    start_time: datetime
    end_time: datetime
    interface_results: List[InterfaceUpdateResult]
    
    @property
    def total_interfaces(self) -> int:
        return len(self.interface_results)
    
    @property
    def success_count(self) -> int:
        return sum(1 for r in self.interface_results if r.status == UpdateStatus.SUCCESS)
    
    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.interface_results if r.status == UpdateStatus.FAILED)
    
    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.interface_results if r.status == UpdateStatus.SKIPPED)
    
    @property
    def total_records(self) -> int:
        return sum(r.record_count for r in self.interface_results)
```

---

## 6. 流程设计

### 6.1 主流程

```
开始更新
    │
    ▼
[初始化]
    │
    ├── 加载配置
    ├── 初始化组件（UpdateManager, DateCalculator, ...）
    └── 验证环境
    │
    ▼
[规划阶段]
    │
    ├── 获取所有可用接口
    ├── 应用过滤条件（包含/排除/权限）
    ├── 确定更新顺序
    └── 生成更新计划
    │
    ▼
[执行阶段] ←────────────────────────┐
    │                                 │
    ├── 获取下一个待更新接口          │
    │                                 │
    ▼                                 │
[计算日期范围]                        │
    │                                 │
    ├── 查询现有数据范围              │
    ├── 应用特殊接口规则              │
    └── 确定更新范围                  │
    │                                 │
    ▼                                 │
[检查是否需要更新]                    │
    │                                 │
    ├── 否 → 记录跳过原因 ────────────┤
    │                                 │
    ▼                                 │
[执行接口更新]                        │
    │                                 │
    ├── 调用现有下载逻辑              │
    ├── 监控进度                      │
    └── 记录结果                      │
    │                                 │
    ▼                                 │
[记录结果] ─────────────────────────┘
    │
    ▼
[报告阶段]
    │
    ├── 汇总统计信息
    ├── 生成更新报告
    └── 输出报告（控制台/文件）
    │
    ▼
结束更新
```

### 6.2 错误处理策略

| 错误类型 | 处理策略 | 说明 |
|----------|---------|------|
| 接口配置错误 | 跳过并记录 | 继续处理其他接口 |
| 网络超时 | 重试3次后跳过 | 使用指数退避策略 |
| API限制 | 等待后重试 | 根据错误码判断 |
| 数据解析错误 | 记录并跳过 | 可能是API返回格式变化 |
| 存储错误 | 终止更新 | 数据目录可能有问题 |

---

## 7. 与现有代码的集成

### 7.1 修改点

| 文件 | 修改内容 | 说明 |
|------|---------|------|
| `main.py` | 添加 `--update` 参数解析 | 新增参数，调用 UpdateManager |
| `config/settings.yaml` | 添加 update 配置段 | 新增配置项 |
| `core/config_loader.py` | 可选：添加 get_update_config 方法 | 方便获取更新配置 |

### 7.2 复用的现有组件

| 组件 | 复用方式 | 说明 |
|------|---------|------|
| `ConfigLoader` | 构造函数注入 | 获取接口配置 |
| `StorageManager` | 构造函数注入 | 读取现有数据 |
| `GenericDownloader` | 构造函数注入 | 执行实际下载 |
| `CoverageManager` | 通过 downloader 获取 | 检测数据覆盖 |
| `TaskScheduler` | 通过 downloader 获取 | 并发任务调度 |

### 7.3 不修改的现有代码

- `pagination_executor.py` - 分页逻辑保持不变
- `downloader.py` - 下载逻辑保持不变
- `coverage_manager.py` - 覆盖率检测逻辑保持不变
- `storage.py` - 存储逻辑保持不变

---

## 8. 测试策略

### 8.1 单元测试

| 测试目标 | 测试内容 |
|----------|---------|
| DateCalculator | 日期计算逻辑、边界条件、特殊接口处理 |
| UpdateReporter | 统计收集、报告生成、各种状态组合 |
| InterfaceSelector | 过滤逻辑、权限检查、包含/排除规则 |
| UpdateManager | 流程协调、异常处理、状态管理 |

### 8.2 集成测试

| 测试场景 | 测试内容 |
|----------|---------|
| 完整更新流程 | 从规划到报告的全流程 |
| 部分接口更新 | 指定接口或组的更新 |
| 错误恢复 | 模拟接口失败后的处理 |
| 并发更新 | 多个接口的并发处理 |

### 8.3 手动测试清单

- [ ] 首次更新（无现有数据）
- [ ] 增量更新（有现有数据）
- [ ] 强制更新（覆盖现有数据）
- [ ] 预览模式（--dry-run）
- [ ] 指定接口更新
- [ ] 指定组更新
- [ ] 排除接口更新
- [ ] 失败接口处理
- [ ] 报告生成（各种格式）

---

## 9. 扩展性设计

### 9.1 未来可能的扩展

| 扩展方向 | 实现方式 |
|----------|---------|
| 定时自动更新 | 添加 scheduler 集成点 |
| 增量更新策略定制 | 添加 UpdateStrategy 接口 |
| 多数据源支持 | 抽象 DataSource 接口 |
| 更新历史记录 | 添加 UpdateHistory 存储 |
| 增量更新API | 暴露 REST API 接口 |

### 9.2 插件机制（可选）

```python
# 更新前/后钩子
class UpdatePlugin:
    def before_interface_update(self, interface_name: str, date_range: DateRange):
        pass
    
    def after_interface_update(self, result: InterfaceUpdateResult):
        pass
```

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| API 限制导致更新失败 | 高 | 实现重试机制、降低并发度、添加延迟 |
| 数据量过大导致内存溢出 | 中 | 使用流式处理、分批写入 |
| 配置错误导致更新错误数据 | 高 | 严格配置验证、预览模式 |
| 更新过程中断导致数据不一致 | 中 | 使用事务性写入、支持断点续传 |
| 接口变更导致解析失败 | 中 | 添加版本检查、优雅降级 |

---

## 11. 实施计划

### 阶段一：基础框架（1-2天）
- [ ] 创建 update/ 目录结构
- [ ] 实现 DateCalculator
- [ ] 实现 UpdateReporter
- [ ] 实现 InterfaceSelector

### 阶段二：核心逻辑（2-3天）
- [ ] 实现 UpdateManager
- [ ] 集成到 main.py
- [ ] 添加配置到 settings.yaml

### 阶段三：测试与优化（1-2天）
- [ ] 编写单元测试
- [ ] 手动测试各种场景
- [ ] 性能优化

### 阶段四：文档（1天）
- [ ] 使用文档
- [ ] 配置文档
- [ ] 故障排查指南

---

## 12. 使用示例

### 12.1 典型使用场景

```bash
# 场景1：首次部署，全量更新
python app4/main.py --update --force

# 场景2：日常增量更新
python app4/main.py --update

# 场景3：更新特定组
python app4/main.py --update --group financial_vip

# 场景4：排除某些接口
python app4/main.py --update --exclude stock_basic,trade_cal

# 场景5：预览将要更新的内容
python app4/main.py --update --dry-run

# 场景6：生成JSON报告供其他工具使用
python app4/main.py --update --report-format json --report-file update_result.json
```

### 12.2 程序化使用

```python
from app4.update import UpdateManager, UpdateOptions

# 创建更新管理器
manager = UpdateManager(
    config_loader=config_loader,
    storage_manager=storage_manager,
    downloader=downloader
)

# 配置更新选项
options = UpdateOptions(
    interfaces=['daily', 'daily_basic'],
    start_date='20240101',
    end_date='20241231'
)

# 执行更新
result = manager.run_update(options)

# 处理结果
if result.failed_count > 0:
    for r in result.interface_results:
        if r.status == UpdateStatus.FAILED:
            print(f"接口 {r.interface_name} 更新失败: {r.error_message}")
```

---

## 13. 总结

本方案设计了一个独立的增量更新模块，具有以下特点：

1. **独立性**：完全独立的模块，不侵入现有代码
2. **可复用性**：组件化设计，便于测试和复用
3. **可配置性**：通过配置文件灵活调整更新行为
4. **可观测性**：详细的日志和报告机制
5. **容错性**：完善的错误处理和恢复机制

该方案充分利用了 App4 现有的成熟组件（CoverageManager、分页执行器等），在其基础上构建更高层次的更新协调逻辑，实现真正的"一键增量更新"功能。
