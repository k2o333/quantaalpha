# Storage Writer 线程时序竞争问题修复方案

## 问题现象

用户执行增量更新时，配置 `limit=5000` 数据下载成功但文件未保存，配置 `limit=6000` 则正常保存。

## 问题诊断

**这不是 limit 配置的问题，而是一个时序竞争 bug。**

### 日志对比分析

**第一次运行 (limit=5000) - 文件未保存:**
```
10:46:03,373 - Waiting for process queue to empty...
10:46:03,676 - Processed 29571 records for moneyflow_dc
10:46:03,895 - Processed and queued 29571 records for moneyflow_dc
10:46:03,906 - Stopping writer thread...
10:46:03,907 - Storage threads stopped  ← 没有写入日志！
```

**第二次运行 (limit=6000) - 文件保存成功:**
```
10:48:28,386 - Processed 29571 records for moneyflow_dc
10:48:28,621 - Processed and queued 29571 records for moneyflow_dc
10:48:28,652 - Stopping writer thread...
10:48:28,912 - 使用SchemaManager成功创建DataFrame for moneyflow_dc，记录数: 29571
10:48:28,924 - Wrote 29571 records to ...parquet  ← 有写入日志！
10:48:28,939 - Storage threads stopped
```

### 根本原因

问题出在 `app4/core/storage.py:210-214` 的 `_writer_worker` 方法：

```python
except queue.Empty:
    # 如果队列为空且收到停止信号（通过self.running判断作为双重保障）
    if not self.running:
        break  # ← 问题在这里！
    continue
```

#### 问题根因验证

1. `storage.py:210-214` 的 `if not self.running: break` 确实是竞争条件的根源
2. 当 `_process_worker` 还在处理数据时，`_writer_worker` 可能因超时+`self.running=False` 提前退出

#### 哨兵机制足够安全

已验证 `storage.py:177-194` 的哨兵处理逻辑：

```python
if item is None:
    # 收到停止信号，处理完当前批次（如果还有剩余）后退出
    while not self.data_queue.empty():
        try:
            extra_item = self.data_queue.get_nowait()
            if extra_item is not None:
                batch_data.append(extra_item)
        except queue.Empty:
            break
    if batch_data:
        self._write_batch(batch_data)
    break
```

收到 `None` 后会处理所有剩余数据，不会丢失。

#### `self.running` 检查是多余的

`stop_writer()` 已经确保正确的停止顺序：
- 先等待 `process_queue` 清空
- 再发送哨兵给 `_writer_worker`
- `join(timeout=120)` 提供超时保护

### 竞争条件时序图

```
时间线 →
─────────────────────────────────────────────────────────────
stop_writer()              _process_worker          _writer_worker
─────────────────────────────────────────────────────────────
self.running = False  ─────┐
                          │
flush_remaining_data()     │
                          │
等待 process_queue 空      │
                          │
process_queue.put(None)────┼──→ 处理最后数据 ────────→ data_queue.put(data)
                          │
data_queue.put(None) ──────┼───────────────────────────→ 但此时 writer 已经退出了!
                          │          (因为之前 queue.Empty + self.running=False)
writer_thread.join()       │
─────────────────────────────────────────────────────────────
```

当 `_writer_worker` 在 `data_queue.get(timeout=1)` 超时时，如果此时 `self.running` 已经是 `False`，它就会直接退出，**即使数据马上就要被放入队列**。

### 为什么时隐时现？

这取决于以下时序：
1. `_process_worker` 处理数据需要的时间（去重、验证）
2. `_writer_worker` 超时检查的时机

当 limit=5000 时有6页，limit=6000 时有5页，网络延迟、数据处理时间的微小差异，刚好在第一次触发了竞争条件。

---

## 修复方案

**核心修改：移除 `_writer_worker` 中的 `self.running` 检查，只依赖哨兵信号 (`None`) 来控制退出。**

### 修改位置

`app4/core/storage.py:210-214`

### 修改内容

```python
# 修改前
except queue.Empty:
    # 如果队列为空且收到停止信号（通过self.running判断作为双重保障）
    if not self.running:
        break
    continue

# 修改后
except queue.Empty:
    continue  # 只等待哨兵信号(None)，不主动退出
```

### 修复原理

- `stop_writer()` 已经保证在发送哨兵 (`None`) 之前，所有数据都已放入队列
- `_writer_worker` 收到 `None` 后会处理队列中所有剩余数据再退出
- 移除 `self.running` 检查后，不会因为超时而过早退出

### 哨兵机制保障

现有的哨兵处理逻辑已经足够安全 (`storage.py:180-196`)：

```python
if item is None:
    # 收到停止信号，处理完当前批次（如果还有剩余）后退出
    # 将队列中剩余所有非None项取出处理
    while not self.data_queue.empty():
        try:
            extra_item = self.data_queue.get_nowait()
            if extra_item is not None:
                batch_data.append(extra_item)
        except queue.Empty:
            break

    if batch_data:
        self._write_batch(batch_data)
    break
```

---

## 影响分析

### 影响范围

- 仅影响 `storage.py` 中的 `_writer_worker` 方法
- 不影响其他模块

### 风险评估

- **低风险**：修改简化了退出逻辑，移除了有问题的竞争条件
- 哨兵机制 (`None`) 仍然确保线程能正常退出
- `stop_writer()` 的 `join(timeout=120)` 确保不会无限等待

---

## 验证方法

1. 执行多次增量更新，确保数据都能正确保存
2. 测试不同 limit 配置（5000, 6000 等）
3. 检查日志确认写入成功
