import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, MagicMock
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app4.core.storage import StorageManager
from app4.core.processor import DataProcessor

class TestStorageManagerCache(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_processor = Mock(spec=DataProcessor)
        self.temp_dir = tempfile.mkdtemp()
        self.storage_manager = StorageManager(
            processor=self.mock_processor,
            storage_dir=self.temp_dir
        )

    def test_initialization_with_cache_attributes(self):
        """Test that StorageManager has new cache-related attributes."""
        self.assertTrue(hasattr(self.storage_manager, 'interface_buffers'))
        self.assertTrue(hasattr(self.storage_manager, 'process_queue'))
        self.assertTrue(hasattr(self.storage_manager, 'buffer_threshold'))
        self.assertTrue(hasattr(self.storage_manager, 'buffer_lock'))
        self.assertTrue(hasattr(self.storage_manager, 'failed_interfaces'))
        self.assertEqual(self.storage_manager.buffer_threshold, 5000)

    def test_buffer_initialization(self):
        """Test that interface buffer is initialized when adding data."""
        interface_name = 'test_interface'
        data = [{'id': 1, 'value': 'test'}]
        self.storage_manager.add_to_buffer(interface_name, data)

        self.assertIn(interface_name, self.storage_manager.interface_buffers)
        buffer = self.storage_manager.interface_buffers[interface_name]
        self.assertEqual(buffer['count'], 1)
        self.assertEqual(len(buffer['data']), 1)

    def test_buffer_threshold_not_reached(self):
        """Test that data is accumulated but not processed when threshold not reached."""
        interface_name = 'test_interface'
        data = [{'id': i, 'value': f'test_{i}'} for i in range(100)]  # Less than 5000
        self.storage_manager.add_to_buffer(interface_name, data)

        buffer = self.storage_manager.interface_buffers[interface_name]
        self.assertEqual(buffer['count'], 100)
        self.assertEqual(len(buffer['data']), 100)
        # Process queue should be empty
        self.assertEqual(self.storage_manager.process_queue.qsize(), 0)

    def test_buffer_threshold_reached(self):
        """Test that data is processed when threshold is reached."""
        interface_name = 'test_interface'
        # Add data that will exceed threshold
        data = [{'id': i, 'value': f'test_{i}'} for i in range(5000)]
        self.storage_manager.add_to_buffer(interface_name, data)

        buffer = self.storage_manager.interface_buffers[interface_name]
        self.assertEqual(buffer['count'], 0)  # Should be reset after processing
        # Process queue should contain the task
        self.assertEqual(self.storage_manager.process_queue.qsize(), 1)

    def test_multiple_interfaces_isolation(self):
        """Test that different interfaces have separate buffers."""
        interface1 = 'interface_1'
        interface2 = 'interface_2'

        data1 = [{'id': i, 'value': f'test_{i}'} for i in range(2500)]
        data2 = [{'id': i, 'value': f'test2_{i}'} for i in range(2500)]

        self.storage_manager.add_to_buffer(interface1, data1)
        self.storage_manager.add_to_buffer(interface2, data2)

        # Both interfaces should have data in their buffers
        self.assertEqual(self.storage_manager.interface_buffers[interface1]['count'], 2500)
        self.assertEqual(self.storage_manager.interface_buffers[interface2]['count'], 2500)

        # Process queue should be empty (threshold not reached)
        self.assertEqual(self.storage_manager.process_queue.qsize(), 0)

    def test_failed_interfaces_management(self):
        """Test that failed interfaces are tracked properly."""
        interface_name = 'test_interface'

        self.assertFalse(interface_name in self.storage_manager.get_failed_interfaces())

        self.storage_manager.failed_interfaces.add(interface_name)

        self.assertTrue(interface_name in self.storage_manager.get_failed_interfaces())

        # Test clear functionality
        self.storage_manager.clear_failed_interface(interface_name)

        self.assertFalse(interface_name in self.storage_manager.get_failed_interfaces())

    def test_flush_remaining_data(self):
        """Test that flush_remaining_data processes all remaining data in buffers."""
        interface_name = 'test_interface'
        data = [{'id': i, 'value': f'test_{i}'} for i in range(2500)]  # Less than threshold

        self.storage_manager.add_to_buffer(interface_name, data)

        # Verify data is in buffer but not processed
        self.assertEqual(self.storage_manager.interface_buffers[interface_name]['count'], 2500)
        initial_queue_size = self.storage_manager.process_queue.qsize()

        # Call flush to process remaining data
        self.storage_manager.flush_remaining_data()

        # Verify buffer is cleared and data is in process queue
        self.assertEqual(self.storage_manager.interface_buffers[interface_name]['count'], 0)
        final_queue_size = self.storage_manager.process_queue.qsize()

        # Should have added one task to process queue
        self.assertEqual(final_queue_size, initial_queue_size + 1)


class TestDownloaderBufferIntegration(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_config_loader = Mock()
        self.mock_processor = Mock(spec=DataProcessor)
        self.mock_storage_manager = Mock(spec=StorageManager)

        # Set up mock return values
        self.mock_storage_manager.interface_buffers = {}
        self.mock_storage_manager.buffer_threshold = 5000
        self.mock_storage_manager.failed_interfaces = set()

        # Import here to avoid issues
        from app4.core.downloader import GenericDownloader
        self.downloader = GenericDownloader(self.mock_config_loader)
        self.downloader.storage_manager = self.mock_storage_manager

    def test_download_single_stock_calls_add_to_buffer(self):
        """Test that download_single_stock calls add_to_buffer after download."""
        interface_config = {
            'api_name': 'test_interface',
            'parameters': {}
        }
        stock = {'ts_code': '000001.SZ'}
        base_params = {'ts_code': '000001.SZ'}

        # Mock the download_data method to return test data
        test_data = [{'ts_code': '000001.SZ', 'trade_date': '20230101'}]
        self.downloader.tushare_api = Mock()
        self.downloader.tushare_api.call_tushare_api = Mock(return_value=test_data)

        # Perform download
        result = self.downloader.download_single_stock(interface_config, stock, base_params)

        # Verify that add_to_buffer was called
        self.mock_storage_manager.add_to_buffer.assert_called_once_with('test_interface', test_data)


class TestMainInitialization(unittest.TestCase):
    def test_storage_manager_initialized_with_processor(self):
        """Test that StorageManager is initialized with processor reference."""
        from app4.core.processor import DataProcessor
        mock_processor = Mock(spec=DataProcessor)

        # Create StorageManager with processor
        temp_dir = tempfile.mkdtemp()
        storage_manager = StorageManager(
            processor=mock_processor,
            storage_dir=temp_dir
        )

        # Verify that processor is stored
        self.assertEqual(storage_manager.processor, mock_processor)