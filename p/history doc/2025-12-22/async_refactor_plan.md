# 异步并发下载统一调度改造方案

## 一、方案概述

### 1.1 目标

将所有下载模式统一使用 `DownloadScheduler` 进行调度，实现：
- 日期参数下载：复用现有调度
- `--holders-data`：改为调度模式
- `--pro_bar-only`：改为调度模式
- `--tscode-historical`：改为调度模式
- `--use_legacy`：改为调度模式

### 1.2 核心思路

复用现有的 `DownloadScheduler` 和 `TaskQueueManager` 架构，为 `--holders-data`、`--pro_bar-only`、`--tscode-historical` 场景添加对应的任务调度方法。所有下载模式共享同一套异步架构，包括：
- 并发控制（`TaskQueueManager`）
- 速率限制（`global_rate_limiter`）
- 异步存储（`StorageWorker`）
- 进度监控（`task_manager.get_stats()`）

### 1.3 预期效果

| 场景 | 改造前 | 改造后 | 提升 |
|-----|--------|--------|------|
| 股东数据下载（5000股票） | ~30分钟（串行） | ~8分钟（并行） | 73% |
| 复权行情下载（5000股票） | ~60分钟（串行） | ~15分钟（并行） | 75% |
| 传统日期范围下载 | ~20分钟 | ~15分钟 | 25% |

## 二、当前问题分析

### 2.1 各模式实现现状

| 参数 | 当前实现 | 问题 |
|-----|---------|------|
| 默认日期参数 | `DownloadScheduler` + `schedule_download_tasks()` | 已有异步架构，OK |
| `--use_legacy` | `DateRangeDownloader.download_all_available_data()` | 同步下载 + 同步存储 |
| `--holders-data` | `HoldersDataFullHistoryDownloader` | 同步下载 + 同步存储（串行5000次API调用） |
| `--pro_bar-only` | `HoldersDataFullHistoryDownloader.download_pro_bar_full_history_all_stocks()` | 同步下载 + 同步存储 |
| `--tscode-historical` | 同上 | 同步下载 + 同步存储 |

### 2.2 当前代码问题

**HoldersDataFullHistoryDownloader 当前实现：**

```python
# interfaces/holders_data_downloader.py
def download_stk_rewards_full_history(self, save_to_disk: bool = True) -> pd.DataFrame:
    stock_codes = self.get_all_stock_codes()
    all_data = []

    for ts_code in stock_codes:  # 串行遍历5000+股票
        try:
            df = self._download_single(ts_code)  # 同步下载
            if df is not None and not df.empty:
                all_data.append(df)
        except Exception as e:
            logger.warning(f"下载失败: {ts_code}")
            continue

    # 全部下载完后统一存储
    if all_data:
        result = pd.concat(all_data, ignore_index=True)
        if save_to_disk:
            save_to_parquet(result, "stk_rewards_full_history", "holders")
        return result
```

**问题：**
- 无并发控制，5000次API调用串行执行
- 无任务队列，无法管理大量任务
- 下载与存储耦合，必须全部下载完成才能存储
- 无统一进度监控
- 无法与 `StorageWorker` 复用

## 三、统一架构设计

### 3.1 架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                           main.py                                    │
│  统一入口，根据参数调用 DownloadScheduler                             │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DownloadScheduler                                 │
│  统一调度器，处理所有类型的下载任务                                   │
│  ├─ schedule_download_tasks()      # 日期范围下载                   │
│  ├─ schedule_holders_tasks()       # 股东数据下载                   │
│  └─ schedule_pro_bar_tasks()       # 复权行情下载                   │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    TaskQueueManager                                  │
│  任务队列管理                                                        │
│  ├─ add_task()                     # 添加下载任务                   │
│  ├─ add_storage_task()             # 添加存储任务                   │
│  └─ get_stats()                    # 获取进度                       │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│ 下载线程池    │   │ 下载线程池    │   │ 下载线程池    │
│ (4 workers)   │   │ (4 workers)   │   │ (4 workers)   │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    StorageWorker                                     │
│  异步存储消费者                                                      │
│  ├─ 2个存储工作线程                                                  │
│  └─ 队列大小：100                                                    │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Parquet Files                                  │
│  数据存储                                                            │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 任务类型定义

