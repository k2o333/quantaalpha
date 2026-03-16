# 改进修复方案

## 问题概述

两个问题独立存在，需要分别修复：

| 问题 | 文件 | 描述 |
|------|------|------|
| 问题1 | `pagination_executor.py` | 单批请求时 `save_callback` 未传递，数据丢失 |
| 问题2 | `storage.py` | Worker 退出时并发安全问题 |

---

## 问题1：pagination_executor 单批请求数据未保存

### 问题定位

```python
# pagination_executor.py 第112-114行
if len(params_list) <= 1:
    if params_list:
        return self._execute_single(
            interface_config, params_list[0], make_request, on_data_ready  # ← 缺少 save_callback
        )
```

### 修复方案

**修改1**：`_execute_single` 方法增加 `save_callback` 参数

```python
def _execute_single(
    self,
    interface_config: Dict[str, Any],
    params: Dict[str, Any],
    make_request: Callable,
    on_data_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    save_callback: Optional[Callable[[str, List[Dict[str, Any]]], None]] = None,  # 新增
) -> List[Dict[str, Any]]:
    result = self._execute_single_request(interface_config, params, make_request, on_data_ready)
    
    # 只有非流式模式才保存（避免重复保存）
    if save_callback and result and not on_data_ready:
        interface_name = interface_config.get("name", "unknown")
        save_callback(interface_name, result)
        logger.info(f"[{interface_name}] 已保存 {len(result)} 条记录 (单批)")
    
    return result
```

**修改2**：`execute` 方法传递 `save_callback`

```python
if len(params_list) <= 1:
    if params_list:
        if coverage_manager and self._should_skip_by_coverage(
            interface_config, params_list[0], coverage_manager
        ):
            logger.info(f"Skipping request due to coverage check")
            return []
        return self._execute_single(
            interface_config, params_list[0], make_request, on_data_ready, save_callback  # 新增
        )
```

### 避免重复保存

- `_execute_single_request` **不**调用 `save_callback`（只负责请求数据）
- `_execute_single` 负责调用 `save_callback`（统一保存入口）
- `_execute_sequential` 已有保存逻辑，无需修改

---

## 问题2：storage worker 退出并发安全问题

### 问题定位

1. `stop_writer` 死等队列清空，可能永久阻塞
2. `flush_remaining_data` 使用 `block=False`，队列满时丢数据
3. `_process_worker` 收到哨兵后立即退出，可能遗漏队列中剩余数据
4. `save_data` 入口未检查 `running` 状态

### 修复方案

**修改1**：`stop_writer` 增加超时和线程存活检查

```python
def stop_writer(self):
    if self.running:
        self.running = False

        # 1. 处理剩余缓存
        self.flush_remaining_data()

        # 2. 等待处理队列清空（带超时）
        logger.info("Waiting for process queue to empty...")
        wait_start = time.time()
        wait_timeout = 60
        while not self.process_queue.empty():
            if not self.process_thread.is_alive():
                logger.error("Process thread died unexpectedly while waiting for queue")
                break
            if time.time() - wait_start > wait_timeout:
                logger.error(f"Timeout ({wait_timeout}s) waiting for process queue to empty")
                break
            time.sleep(0.1)

        # 3. 发送哨兵并等待线程退出
        self.process_queue.put(None)
        if self.process_thread:
            self.process_thread.join(timeout=60)
            if self.process_thread.is_alive():
                logger.warning("Process thread did not stop within timeout")

        self.data_queue.put(None)
        if self.writer_thread:
            self.writer_thread.join(timeout=120)
            if self.writer_thread.is_alive():
                logger.warning("Writer thread did not stop within timeout")

        logger.info("Storage threads stopped")
```

**修改2**：`save_data` 入口增加状态检查

```python
def save_data(self, interface_name: str, data: List[Dict[str, Any]], async_write: bool = True):
    try:
        if isinstance(data, pl.DataFrame):
            data_records = data.to_dicts()
        elif isinstance(data, dict):
            data_records = [data]
        else:
            data_records = data or []

        if not data_records:
            return

        # 新增：如果正在关闭，降级为同步写入
        if not self.running and async_write:
            logger.warning(f"Storage is stopping, falling back to sync write for {interface_name}")
            self._write_interface_data(interface_name, data_records)
            return

        # ... 原有逻辑
```

**修改3**：`_process_worker` 支持排空队列后退出

```python
def _process_worker(self):
    pending_stop = False
    dedup_stats_total = {
        "total_processed": 0,
        "total_deduped": 0,
        "interfaces": set(),
    }

    while True:
        try:
            task = self.process_queue.get(timeout=1)

            if task is None:
                # 收到哨兵，标记待停止，但继续处理队列中的剩余数据
                pending_stop = True
                # 排空队列中剩余的非None数据
                while not self.process_queue.empty():
                    try:
                        remaining = self.process_queue.get_nowait()
                        if remaining is not None:
                            # 处理剩余数据（复用下面的处理逻辑）
                            task = remaining
                            break  # 跳出内层循环，在外层处理task后再次检查
                    except queue.Empty:
                        break
                
                if task is None:
                    # 真正没有数据了，退出
                    if dedup_stats_total["total_processed"] > 0:
                        dedup_rate = (
                            dedup_stats_total["total_deduped"]
                            / dedup_stats_total["total_processed"]
                        ) * 100
                        logger.info(
                            f"Process worker summary: processed {dedup_stats_total['total_processed']} records, "
                            f"deduped {dedup_stats_total['total_deduped']} ({dedup_rate:.2f}%)"
                        )
                    logger.info("Process worker exiting")
                    break

            interface_name = task["interface"]
            data = task["data"]
            # ... 原有处理逻辑
```

**修改4**：`flush_remaining_data` 使用带超时的阻塞put

```python
def flush_remaining_data(self):
    items_to_flush = []

    with self.buffer_lock:
        for interface_name, buffer in self.interface_buffers.items():
            if buffer["count"] > 0 and buffer["data"]:
                items_to_flush.append({
                    "interface_name": interface_name,
                    "data": buffer["data"],
                    "count": buffer["count"],
                })
                buffer["data"] = []
                buffer["count"] = 0

    for item in items_to_flush:
        try:
            # 使用带超时的阻塞put，避免队列满时丢数据
            self.process_queue.put(
                {"interface": item["interface_name"], "data": item["data"], "timestamp": time.time()},
                block=True,
                timeout=30  # 最多等待30秒
            )
            logger.info(f"Flushed {len(item['data'])} records for {item['interface_name']}")
        except queue.Full:
            logger.error(f"Process queue full after 30s timeout, dropping data for {item['interface_name']}")
```

---

## 方案对比

| 方面 | bug_fix_report | storage_worker修复 | 本方案 |
|------|---------------|-------------------|--------|
| 问题定位 | 准确 | 准确 | 准确 |
| 重复保存风险 | 存在 | N/A | 已避免 |
| 修复复杂度 | 中 | 高 | 低 |
| 代码改动量 | 多处 | 多处 | 最小必要改动 |

---

## 验证方法

**问题1验证**：
```bash
/root/miniforge3/envs/get/bin/python app4/main.py --update --interface stk_factor_pro --start_date 19900101
```

预期日志：
```
[stk_factor_pro] 已保存 2945 条记录 (单批)
```

**问题2验证**：
观察程序退出时的日志，确保：
1. 无 "Timeout waiting for process queue to empty" 错误
2. 无 "Process thread died unexpectedly" 错误
3. 显示 "Process worker summary: processed X records" 统计

---

**日期**: 2026-03-06
