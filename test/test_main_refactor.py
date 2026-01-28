import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock

# Add the app4 directory to the Python path to import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app4'))

from app4.main import handle_stock_loop_interface


def test_stock_loop_unified_handler():
    """
    Test the unified stock_loop handling interface
    """
    # Mock the required dependencies
    with patch('app4.main.ConfigLoader') as mock_config_loader, \
         patch('app4.main.CacheWarmer') as mock_cache_warmer, \
         patch('app4.main.TaskScheduler') as mock_scheduler, \
         patch('app4.main.DataProcessor') as mock_processor, \
         patch('app4.main.StorageManager') as mock_storage_manager, \
         patch('app4.main.GenericDownloader') as mock_downloader_class, \
         patch('app4.main.RateLimiter') as mock_rate_limiter, \
         patch('app4.main.validate_and_adjust_date') as mock_validate_date, \
         patch('app4.main.__prepare_stock_list') as mock_prepare_stock_list, \
         patch('app4.main.__run_concurrent_stock_download') as mock_run_concurrent, \
         patch('app4.main.setup_logging') as mock_setup_logging:

        # Mock configuration loader
        mock_config_instance = Mock()
        mock_config_instance.get_interface_config.return_value = {'name': 'top10_holders', 'pagination': {'mode': 'stock_loop'}}
        mock_config_instance.get_global_config.return_value = {
            'concurrency': {'max_queue_size': 1000},
            'request': {'rate_limit': 60},
            'storage': {'base_dir': '../data', 'batch_size': 10000}
        }
        mock_config_loader.return_value = mock_config_instance

        # Mock cache warmer
        mock_cache_warmer_instance = Mock()
        mock_cache_warmer_instance.preload_trade_calendar.return_value = []
        mock_cache_warmer_instance.preload_stock_list.return_value = []
        mock_cache_warmer.return_value = mock_cache_warmer_instance

        # Mock scheduler
        mock_scheduler_instance = Mock()
        mock_scheduler.return_value = mock_scheduler_instance

        # Mock processor
        mock_processor_instance = Mock()
        mock_processor.return_value = mock_processor_instance

        # Mock storage manager
        mock_storage_manager_instance = Mock()
        mock_storage_manager.return_value = mock_storage_manager_instance

        # Mock downloader
        mock_downloader_instance = Mock()
        mock_downloader_class.return_value = mock_downloader_instance

        # Mock rate limiter
        mock_rate_limiter_instance = Mock()
        mock_rate_limiter.return_value = mock_rate_limiter_instance

        # Mock date validation
        mock_validate_date.return_value = ('20230101', '20231231')

        # Mock stock list preparation
        mock_prepare_stock_list.return_value = [{'ts_code': '000001.SZ'}, {'ts_code': '000002.SZ'}]

        # Mock concurrent download
        mock_run_concurrent.return_value = 100  # Mock that 100 records were downloaded

        # Test the function
        handle_stock_loop_interface('top10_holders', '20230101', '20231231',
                                   'parquet', '../data', 'INFO', 4, False, True)

        # Verify the function was called correctly
        assert mock_config_loader.called
        assert mock_cache_warmer.called
        assert mock_scheduler.called
        assert mock_processor.called
        assert mock_storage_manager.called
        assert mock_downloader_class.called
        assert mock_rate_limiter.called
        assert mock_validate_date.called
        assert mock_prepare_stock_list.called
        assert mock_run_concurrent.called

        print("test_stock_loop_unified_handler passed!")