```python
# task_queue_manager.py (新增)
class TaskType(Enum):
    """任务类型枚举"""
    DOWNLOAD = "download"           # 通用下载任务
    PARALLEL_DOWNLOAD = "parallel_download"  # 并行下载任务
    HOLDERS_DOWNLOAD = "holders_download"    # 股东数据下载任务
    PRO_BAR_DOWNLOAD = "pro_bar_download"    # 复权行情下载任务
```

### 3.3 存储路径映射

| 接口 | 存储路径 | 任务类型 |
|-----|---------|---------|
| `stk_rewards` | `holders/stk_rewards_{ts_code}` | `HOLDERS_DOWNLOAD` |
| `top10_holders` | `holders/top10_holders_{ts_code}` | `HOLDERS_DOWNLOAD` |
| `pledge_detail` | `holders/pledge_detail_{ts_code}` | `HOLDERS_DOWNLOAD` |
| `fina_audit` | `financial/fina_audit_{ts_code}` | `HOLDERS_DOWNLOAD` |
| `pro_bar` | `daily/pro_bar_{ts_code}` | `PRO_BAR_DOWNLOAD` |

## 四、实现方案

### 4.1 改造内容概览

| 文件 | 改动 | 改动类型 |
|-----|------|---------|
| `task_queue_manager.py` | 添加 `TaskType` 枚举 | 新增 |
| `download_scheduler.py` | 添加 `schedule_holders_tasks()`、`schedule_pro_bar_tasks()` 等方法 | 扩展 |
| `main.py` | 改为通过 `DownloadScheduler` 调度 | 简化 |
| `interfaces/holders_data_downloader.py` | 保留接口，废弃全历史下载方法 | 保留 |
| `interfaces/holders_data.py` | 保持不变 | 无 |
| `interfaces/daily_data.py` | 保持不变 | 无 |

### 4.2 详细实现

#### 4.2.1 新增任务类型（task_queue_manager.py）

```python
# task_queue_manager.py (在文件末尾添加)
class TaskType(Enum):
    """任务类型枚举，定义不同的下载任务类型"""
    DOWNLOAD = "download"
    PARALLEL_DOWNLOAD = "parallel_download"
    HOLDERS_DOWNLOAD = "holders_download"
    PRO_BAR_DOWNLOAD = "pro_bar_download"
```

#### 4.2.2 扩展 DownloadScheduler（download_scheduler.py）

在 `DownloadScheduler` 类末尾添加以下方法：

