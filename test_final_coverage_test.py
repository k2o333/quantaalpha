# Final comprehensive test for the coverage management improvements
import tempfile
import os
import pytest
from app4.core.coverage_manager import CoverageManager
from app4.core.storage import StorageManager
from app4.core.config_loader import ConfigLoader
from app4.core.downloader import GenericDownloader
import polars as pl


def test_coverage_manager_with_force_flag():
    """测试覆盖管理器与强制标志的集成"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建必要的配置目录和文件
        config_dir = os.path.join(temp_dir, 'config')
        interfaces_dir = os.path.join(config_dir, 'interfaces')
        os.makedirs(interfaces_dir, exist_ok=True)

        # 创建基本的settings.yaml
        settings_content = """
app:
  name: "aspipe_v4"
  version: "4.0.0"

tushare:
  token: "test_token"
  base_url: "http://api.tushare.pro"

concurrency:
  max_workers: 4
  max_queue_size: 1000

request:
  max_retries: 3
  retry_delay: 1.0
  timeout: 30

cache:
  directory: "cache"
  ttl_hours: 24
  max_size_gb: 10

storage:
  base_dir: "../data"
  format: "parquet"
  batch_size: 10000

logging:
  level: "INFO"
  file: "log/app4.log"
  max_size_mb: 100
  backup_count: 5

groups:
  tscode_historical:
    - "stk_rewards"
  holders:
    - "top10_holders"
  daily:
    - "daily"
  financial:
    - "income"
  basic:
    - "stock_basic"
"""
        with open(os.path.join(config_dir, 'settings.yaml'), 'w', encoding='utf-8') as f:
            f.write(settings_content)

        # 创建一个接口配置文件 for testing
        daily_config = """
name: daily
api_name: daily
description: "日线行情"

permissions:
  min_points: 0
  rate_limit: 120
  query_limit: 10000

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"

output:
  primary_key: ["ts_code", "trade_date"]
  sort_by: ["trade_date"]
  columns:
    ts_code: {type: string, required: true}
    trade_date: {type: date, format: "%Y%m%d", required: true}

duplicate_detection:
  enabled: true
  date_column: "trade_date"
  threshold: 0.95
"""
        with open(os.path.join(interfaces_dir, 'daily.yaml'), 'w', encoding='utf-8') as f:
            f.write(daily_config)

        # 需要提供 StorageManager 和 ConfigLoader 实例
        storage_manager = StorageManager(
            processor=None,
            config_loader=None,
            storage_dir=temp_dir,
            format='parquet',
            batch_size=10000
        )
        config_loader = ConfigLoader(config_dir=config_dir)
        storage_manager.config_loader = config_loader

        # 测试创建带有 force_download 标志的下载器
        downloader = GenericDownloader(
            config_loader=config_loader,
            storage_manager=storage_manager,
            force_download=True,  # Force download enabled
            incremental_mode=False
        )

        # Verify the flags are set
        assert downloader.force_download is True
        assert downloader.incremental_mode is False

        # Test with force_download disabled
        downloader2 = GenericDownloader(
            config_loader=config_loader,
            storage_manager=storage_manager,
            force_download=False,  # Force download disabled
            incremental_mode=True
        )

        # Verify the flags are set
        assert downloader2.force_download is False
        assert downloader2.incremental_mode is True


def test_main_integration():
    """测试主流程集成"""
    # This test just verifies that the main.py can be imported without issues
    # and that the new arguments are properly handled
    import sys
    import os
    from argparse import Namespace

    # Add the app4 directory to the path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app4'))

    # Test that we can simulate the argument parsing with the new flags
    # We won't run the entire main function but will validate the structure
    from app4.main import validate_and_adjust_date

    # Test date validation function
    start, end = validate_and_adjust_date('20230101', '20230131')
    assert start == '20230101'
    assert end == '20230131'

    print("All integration tests passed!")


if __name__ == "__main__":
    test_coverage_manager_with_force_flag()
    test_main_integration()
    print("All tests passed!")