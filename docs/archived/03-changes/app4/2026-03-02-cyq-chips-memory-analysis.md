---
doc_type: change
module: app4
status: archived
owner: quan
created: 2026-03-02
updated: 2026-03-02
summary: cyq_chips 内存优化问题分析与现状报告
---

# cyq_chips 内存优化问题分析与现状报告

**创建日期**: 2026-03-04  
**文档版本**: v1.0  
**相关接口**: cyq_chips (筹码分布)  
**问题现象**: 下载时内存占用高达 50%+ (16GB+/32GB)

---

## 1. 问题概述

### 1.1 现象描述

在执行 `python app4/main.py --interface cyq_chips` 时，服务器内存占用从初始 10% 飙升至 50% 以上（约 16GB+）：

```bash
# 启动命令示例
python app4/main.py --interface cyq_chips

# 或使用 update 模式
python app4/main.py --update --interface cyq_chips --start_date 20230101 --end_date 20260304
```

### 1.2 内存占用分布

| 组件 | 估算占用 | 占比 | 说明 |
|------|----------|------|------|
| **并发下载缓冲** | ~8-10GB | 30-31% | 4线程同时处理，每只股票 DataFrame 积压 |
| **Polars 内存池** | ~3-4GB | 9-12% | Arrow 缓冲区保留，不归还 OS |
| **CoverageManager** | ~2-3GB | 6-9% | 读取日期列进行覆盖率检测 |
| **Python 基础进程** | ~1GB | 3% | 解释器 + 加载的库 |
| **其他开销** | ~1-2GB | 3-6% | 日志、缓存、线程栈等 |
| **合计** | **~16GB+** | **50%+** | 32GB 服务器的占用比例 |

---

## 2. 代码现状分析

### 2.1 去重简化方案已实施 ✅

根据 `/home/quan/testdata/aspipe_v4/p/2026-3-2/memorydebug/dedup_simplification_plan.md`，已与 2026-03-02 实施去重简化方案。

#### 2.1.1 实施状态

| 文件 | 位置 | 状态 | 说明 |
|------|------|------|------|
| `main.py` | Line 417 | ✅ 已禁用 | `if False:` 硬编码禁用 |
| `storage.py` | Line 709-711 | ✅ 已禁用 | `if False:` 硬编码禁用 |

#### 2.1.2 代码截图

**main.py (Line 412-439)**:
```python
dedup_config = interface_config.get("dedup", {"dedup_enabled": True})

if False:  # dedup_config.get('dedup_enabled', True) and primary_keys:  ← 已禁用
    try:
        existing_df = storage_manager.read_interface_data(
            interface_name, columns=primary_keys
        )
        # ... 去重逻辑 ...
```

**storage.py (Line 702-762)**:
```python
# ✅ 与历史数据去重（外部去重）
# [简化] 禁用与已有数据的去重，依赖 CoverageManager + 存储层主键约束
# 批次内去重已在 processor 中完成
output_config = interface_config.get("output", {})
primary_keys = output_config.get("primary_key", [])

if (
    False  # ← 已禁用
):  # dedup_config.get('dedup_enabled', True) and primary_keys:
    try:
        existing_df = self.read_interface_data(
            interface_name, columns=primary_keys
        )
        # ... 去重逻辑 ...
```

#### 2.1.3 效果评估

- ✅ **不再加载全量磁盘数据进行合并去重**
- ⚠️ **但 CoverageManager 仍会读取日期列进行检测**（见 2.3 节）

---

### 2.2 并发下载缓冲问题 ❌

#### 2.2.1 问题描述

并发下载缓冲与去重是**完全独立**的问题：

```
下载流程（问题分离）：
┌─────────────────────────────────────────────────────────────────┐
│  阶段1: 并发下载（问题1: 并发缓冲）                                 │
│  ├── 线程1: 下载 688066.SH → DataFrame (10,000条) → 内存          │
│  ├── 线程2: 下载 300894.SZ → DataFrame (10,000条) → 内存          │
│  ├── 线程3: 下载 301120.SZ → DataFrame (10,000条) → 内存          │
│  └── 线程4: 下载 600775.SH → DataFrame (10,000条) → 内存          │
│  【并发缓冲问题在这里】← 同时4个DataFrame在内存                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  阶段2: 存储处理（问题2: 与已有数据去重 - 已解决）                   │
│  ├── 原逻辑: 读取磁盘已有数据 + 合并去重 → 【已禁用】               │
│  └── 现逻辑: 直接写入新文件（无额外内存占用）                       │
│  【与已有数据去重问题在这里】← 已解决                              │
└─────────────────────────────────────────────────────────────────┘
```

#### 2.2.2 关键代码

**并发度配置** (`app4/config/settings.yaml`):
```yaml
concurrency:
  max_workers: 4  # 默认并发数
  max_queue_size: 1000
```

**任务调度** (`app4/core/scheduler.py`):
- 使用 `ThreadPoolExecutor` 管理并发
- Token Bucket 算法进行速率限制