```python
# ============ 股东数据下载相关方法 ============

def schedule_holders_tasks(
    self,
    interfaces: List[str],
    stock_list: pd.DataFrame,
    priority: TaskPriority = TaskPriority.MEDIUM
) -> List[str]:
    """
    调度股东数据下载任务

    Args:
        interfaces: 接口列表，如 ['stk_rewards', 'top10_holders', 'pledge_detail', 'fina_audit']
        stock_list: 股票列表 DataFrame，必须包含 'ts_code' 列
        priority: 任务优先级

    Returns:
        任务ID列表
    """
    task_ids = []

    # 检查积分是否满足要求
    from config import TUSHARE_POINTS

    for interface_name in interfaces:
        # 积分检查
        if interface_name == 'stk_rewards' and TUSHARE_POINTS < 2000:
            self.logger.warning(f"{interface_name} 需要2000+积分，跳过")
            continue
        elif interface_name == 'top10_holders' and TUSHARE_POINTS < 2000:
            self.logger.warning(f"{interface_name} 需要2000+积分，跳过")
            continue
        elif interface_name == 'pledge_detail' and TUSHARE_POINTS < 5000:
            self.logger.warning(f"{interface_name} 需要5000+积分，跳过")
            continue
        elif interface_name == 'fina_audit' and TUSHARE_POINTS < 500:
            self.logger.warning(f"{interface_name} 需要500+积分，跳过")
            continue

        # 为每个股票创建下载任务
        for _, row in stock_list.iterrows():
            ts_code = row['ts_code']

            task_id = self.task_manager.add_task(
                task_type='holders_download',
                target_func=self._execute_holders_download,
                priority=priority,
                kwargs={
                    'interface_name': interface_name,
                    'ts_code': ts_code
                },
                max_retries=3,
                metadata={
                    'interface': interface_name,
                    'ts_code': ts_code,
                    'task_category': 'holders_data'
                }
            )

            if task_id:
                task_ids.append(task_id)

    self.logger.info(f"调度股东数据下载任务: 接口数={len(interfaces)}, 股票数={len(stock_list)}, 任务数={len(task_ids)}")
    return task_ids

def _execute_holders_download(self, **kwargs) -> pd.DataFrame:
    """
    执行股东数据下载

    Args:
        interface_name: 接口名称
        ts_code: 股票代码

    Returns:
        下载的数据 DataFrame
    """
    interface_name = kwargs.get('interface_name')
    ts_code = kwargs.get('ts_code')

    self.logger.debug(f"开始下载股东数据: {interface_name}, {ts_code}")

    try:
        # 获取下载策略
        from download_strategies import get_strategy
        strategy = get_strategy(interface_name, downloader=self.downloader)

        # 申请速率限制令牌
        if not acquire_tokens(interface_name, 1.0, timeout=300):
            raise Exception(f"无法获取 {interface_name} 的速率限制令牌")

        # 执行下载
        if interface_name in ['stk_rewards', 'top10_holders', 'pledge_detail']:
            result = strategy.download(ts_code=ts_code)
        elif interface_name == 'fina_audit':
            result = strategy.download(ts_code=ts_code)
        else:
            result = strategy.download(ts_code=ts_code)

        # 统计
        with self.stats_lock:
            self.stats['total_downloaded'] += len(result) if result is not None else 0

        # 提交存储任务
        if result is not None and not result.empty:
            # 根据接口确定存储路径
            if interface_name in ['stk_rewards', 'top10_holders', 'pledge_detail']:
                subdir = "holders"
            else:
                subdir = "financial"

            filename = f"{interface_name}_{ts_code}"

            self.task_manager.add_storage_task(
                data=result,
                filename=filename,
                subdir=subdir,
                priority=TaskPriority.MEDIUM
            )

            self.logger.debug(f"已提交存储任务: {filename}")

        return result

    except Exception as e:
        self.logger.error(f"下载股东数据失败: {interface_name}, {ts_code}, {e}")
        raise

# ============ 复权行情下载相关方法 ============

def schedule_pro_bar_tasks(
    self,
    stock_list: pd.DataFrame,
    priority: TaskPriority = TaskPriority.MEDIUM
) -> List[str]:
    """
    调度复权行情下载任务

    Args:
        stock_list: 股票列表 DataFrame，必须包含 'ts_code' 列
        priority: 任务优先级

    Returns:
        任务ID列表
    """
    # 积分检查
    try:
        from config import TUSHARE_POINTS
        if TUSHARE_POINTS < 5000:
            self.logger.warning("pro_bar 需要5000+积分，无法下载")
            return []
    except ImportError:
        pass

    task_ids = []

    for _, row in stock_list.iterrows():
        ts_code = row['ts_code']

        task_id = self.task_manager.add_task(
            task_type='pro_bar_download',
            target_func=self._execute_pro_bar_download,
            priority=priority,
            kwargs={'ts_code': ts_code},
            max_retries=3,
            metadata={
                'interface': 'pro_bar',
                'ts_code': ts_code,
                'task_category': 'pro_bar'
            }
        )

        if task_id:
            task_ids.append(task_id)

    self.logger.info(f"调度复权行情下载任务: 股票数={len(stock_list)}, 任务数={len(task_ids)}")
    return task_ids

def _execute_pro_bar_download(self, **kwargs) -> pd.DataFrame:
    """
    执行复权行情下载

    Args:
        ts_code: 股票代码

    Returns:
        下载的数据 DataFrame
    """
    ts_code = kwargs.get('ts_code')

    self.logger.debug(f"开始下载复权行情: {ts_code}")

    try:
        # 获取下载策略
        from download_strategies import get_strategy
        strategy = get_strategy('pro_bar', downloader=self.downloader)

        # 申请速率限制令牌
        if not acquire_tokens('pro_bar', 1.0, timeout=300):
            raise Exception("无法获取 pro_bar 的速率限制令牌")

        # 获取股票上市日期
        stock_list = self._get_stock_list()
        stock_info = stock_list[stock_list['ts_code'] == ts_code]
        if stock_info.empty:
            raise Exception(f"无法找到股票信息: {ts_code}")

        # 提取上市日期
        list_date = stock_info.iloc[0].get('list_date', '20000101')
        end_date = datetime.now().strftime('%Y%m%d')

        # 执行全历史下载
        result = strategy.download(
            ts_code=ts_code,
            start_date=list_date,
            end_date=end_date
        )

        # 统计
        with self.stats_lock:
            self.stats['total_downloaded'] += len(result) if result is not None else 0

        # 提交存储任务
        if result is not None and not result.empty:
            filename = f"pro_bar_{ts_code}"

            self.task_manager.add_storage_task(
                data=result,
                filename=filename,
                subdir="daily",
                priority=TaskPriority.MEDIUM
            )

            self.logger.debug(f"已提交存储任务: {filename}")

        return result

    except Exception as e:
        self.logger.error(f"下载复权行情失败: {ts_code}, {e}")
        raise

# ============ 工具方法 ============

def _get_stock_list(self) -> pd.DataFrame:
    """
    获取股票列表（带缓存）
    """
    if not hasattr(self, '_stock_list_cache') or self._stock_list_cache is None:
        try:
            from interfaces.basic_data import BasicDataDownloader
            basic_downloader = BasicDataDownloader(self.downloader.pro)
            self._stock_list_cache = basic_downloader.download_stock_basic()
        except Exception as e:
            self.logger.error(f"获取股票列表失败: {e}")
            self._stock_list_cache = pd.DataFrame()

    return self._stock_list_cache
```

