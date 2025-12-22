# 下载调度器任务执行缺陷修复方案

## 问题描述

在 `download_scheduler.py` 中发现了一个关键的架构缺陷：生产者-消费者模式只实现了生产部分，缺少消费者部分。

### 问题现象
- 任务被成功调度到队列中（显示"调度了28个下载任务"）
- 但任务从未被执行（一直显示"已完成: 0"）
- 程序卡住，监控日志显示任务数始终不变

### 根本原因
1. 任务通过 `self.task_manager.add_task()` 被添加到任务队列
2. `execute_scheduled_tasks()` 方法只启动了监控线程，没有启动消费者线程
3. 没有任何代码从队列中取出任务并执行
4. 程序只是被动等待任务完成，但任务实际上从未被执行

## 解决方案

### 方案概述
在 `DownloadScheduler` 类中添加消费者工作线程，实现完整的生产者-消费者模式。

### 详细实现

修改 `execute_scheduled_tasks` 方法，在其中添加消费者线程：

```python
def execute_scheduled_tasks(self, wait_for_completion: bool = True) -> Dict[str, Any]:
    """
    执行所有已调度的任务
    """
    if self.is_running:
        self.logger.warning("调度器已在运行中")
        return self.get_stats()

    self.logger.info(f"开始执行下载调度，日期范围: {self.start_date} - {self.end_date}")
    self.is_running = True
    self.main_thread = threading.current_thread()

    # 启动任务消费者线程
    consumer_threads = []
    for i in range(self.max_workers):
        consumer_thread = threading.Thread(
            target=self._task_consumer_loop,
            name=f"TaskConsumer-{i}",
            daemon=True
        )
        consumer_thread.start()
        consumer_threads.append(consumer_thread)

    # 启动监控线程
    monitor_thread = threading.Thread(target=self._monitor_progress, daemon=True)
    monitor_thread.start()

    try:
        if wait_for_completion:
            # 等待所有任务完成
            self.task_manager.wait_for_all_tasks()
            self.storage_worker.wait_for_completion()
        else:
            # 不等待，立即返回
            pass

        self.logger.info("下载调度完成")
        return self.get_stats()

    except KeyboardInterrupt:
        self.logger.info("接收到中断信号，正在关闭调度器...")
        self.shutdown()
    except Exception as e:
        self.logger.error(f"执行下载调度时出错: {e}")
        raise
    finally:
        self.is_running = False

def _task_consumer_loop(self):
    """
    任务消费者循环 - 从队列中获取并执行任务
    """
    while self.is_running and not self.shutdown_event.is_set():
        try:
            # 从任务队列获取任务
            task = self.task_manager.get_next_task(timeout=1.0)

            if task is None:
                # 无任务可执行，继续循环
                continue

            try:
                # 更新任务状态为处理中
                task.status = TaskStatus.PROCESSING
                task.started_at = datetime.now()

                # 执行任务
                self.logger.info(f"开始执行任务: {task.task_id}, 类型: {task.task_type}")

                # 调用任务目标函数
                result = task.target_func(*task.args, **task.kwargs)

                # 标记任务完成
                task.result = result
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()

                # 完成任务
                self.task_manager.complete_task(task.task_id, result, success=True)

                # 如果任务需要等待完成，需要额外处理
                if task.wait_for_completion:
                    # 处理等待完成的逻辑
                    pass

                self.logger.info(f"任务执行完成: {task.task_id}")

            except Exception as e:
                task.error = e
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()

                self.logger.error(f"任务执行失败: {task.task_id}, 错误: {e}")

                # 根据重试配置决定是否重试
                if task.retry_count < task.max_retries:
                    if self.task_manager.retry_task(task):
                        self.logger.info(f"任务已安排重试: {task.task_id}")
                    else:
                        self.task_manager.complete_task(task.task_id, e, success=False)
                else:
                    self.task_manager.complete_task(task.task_id, e, success=False)

        except queue.Empty:
            # 队列为空，继续循环
            continue
        except Exception as e:
            self.logger.error(f"任务消费者循环错误: {e}")
            # 短暂休眠避免过于频繁的错误
            time.sleep(1)
```

## 其他考虑

### 需要导入的模块
在文件开头需要添加：
```python
import queue
```

### 线程安全
- 确保 `self.is_running` 和其他共享状态的线程安全
- 添加适当的锁保护

### 错误处理
- 增加对任务异常情况的处理
- 完善重试逻辑

## 实施建议

1. **修改 `execute_scheduled_tasks` 方法**：添加消费者线程启动逻辑

2. **添加 `_task_consumer_loop` 方法**：实现任务消费逻辑

3. **测试验证**：运行测试验证任务是否能被正常消费和执行

4. **性能优化**：根据需要调整消费者线程数量

## 预期效果

- 任务队列中的任务会被消费者线程逐个取出并执行
- 任务状态会从队列状态变为处理中，再到完成
- 监控日志中"已完成"的数量会逐渐增加
- 下载调度过程能正常完成，不再是卡住的状态

这个修复将使生产者-消费者模式完整，解决当前任务阻塞的问题。