# test/test_coverage_manager.py
import tempfile
import os
import pytest
from app4.core.coverage_manager import CoverageManager
from app4.core.storage import StorageManager
from app4.core.config_loader import ConfigLoader
import polars as pl


def test_coverage_manager_initialization():
    """测试覆盖管理器初始化"""
    # 由于ConfigLoader需要配置文件，使用临时路径进行测试
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

        # 需要提供 StorageManager 和 ConfigLoader 实例
        storage_manager = StorageManager(
            processor=None,  # We can pass None for this test
            config_loader=None,  # We'll set this after creating config_loader
            storage_dir=temp_dir,
            format='parquet',
            batch_size=10000
        )
        config_loader = ConfigLoader(config_dir=config_dir)

        # Update storage manager with the config_loader
        storage_manager.config_loader = config_loader

        manager = CoverageManager(storage_manager, config_loader)

        # Test basic initialization
        assert manager.storage_manager == storage_manager
        assert manager.config_loader == config_loader


def test_should_skip_methods():
    """测试覆盖管理器的跳过逻辑"""
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

        manager = CoverageManager(storage_manager, config_loader)

        # Test should_skip method with different strategies
        params = {
            'start_date': '20230101',
            'end_date': '20230131',
            'ts_code': '000001.SZ'
        }

        # Test that it doesn't fail with basic parameters
        result = manager.should_skip('daily', params, strategy='date_range')
        # This might return False if no data exists, which is expected
        assert isinstance(result, bool)

        # Test with different strategies
        result_period = manager.should_skip('daily', params, strategy='period')
        assert isinstance(result_period, bool)

        result_stock = manager.should_skip('daily', params, strategy='stock')
        assert isinstance(result_stock, bool)


def test_coverage_status_methods():
    """测试覆盖率状态获取方法"""
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

        manager = CoverageManager(storage_manager, config_loader)

        # Test get_coverage_status method
        status = manager.get_coverage_status('daily', '20230101', '20230131')

        # Should return a dict with coverage info
        assert isinstance(status, dict)
        assert 'covered' in status
        assert 'coverage_rate' in status