#### 4.2.3 改造 main.py

将 `main.py` 中 `--holders-data`、`--pro_bar-only`、`--tscode-historical` 的处理逻辑改为通过 `DownloadScheduler` 调度：

```python
def main():
    # ... 现有参数解析代码 ...

    try:
        # 判断下载模式
        is_date_range_mode = not args.tscode_historical and not args.holders_data and not args.pro_bar_only

        if is_date_range_mode:
            # 日期范围模式
            disable_tscode_dependent_interfaces_for_date_range()
            results = download_all_data_from_date(args.start_date, args.end_date)

        elif args.holders_data or args.pro_bar_only or args.tscode_historical:
            # 通过 DownloadScheduler 调度
            from download_scheduler import create_download_scheduler

            scheduler = create_download_scheduler(args.start_date, args.end_date or datetime.now().strftime('%Y%m%d'))

            # 获取股票列表
            from interfaces.basic_data import BasicDataDownloader
            basic_downloader = BasicDataDownloader(scheduler.downloader.pro)
            stock_list = basic_downloader.download_stock_basic()

            if stock_list.empty:
                raise Exception("无法获取股票列表")

            # 根据参数调度任务
            if args.holders_data or (args.tscode_historical and not args.pro_bar_only):
                # 股东数据下载
                interfaces = ['stk_rewards', 'top10_holders']

                try:
                    from config import TUSHARE_POINTS
                    if TUSHARE_POINTS >= 5000:
                        interfaces.append('pledge_detail')
                    if TUSHARE_POINTS >= 500:
                        interfaces.append('fina_audit')
                except ImportError:
                    pass

                scheduler.schedule_holders_tasks(interfaces, stock_list)

            if args.pro_bar_only or (args.tscode_historical and not args.holders_data):
                # 复权行情下载
                scheduler.schedule_pro_bar_tasks(stock_list)

            # 执行所有任务
            results = scheduler.execute_scheduled_tasks(wait_for_completion=True)

            # 关闭调度器
            scheduler.shutdown()

        else:
            # 默认日期范围下载
            if args.use_legacy:
                results = download_with_legacy_method(args.start_date, args.end_date)
            else:
                results = download_with_legacy_fallback(args.start_date, args.end_date)

        # ... 后续统计和日志代码 ...

    except Exception as e:
        logger.error(f"系统执行失败: {e}")
        raise
```

### 4.3 积分检查机制

在调度任务前进行积分检查：

