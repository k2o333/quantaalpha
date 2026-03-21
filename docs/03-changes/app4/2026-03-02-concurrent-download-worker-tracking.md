---
doc_type: change
module: app4
status: archived
owner: quan
created: 2026-03-02
updated: 2026-03-02
summary: 并发接口下载与 Worker/Task ID 全链路追踪方案
---

# 并发接口下载 + Worker/Task ID 全链路追踪方案

## 1. 目标

当前 `--update --update-group period_range` 执行时，所有接口**串行**处理。目标是：

1. **多个 worker 并发下载不同接口**（接口级并发）
2. **每个 worker 有唯一 worker_id**，贯穿下载 → 处理 → 存储全链路日志
3. **每个接口任务有唯一 task_id**，用于追踪单个接口从开始到写盘的完整生命周期

## 2. 现状分析

### 2.1 当前架构

```
main.py (run_update_mode)
  └─ UpdateManager.run_update()
       └─ for interface in interfaces:          ← 串行！
            └─ update_interface(name, options)
                 └─ _execute_download()
                      └─ PaginationExecutor.execute()
                           └─ _execute_period_range_sequential()   ← period_range 模式
                                └─ _make_request()  ← API 调用
                      └─ StorageManager.save_data()  ← 异步写入
```

### 2.2 线程模型

| 线程 | 说明 |
|------|------|
| **主线程** | `run_update()` 串行遍历接口 |
| **StorageManager._process_worker** | 1 个后台线程，处理数据去重 |
| **StorageManager._writer_worker** | 1 个后台线程，写入 Parquet 文件 |

### 2.3 已有的线程安全机制

| 组件 | 是否线程安全 | 说明 |
|------|:---:|------|
| `RateLimiter` | ✅ | 内部有 `threading.Lock`，令牌桶算法线程安全 |
| `StorageManager.add_to_buffer` | ✅ | 有 `buffer_lock` |
| `StorageManager.save_data` | ✅ | 数据通过 `process_queue` 异步处理 |
| `GenericDownloader._make_request` | ✅ | Session 线程安全，rate_limiter 线程安全 |
| `GenericDownloader._memory_cache` | ✅ | 有 `_cache_lock (RLock)` |
| `CheckpointManager` | ❌ | 无锁，多线程不安全 |
| `UpdateReporter` | ❌ | `interface_results` 列表无锁 |
| `PaginationExecutor` | ✅ | 无状态，每次调用独立 |

## 3. ID 体系设计

### 3.1 Worker ID

- **格式**: `W-{序号}`，例如 `W-01`, `W-02`, `W-03`
- **分配**: 线程池中每个线程启动时分配
- **作用域**: 一个 worker 线程在整个生命周期内使用同一个 worker_id
- **传播**: 通过 `threading.local()` 存储，在日志 Filter 中自动注入

### 3.2 Task ID

- **格式**: `T-{接口名缩写}-{时间戳后6位}`，例如 `T-income_vip-a3b2c1`
- **分配**: 每个接口任务开始时生成
- **作用域**: 从 `update_interface()` → `_execute_download()` → `PaginationExecutor` → `save_data()` 全链路
- **传播**: 通过参数传递（显式）+ `threading.local()` 存储（兜底）

### 3.3 Storage Worker ID

- **格式**: `SW-process`, `SW-writer`
- **分配**: 存储线程启动时固定
- **日志示例**:

```
# 下载线程日志
2026-03-05 10:00:01 [W-01][T-income_vip-a3b2c1] INFO - 开始下载 income_vip: 20240101~20260305
2026-03-05 10:00:02 [W-01][T-income_vip-a3b2c1] INFO - [income_vip] Saved 500 records for period 20240331
2026-03-05 10:00:03 [W-02][T-balancesheet-f4e5d6] INFO - 开始下载 balancesheet_vip: 20240101~20260305

# 存储线程日志
2026-03-05 10:00:02 [SW-process][-] INFO - Processed 500 records for income_vip
2026-03-05 10:00:03 [SW-writer][-] INFO - Wrote 500 records to data/income_vip/income_vip_20240101_20240331_xxx.parquet
```

## 4. 改动方案

### 4.1 新增文件: `core/trace.py` — 追踪上下文