**下载缓冲** (`app4/core/downloader.py`):
```python
# 多线程同时执行 download_stock_task
with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
    futures = [executor.submit(download_stock_task, stock) for stock in stock_batch]
```

#### 2.2.3 内存堆积原因

| 因素 | 说明 |
|------|------|
| **并发下载** | 4线程同时处理，每只股票的 DataFrame 同时存在于内存 |
| **队列积压** | `process_queue` 和 `data_queue` 的数据未及时消费 |
| **GC 延迟** | Python 垃圾回收不是实时的，旧的 DataFrame 引用未立即释放 |
| **Polars 开销** | DataFrame 内存开销是原始数据的 5-10 倍 |

---

### 2.3 CoverageManager 日期列读取问题 ⚠️

#### 2.3.1 问题描述

即使禁用了与已有数据的去重，`CoverageManager` 仍会在下载前读取日期列进行覆盖率检测：

**代码位置**: `app4/core/coverage_manager.py:135-140`
```python
# 读取接口数据，只读取日期列
df = self.storage_manager.read_interface_data(
    interface_name,
    start_date=start_date,
    end_date=end_date,
    columns=[date_column],  # 只读日期列，但数据量大
)
```

#### 2.3.2 内存影响

| 接口 | 单只股票日期记录数 | 5,485只股票总记录数 | 内存占用 |
|------|-------------------|-------------------|----------|
| cyq_chips | ~10,000 条 | ~5,500 万条 | ~2-3GB |

**说明**：虽然只读取 `trade_date` 单列，但 cyq_chips 是高频数据，累计数据量巨大。

#### 2.3.3 缓存机制

`CoverageManager` 实现了内存缓存（`OrderedDict`）：
```python
# coverage_manager.py:44-46
self._existing_dates_cache = OrderedDict()
self._cache_size = cache_size  # 默认 128
self._existing_dates_lock = threading.RLock()
```

但缓存大小有限（默认 128），对于 cyq_chips 这种大数据接口效果有限。

---

### 2.4 Polars 内存池问题 ⚠️

#### 2.4.1 问题描述

Polars 使用 **Apache Arrow** 内存格式，其内存管理策略是：
- 内存分配后**不归还操作系统**，保留在进程内复用
- 表现为"内存泄漏"，实际是"内存池保留"

#### 2.4.2 内存占用示意

```
Polars 内存管理：
┌─────────────────────────────────────────────┐
│  操作系统视角: 进程占用 16GB                   │
│  ┌─────────────────────────────────────┐   │
│  │  Polars 视角:                        │   │
│  │  - 正在使用: 4GB (活跃 DataFrame)     │   │
│  │  - 内存池(保留): 8GB (标记为可用)      │   │
│  │  - 真正空闲: 4GB                      │   │
│  └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
         ↓
    调用 gc.collect() 或 del df
         ↓
    内存池不会缩小，但标记为可用
         ↓
    其他 DataFrame 可以复用这 8GB
         ↓
    但 OS 认为进程仍占用 16GB！
```

#### 2.4.3 特性说明

| 特性 | 说明 |
|------|------|
| **Arrow 缓冲区** | 用于后续 DataFrame 复用 |
| **字符串/二进制池** | 避免重复分配大内存块 |
| **列数据连续内存** | Arrow 要求列式存储连续 |

---

### 2.5 依赖库冗余问题 ⚠️

#### 2.5.1 依赖分析

根据 `app4/requirements.txt` 和代码实际使用情况：

| 库 | 版本要求 | 实际使用 | 占用估算 | 优化建议 |
|----|----------|----------|----------|----------|
| **polars** | ==0.20.31 | ✅ 核心使用 | ~300MB | ❌ 必需 |
| **pyarrow** | >=10.0.0 | ⚠️ 仅导入未使用 | ~200MB | ❌ Polars 依赖 |
| **numpy** | >=1.24.0 | ⚠️ 只用一行 | ~100MB | ✅ 可移除 |
| **pandas** | >=1.5.0 | ❌ 未使用 | ~200MB | ✅ 可测试移除 |

#### 2.5.2 NumPy 使用情况

**仅一处使用** (`app4/core/processor.py:2, 269`):
```python
import numpy as np
# ...
df = df.fill_null(np.nan)  # 第269行
```

**替代方案**:
```python
# 方案1: Python 原生
df = df.fill_null(float('nan'))

# 方案2: Polars 原生
df = df.fill_null(pl.lit(float('nan')))
```

#### 2.5.3 Pandas 使用情况

**搜索结果**: 代码中无 `pd.` 或 `pandas` 的直接使用

**可能来源**:
- 历史遗留（早期开发用过，后迁移到 Polars）
- 第三方库依赖（如 tushare SDK）
- 兼容性预留

**注意**: 代码中使用 `requests` 直接调用 TuShare API，未使用 tushare SDK：
```python
# downloader.py:715
api_url = tushare_config.get("api_url", "http://api.tushare.pro/api")
# 使用 requests.post 直接请求
```

---

## 3. 根因总结

### 3.1 内存占用根因