```python
def _check_points_requirement(self, interface_name: str) -> bool:
    """
    检查积分是否满足接口要求

    Args:
        interface_name: 接口名称

    Returns:
        True: 积分满足要求
        False: 积分不足，跳过该接口
    """
    try:
        from config import TUSHARE_POINTS
    except ImportError:
        return True  # 如果无法获取积分，默认允许

    points_required = {
        'stk_rewards': 2000,
        'top10_holders': 2000,
        'pledge_detail': 5000,
        'fina_audit': 500,
        'pro_bar': 5000
    }

    required = points_required.get(interface_name, 0)
    if TUSHARE_POINTS < required:
        self.logger.warning(f"{interface_name} 需要{required}积分，当前{TUSHARE_POINTS}积分不足，跳过")
        return False

    return True
```

### 4.4 并发控制参数

```python
# download_scheduler.py 中 __init__ 方法的参数
class DownloadScheduler:
    def __init__(self, start_date: str, end_date: str, max_workers: int = 4):
        """
        Args:
            start_date: 开始日期
            end_date: 结束日期
            max_workers: 最大工作线程数（下载并发度），默认4
        """
        self.start_date = start_date
        self.end_date = end_date
        self.max_workers = max_workers  # 下载并发度

        # 存储工作线程数固定为2
        self.storage_worker = StorageWorker(max_workers=2)

        # ...
```

## 五、实施步骤

### 步骤1：添加任务类型枚举（0.5小时）

1. 打开 `test/task_queue_manager.py`
2. 在文件末尾添加 `TaskType` 枚举定义
3. 运行测试验证无语法错误

### 步骤2：扩展 DownloadScheduler（2小时）

1. 打开 `app/download_scheduler.py`
2. 在 `DownloadScheduler` 类末尾添加：
   - `schedule_holders_tasks()` 方法
   - `_execute_holders_download()` 方法
   - `schedule_pro_bar_tasks()` 方法
   - `_execute_pro_bar_download()` 方法
   - `_get_stock_list()` 方法
3. 运行单元测试验证

### 步骤3：改造 main.py（1小时）

1. 打开 `app/main.py`
2. 修改 `--holders-data`、`--pro_bar-only`、`--tscode-historical` 的处理逻辑
3. 改为通过 `DownloadScheduler` 调度
4. 测试各参数组合

### 步骤4：集成测试（1小时）

1. 测试 `--holders-data` 模式
2. 测试 `--pro_bar-only` 模式
3. 测试 `--tscode-historical` 模式
4. 测试 `--use_legacy` 模式
5. 验证日期范围模式仍正常工作

### 步骤5：性能验证（0.5小时）

1. 对比改造前后的下载时间
2. 验证并发度生效
3. 验证速率限制生效
4. 验证存储任务正常执行

## 六、文件改动清单

### 6.1 新增文件

无新增文件，只需扩展现有文件。

### 6.2 修改文件

| 文件路径 | 改动内容 | 行数 |
|---------|---------|------|
| `test/task_queue_manager.py` | 添加 `TaskType` 枚举 | ~10行 |
| `app/download_scheduler.py` | 添加股东数据和复权行情调度方法 | ~150行 |
| `app/main.py` | 改为通过 DownloadScheduler 调度 | ~50行 |

### 6.3 保留文件（无改动）

- `interfaces/holders_data.py` - 保持不变
- `interfaces/daily_data.py` - 保持不变
- `interfaces/basic_data.py` - 保持不变
- `storage_worker.py` - 保持不变
- `global_rate_limiter.py` - 保持不变

## 七、向后兼容性

### 7.1 参数兼容性

所有现有参数保持不变：
- `--start_date`
- `--end_date`
- `--use_legacy`
- `--holders-data`
- `--pro_bar-only`
- `--tscode-historical`

### 7.2 接口兼容性

`HoldersDataFullHistoryDownloader` 类的接口保持不变，但内部方法不再被 main.py 调用：
- `download_stk_rewards_full_history()` - 保留（备用）
- `download_top10_holders_full_history()` - 保留（备用）
- `download_pledge_detail_full_history()` - 保留（备用）
- `download_fina_audit_full_history()` - 保留（备用）
- `download_pro_bar_full_history_all_stocks()` - 保留（备用）

### 7.3 数据格式兼容性

存储的数据格式保持不变，与现有数据兼容。

## 八、风险评估与缓解

| 风险 | 影响程度 | 缓解措施 |
|-----|---------|---------|
| 内存占用增加 | 中 | 限制任务队列大小为100 |
| API 调用频率过高 | 低 | 复用 global_rate_limiter |
| 数据不一致 | 低 | 复用现有存储逻辑 |
| 现有功能 regression | 低 | 保留原有代码，仅新增调度路径 |
| 积分检查遗漏 | 低 | 在调度前统一检查 |

