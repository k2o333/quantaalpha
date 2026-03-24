# 24H 调度中心设计文档

**版本:** 1.0  
**状态:** 设计完成  
**日期:** 2026-03-24

## 1. 概述

24H 调度中心是因子库自治运营的核心引擎，统一管理三个关键工作流：

1. **数据监控 (Data Monitor)**: 监听 app4 数据管道更新，触发因子回测
2. **温故 (Revalidation)**: 定时复验已有因子，更新状态
3. **知新 (Mining)**: 定时挖掘新因子，扩展因子库

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    MiningOrchestrator                             │
│  (统一调度入口，管理三个子模块的生命周期)                           │
└────────────────┬──────────────────┬──────────────────────────────┘
                 │                  │                               │
                 ▼                  ▼                               ▼
┌────────────────────────┐ ┌──────────────────┐ ┌────────────────────────────┐
│   DataMonitorTrigger  │ │ RevalidationSched│ │     MiningScheduler        │
│   (数据监控)           │ │    (温故)         │ │       (知新)               │
│                       │ │                  │ │                            │
│ - 文件系统轮询         │ │ - APScheduler    │ │ - APScheduler              │
│ - Parquet 变更检测    │ │ - 调用 library   │ │ - RAG 检索上下文           │
│ - 触发因子回测        │ │ - 状态更新       │ │ - LLM 生成新因子            │
└────────────────────────┘ └──────────────────┘ └────────────────────────────┘
         │                         │                         │
         └─────────────────────────┼─────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────┐
                    │   FactorLibraryManager   │
                    │   (因子库)                │
                    └──────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────┐
                    │   VectorStore (RAG)      │
                    │   (向量检索)             │
                    └──────────────────────────┘
```

### 2.2 模块职责

| 模块 | 职责 | 关键接口 |
|------|------|----------|
| `MiningOrchestrator` | 统一入口，生命周期管理 | `start()`, `stop()`, `run_*_cycle()` |
| `DataMonitorTrigger` | 文件系统监控 | `check_for_updates()` |
| `RevalidationScheduler` | 定时复验 | `run_revalidation()` |
| `MiningScheduler` | 定时挖掘 | `run_mining()` |

### 2.3 事件流

```
数据更新事件
    │
    ├─→ [FactorLibraryManager] 标记相关因子为 stale
    │
    └─→ [RevalidationScheduler] 触发复验

定时触发 (24H)
    │
    ├─→ [RevalidationScheduler]
    │       │
    │       ├─→ select_revalidation_candidates(days=21)
    │       │
    │       ├─→ 对每个候选因子运行回测
    │       │
    │       └─→ apply_validation_result() → 状态机更新

定时触发 (12H)
    │
    └─→ [MiningScheduler]
            │
            ├─→ query_active_factors_RAG() 获取上下文
            │
            ├─→ LLM 生成新因子
            │
            ├─→ 回测验证
            │
            └─→ 入库 (pending_validation)
```

## 3. 技术选型

### 3.1 任务调度

| 候选 | 优点 | 缺点 | 推荐 |
|------|------|------|------|
| **APScheduler** | 轻量、无外部依赖、易集成 | 无分布式支持 | ✅ **推荐** |
| Celery | 分布式支持、成熟 | 需要 Redis、复杂度高 | 后期扩展 |
| Prefect | 现代化、流程可视化 | 学习曲线、依赖外部服务 | 后期扩展 |

**决策理由**: 当前为单机部署，APScheduler 满足需求且零运维成本。后期如需分布式，可平滑迁移到 Celery。

### 3.2 进程管理

| 候选 | 优点 | 缺点 | 推荐 |
|------|------|------|------|
| **Supervisor** | 配置简单、进程管理、易监控 | 无 systemd 集成 | ✅ **推荐** |
| systemd | 系统级集成、自重启 | 配置复杂 | 备选 |
| Docker Compose | 容器化、易部署 | 资源开销大 | 部署用 |

**决策理由**: Supervisor 配置简洁，自带 `supervisorctl` 管理界面，与 APScheduler 配合良好。

### 3.3 数据监控

| 候选 | 优点 | 缺点 | 推荐 |
|------|------|------|------|
| **文件系统轮询** | 简单、无依赖 | 有延迟 | ✅ **推荐** (v1) |
| inotify | 实时、事件驱动 | Linux 特有 | 后期优化 |

**决策理由**: v1 采用轮询方案（默认 5 分钟间隔），简单可靠。后期可升级到 inotify 实时检测。

### 3.4 向量库

| 候选 | 优点 | 缺点 | 推荐 |
|------|------|------|------|
| **ChromaDB** | 轻量、Python 原生、易用 | 生产扩展性待验证 | ✅ **推荐** |
| sqlite-vss | SQLite 集成、简单 | 功能有限 | 备选 |
| Milvus | 生产级、分布式 | 部署复杂 | 后期扩展 |

**决策理由**: ChromaDB 已在 S06 中集成，使用其作为向量存储可复用现有代码。

### 3.5 配置管理

| 候选 | 优点 | 缺点 | 推荐 |
|------|------|------|------|
| **YAML + Pydantic** | 类型安全、验证、默认值 | 多一层解析 | ✅ **推荐** |
| JSON | 通用、无依赖 | 无类型验证 | 备选 |
| 环境变量 | 12-factor 友好 | 复杂配置困难 | 敏感信息 |

**决策理由**: `SchedulerConfig` 使用 Pydantic dataclass，提供类型安全和默认值。

### 3.6 日志与监控

| 候选 | 优点 | 缺点 | 推荐 |
|------|------|------|------|
| **Loguru** | 零配置、结构化日志 | 非标准 | ✅ **推荐** |
| Grafana + Loki | 可视化、查询 | 需要额外服务 | 后期扩展 |
| ELK Stack | 生态成熟 | 运维复杂 | 备选 |

**决策理由**: Loguru 已集成在项目中，零配置即可输出结构化日志。

## 4. 配置设计

### 4.1 SchedulerConfig 默认值

```python
@dataclass
class SchedulerConfig:
    # 数据监控
    data_check_interval_seconds: int = 300  # 5 分钟
    data_dirs: list[str] = []

    # 复验调度
    revalidation_interval_hours: int = 24  # 每日复验
    revalidation_days_threshold: int = 21  # 21 天未验证则复验
    max_revalidation_per_run: int = 10

    # 挖掘调度
    mining_interval_hours: int = 12  # 每 12 小时挖掘
    max_mining_per_run: int = 5

    # 全局开关
    enable_data_monitor: bool = True
    enable_revalidation: bool = True
    enable_mining: bool = True
