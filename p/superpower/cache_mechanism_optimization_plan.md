# 缓存机制优化实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复缓存机制设计缺陷，减少90-100秒性能浪费，提升系统整体性能

**Architecture:** 全局缓存预热器模式，通过预加载交易日历和股票列表到内存实现高效缓存

**Tech Stack:** Python, Polars, 多线程, 缓存管理

---

### Task 1: 创建缓存预热器类

**Files:**
- Create: `app4/core/cache_warmer.py`

**Step 1: Write the failing test**

```python
# test_cache_warmer.py
from app4.core.cache_warmer import CacheWarmer
import tempfile
import os

def test_cache_warmer_initialization():
    """测试缓存预热器初始化"""
    with tempfile.TemporaryDirectory() as temp_dir:
        warmer = CacheWarmer(temp_dir)
        assert warmer.data_dir == temp_dir
        assert warmer.trade_calendar_cache is None
        assert warmer.stock_list_cache is None
```

**Step 2: Run test to verify it fails**

运行: `pytest test_cache_warmer.py::test_cache_warmer_initialization -v`
Expected: FAIL with file not found

**Step 3: Write minimal implementation**

```python
import os
import polars as pl
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class CacheWarmer:
    """全局缓存预热器 - 在程序启动时加载常用数据到内存"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.trade_calendar_cache = None
        self.stock_list_cache = None

    def preload_trade_calendar(self) -> Optional[List[Dict[str, Any]]]:
        """预加载交易日历到内存"""
        if self.trade_calendar_cache is not None:
            return self.trade_calendar_cache

        trade_cal_dir = os.path.join(self.data_dir, 'trade_cal')

        if not os.path.exists(trade_cal_dir):
            logger.warning(f"交易日历目录不存在: {trade_cal_dir}")
            return None

        try:
            # 读取所有交易日历文件
            df = pl.read_parquet(trade_cal_dir)

            # 过滤有效交易日
            df = df.filter(
                (pl.col('is_open') == 1) &
                (pl.col('exchange') == 'SSE')
            ).select(['cal_date', 'is_open', 'exchange'])

            # 去重并排序
            df = df.unique(subset=['cal_date'], keep='last').sort('cal_date')

            # 转换为字典列表
            self.trade_calendar_cache = df.to_dicts()

            logger.info(f"预加载交易日历成功: {len(self.trade_calendar_cache)}条记录")

            return self.trade_calendar_cache

        except Exception as e:
            logger.error(f"预加载交易日历失败: {str(e)}")
            return None

    def preload_stock_list(self) -> Optional[List[Dict[str, Any]]]:
        """预加载股票列表到内存"""
        if self.stock_list_cache is not None:
            return self.stock_list_cache

        stock_basic_dir = os.path.join(self.data_dir, 'stock_basic')

        if not os.path.exists(stock_basic_dir):
            logger.warning(f"股票列表目录不存在: {stock_basic_dir}")
            return None

        try:
            # 读取股票列表
            df = pl.read_parquet(stock_basic_dir)

            # 过滤有效股票
            df = df.filter(pl.col('status') == 'L')  # 只保留上市股票

            # 转换为字典列表
            self.stock_list_cache = df.to_dicts()

            logger.info(f"预加载股票列表成功: {len(self.stock_list_cache)}只股票")

            return self.stock_list_cache

        except Exception as e:
            logger.error(f"预加载股票列表失败: {str(e)}")
            return None

    def get_trade_calendar(self, start_date: str, end_date: str) -> Optional[List[Dict[str, Any]]]:
        """从缓存获取指定日期范围的交易日历"""
        if self.trade_calendar_cache is None:
            return None

        # 过滤日期范围
        filtered = [
            day for day in self.trade_calendar_cache
            if start_date <= day['cal_date'] <= end_date
        ]

        return filtered if filtered else None

    def get_stock_list(self) -> Optional[List[Dict[str, Any]]]:
        """从缓存获取股票列表"""
        return self.stock_list_cache
```

**Step 4: Run test to verify it passes**

运行: `pytest test_cache_warmer.py::test_cache_warmer_initialization -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app4/core/cache_warmer.py
git commit -m "feat: implement CacheWarmer class"
```

### Task 2: 修改Downloader以使用缓存预热器