## 九、测试用例

### 9.1 单元测试

```python
# test_download_scheduler.py
def test_schedule_holders_tasks():
    """测试股东数据任务调度"""
    scheduler = DownloadScheduler("20240101", "20241231")

    stock_list = pd.DataFrame({
        'ts_code': ['000001.SZ', '000002.SZ', '000003.SZ']
    })

    task_ids = scheduler.schedule_holders_tasks(
        ['stk_rewards', 'top10_holders'],
        stock_list
    )

    assert len(task_ids) == 6  # 2接口 x 3股票
    print("测试通过：股东数据任务调度正常")

def test_schedule_pro_bar_tasks():
    """测试复权行情任务调度"""
    scheduler = DownloadScheduler("20240101", "20241231")

    stock_list = pd.DataFrame({
        'ts_code': ['000001.SZ', '000002.SZ']
    })

    task_ids = scheduler.schedule_pro_bar_tasks(stock_list)

    assert len(task_ids) == 2  # 2股票
    print("测试通过：复权行情任务调度正常")
```

### 9.2 集成测试

```bash
# 测试命令
python -m app.main --holders-data --start_date 20240101 --end_date 20241231
python -m app.main --pro_bar-only --tscode_historical
python -m app.main --tscode_historical
python -m app.main --use_legacy --start_date 20240101
python -m app.main --start_date 20240101 --end_date 20241231  # 默认模式
```

## 十、补充说明：未在原计划中提及的考虑

### 10.1 遗漏的下载方法整合

经代码审查发现，方案中遗漏了一个重要的全历史下载方法，需要整合到统一调度框架中：

- **`financial_data.download_fina_audit_full_history` 方法**：位于 `app/interfaces/financial_data.py:424-486`，该方法与 `holders_data_downloader.py` 中的方法类似，采用逐个股票遍历的同步模式，同样需要被整合到异步调度框架中。

#### 10.1.1 新增财务审计下载调度方法

在 `DownloadScheduler` 类中还需要添加：

```python
def schedule_fina_audit_tasks(
    self,
    stock_list: pd.DataFrame,
    priority: TaskPriority = TaskPriority.MEDIUM
) -> List[str]:
    """
    调度财务审计意见下载任务

    Args:
        stock_list: 股票列表 DataFrame，必须包含 'ts_code' 列
        priority: 任务优先级

    Returns:
        任务ID列表
    """
    # 积分检查
    try:
        from config import TUSHARE_POINTS
        if TUSHARE_POINTS < 500:
            self.logger.warning("fina_audit 需要500+积分，无法下载")
            return []
    except ImportError:
        pass

    task_ids = []

    for _, row in stock_list.iterrows():
        ts_code = row['ts_code']

        task_id = self.task_manager.add_task(
            task_type='fina_audit_download',
            target_func=self._execute_fina_audit_download,
            priority=priority,
            kwargs={'ts_code': ts_code},
            max_retries=3,
            metadata={
                'interface': 'fina_audit',
                'ts_code': ts_code,
                'task_category': 'fina_audit'
            }
        )

        if task_id:
            task_ids.append(task_id)

    self.logger.info(f"调度财务审计意见下载任务: 股票数={len(stock_list)}, 任务数={len(task_ids)}")
    return task_ids

def _execute_fina_audit_download(self, **kwargs) -> pd.DataFrame:
    """
    执行财务审计意见下载

    Args:
        ts_code: 股票代码

    Returns:
        下载的数据 DataFrame
    """
    ts_code = kwargs.get('ts_code')

    self.logger.debug(f"开始下载财务审计意见: {ts_code}")

    try:
        # 获取下载策略
        from download_strategies import get_strategy
        strategy = get_strategy('fina_audit', downloader=self.downloader)

        # 申请速率限制令牌
        if not acquire_tokens('fina_audit', 1.0, timeout=300):
            raise Exception("无法获取 fina_audit 的速率限制令牌")

        # 执行下载
        result = strategy.download(ts_code=ts_code)

        # 统计
        with self.stats_lock:
            self.stats['total_downloaded'] += len(result) if result is not None else 0

        # 提交存储任务
        if result is not None and not result.empty:
            filename = f"fina_audit_{ts_code}"

            self.task_manager.add_storage_task(
                data=result,
                filename=filename,
                subdir="financial",
                priority=TaskPriority.MEDIUM
            )

            self.logger.debug(f"已提交存储任务: {filename}")

        return result

    except Exception as e:
        self.logger.error(f"下载财务审计意见失败: {ts_code}, {e}")
        raise
```