```python
"""
全链路追踪模块
提供 worker_id 和 task_id 的线程本地存储和日志注入
"""
import threading
import logging
import uuid
from typing import Optional


# 线程本地存储
_trace_local = threading.local()


def set_worker_id(worker_id: str):
    """设置当前线程的 worker_id"""
    _trace_local.worker_id = worker_id


def get_worker_id() -> str:
    """获取当前线程的 worker_id，默认 'MAIN'"""
    return getattr(_trace_local, 'worker_id', 'MAIN')


def set_task_id(task_id: str):
    """设置当前线程正在执行的 task_id"""
    _trace_local.task_id = task_id


def get_task_id() -> str:
    """获取当前线程的 task_id，默认 '-'"""
    return getattr(_trace_local, 'task_id', '-')


def generate_task_id(interface_name: str) -> str:
    """生成 task_id"""
    short_uuid = uuid.uuid4().hex[:6]
    return f"T-{interface_name}-{short_uuid}"


class TraceLogFilter(logging.Filter):
    """日志过滤器，自动注入 worker_id 和 task_id"""

    def filter(self, record):
        record.worker_id = get_worker_id()
        record.task_id = get_task_id()
        return True
```

### 4.2 修改: `main.py` — 日志格式和 CLI 参数

**改动点 1**: `setup_logging()` 中修改日志格式

```diff
 formatter = logging.Formatter(
-    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
+    "%(asctime)s [%(worker_id)s][%(task_id)s] %(name)s - %(levelname)s - %(message)s"
 )
+
+ # 添加 TraceLogFilter
+ from core.trace import TraceLogFilter
+ trace_filter = TraceLogFilter()
+ root_logger.addFilter(trace_filter)
```

**改动点 2**: 新增 CLI 参数 `--update-workers`

```python
parser.add_argument(
    "--update-workers",
    type=int,
    default=1,
    dest="update_workers",
    help="并发下载接口的 worker 数量（默认 1，即串行）",
)
```

**改动点 3**: `run_update_mode()` 中传递 `max_workers` 到 `UpdateOptions`

```python
options = UpdateOptions(
    ...
    max_workers=getattr(args, "update_workers", 1),
)
```

### 4.3 修改: `update/update_manager.py` — 核心并发改造

**改动点 1**: 导入追踪模块

```python
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.trace import set_worker_id, set_task_id, generate_task_id
```

**改动点 2**: `run_update()` 中的串行循环 → 并发执行

```python
def run_update(self, options: UpdateOptions) -> UpdateResult:
    ...
    # 添加锁（保护 checkpoint 和 reporter）
    self._lock = threading.Lock()

    max_workers = options.max_workers

    if max_workers <= 1:
        # 保持原有串行逻辑（向后兼容）
        for idx, interface_name in enumerate(interfaces, 1):
            ...  # 原有代码不变
    else:
        # 并发模式
        self._run_concurrent_update(interfaces, options, max_workers)
    ...
```

新增方法 `_run_concurrent_update()`:

```python
def _run_concurrent_update(
    self,
    interfaces: List[str],
    options: UpdateOptions,
    max_workers: int
):
    """并发更新多个接口"""
    consecutive_errors = 0  # 原子计数器用锁保护

    def worker_fn(worker_id: str, interface_name: str):
        """单个 worker 执行的函数"""
        nonlocal consecutive_errors

        # 设置线程追踪上下文
        set_worker_id(worker_id)
        task_id = generate_task_id(interface_name)
        set_task_id(task_id)

        logger.info(f"开始处理接口: {interface_name}")

        # 线程安全地记录接口开始
        with self._lock:
            self.checkpoint_manager.record_interface_start(interface_name)
            self.reporter.record_interface_start(interface_name)

        try:
            result = self.update_interface(interface_name, options)

            with self._lock:
                self.reporter.record_interface_result(result)

                if result.status == UpdateStatus.FAILED:
                    consecutive_errors += 1
                else:
                    consecutive_errors = 0

                self.checkpoint_manager.record_interface_complete(
                    interface_name,
                    result.status in [UpdateStatus.SUCCESS, UpdateStatus.SKIPPED],
                    result.error_message
                )

            return result

        except Exception as e:
            logger.error(f"更新接口 {interface_name} 时发生异常: {e}")

            result = InterfaceUpdateResult(
                interface_name=interface_name,
                status=UpdateStatus.FAILED,
                error_message=str(e)
            )

            with self._lock:
                consecutive_errors += 1
                self.reporter.record_interface_result(result)
                self.checkpoint_manager.record_interface_complete(
                    interface_name, False, str(e)
                )

            return result

    # 使用线程池
    with ThreadPoolExecutor(
        max_workers=max_workers,
        thread_name_prefix="update-worker"
    ) as executor:
        # 分配 worker_id 给每个任务
        futures = {}
        for idx, interface_name in enumerate(interfaces):
            worker_id = f"W-{(idx % max_workers) + 1:02d}"  # 循环分配
            future = executor.submit(worker_fn, worker_id, interface_name)
            futures[future] = interface_name

        for future in as_completed(futures):
            interface_name = futures[future]
            try:
                result = future.result()
                logger.info(
                    f"接口 {interface_name} 完成: {result.status.name}"
                )
            except Exception as e:
                logger.error(f"接口 {interface_name} 未预期的异常: {e}")
```