**Files:**
- Modify: `app4/core/downloader.py`

**Step 1: Write the failing test**

```python
# test_downloader_cache_integration.py
from app4.core.downloader import GenericDownloader
from app4.core.config_loader import ConfigLoader
from app4.core.cache_warmer import CacheWarmer

def test_downloader_with_cache_warmer():
    """测试Downloader与缓存预热器集成"""
    config_loader = ConfigLoader('app4/config')

    # 创建模拟缓存
    mock_trade_cal = [{'cal_date': '20230101', 'is_open': 1, 'exchange': 'SSE'}]
    mock_stock_list = [{'ts_code': '000001.SZ', 'name': '平安银行'}]

    downloader = GenericDownloader(
        config_loader=config_loader,
        max_workers=1,
        trade_calendar_cache=mock_trade_cal,
        stock_list_cache=mock_stock_list
    )

    # 验证缓存被正确设置
    assert downloader._memory_cache['trade_cal'][('global',)] == mock_trade_cal
    assert downloader._memory_cache['stock_list'] == mock_stock_list
```

**Step 2: Run test to verify it fails**

运行: `pytest test_downloader_cache_integration.py::test_downloader_with_cache_warmer -v`
Expected: FAIL with parameter not found

**Step 3: Write minimal implementation**

修改 `app4/core/downloader.py` 中的 `GenericDownloader` 类构造函数:

```python
def __init__(self, config_loader, max_workers=4,
             trade_calendar_cache=None, stock_list_cache=None):
    # ... 现有初始化代码 ...

    # 使用传入的缓存（如果不为None）
    if trade_calendar_cache is not None:
        with self._cache_lock:
            self._memory_cache['trade_cal'][('global',)] = trade_calendar_cache

    if stock_list_cache is not None:
        with self._cache_lock:
            self._memory_cache['stock_list'] = stock_list_cache
```

同时修改 `get_trade_calendar` 方法使用全局缓存键:

```python
def get_trade_calendar(self, start_date: str, end_date: str) -> Optional[List[Dict[str, Any]]]:
    """获取交易日历，优先使用预热缓存"""
    # 使用全局缓存键
    cache_key = ('global',)  # 改为固定键

    with self._cache_lock:
        if cache_key in self._memory_cache['trade_cal']:
            # 从全局缓存过滤日期范围
            all_days = self._memory_cache['trade_cal'][cache_key]
            if all_days:
                return [d for d in all_days if start_date <= d['cal_date'] <= end_date]

    # 回退到原有逻辑
    return self._get_trade_calendar_from_data_dir(start_date, end_date) or self._fetch_from_api(start_date, end_date)
```

**Step 4: Run test to verify it passes**

运行: `pytest test_downloader_cache_integration.py::test_downloader_with_cache_warmer -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app4/core/downloader.py
git commit -m "feat: integrate cache warmer with downloader"
```

### Task 3: 在main.py中集成缓存预热器

**Files:**
- Modify: `app4/main.py`

**Step 1: Write the failing test**

此任务集成到现有main.py，不需要单独测试

**Step 2: Write minimal implementation**

修改 `app4/main.py` 文件，添加缓存预热器的初始化和使用:

```python
# 在文件顶部导入CacheWarmer
from app4.core.cache_warmer import CacheWarmer

# 在main函数中添加缓存预热逻辑
def main():
    # ... 现有参数解析代码 ...

    # 初始化缓存预热器
    data_dir = config_loader.get_global_config()['storage']['base_dir']
    cache_warmer = CacheWarmer(data_dir)

    # 预热缓存
    logger.info("预热全局缓存...")
    trade_cal_cache = cache_warmer.preload_trade_calendar()
    stock_list_cache = cache_warmer.preload_stock_list()

    # 传递缓存到Downloader
    downloader = GenericDownloader(
        config_loader=config_loader,
        max_workers=args.max_workers,
        trade_calendar_cache=trade_cal_cache,  # 传递交易日历缓存
        stock_list_cache=stock_list_cache      # 传递股票列表缓存
    )

    # ... 其余现有代码 ...
```

**Step 3: Commit**

```bash
git add app4/main.py
git commit -m "feat: integrate cache warmer in main entry point"
```