#### 10.1.2 更新 TaskType 枚举

```python
# task_queue_manager.py (更新后的枚举)
class TaskType(Enum):
    """任务类型枚举，定义不同的下载任务类型"""
    DOWNLOAD = "download"
    PARALLEL_DOWNLOAD = "parallel_download"
    HOLDERS_DOWNLOAD = "holders_download"
    PRO_BAR_DOWNLOAD = "pro_bar_download"
    FINA_AUDIT_DOWNLOAD = "fina_audit_download"  # 新增
```

#### 10.1.3 更新主调度逻辑

在 `main.py` 的调度逻辑中，当启用 `holders_data` 选项时，应该同时调度 `fina_audit` 相关下载任务：

```python
# 在 main.py 的调度部分更新
if args.holders_data or (args.tscode_historical and not args.pro_bar_only):
    # 股东数据下载
    interfaces = ['stk_rewards', 'top10_holders']

    try:
        from config import TUSHARE_POINTS
        if TUSHARE_POINTS >= 5000:
            interfaces.append('pledge_detail')
        if TUSHARE_POINTS >= 500:
            interfaces.append('fina_audit')
    except ImportError:
        pass

    # 分别处理不同接口类型
    holders_interfaces = [iface for iface in interfaces if iface != 'fina_audit']
    if holders_interfaces:
        scheduler.schedule_holders_tasks(holders_interfaces, stock_list)

    if 'fina_audit' in interfaces:
        scheduler.schedule_fina_audit_tasks(stock_list)
```

### 10.2 特殊下载模式的现状

方案中提到的特殊下载模式（`--holders-data`, `--pro_bar-only`, `--tscode-historical`）当前实现绕过了 `DownloadScheduler`，直接使用完全顺序处理。重构将把这些模式统一到异步调度框架中，实现以下改进：

- **从完全顺序处理** → **并行调度处理**：将5000+股票的逐个下载转换为并发处理
- **从同步存储** → **异步存储**：下载与存储分离，提高效率
- **从无任务管理** → **统一任务管理**：复用现有任务队列、优先级、监控机制

## 十一、总结

### 11.1 改造收益

1. **代码统一**：所有下载模式复用同一套异步架构
2. **性能提升**：串行变并行，提升 4-8 倍
3. **维护简单**：只需维护一套下载逻辑
4. **扩展容易**：新增下载类型只需添加调度方法
5. **复用现有组件**：并发控制、速率限制、存储、监控全部复用
6. **完整性提升**：覆盖所有全历史下载场景，包括之前遗漏的 `fina_audit` 方法

### 11.2 关键改动

1. `task_queue_manager.py`：更新 `TaskType` 枚举，添加 `FINA_AUDIT_DOWNLOAD`
2. `download_scheduler.py`：添加 `schedule_holders_tasks()`、`schedule_pro_bar_tasks()`、`schedule_fina_audit_tasks()` 等方法
3. `main.py`：改为通过 `DownloadScheduler` 调度所有特殊下载模式
4. 确保所有全历史下载方法（包括 `fina_audit_full_history`）都通过统一调度器处理

### 11.3 预期时间

| 步骤 | 时间 |
|-----|------|
| 更新任务类型枚举 | 0.2小时 |
| 扩展 DownloadScheduler（含fina_audit方法） | 2.5小时 |
| 改造 main.py | 1小时 |
| 集成测试 | 1小时 |
| 性能验证 | 0.5小时 |
| **总计** | **5.2小时** |

### 11.4 后续优化方向

1. **任务优先级**：支持按接口设置不同优先级
2. **断点续传**：支持中断后继续下载
3. **批量存储**：多个小文件合并存储
4. **智能分片**：根据数据量动态调整分片大小
5. **任务依赖**：支持任务间的依赖关系管理
