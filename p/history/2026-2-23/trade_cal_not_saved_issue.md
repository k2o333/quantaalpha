# 问题：运行时获取的 trade_cal 数据不保存到本地

## 问题概述

当下载接口数据时，如果请求的日期范围超出本地 trade_cal（交易日历）的覆盖范围，系统会从 TuShare API 获取缺失的交易日历数据。但是，**运行时获取的 trade_cal 数据不会自动保存到本地**，导致下次运行时需要重复请求相同数据。

## 影响范围

- 重复消耗 TuShare API 请求配额
- 每次运行都需要重新获取未覆盖的日期范围
- 当日数据下载场景下问题尤为明显（因为 trade_cal 可能未包含当日）

## 问题复现场景

```
1. 首次运行程序
   - preload_global_trade_calendar() 请求 trade_cal
   - 获取 19900101-20250220 的数据
   - ✅ 保存到本地

2. 运行中请求超出范围的日期
   - 用户请求下载 20250220-20250228 的数据（包含当日）
   - 本地 trade_cal 未覆盖 20250221-20250228
   - downloader.get_trade_calendar() 触发 API 请求
   - ❌ 获取后仅缓存到内存，不保存到本地

3. 程序结束，内存缓存丢失

4. 下次运行
   - 仍然需要重新请求 20250221-20250228
   - 浪费 API 请求配额
```

## 代码分析

### 两个调用路径的行为差异

#### 路径 1: 启动时预加载 - 会保存

文件: `app4/main.py` 第320-327行

```python
if trade_calendar:
    trade_days = [day for day in trade_calendar if day.get('is_open', 0) == 1]
    trade_days = sorted(trade_days, key=lambda x: x['cal_date'])
    
    # ✅ 保存到存储
    logger.info(f"Saving {len(trade_days)} trade days to storage")
    storage_manager.save_data('trade_cal', trade_calendar, async_write=False)
    
    # 填充内存缓存
    cache_key = (start_date, end_date)
    with downloader._cache_lock:
        downloader._memory_cache['trade_cal'][cache_key] = trade_calendar
```

#### 路径 2: 运行时请求 - 不会保存

文件: `app4/core/downloader.py` 第366-387行

```python
trade_calendar = self._get_trade_calendar_from_data_dir(start_date, end_date)
if not trade_calendar:
    # 3. 请求 API
    logger.info(
        f"Trade calendar not found locally, fetching from API: {start_date}-{end_date}"
    )
    calendar_params = {
        "start_date": start_date,
        "end_date": end_date,
        "exchange": "SSE",
    }
    # 使用 _make_request 直接请求，避免递归调用
    trade_calendar = self._make_request(
        self.config_loader.get_interface_config("trade_cal"), calendar_params
    )

    # ❌ 只更新内存缓存，没有保存到本地
    if trade_calendar:
        with self._cache_lock:
            cache_key = (start_date, end_date)
            self._memory_cache["trade_cal"][cache_key] = trade_calendar

return trade_calendar  # 直接返回，未保存
```

### 调用流程图

```
程序启动流程:
┌─────────────────────────────────────────────────────────────┐
│  main.py                                                    │
│    ├── preload_global_trade_calendar()  ← 会保存到本地      │
│    │     ├── 检查内存缓存                                    │
│    │     ├── 检查本地文件                                    │
│    │     └── 请求 API → save_data() ✅                      │
│    │                                                         │
│    └── 下载其他接口数据...                                    │
│          └── downloader.get_trade_calendar() ← 不会保存     │
│                ├── 检查内存缓存                              │
│                ├── 检查本地文件                              │
│                └── 请求 API → 仅内存缓存 ❌                  │
└─────────────────────────────────────────────────────────────┘
```

## 相关问题

### 当日数据下载的额外问题

当请求日期超出 trade_cal 覆盖范围时，系统采取降级策略：

1. **静默降级** - 不报错，继续执行
2. **使用自然日** - 可能请求非交易日（周末/节假日）
3. **依赖 TuShare API 处理** - 返回有则返回，无则返回空

代码位置: `app4/core/pagination.py` 第354-358行

```python
trade_days = self._get_trade_days(start_date, end_date)
if not trade_days:
    yield params  # ⚠️ 直接使用原始参数，无警告
    continue
```

### 缺少的警告机制

代码位置: `app4/core/pagination.py` 第490-496行

```python
def _get_trade_days(self, start_date, end_date):
    if not self.context.trade_calendar:
        return []  # ⚠️ 静默返回空列表，无警告日志
```

## 建议修复方案

### 方案 1: 在 downloader.py 中添加保存逻辑

在 `downloader.py` 的 `get_trade_calendar` 方法中，当从 API 获取数据后，调用 storage_manager 保存数据。

```python
# downloader.py 第381行之后添加
if trade_calendar:
    # 保存到本地存储
    if hasattr(self, 'storage_manager') and self.storage_manager:
        self.storage_manager.save_data('trade_cal', trade_calendar, async_write=False)
        logger.info(f"Saved {len(trade_calendar)} trade calendar records to storage")
    
    # 更新内存缓存
    with self._cache_lock:
        cache_key = (start_date, end_date)
        self._memory_cache["trade_cal"][cache_key] trade_calendar
```

### 方案 2: 使用全局缓存键

将运行时获取的 trade_cal 数据合并到全局缓存中，并持久化保存。

### 方案 3: 添加警告日志

在 `_get_trade_days` 方法中添加警告日志，提醒用户日期范围超出 trade_cal 覆盖范围。

## 优先级建议

| 问题 | 优先级 | 说明 |
|------|--------|------|
| 运行时 trade_cal 不保存 | 高 | 持续浪费 API 配额 |
| 缺少警告机制 | 中 | 影响用户体验和问题排查 |
| 降级到自然日 | 低 | TuShare API 会正确处理 |

## 相关文件

- `app4/main.py` - 启动时预加载逻辑
- `app4/core/downloader.py` - 运行时请求逻辑
- `app4/core/pagination.py` - 分页执行时的降级处理
- `app4/core/coverage_manager.py` - 覆盖率检测

## 创建日期

2026-02-23