```
┌─────────────────────────────────────────────────────────────┐
│                    内存占用 16GB+ (50%+)                     │
├─────────────────────────────────────────────────────────────┤
│  并发下载缓冲 (8-10GB)                                        │
│  ├── 4线程同时处理                                            │
│  ├── 每只 DataFrame 10,000条 × 10列 × 50字节                │
│  ├── Polars 开销 5-10x                                      │
│  └── GC 延迟释放                                              │
├─────────────────────────────────────────────────────────────┤
│  Polars 内存池 (3-4GB)                                       │
│  ├── Arrow 缓冲区保留                                         │
│  ├── 字符串/二进制池                                          │
│  └── 不归还 OS                                                │
├─────────────────────────────────────────────────────────────┤
│  CoverageManager (2-3GB)                                     │
│  ├── 读取日期列进行检测                                       │
│  ├── cyq_chips 数据量大                                       │
│  └── 缓存命中率低                                             │
├─────────────────────────────────────────────────────────────┤
│  Python 基础 (1GB)                                           │
│  ├── 解释器 + 库加载                                          │
│  └── Polars/PyArrow/NumPy/Pandas                            │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 问题优先级

| 优先级 | 问题 | 影响 | 解决难度 |
|--------|------|------|----------|
| P0 | 并发下载缓冲 | 最大 | 简单（降并发） |
| P1 | CoverageManager | 中等 | 中等（加跳过逻辑） |
| P2 | Polars 内存池 | 中等 | 较难（需特化处理） |
| P3 | 依赖库清理 | 小 | 简单（测试后移除） |

---

## 4. 解决方案

### 4.1 方案 A: 快速缓解（立即生效）

**目标**: 内存降至 25-30%

```bash
# 降低并发度到 1
python app4/main.py --interface cyq_chips --concurrency 1
```

**效果**:
- 单线程处理，避免同时堆积多个 DataFrame
- 下载速度降低，但内存占用显著下降

---

### 4.2 方案 B: CoverageManager 优化

**目标**: 首次下载时跳过检测

**代码修改** (`app4/core/coverage_manager.py`):
```python
def should_skip(self, interface_name: str, params: Dict[str, Any]) -> bool:
    # 新增: 检查是否已有数据
    if not self._has_existing_data(interface_name):
        return False  # 无数据，不跳过，也不读取
    
    # 原有检测逻辑...
```

**效果**:
- 首次下载时避免读取日期列
- 节省 2-3GB 内存

---

### 4.3 方案 C: 接口特化配置（推荐）

**目标**: 根据接口特性自动调整

**配置修改** (`app4/config/interfaces/cyq_chips.yaml`):
```yaml
name: cyq_chips
api_name: cyq_chips

# 新增: 接口级配置
download:
  max_concurrency: 1  # 大数据接口用单线程
  skip_coverage_check: true  # 首次下载跳过检测
  
# 保留: 批次内去重
dedup:
  batch_dedup: true  # 批次内去重
```

**代码修改** (`app4/main.py`):
```python
# 根据接口配置调整并发度
interface_concurrency = interface_config.get('download', {}).get('max_concurrency', global_concurrency)
```

---

### 4.4 方案 D: 依赖清理

**目标**: 节省 ~300MB 内存

**步骤**:
1. **移除 NumPy**:
   ```python
   # processor.py:269
   # 替换
   df = df.fill_null(float('nan'))
   ```

2. **测试移除 Pandas**:
   ```bash
   # 临时注释掉 requirements.txt 中的 pandas
   # 运行测试
   python -c "import app4.main"
   ```

---

## 5. 实施建议

### 5.1 短期（立即执行）

1. 使用 `--concurrency 1` 启动下载
2. 监控内存占用

### 5.2 中期（本周内）

1. 实施 CoverageManager 跳过逻辑
2. 测试移除 NumPy

### 5.3 长期（本月内）

1. 实施接口特化配置（方案 C）
2. 全面测试后移除 Pandas
3. 评估 Polars 内存池特化处理

---

## 6. 附录

### 6.1 相关文档

| 文档 | 路径 |
|------|------|
| 去重简化方案 | `/home/quan/testdata/aspipe_v4/p/2026-3-2/memorydebug/dedup_simplification_plan.md` |
| 本报告 | `/home/quan/testdata/aspipe_v4/p/2026-3-2/cyq_chips_memory_analysis.md` |

### 6.2 相关代码文件

| 文件 | 关键位置 | 说明 |
|------|----------|------|
| `app4/main.py` | Line 417 | 已禁用存储前去重 |
| `app4/core/storage.py` | Line 709-711 | 已禁用存储时去重 |
| `app4/core/coverage_manager.py` | Line 135-140 | 日期列读取 |
| `app4/core/processor.py` | Line 2, 269 | NumPy 使用 |
| `app4/config/settings.yaml` | concurrency | 并发配置 |

### 6.3 命令参考

```bash
# 快速降低内存
python app4/main.py --interface cyq_chips --concurrency 1

# update 模式
python app4/main.py --update --interface cyq_chips --start_date 20230101 --end_date 20260304

# 监控内存
watch -n 1 "free -h && ps aux | grep python | grep -v grep"
```

---

**报告完成**
