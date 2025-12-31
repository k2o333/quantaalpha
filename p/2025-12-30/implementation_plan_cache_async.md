# App4 性能优化实施方案：激活缓存与异步并发

本方案基于对现状的深入分析，采用**最小化修改**原则，旨在通过激活现有代码中被禁用的缓存功能，并利用已有的调度器实现股票级并发下载，从而大幅提升数据获取效率。

## 1. 核心目标

1.  **激活缓存**：移除 `downloader.py` 中的调试代码，使业务数据缓存生效。
2.  **原子写入**：优化 `CacheManager`，确保多线程环境下缓存写入的安全性。
3.  **异步并发**：重构 `stock_loop` 模式的下载逻辑，利用 `TaskScheduler` 实现多只股票并发下载。

## 2. 实施步骤详解

### 步骤 1：激活业务数据缓存

**目标文件**：`app4/core/downloader.py`

**现状**：
代码中存在人为设置的 `cached_data = None`，导致缓存逻辑被跳过。

**修改操作**：
1.  移除或注释掉第 55 行附近的调试代码。
2.  启用缓存读取逻辑。
3.  在缓存写入处添加日志，便于观察。

```python
# 修改前
cache_key = self._generate_cache_key(interface_name, params)
cached_data = None  # <--- 问题所在
if cached_data is not None:
    return cached_data

# 修改后
cache_key = self._generate_cache_key(interface_name, params)
cached_data = self.cache_manager.get(cache_key) # <--- 恢复读取
if cached_data is not None:
    logger.info(f"Cache hit for {interface_name} with key: {cache_key}")
    return cached_data
```

### 步骤 2：确保缓存写入的线程安全 (Atomic Write)

**目标文件**：`app4/core/cache_manager.py`

**现状**：
直接写入目标 Parquet 文件。在并发下载场景下，如果多个线程尝试操作相关文件（虽概率较低，但需防范），或写入中途程序中断，可能导致文件损坏。

**修改操作**：
修改 `set` 方法，采用“写入临时文件 -> 原子重命名”的策略。

```python
def set(self, key: str, data: Any, ttl: Optional[int] = None) -> bool:
    # ... 前置代码 ...
    cache_path = self._get_cache_path(key)
    temp_path = cache_path + f".tmp.{os.getpid()}.{threading.get_ident()}" # 确保临时文件名唯一

    try:
        # 1. 写入临时文件
        if isinstance(data, list):
            pl.DataFrame(data).write_parquet(temp_path)
        # ... 其他类型处理 ...
        
        # 2. 原子替换
        os.replace(temp_path, cache_path)
        return True
    except Exception as e:
        # 清理残余
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False
```

### 步骤 3：实现股票级并发下载

**目标文件 1**：`app4/core/downloader.py`

**操作**：提取单只股票下载逻辑为独立方法，供 Scheduler 调用。

```python
def download_single_stock(self, interface_config: Dict, params: Dict) -> List[Dict]:
    """提取出的原子化下载方法"""
    # 1. 检查缓存
    # 2. 执行 date_range_pagination
    # 3. 写入缓存
    # ... (逻辑源自原 _execute_stock_loop_pagination 内部循环)
    pass
```

**目标文件 2**：`app4/main.py`

**操作**：
在主流程中识别 `stock_loop` 分页模式，转入并发处理流程。

```python
# 伪代码逻辑
if pagination_mode == 'stock_loop':
    # 并发路径
    _run_concurrent_stock_download(downloader, scheduler, ...)
else:
    # 原有同步路径
    downloader.download(...)
```

**辅助函数 `_run_concurrent_stock_download`**：
1.  获取股票列表（利用 CacheManager）。
2.  将股票列表分批（Batch）。
3.  构建任务列表，提交给 `scheduler.submit_tasks`。
4.  收集结果并合并。

## 3. 验证计划

### 验证场景 A：缓存激活验证
1.  运行命令：`python main.py --pro-bar-only --start_date 20240101 --end_date 20240105`
2.  检查日志，确认数据已下载并写入缓存。
3.  **再次运行相同命令**。
4.  预期结果：日志显示 "Cache hit"，且运行瞬间完成，无需网络请求。

### 验证场景 B：并发加速验证
1.  运行命令：`python main.py --pro-bar-only --start_date 20240101 --end_date 20240201 --concurrency 8`
2.  观察日志：应看到多个线程交替输出 "Downloading..." 日志。
3.  对比测试：记录 50 只股票的下载时间，对比优化前（串行）与优化后（并发）的耗时。预期应有 4-6 倍的速度提升。

### 验证场景 C：数据一致性
1.  对比并发下载生成的 Parquet 文件与串行下载的文件，记录数应完全一致。
2.  检查 Cache 目录，不应存在 `.tmp` 残留文件。

## 4. 回滚策略

如果出现严重 Bug：
1.  **关闭缓存**：在 `downloader.py` 中恢复 `cached_data = None`。
2.  **关闭并发**：在 `main.py` 中将 `concurrency` 设置为 1，或强制走同步路径。

---
*日期：2025-12-30*
*执行人：Gemini CLI Agent*