> **注意**: `worker_id` 是循环分配的（`idx % max_workers`），因此线程池复用线程时，同一个线程可能处理多个接口，但每次会重新设置 `worker_id` 和 `task_id`。

### 4.4 修改: `update/models.py` — UpdateOptions.max_workers 默认值

默认值已是 `1`（保持串行），无需改动。

### 4.5 修改: `core/storage.py` — 存储 worker 标识

在 `start_writer()` 中为存储线程设置 worker_id：

```python
def start_writer(self):
    if not self.running:
        self.running = True

        def _writer_with_trace():
            from .trace import set_worker_id
            set_worker_id("SW-writer")
            self._writer_worker()

        def _process_with_trace():
            from .trace import set_worker_id
            set_worker_id("SW-process")
            self._process_worker()

        self.writer_thread = threading.Thread(
            target=_writer_with_trace, daemon=True
        )
        self.writer_thread.start()

        self.process_thread = threading.Thread(
            target=_process_with_trace, daemon=True
        )
        self.process_thread.start()

        logger.info("Storage writer and process threads started")
```

### 4.6 不需要修改的文件

| 文件 | 原因 |
|------|------|
| `core/downloader.py` | `_make_request` 已线程安全（Session + RateLimiter 都有锁），`threading.local()` 会自动继承 worker_id |
| `core/pagination_executor.py` | 无状态组件，每次 `execute()` 独立运行于调用线程，自然继承调用者的 worker_id/task_id |
| `core/pagination.py` | 纯计算，无线程安全问题 |
| `core/coverage_manager.py` | 只读操作，多线程安全 |
| `core/context.py` | 数据类，无线程安全问题 |

## 5. 数据流图（改造后）

```
                      ┌─ Worker W-01 ──────────────────────────┐
                      │  set_worker_id("W-01")                 │
                      │  task_id = "T-income_vip-a3b2c1"       │
                      │  update_interface("income_vip", ...)   │
main thread           │    └─ PaginationExecutor.execute()     │
  UpdateManager       │         └─ _make_request() [W-01 日志] │
  .run_update()  ─────│         └─ save_callback() ──────┐     │
  ThreadPoolExecutor  │                                   │     │
  (max_workers=3)     └──────────────────────────────────│─────┘
                      ┌─ Worker W-02 ─────────────────────│─────┐
                      │  task_id = "T-balancesheet-f4e5d6" │     │
                      │  ...同上流程...                     │     │
                      └──────────────────────────────────│─────┘
                      ┌─ Worker W-03 ─────────────────────│─────┐
                      │  task_id = "T-cashflow-c7d8e9"    │     │
                      │  ...同上流程...                     │     │
                      └──────────────────────────────────│─────┘
                                                          │
                                                          ▼
                                         ┌─ SW-process Thread ─┐
                                         │  去重 → 验证 → 队列  │
                                         └──────────┬──────────┘
                                                    ▼
                                         ┌─ SW-writer Thread ──┐
                                         │  写入 Parquet 文件    │
                                         └─────────────────────┘
```

## 6. 日志效果示例

### 6.1 并发下载日志

```
2026-03-05 10:00:00 [MAIN][-] update_manager - INFO - 开始增量更新，3 个接口，使用 3 个 worker
2026-03-05 10:00:01 [W-01][T-income_vip-a3b2c1] update_manager - INFO - 开始处理接口: income_vip
2026-03-05 10:00:01 [W-02][T-balancesheet-f4e5d6] update_manager - INFO - 开始处理接口: balancesheet_vip
2026-03-05 10:00:01 [W-03][T-cashflow-c7d8e9] update_manager - INFO - 开始处理接口: cashflow_vip
2026-03-05 10:00:02 [W-01][T-income_vip-a3b2c1] pagination_executor - INFO - [income_vip] Saved 500 records for period 20240331
2026-03-05 10:00:02 [SW-process][-] storage - INFO - Processed 500 records for income_vip
2026-03-05 10:00:03 [W-02][T-balancesheet-f4e5d6] downloader - DEBUG - Making POST request to api.tushare.pro for balancesheet_vip (attempt 1)
2026-03-05 10:00:03 [SW-writer][-] storage - INFO - Wrote 500 records to data/income_vip/income_vip_20240101_20240331_xxx.parquet
2026-03-05 10:00:05 [W-01][T-income_vip-a3b2c1] update_manager - INFO - 接口 income_vip 更新完成，共 2000 条记录
2026-03-05 10:00:05 [W-01][T-fina_indicator-b1c2d3] update_manager - INFO - 开始处理接口: fina_indicator_vip
```

