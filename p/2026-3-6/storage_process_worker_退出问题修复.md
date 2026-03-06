# Storage Process Worker 退出问题修复

## 问题现象

运行 `python app4/main.py --update --update-group period_range` 下载完成后，Python 进程不退出，卡在最后阶段。

日志显示：
```
Waiting for process queue to empty...
Processed 8548 records for pledge_stat
...
Wrote 8548 records to /home/quan/testdata/aspipe_v4/data/pledge_stat/pledge_stat_20250930_20251231_1772735490128_3e2930d7.parquet
```

程序停在这里，没有后续的 "Stopping writer thread..." 日志，也没有正常退出。

---

## 根本原因

问题出在 `app4/core/storage.py` 的 `_process_worker` 线程中。

### 原代码逻辑

```python
def _process_worker(self):
    ...
    while self.running:  # 问题所在：用 running 标志控制循环
        try:
            task = self.process_queue.get(timeout=1)
            if task is None:
                ...
                break
            # 处理数据...
        except queue.Empty:
            continue  # 超时后继续循环
```

### `stop_writer()` 的执行顺序

```python
def stop_writer(self):
    if self.running:
        self.running = False  # 1. 先设置 running = False

        self.flush_remaining_data()  # 2. 将剩余数据放入 process_queue

        # 3. 等待队列清空
        while not self.process_queue.empty():
            time.sleep(0.1)  # <-- 卡在这里！

        self.process_queue.put(None)  # 4. 发送哨兵（永远执行不到）
        ...
```

### 竞态条件

1. `stop_writer()` 设置 `self.running = False`
2. `_process_worker` 线程在 `queue.get(timeout=1)` 超时后
3. 由于 `self.running` 已经是 `False`，`while self.running` 条件不满足
4. **线程直接退出**，不再消费队列中的数据
5. `stop_writer()` 中的 `while not self.process_queue.empty()` 永远等不到队列为空
6. **程序卡死**

---

## 修复方案

将 `_process_worker` 的循环条件从 `while self.running:` 改为 `while True:`，让线程**仅通过哨兵信号 (`None`) 退出**。

### 修复后代码

```python
def _process_worker(self):
    """处理线程：数据去重、验证、放入写入队列"""
    dedup_stats_total = {
        "total_processed": 0,
        "total_deduped": 0,
        "interfaces": set(),
    }

    while True:  # 修复：改用 while True，通过哨兵退出
        try:
            task = self.process_queue.get(timeout=1)

            # 检查停止信号
            if task is None:
                # 收到哨兵，处理完当前数据后退出
                ...
                break
            # 处理数据...
        except queue.Empty:
            continue  # 超时后继续等待
```

### 修复效果

1. 线程会持续消费队列中的数据
2. 只有收到哨兵信号 (`None`) 才会退出
3. `stop_writer()` 的执行顺序正确：
   - 先等待队列清空（线程仍在消费）
   - 队列清空后发送哨兵
   - 线程收到哨兵后退出

---

## 修改文件

- `app4/core/storage.py:588` - `_process_worker` 方法

---

## 日期

2026-03-06
