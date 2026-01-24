# 覆盖管理改进实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现智能覆盖管理器，支持增量更新和强制覆盖，提升用户体验

**Architecture:** CoverageManager类实现智能判断逻辑，集成到主下载流程

**Tech Stack:** Python, Polars, 命令行参数解析

---

### Task 1: 创建CoverageManager类

**Files:**
- Create: `app4/core/coverage_manager.py`

**Step 1: Write the failing test**

```python
# test_coverage_manager.py
from app4.core.coverage_manager import CoverageManager
import tempfile
import os

def test_coverage_manager_initialization():
    """测试覆盖管理器初始化"""
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = CoverageManager(temp_dir)
        assert manager.storage_dir == temp_dir
```

**Step 2: Run test to verify it fails**

运行: `pytest test_coverage_manager.py::test_coverage_manager_initialization -v`
Expected: FAIL with file not found

**Step 3: Write minimal implementation**

```python
# /home/quan/testdata/aspipe_v4/app4/core/coverage_manager.py

import os
import polars as pl
from typing import Optional, List, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

class CoverageManager:
    """智能覆盖管理器 - 支持增量更新和强制覆盖"""

    def __init__(self, storage_dir: str):
        self.storage_dir = storage_dir

    def should_skip_stock(self, interface: str, ts_code: str,
                         start_date: str = None, end_date: str = None,
                         force: bool = False) -> Tuple[bool, str]:
        """
        智能判断是否跳过股票

        Returns:
            (should_skip, reason)
        """
        if force:
            return False, "强制覆盖模式"

        # 检查数据文件是否存在
        dir_path = os.path.join(self.storage_dir, interface)
        if not os.path.exists(dir_path):
            return False, "数据目录不存在"

        try:
            df = pl.read_parquet(dir_path)

            # 检查股票是否存在
            stock_data = df.filter(pl.col('ts_code') == ts_code)
            if stock_data.is_empty():
                return False, "股票数据不存在"

            # 如果有日期参数，检查时间范围
            if start_date and end_date:
                # 确定日期列名
                if 'trade_date' in df.columns:
                    date_col = 'trade_date'
                elif 'ann_date' in df.columns:
                    date_col = 'ann_date'
                elif 'end_date' in df.columns:
                    date_col = 'end_date'
                else:
                    return True, "股票数据已存在（无法检查日期范围）"

                # 检查是否已有该时间范围的数据
                existing_start = stock_data[date_col].min()
                existing_end = stock_data[date_col].max()

                if existing_start <= start_date and existing_end >= end_date:
                    return True, f"数据已完整存在（{existing_start}至{existing_end}）"
                else:
                    return False, f"数据部分存在，需补充（现有：{existing_start}至{existing_end}，需要：{start_date}至{end_date}）"

            return True, "股票数据已存在"

        except Exception as e:
            # 读取失败，视为不存在，重新下载
            return False, f"读取现有数据失败：{str(e)}"
```

**Step 4: Run test to verify it passes**

运行: `pytest test_coverage_manager.py::test_coverage_manager_initialization -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app4/core/coverage_manager.py
git commit -m "feat: implement CoverageManager class"
```

### Task 2: 在main.py中集成覆盖管理

**Files:**
- Modify: `app4/main.py`

**Step 1: Write the failing test**

此任务集成到现有main.py，不需要单独测试

**Step 2: Write minimal implementation**

修改 `app4/main.py` 文件，添加命令行参数和覆盖管理器集成:

```python
# 在参数解析部分添加新参数
parser.add_argument('--force', action='store_true',
                   help='强制覆盖已存在的数据')
parser.add_argument('--incremental', action='store_true',
                   help='增量模式 - 只下载缺失的时间段')

# 修改process_interface函数或添加新的处理逻辑
def process_interface_with_coverage(args, config_loader, downloader, storage, dedup):
    """使用覆盖管理器处理接口"""
    from app4.core.coverage_manager import CoverageManager

    # 初始化覆盖管理器
    storage_dir = config_loader.get_global_config()['storage']['base_dir']
    coverage_manager = CoverageManager(storage_dir)

    # 如果是ts_code依赖的接口，检查是否需要跳过
    if args.ts_code:
        should_skip, reason = coverage_manager.should_skip_stock(
            interface=args.interface,
            ts_code=args.ts_code,
            start_date=args.start_date,
            end_date=args.end_date,
            force=args.force
        )

        if should_skip and not args.force:
            logger.info(f"跳过 {args.ts_code}：{reason}")
            return
        else:
            logger.info(f"处理 {args.ts_code}：{reason}")

    # 调用原有的处理逻辑
    process_interface(args, config_loader, downloader, storage, dedup)
```

将主执行逻辑中的interface处理部分替换为使用覆盖管理的版本。

**Step 3: Commit**

```bash
git add app4/main.py
git commit -m "feat: integrate CoverageManager with main entry point"
```

### Task 3: 验证和测试覆盖管理器

**Files:**
- Create: `test/test_coverage_manager.py`

**Step 1: Write the failing test**

```python
# test/test_coverage_manager.py
import tempfile
import os
import pytest
from app4.core.coverage_manager import CoverageManager
import polars as pl

def test_should_skip_stock_logic():
    """测试覆盖管理器的跳过逻辑"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建测试数据
        df = pl.DataFrame({
            'ts_code': ['000001.SZ', '000001.SZ'],
            'trade_date': ['20230101', '20230102'],
            'value': [100, 200]
        })

        interface_dir = os.path.join(temp_dir, 'test_interface')
        os.makedirs(interface_dir)
        df.write_parquet(os.path.join(interface_dir, 'test.parquet'))

        manager = CoverageManager(temp_dir)

        # 1. 测试强制覆盖模式
        should_skip, reason = manager.should_skip_stock(
            interface='test_interface',
            ts_code='000001.SZ',
            start_date='20230101',
            end_date='20230102',
            force=True
        )
        assert should_skip is False
        assert reason == "强制覆盖模式"

        # 2. 测试数据已完整存在
        should_skip, reason = manager.should_skip_stock(
            interface='test_interface',
            ts_code='000001.SZ',
            start_date='20230101',
            end_date='20230102',
            force=False
        )
        assert should_skip is True
        assert "数据已完整存在" in reason

        # 3. 测试部分数据存在，需要补充
        should_skip, reason = manager.should_skip_stock(
            interface='test_interface',
            ts_code='000001.SZ',
            start_date='20221201',
            end_date='20230105',
            force=False
        )
        assert should_skip is False
        assert "数据部分存在，需补充" in reason

        # 4. 测试股票数据不存在
        should_skip, reason = manager.should_skip_stock(
            interface='test_interface',
            ts_code='000002.SZ',
            force=False
        )
        assert should_skip is False
        assert "股票数据不存在" in reason
```

**Step 2: Run test to verify it passes**

运行: `pytest test/test_coverage_manager.py::test_should_skip_stock_logic -v`
Expected: PASS

**Step 3: Commit**

```bash
git add test/test_coverage_manager.py
git commit -m "test: add tests for CoverageManager"
```