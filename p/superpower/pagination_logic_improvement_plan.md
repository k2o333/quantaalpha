# 分页逻辑改进实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 优化分页逻辑减少重复数据，提升30-40%执行效率

**Architecture:** 智能分页策略，根据接口数据量级别和类型动态调整窗口大小

**Tech Stack:** Python, 日期处理, 数据分页算法

---

### Task 1: 实现智能分页策略

**Files:**
- Modify: `app4/core/downloader.py`

**Step 1: Write the failing test**

```python
# test_smart_pagination.py
from app4.core.downloader import GenericDownloader
from app4.core.config_loader import ConfigLoader

def test_smart_pagination_strategy():
    """测试智能分页策略"""
    config_loader = ConfigLoader('app4/config')
    downloader = GenericDownloader(config_loader)

    # 测试不同类型接口的窗口大小
    small_interfaces = ['fina_audit', 'forecast_vip']
    medium_interfaces = ['top10_holders', 'top10_floatholders', 'pledge_detail', 'dividend']
    financial_interfaces = ['balancesheet_vip', 'income_vip', 'cashflow_vip']

    for interface in small_interfaces:
        window_size = downloader._get_window_size_for_interface(interface)
        assert window_size >= 3650  # 小数据量接口使用大窗口

    for interface in medium_interfaces:
        window_size = downloader._get_window_size_for_interface(interface)
        assert 1000 <= window_size <= 2000  # 中等数据量接口使用中等窗口

    for interface in financial_interfaces:
        window_size = downloader._get_window_size_for_interface(interface)
        assert window_size >= 10000  # 财务数据接口使用大窗口
```

**Step 2: Run test to verify it fails**

运行: `pytest test_smart_pagination.py::test_smart_pagination_strategy -v`
Expected: FAIL with method not found

**Step 3: Write minimal implementation**

在 `app4/core/downloader.py` 中添加智能分页相关方法:

```python
def _get_window_size_for_interface(self, interface_name: str) -> int:
    """根据接口类型确定窗口大小"""
    # 定义接口数据量级别
    data_volume_config = {
        # 小数据量接口：每只股票数据量<100条
        'small': ['fina_audit', 'forecast_vip', 'express_vip', 'disclosure_date'],
        # 中等数据量：100-1000条
        'medium': ['top10_holders', 'top10_floatholders', 'pledge_detail', 'dividend',
                  'repurchase', 'concept_detail', 'share_float', 'stk_holdertrade'],
        # 大数据量：>1000条
        'large': ['stk_factor', 'stk_factor_pro', 'moneyflow_hsgt', 'moneyflow_north',
                 'moneyflow_stock', 'block_trade', 'stk_rewards', 'pledge_stat'],
        # 财务数据接口：全量数据
        'financial': ['balancesheet_vip', 'income_vip', 'cashflow_vip', 'fina_indicator_vip']
    }

    # 确定接口类型
    for typ, interfaces in data_volume_config.items():
        if interface_name in interfaces:
            if typ == 'small':
                return 3650  # 10年窗口，减少请求次数
            elif typ == 'medium':
                return 1825  # 5年窗口
            elif typ == 'financial':
                return 36500  # 100年，实际上一次性获取
            else:  # large
                return 365  # 默认1年窗口

    # 默认情况
    return 365

def _execute_date_range_pagination(self, interface_config, params):
    """智能分页 - 根据预期数据量调整窗口大小"""

    # 获取接口配置
    interface_name = interface_config['name']
    pagination_config = interface_config.get('pagination', {})

    # 获取参数
    start_date = params.get('start_date', '20050101')
    end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

    # 获取接口特定的窗口大小
    window_size = self._get_window_size_for_interface(interface_name)

    # 根据接口类型调整并发数
    if interface_name in ['fina_audit', 'forecast_vip', 'express_vip', 'disclosure_date']:
        max_workers = 1
    elif interface_name in ['top10_holders', 'top10_floatholders', 'pledge_detail', 'dividend']:
        max_workers = 2
    elif interface_name in ['balancesheet_vip', 'income_vip', 'cashflow_vip', 'fina_indicator_vip']:
        # 财务数据接口是全量返回，不应分页
        logger.info(f"财务接口{interface_name}使用全量请求模式")
        return self._fetch_with_retry(interface_config, params)
    else:
        max_workers = self.max_workers

    # 获取交易日历
    trade_days = self.get_trade_calendar(start_date, end_date)

    # 生成日期窗口
    windows = []
    for i in range(0, len(trade_days), window_size):
        window_trade_days = trade_days[i:i+window_size]
        if window_trade_days:  # 确保窗口不为空
            window_start = window_trade_days[0]['cal_date']
            window_end = window_trade_days[-1]['cal_date']
            windows.append((window_start, window_end))

    # 并发执行请求
    all_data = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 创建任务
        futures = []
        for window_start, window_end in windows:
            window_params = params.copy()
            window_params['start_date'] = window_start
            window_params['end_date'] = window_end

            future = executor.submit(
                self._fetch_with_retry,
                interface_config,
                window_params
            )
            futures.append(future)

        # 收集结果
        for future in as_completed(futures):
            try:
                data = future.result()
                if data:
                    all_data.extend(data)
            except Exception as e:
                logger.error(f"分页请求失败: {str(e)}")
                continue

    return all_data
```

