# Storage Process Worker 退出问题修复完善方案

## 之前方案的不足（只有 `while True` 的缺陷）
1. **数据可能丢失 (Queue Full)**: 在 `flush_remaining_data` 中，它使用了 `block=False` 来将剩余数据塞入 `process_queue`。如果队列满（`maxsize=20`），直接抛出 `queue.Full` 异常并且将最后的数据丢弃了。
2. **潜在死循环卡死 (`stop_writer` hang)**: 在 `stop_writer` 中，主线程会死等 `while not self.process_queue.empty(): time.sleep(0.1)`。如果 `process_thread` 在某些情况下遇到未知异常中途崩溃退出了（`is_alive() == False`），主线程会**永远卡在这里**，因为没人消费队列，它永远不会变为 empty。
3. **并发写入的数据丢失重排**: 在 `stop_writer` 执行期间（等待 empty 然后放置 None），如果有尚未结束的下载协程或线程仍然调用 `save_data`，它仍然会将数据通过 `add_to_buffer` 追加。如果数据追加在了哨兵 `None` 之后，`_process_worker` 接到 `None` 就直接 `break` 退出，导致 `None` 后面的数据被永远遗弃在 `process_queue` 中；而在 `_writer_worker` 中，也有可能遇到收到哨兵后依然有异步数据推入的情况。
4. **状态判断缺失**: `save_data` 中完全没有判断 `self.running` 的状态，即使系统正在 shutdown 也在不断接纳数据。

## 完善修复方案设计

我们需要对 `app4/core/storage.py` 中的以下部分进行系统性重构与修复：

### 1. 安全的数据冲刷与处理线程优雅退出
-修改 `flush_remaining_data`：不应该使用 `block=False`，而应该用循环尝试并增加超时跳过，或者用能阻塞的方式插入。因为是在执行 Shutdown 操作，必须使用带合理的 timeout 避免无限阻塞。
-改进 `stop_writer` 的死等逻辑：
```python
logger.info("Waiting for process queue to empty...")
wait_timeout = 60
start_wait = time.time()
while not self.process_queue.empty():
    if not self.process_thread.is_alive():
        logger.error("Process thread died unexpectedly while waiting for queue to empty")
        break
    if time.time() - start_wait > wait_timeout:
        logger.error("Timeout waiting for process queue to empty")
        break
    time.sleep(0.1)
```

### 2. 改进 `_process_worker` 对哨兵的消费，严密处理尾部追加数据
与 `_writer_worker` 类似，在 `_process_worker` 碰到 `task is None` 时不能直接退出，而应该把当前能在队列中获取到的非 `None` 元素全部**兜底处理**（drain the queue）再退出，防止最后微小的时间差由于并发导致数据遗漏。
在 `_process_worker` 内部维护一个 `pending_stop` 变量：
```python
        pending_stop = False
        while True:
            try:
                task = self.process_queue.get(timeout=1)
                if task is None:
                    pending_stop = True
                
                # 如果拿到正常的任务，照常处理
                if task is not None:
                    # 原有的处理逻辑 (去重，存入 data_queue 等)
                    pass

                # 处理完当前任务后，如果正处于停止阶段，检查队列是否真正空了
                if pending_stop and self.process_queue.empty():
                    # 退出前输出统计
                    ...
                    break

            except queue.Empty:
                if pending_stop:
                    break
                continue
```

### 3. 在入口处防止 shutdown 后的脏写
在 `save_data` 的开头应该检查:
```python
if not self.running:
    # 既然此时 storage process worker 可能已经即将退出，我们不该继续推进队列。
    # 根据系统的约定，要么报错，要么回退为同步写盘（直接调用 _write_interface_data）。
    logger.warning("Storage is stopping, falling back to sync write")
    self._write_interface_data(interface_name, data_records)
    return
```
这能从源头阻断在 `stop_writer` 后还有杂波并发请求进入 queue 导致难以预测的状态。

### 4. 改进 `_writer_worker`
配合上述的修改，如果前端的 `process_worker` 等所有上游线程已经安全关闭，`_writer_worker` 也要有一个类似超时的机制或者强壮的死循环退出机制避免异常假死。

## 代码修改计划

1. `app4/core/storage.py:141` -> `stop_writer()` 中增加对 `is_alive()` 与 `timeout` 的检查。
2. `app4/core/storage.py:575` -> `flush_remaining_data()` 改用安全的阻塞塞入或者循环安全重试。
3. `app4/core/storage.py:588` -> `_process_worker()` 重构其主循环，支持 `pending_stop` 时也能排空剩余任务。
4. `app4/core/storage.py:821` -> `save_data()` 入口加校验，降级为同步直写（在非 running 时）。
