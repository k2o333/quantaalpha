---
doc_type: change
module: app4
status: archived
owner: quan
created: 2026-02-25
updated: 2026-02-25
summary: disclosure_date 等接口数据重复保存问题分析
---

# disclosure_date 等接口数据重复保存问题分析

## 问题现象

在运行增量更新时，日志显示每个 period 的数据被"保存两次"：

```
# 第一次：数据下载后立即记录
[disclosure_date] Saved 5618 records for period 20240930
[disclosure_date] Saved 5700 records for period 20241231
[disclosure_date] Saved 5663 records for period 20250331
...

# 第二次：实际写入文件时的处理记录
Processed 5302 records for disclosure_date
Processed 5551 records for disclosure_date
Processed 5380 records for disclosure_date
...

# 程序结束时的最终清理
Processed 5415 records for disclosure_date
Deduplication completed: input=5415, output=0, removed=5415
All records already exist, skipping save
```

观察到的关键现象：
1. 第一次 "Saved" 的记录数 > 第二次 "Processed" 的记录数
2. 第二次处理时显示有重复记录被去除
3. 程序结束时又有一次处理，且所有记录都被去重跳过

---

## 问题根因

### 数据流程分析

使用 `period_range` 模式（`periods_per_batch: 1`）的接口，数据流程如下：

```
┌─────────────────────────────────────────────────────────────────────┐
│                        downloader._execute_pagination               │
├─────────────────────────────────────────────────────────────────────┤
│  1. pagination_executor.execute(..., save_callback=save_callback) │
│                                                                     │
│  2. _execute_period_range_sequential()                             │
│     for each period:                                                │
│         data = _execute_single_request(params)                     │
│         if data:                                                    │
│             all_data.extend(data)                                   │
│             save_callback(interface_name, data)  ← 第一次"保存"     │
│             logger.info(f"Saved {len(data)} records...")            │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    storage.save_data (async)                        │
├─────────────────────────────────────────────────────────────────────┤
│  检查数据是否有 _update_time 字段（已处理标记）                     │
│                                                                     │
│  if data_already_processed:                                        │
│      # 直接放入 data_queue（WriteWorker 消费）                     │
│      data_queue.put({'interface_name': ..., 'data': ...})          │
│  else:                                                               │
│      # 放入 buffer，触发 flush 后进入 process_queue                 │
│      add_to_buffer(interface_name, data, flush_immediately=...)   │
│                                                                     │
│  ⚠️ 此时数据只是放入 buffer，没有进行任何去重处理！                  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│              storage._process_worker (ProcessThread)                │
├─────────────────────────────────────────────────────────────────────┤
│  ⚠️ 这是第一次真正的"处理"，包括：                                   │
│                                                                     │
│  1. 内部去重（批次内去重）                                          │
│     df = self.processor.process_data(data, interface_config)       │
│     - 根据主键去重，保留最后一条                                     │
│                                                                     │
│  2. 外部去重（与历史数据比较）                                      │
│     existing_df = self.read_interface_data(interface_name, ...)   │
│     df = deduplicate_against_existing(df, existing_df, primary_keys)│
│                                                                     │
│  3. 写入文件                                                        │
│     self._write_interface_data(interface_name, df)                 │
│                                                                     │
│  logger.info(f"Processed {len(df)} records...")  ← 第二次日志─────────────────────────────────────────────────────────────────────┘
                                    │
     │
└                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 程序结束时的清理流程                                 │
├─────────────────────────────────────────────────────────────────────┤
│  - buffer 中剩余数据进入 process_worker                            │
│  - 再次进行去重处理                                                 │
│  - 如果数据已存在，output=0，skipped save                          │
└─────────────────────────────────────────────────────────────────────┘
```

### 关键发现

1. **第一次 "Saved" 不是真正的保存**：只是将数据放入 buffer
2. **真正的去重发生在 process_worker**：这是第一次真正的数据处理
3. **程序结束时的"重复"是正常的清理**：buffer 中残留数据再次处理

---

## 受影响的接口

以下 10 个接口使用相同的 `period_range` + `periods_per_batch: 1` 配置：

| 接口名称 | 配置文件 | 
|---------|---------|
| disclosure_date | `disclosure_date.yaml` |
| top10_holders | `top10_holders.yaml` |
| top10_floatholders | `top10_floatholders.yaml` |
| fina_indicator_vip | `fina_indicator_vip.yaml` |
| cashflow_vip | `cashflow_vip.yaml` |
| balancesheet_vip | `balancesheet_vip.yaml` |
| express_vip | `express_vip.yaml` |
| forecast_vip | `forecast_vip.yaml` |
| fina_mainbz_vip | `fina_mainbz_vip.yaml` |
| income_vip | `income_vip.yaml` |

---

## 解决方案

### 方案一：在 save_callback 阶段直接标记数据已处理

**思路**：在第一次 save_callback 调用时，直接给数据添加 `_update_time` 标记，让数据直接进入 data_queue 等待写入，而不是经过 buffer。

**修改位置**：`pagination_executor.py` 的 `save_callback` 调用

```python
# 在调用 save_callback 前，给数据添加处理标记
def save_callback_with_mark(iface_name: str, data: list):
    if data:
        # 添加 _update_time 标记，标识数据已处理
        current_time = int(time.time() * 1000)
        for item in data:
            item['_update_time'] = current_time
        self.storage_manager.save_data(iface_name, data, async_write=True)
```

**优点**：
- 减少一次数据处理（buffer → process_worker）
- 数据更早进入写入队列

**缺点**：
- 需要修改 pagination_executor 的调用逻辑

---

### 方案二：优化日志输出，避免误导

**思路**：将第一次的 "Saved" 日志改为 "Queued" 或 "Buffered"，更清晰地反映实际情况。

**修改位置**：`pagination_executor.py` 第 252 行

```python
# 修改前
logger.info(f"[{interface_name}] Saved {len(data)} records for period {period}")

# 修改后
logger.info(f"[{interface_name}] Queued {len(data)} records for period {period}")
```

---

### 方案三：合并处理流程

**思路**：在 save_callback 阶段直接完成去重和写入，避免二次处理。

**修改位置**：在 `update_manager.py` 的 `save_callback` 中直接调用同步写入方法。

```python
def save_callback(iface_name: str, data: list):
    if data:
        # 同步写入，直接处理（去重+写入）
        self.storage_manager.save_data(iface_name, data, async_write=False)
```

**优点**：
- 简化流程，数据立即持久化

**缺点**：
- 可能降低并发性能
- 失去异步写入的优势

---

## 推荐方案

建议采用**方案一 + 方案二**的组合：

1. **方案二（低优先级）**：修改日志措辞，避免用户误解
2. **方案一（高优先级）**：优化数据处理流程，减少不必要的处理步骤

---

## 附录：相关代码位置

| 文件 | 行号 | 说明 |
|-----|------|------|
| `pagination_executor.py` | 248 | 调用 save_callback |
| `pagination_executor.py` | 252 | "Saved" 日志 |
| `storage.py` | 742-758 | save_data 方法，检查 _update_time |
| `storage.py` | 591-625 | process_worker 的数据处理 |
| `update_manager.py` | 464-467 | save_callback 定义 |