**Step 4: Run test to verify it passes**

运行: `pytest test_smart_pagination.py::test_smart_pagination_strategy -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app4/core/downloader.py
git commit -m "feat: implement smart pagination strategy"
```

### Task 2: 实现前置去重功能

**Files:**
- Modify: `app4/core/downloader.py`

**Step 1: Write the failing test**

```python
# test_pre_deduplication.py
from app4.core.downloader import GenericDownloader
from app4.core.config_loader import ConfigLoader
import tempfile
import os

def test_pre_deduplication():
    """测试前置去重功能"""
    config_loader = ConfigLoader('app4/config')
    downloader = GenericDownloader(config_loader)

    # 创建临时数据目录结构
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建测试数据文件
        import polars as pl
        df = pl.DataFrame({
            'ts_code': ['000001.SZ'],
            'trade_date': ['20230101'],
            'value': [100]
        })

        interface_dir = os.path.join(temp_dir, 'test_interface')
        os.makedirs(interface_dir, exist_ok=True)
        df.write_parquet(os.path.join(interface_dir, 'test.parquet'))

        # 测试前置去重检查
        exists = downloader._is_stock_data_exists('test_interface', '000001.SZ', temp_dir)
        assert exists is True

        exists = downloader._is_stock_data_exists('test_interface', '000002.SZ', temp_dir)
        assert exists is False
```

**Step 2: Run test to verify it fails**

运行: `pytest test_pre_deduplication.py::test_pre_deduplication -v`
Expected: FAIL with method not found

**Step 3: Write minimal implementation**

在 `app4/core/downloader.py` 中添加前置去重相关方法:

```python
def _is_stock_data_exists(self, interface_name: str, ts_code: str, storage_dir: str = None) -> bool:
    """检查股票数据是否已存在"""
    if storage_dir is None:
        storage_dir = self.global_config.get('storage', {}).get('base_dir', '../data')

    dir_path = os.path.join(storage_dir, interface_name)

    if not os.path.exists(dir_path):
        return False

    try:
        # 读取现有数据
        df = pl.read_parquet(dir_path)

        # 检查该股票是否存在
        return df.filter(pl.col('ts_code') == ts_code).height > 0
    except Exception:
        return False

def _execute_stock_loop_pagination(self, interface_config, params):
    """股票循环分页 - 增加前置去重"""

    all_data = []
    stock_list = self._get_stock_list()  # 使用改进后的获取股票列表方法

    # 根据接口类型确定并发数
    interface_name = interface_config['name']
    if interface_name in ['fina_audit', 'forecast_vip', 'express_vip', 'disclosure_date']:
        max_workers = 1
    elif interface_name in ['top10_holders', 'top10_floatholders', 'pledge_detail', 'dividend']:
        max_workers = 2
    else:
        max_workers = self.max_workers

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 创建任务
        futures = []
        for stock in stock_list:
            ts_code = stock['ts_code']

            # 前置去重：检查本地是否已有该股票的数据
            if self._is_stock_data_exists(interface_name, ts_code):
                logger.info(f"股票{ts_code}数据已存在，跳过")
                continue

            # 准备参数
            stock_params = params.copy()
            stock_params['ts_code'] = ts_code

            future = executor.submit(
                self._fetch_with_retry,
                interface_config,
                stock_params
            )
            futures.append(future)

        # 收集结果
        for future in as_completed(futures):
            try:
                data = future.result()
                if data:
                    all_data.extend(data)
            except Exception as e:
                logger.error(f"获取股票数据失败: {str(e)}")
                continue

    return all_data
```

**Step 4: Run test to verify it passes**

运行: `pytest test_pre_deduplication.py::test_pre_deduplication -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app4/core/downloader.py
git commit -m "feat: implement pre-deduplication in pagination"
```