```

### 4.2 状态转换规则 (调度视角)

```
┌──────────────────┐
│ pending_validation│
└────────┬─────────┘
         │ 验证成功
         ▼
┌──────────────────┐
│     active       │◄─────────────┐
└────────┬─────────┘              │
         │ 超过 30 天未验证        │ 重新验证成功
         ▼                        │
┌──────────────────┐               │
│     stale        │───────────────┘
└────────┬─────────┘
         │ 重新验证
         ▼
┌──────────────────┐
│   degraded       │
└────────┬─────────┘
         │ 连续失败 >= 3
         ▼
┌──────────────────┐
│   deprecated     │
└──────────────────┘
```

## 5. 异常处理与故障恢复

### 5.1 异常分类

| 级别 | 说明 | 处理方式 |
|------|------|----------|
| 瞬时错误 | 网络抖动、超时 | 重试 3 次后跳过 |
| 可恢复错误 | 数据缺失、格式错误 | 记录日志，更新因子状态为 degraded |
| 致命错误 | 配置错误、依赖缺失 | 停止调度器，记录错误，上报 |

### 5.2 恢复策略

1. **优雅停止**: 收到停止信号时，等待当前任务完成
2. **状态持久化**: 每次状态变更写入因子库
3. **心跳检测**: 调度器定期写入心跳时间戳
4. **超时处理**: 单个因子处理超时（默认 10 分钟）后强制跳过

### 5.3 故障检测

```python
def get_health_report(self) -> dict:
    """返回各子系统健康状态"""
    return {
        "status": self.status.value,
        "data_monitor": {"running": ..., "last_check": ...},
        "revalidation": {"total_runs": ..., "last_run": ..., "next_run": ...},
        "mining": {"total_runs": ..., "last_run": ..., "next_run": ...},
        "errors": {"count": ..., "last_error": ...},
    }
```

## 6. 接口契约

### 6.1 MiningOrchestrator API

```python
class MiningOrchestrator:
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def run_revalidation_cycle(self) -> RevalidationResult: ...
    def run_mining_cycle(self) -> MiningResult: ...
    def check_data_updates(self) -> list[SchedulerContext]: ...
    def get_status(self) -> OrchestratorStatus: ...
    def get_stats(self) -> OrchestratorStats: ...
    def get_health_report(self) -> dict: ...
    def on_event(self, callback: callable) -> None: ...
```

### 6.2 外部依赖集成点

| 依赖 | 集成位置 | 用途 |
|------|----------|------|
| `FactorLibraryManager` | `DefaultRevalidationScheduler` | 复验候选查询、结果更新 |
| `FactorVectorStore` | `DefaultMiningScheduler` | RAG 上下文检索 |
| `ProviderPool` | `DefaultMiningScheduler` | LLM 生成请求 |

## 7. 下一步

### Phase 1 (v1) - 当前设计
- [x] 接口定义完成
- [x] 默认实现完成
- [ ] 与 FactorLibraryManager 集成
- [ ] Supervisor 配置

### Phase 2 (v2)
- [ ] inotify 实时监控
- [ ] 健康检查 API
- [ ] Grafana 监控面板

### Phase 3 (v3)
- [ ] 分布式支持 (Celery)
- [ ] 因子血缘追踪
- [ ] A/B 测试框架

## 8. 附录

### A. 文件清单

```
quantaalpha/continuous/
├── __init__.py           # 模块导出
├── orchestrator.py       # MiningOrchestrator 主类
├── scheduler.py          # 接口定义
├── implementations.py    # 默认实现
└── DESIGN.md             # 本文档
```

### B. 测试策略

- 单元测试: 各 Scheduler 独立测试
- 集成测试: Orchestrator 端到端测试
- 冒烟测试: Supervisor 启动验证