### 6.2 问题追溯示例

如果某个请求失败，可以通过 task_id 快速过滤日志：

```bash
# 追踪某个接口任务的完整生命周期
grep "T-income_vip-a3b2c1" app4.log

# 查看某个 worker 的所有活动
grep "W-01" app4.log

# 查看存储层的处理情况
grep "SW-" app4.log
```

## 7. 风险评估

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| API 限流被多 worker 突破 | 被 ban IP | 低 | `RateLimiter` 是全局共享的，内部有锁，多线程仍然受限。250 req/min 的总限制不变 |
| 存储线程成为瓶颈 | 数据积压 | 中 | `process_queue` 已有 `maxsize=20` 的反压机制。如果积压严重，worker 线程会在 `save_data` / `add_to_buffer` 时阻塞 |
| checkpoint 数据竞争 | 断点信息丢失 | 高（无锁时） | 方案中已加 `threading.Lock` 保护 |
| reporter 数据竞争 | 报告数据不一致 | 高（无锁时） | 方案中已加 `threading.Lock` 保护 |
| 日志交叉难以阅读 | 调试困难 | 中 | worker_id + task_id 标识使得 `grep` 过滤变得简单 |
| 单接口内的 period_range 仍是串行 | 无法加速单接口 | N/A | 本方案只解决**接口间并发**，单接口内部逻辑不变。如果需要单接口内也并发，需另外设计 |

## 8. 配置建议

```yaml
# settings.yaml 新增
update:
  max_workers: 3              # 建议 3-4，因为全局 rate_limit=250/min
                               # 3 个 worker 每个约 83 req/min，合理分配
```

**推荐值**:
- `period_range` 组（11 个接口）: `--update-workers 3`
- `reverse_date_range` 组（20 个接口）: `--update-workers 4`
- 全量更新: `--update-workers 3`（因为 rate_limit 限制）

## 9. 改动文件汇总

| 文件 | 改动类型 | 改动量 | 说明 |
|------|---------|--------|------|
| `core/trace.py` | **新增** | ~50 行 | worker_id/task_id 管理 + 日志 Filter |
| `main.py` | 修改 | ~15 行 | 日志格式、CLI 参数、options 传递 |
| `update/update_manager.py` | 修改 | ~80 行 | 并发执行逻辑 + 锁 |
| `core/storage.py` | 修改 | ~15 行 | 存储线程设置 worker_id |
| **总计** | | **~160 行** | |

## 10. 验证计划

### 10.1 手动测试

```bash
# 1. 串行模式（默认，验证向后兼容）
/root/miniforge3/envs/get/bin/python app4/main.py --update \
  --update-group period_range \
  --start_date 20250101 --end_date 20250131

# 验证：日志中应显示 [MAIN] 前缀，行为与改动前一致

# 2. 并发模式（3 个 worker）
/root/miniforge3/envs/get/bin/python app4/main.py --update \
  --update-group period_range \
  --update-workers 3 \
  --start_date 20250101 --end_date 20250131

# 验证：
# - 日志中应出现 [W-01], [W-02], [W-03] 前缀
# - 同一时间应有多个接口在下载
# - 每个接口有唯一的 [T-xxx] task_id
# - 存储线程日志显示 [SW-process], [SW-writer]
# - 数据最终写入正确，文件数量与串行模式一致

# 3. 日志追踪测试
grep "W-01" log/app4.log   # 应只看到 worker 1 的活动
grep "T-income_vip" log/app4.log  # 应看到该接口的完整生命周期
grep "SW-" log/app4.log    # 应看到存储线程的活动
```

### 10.2 建议用户手动验证的点

1. **数据正确性**: 并发模式下载的数据文件数量和内容应与串行模式**一致**
2. **性能提升**: 并发模式下总耗时应明显低于串行模式（理想情况下约为 `串行时间 / worker数`，受限于 rate_limit）
3. **报告完整性**: 更新报告中应包含所有接口的结果

> **注意**: 由于项目无现有的单元测试文件（只有编译后的 `.pyc` 缓存），本方案不新增自动化测试。如需要可后续补充。
