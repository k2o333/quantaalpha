# Results 列表内存泄漏解决方案

**创建日期**: 2026-03-04  
**问题类型**: 数据重复引用  
**影响接口**: 所有 stock_loop 模式接口（cyq_chips 等）  
**预期内存节省**: 50%+

---

## 1. 问题发现

在下载大数据量接口时，内存持续增长且不释放。

**根因**：同一份数据被两个地方同时持有。

```
download_single_stock()
    ↓
    stock_data = [70000条数据]
    ↓
    add_to_buffer(stock_data)  ← buffer 持有引用 #1
    ↓
    return stock_data          ← 返回给调用者
    ↓
    results.append(stock_data) ← results 持有引用 #2
    
# 内存翻倍！
```

---

## 2. 代码定位

### 2.1 downloader.py (第 660-663 行)

```python
# 当前代码
if stock_data:
    self.storage_manager.add_to_buffer(interface_config["api_name"], stock_data)

return stock_data or []  # ← 返回数据引用
```

### 2.2 main.py (第 287-295 行)

```python
results = scheduler.submit_tasks(tasks)

for result in results:
    if result:
        total_records += len(result)  # ← results 仍持有所有数据
```

---

## 3. 内存增长时序

```
T1: 提交 100 个任务
    → 4 线程并发下载

T2: 部分完成
    → buffer 持有 280000 条
    → results 持有 280000 条
    → 实际内存: 560000 条等效

T3: 全部完成
    → buffer 持有 7000000 条
    → results 持有 7000000 条
    → 实际内存: 14000000 条等效 ≈ 14GB+

T4: 处理 results
    → results 仍被引用，无法释放
    → 内存不变

T5: 下一批任务
    → 旧 results + 新数据
    → 内存继续增长
```

---

## 4. 解决方案

**核心**：只返回计数，不返回数据。

### 4.1 修改 downloader.py

```python
# 修改前
if stock_data:
    self.storage_manager.add_to_buffer(interface_config["api_name"], stock_data)
return stock_data or []

# 修改后
if stock_data:
    self.storage_manager.add_to_buffer(interface_config["api_name"], stock_data)
return len(stock_data) if stock_data else 0
```

### 4.2 修改 main.py

```python
# 修改前
for result in results:
    if result:
        total_records += len(result)

# 修改后
for result in results:
    if result:
        total_records += result
```

---

## 5. 效果对比

| 指标 | 修改前 | 修改后 |
|------|--------|--------|
| 数据引用数 | 2 份 | 1 份 |
| results 内存 | ~7GB | ~几KB |
| 峰值内存 | 20GB+ | 8-10GB |
| 内存曲线 | 线性增长 | 锯齿波动 |

---

## 6. 测试验证

```bash
# 启动并监控
python app4/main.py --interface cyq_chips &
pid=$!

while kill -0 $pid 2>/dev/null; do
    rss=$(ps -o rss= -p $pid | awk '{printf "%.0f", $1/1024}')
    echo "$(date '+%H:%M:%S'): ${rss}MB"
    sleep 2
done
```

**预期输出**（锯齿状）：

```
17:00:01: 150MB
17:00:05: 500MB   # 上升
17:00:10: 1.2GB   # 上升
17:00:15: 800MB   # 下降 ← 生效
17:00:20: 1.5GB   # 上升
17:00:25: 900MB   # 下降 ← 生效
```

---

## 7. 实施清单

- [ ] 修改 `app4/core/downloader.py` 第 660-663 行
- [ ] 修改 `app4/main.py` 第 287-295 行
- [ ] 修改 `app4/main.py` 第 298-305 行
- [ ] 验证内存锯齿状波动
