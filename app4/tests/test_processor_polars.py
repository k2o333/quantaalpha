import unittest
import polars as pl
import logging
from unittest.mock import patch, MagicMock
from app4.core.processor import DataProcessor

class TestProcessorPolars(unittest.TestCase):
    def setUp(self):
        self.processor = DataProcessor()
        # Suppress logging noise during normal tests
        logging.getLogger('app4.core.processor').setLevel(logging.CRITICAL)

    def test_handle_primary_keys_no_duplicates(self):
        df = pl.DataFrame({"id": [1, 2, 3], "val": ["a", "b", "c"]})
        config = {"api_name": "test", "output": {"primary_key": ["id"]}}
        
        with patch('app4.core.processor.logger') as mock_logger:
            result_df = self.processor._handle_primary_keys(df, config)
            # Should not log duplicate warning
            duplicate_warnings = [
                call for call in mock_logger.warning.call_args_list
                if "duplicate records" in str(call)
            ]
            self.assertEqual(len(duplicate_warnings), 0)

    def test_handle_primary_keys_with_duplicates(self):
        # 4 rows, 2 are duplicates of id=2
        df = pl.DataFrame({"id": [1, 2, 2, 3], "val": ["a", "b", "c", "d"]})
        config = {"api_name": "test", "output": {"primary_key": ["id"]}}
        
        with patch('app4.core.processor.logger') as mock_logger:
            result_df = self.processor._handle_primary_keys(df, config)
            # Should log warning for 1 duplicate record
            mock_logger.warning.assert_any_call(
                "Found 1 duplicate records (by primary key) for interface test"
            )

    def test_validate_data_empty_df(self):
        df = pl.DataFrame(schema={"id": pl.Int64})
        config = {"api_name": "test", "output": {"primary_key": ["id"]}}
        result = self.processor.validate_data(df, config)
        
        self.assertEqual(result['total_records'], 0)
        self.assertEqual(result['duplicate_records'], 0)
        self.assertTrue(result['valid'])

    def test_validate_data_no_primary_keys(self):
        df = pl.DataFrame({"id": [1, 1], "val": ["a", "a"]})
        config = {"api_name": "test", "output": {}} # No primary_key
        result = self.processor.validate_data(df, config)
        
        self.assertEqual(result['total_records'], 2)
        self.assertEqual(result['duplicate_records'], 0)
        self.assertTrue(result['valid'])

    def test_validate_data_with_duplicates(self):
        df = pl.DataFrame({"id": [1, 1, 2], "val": ["a", "b", "c"]})
        config = {"api_name": "test", "output": {"primary_key": ["id"]}}
        result = self.processor.validate_data(df, config)
        
        self.assertEqual(result['total_records'], 3)
        self.assertEqual(result['duplicate_records'], 1)
        self.assertEqual(result['unique'], 2)
        self.assertFalse(result['valid']) # Valid is False when duplicates exist

    def test_create_dataframe_fallback_logging(self):
        # Trigger fallback path using complex types that might fail simple pl.from_dicts
        # Let's mock pl.from_dicts to fail
        data = [{"id": 1}, {"id": 2}]
        with patch('polars.from_dicts', side_effect=[Exception("mock fail"), pl.DataFrame(data)]):
            with patch('app4.core.processor.logger') as mock_logger:
                df = self.processor._create_dataframe_row_by_row(data)
                
                # Verify warning handles the fallback
                mock_logger.warning.assert_any_call(
                    "pl.from_dicts failed for 2 rows, falling back to chunk mode: mock fail"
                )
                
                # Verify info logging matches our required format
                info_calls = [
                    call[0][0] for call in mock_logger.info.call_args_list
                    if "DataFrame fallback" in call[0][0]
                ]
                self.assertEqual(len(info_calls), 1)
                self.assertIn("2 rows", info_calls[0])
                self.assertIn("1 chunks", info_calls[0]) # 1000 chunk size, 2 rows -> 1 chunk

if __name__ == '__main__':
    unittest.main()
