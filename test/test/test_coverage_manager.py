"""Coverage Manager 测试文件 - 测试缓存与存储同步机制"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch
import polars as pl

from app4.core.coverage_manager import CoverageManager
from app4.core.storage import StorageManager
from app4.core.config_loader import ConfigLoader


def test_cache_storage_sync():
    """测试缓存与存储同步机制"""

    # 创建临时目录用于测试存储
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建模拟的 ConfigLoader
        config_loader = Mock(spec=ConfigLoader)
        config_loader.get_interface_config.return_value = {
            'duplicate_detection': {
                'enabled': True,
                'date_column': 'trade_date',
                'threshold': 0.95
            },
            'pagination': {
                'enabled': True,
                'mode': 'date_range'
            }
        }

        # 创建 StorageManager 实例
        storage_manager = StorageManager(storage_dir=temp_dir)
        storage_manager.start_writer() # 启动写入线程

        # 创建 CoverageManager 实例
        coverage_manager = CoverageManager(storage_manager, config_loader)

        # 模拟下载器
        downloader = Mock()
        # 模拟交易日历
        mock_calendar = [
            {'cal_date': '20230101', 'is_open': 1},
            {'cal_date': '20230102', 'is_open': 1},
            {'cal_date': '20230103', 'is_open': 1},
            {'cal_date': '20230104', 'is_open': 0},  # 非交易日
            {'cal_date': '20230105', 'is_open': 1},
        ]
        downloader.get_trade_calendar.return_value = mock_calendar
        coverage_manager.downloader = downloader

        interface_name = 'testdaily'  # 避免接口名包含下划线导致的文件名解析问题
        start_date = '20230101'
        end_date = '20230105'

        # 1. 首先检查初始状态 - 数据库中没有数据
        initial_status = coverage_manager.get_coverage_status(interface_name, start_date, end_date)
        assert initial_status['covered'] is False
        assert initial_status['total_found'] == 0
        assert initial_status['total_expected'] == 4  # 4个交易日

        # 2. 模拟向存储中写入部分数据
        test_data = pl.DataFrame({
            'ts_code': ['000001.SZ', '000001.SZ', '000002.SZ'],
            'trade_date': ['20230101', '20230102', '20230103'],
            'close': [10.1, 10.2, 10.3]
        })

        # 写入数据到存储
        coverage_manager.storage_manager.save_data(interface_name, test_data.to_dicts())

        # 等待数据处理完成（异步）
        import time
        time.sleep(0.2)  # 等待异步处理

        # 3. 检查缓存是否正确更新 - 应该有部分数据覆盖
        # 清除缓存以确保重新计算
        cache_key = f"{interface_name}:{start_date}:{end_date}"
        with coverage_manager._cache_lock:
            if cache_key in coverage_manager._coverage_cache:
                del coverage_manager._coverage_cache[cache_key]

        cached_status = coverage_manager.get_coverage_status(interface_name, start_date, end_date)
        assert cached_status['covered'] is False  # 因为覆盖率低于阈值 (3/4 = 0.75 < 0.95)
        assert cached_status['total_found'] == 3  # 找到了3个日期的数据
        assert cached_status['total_expected'] == 4  # 总共4个交易日

        # 4. 模拟写入更多数据，使覆盖率超过阈值
        additional_data = pl.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ'],
            'trade_date': ['20230105', '20230105'],  # 添加最后一个交易日的数据
            'close': [10.4, 10.5]
        })

        coverage_manager.storage_manager.save_data(interface_name, additional_data.to_dicts())

        # 等待数据处理完成（异步）
        time.sleep(0.2)  # 等待异步处理

        # 5. 清除缓存并重新检查 - 应该现在达到覆盖率阈值
        coverage_manager._coverage_cache.clear()
        updated_status = coverage_manager.get_coverage_status(interface_name, start_date, end_date)

        # 现在应该满足覆盖率要求，因为全部4个交易日都有数据
        assert updated_status['total_found'] == 4
        assert updated_status['total_expected'] == 4
        assert updated_status['coverage_rate'] == 1.0  # 100%覆盖率
        assert updated_status['covered'] is True  # 因为覆盖率 >= 0.95

        # 6. 测试 mark_as_completed 方法
        new_start_date = '20230106'
        new_end_date = '20230110'

        # 初始状态应该是未覆盖
        new_status_before = coverage_manager.get_coverage_status(interface_name, new_start_date, new_end_date)
        assert new_status_before['covered'] is False

        # 手动标记为已完成
        coverage_manager.mark_as_completed(interface_name, new_start_date, new_end_date)

        # 再次检查状态 - 应该被标记为已覆盖
        new_status_after = coverage_manager.get_coverage_status(interface_name, new_start_date, new_end_date)
        assert new_status_after['covered'] is True

        # 7. 测试 ts_code 特定标记
        ts_code_specific_start = '20230111'
        ts_code_specific_end = '20230115'

        # 初始状态
        ts_code_status_before = coverage_manager.get_coverage_status(interface_name, ts_code_specific_start, ts_code_specific_end)
        assert ts_code_status_before['covered'] is False

        # 标记特定 ts_code 完成
        coverage_manager.mark_as_completed(interface_name, ts_code_specific_start, ts_code_specific_end, ts_code='000001.SZ')

        # 检查是否正确更新
        ts_code_status_after = coverage_manager.get_coverage_status(interface_name, ts_code_specific_start, ts_code_specific_end)
        # 对于不区分股票代码的范围检查，标记特定ts_code不应该自动设为全覆盖
        # 但我们可以在缓存中看到更新的记录

        # 8. 测试 should_skip 方法
        # 首先，由于当前范围已覆盖，should_skip 应该返回 True
        params_with_dates = {
            'start_date': start_date,
            'end_date': end_date
        }
        skip_result = coverage_manager.should_skip(interface_name, params_with_dates, strategy='date_range')
        assert skip_result is True  # 因为已经满足覆盖条件

        # 对于未覆盖的范围，should_skip 应该返回 False
        params_new_range = {
            'start_date': '20230120',
            'end_date': '20230125'
        }
        skip_result_new = coverage_manager.should_skip(interface_name, params_new_range, strategy='date_range')
        assert skip_result_new is False  # 因为这个范围没有数据

        print("所有缓存与存储同步测试通过！")

        # 停止存储管理器的写入线程
        storage_manager.stop_writer()


if __name__ == "__main__":
    test_cache_storage_sync()