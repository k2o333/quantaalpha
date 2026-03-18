"""
Data deduplication module for aspipe_v4.

This module provides unified data deduplication logic across the system,
with detailed statistics tracking and flexible configuration options.
"""

import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple, Any
import polars as pl
from datetime import datetime
import logging
import time
import os


@dataclass
class DedupStats:
    """
    Statistics for deduplication operations.
    """
    # Input metrics
    input_rows: int = 0
    input_duplicates: int = 0

    # Processing metrics
    processed_rows: int = 0
    compared_rows: int = 0

    # Output metrics
    output_rows: int = 0
    removed_rows: int = 0

    # Performance metrics
    processing_time_ms: float = 0.0
    comparison_time_ms: float = 0.0

    # Status tracking
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, error: str) -> None:
        """Add an error message to the stats."""
        self.errors.append(error)

    def add_warning(self, warning: str) -> None:
        """Add a warning message to the stats."""
        self.warnings.append(warning)

    def get_dedup_rate(self) -> float:
        """Calculate the deduplication rate."""
        if self.input_rows == 0:
            return 0.0
        return (self.removed_rows / self.input_rows) * 100

    def get_efficiency(self) -> float:
        """Calculate processing efficiency."""
        if self.input_rows == 0:
            return 0.0
        return (self.output_rows / self.input_rows) * 100


class DataDeduplicator:
    """
    Unified data deduplication class with flexible configuration and statistics tracking.
    """

    DEFAULT_CONFIG = {
        'primary_keys': ['ts_code', 'trade_date'],  # Default primary key fields
        'hash_fields': None,  # If None, uses primary_keys for hashing
        'keep_strategy': 'first',  # 'first', 'last', 'latest_date'
        'date_field': 'trade_date',  # Field to use for 'latest_date' strategy
        'case_sensitive': True,  # Whether string comparisons are case sensitive
        'ignore_fields': set(),  # Fields to ignore during duplicate detection
        'allow_partial_matches': False,  # Whether to allow partial matching
        'max_memory_usage': 1024 * 1024 * 100,  # 100MB max memory for hash sets
        'enable_stats': True,
        'validate_schema': True,
        'remove_null_duplicates': True,  # Remove rows that are completely null
        'fuzzy_threshold': 0.95  # For fuzzy matching (if implemented)
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the deduplicator with configuration.

        Args:
            config: Optional configuration dictionary. Will be merged with DEFAULT_CONFIG.
        """
        self.config = {**self.DEFAULT_CONFIG}
        if config:
            self.config.update(config)

        self.logger = logging.getLogger(__name__)
        self.stats = DedupStats()
        self._hash_cache: Optional[Set[str]] = None
        self._memory_usage = 0

    def deduplicate(self, df: pl.DataFrame,
                   primary_keys: Optional[List[str]] = None,
                   reset_stats: bool = True) -> Tuple[pl.DataFrame, DedupStats]:
        """
        Deduplicate data based on primary keys.

        Args:
            df: Input DataFrame to deduplicate
            primary_keys: Override primary keys for this operation
            reset_stats: Whether to reset statistics before operation

        Returns:
            Tuple of (deduplicated DataFrame, statistics)
        """
        start_time = time.time()

        if reset_stats:
            self.stats = DedupStats()

        # Update input stats
        self.stats.input_rows = len(df)

        if len(df) == 0:
            self.stats.processing_time_ms = (time.time() - start_time) * 1000
            return df, self.stats

        # Validate schema if enabled
        if self.config['validate_schema']:
            validation_result = self._validate_schema(df, primary_keys)
            if not validation_result:
                self.stats.add_error("Schema validation failed")
                return df, self.stats

        # Determine primary keys to use
        keys_to_use = primary_keys or self.config['primary_keys']
        if isinstance(keys_to_use, str):
            keys_to_use = [keys_to_use]

        # Check if primary keys exist in DataFrame
        missing_keys = [key for key in keys_to_use if key not in df.columns]
        if missing_keys:
            error_msg = f"Primary keys not found in DataFrame: {missing_keys}"
            self.stats.add_error(error_msg)
            self.logger.warning(error_msg)
            # Fallback: return original data
            self.stats.processing_time_ms = (time.time() - start_time) * 1000
            return df, self.stats

        # Perform deduplication based on strategy
        result_df = self._perform_deduplication(df, keys_to_use)

        # Update final stats
        self.stats.output_rows = len(result_df)
        self.stats.removed_rows = self.stats.input_rows - self.stats.output_rows
        self.stats.processing_time_ms = (time.time() - start_time) * 1000

        # Add warning if no deduplication occurred
        if self.stats.removed_rows == 0:
            self.stats.add_warning("No duplicates found in data")

        if self.config['enable_stats']:
            # 使用 INFO 级别记录去重结果，提高可观测性
            import logging
            log_level = logging.INFO if self.stats.removed_rows > 0 else logging.DEBUG
            self.logger.log(log_level,
                           f"Deduplication completed: {self.stats.input_rows} -> {self.stats.output_rows} rows "
                           f"({self.stats.get_dedup_rate():.2f}% dedup rate)")

        return result_df, self.stats

    def _validate_schema(self, df: pl.DataFrame, primary_keys: Optional[List[str]]) -> bool:
        """Validate that required fields exist in the DataFrame."""
        keys_to_check = primary_keys or self.config['primary_keys']
        if isinstance(keys_to_check, str):
            keys_to_check = [keys_to_check]

        missing_cols = [col for col in keys_to_check if col not in df.columns]
        if missing_cols:
            self.logger.warning(f"Missing columns for deduplication: {missing_cols}")
            return False
        return True

    def _perform_deduplication(self, df: pl.DataFrame, primary_keys: List[str]) -> pl.DataFrame:
        """Perform the actual deduplication based on the configured strategy."""
        strategy = self.config['keep_strategy']

        try:
            if strategy == 'first':
                # Keep first occurrence of each duplicate
                deduplicated_df = df.unique(subset=primary_keys, keep='first')
            elif strategy == 'last':
                # Keep last occurrence of each duplicate
                deduplicated_df = df.unique(subset=primary_keys, keep='last')
            elif strategy == 'latest_date':
                # Keep the row with the latest date in the specified date field
                date_field = self.config['date_field']
                if date_field in df.columns:
                    # Sort by primary keys first, then by date field in descending order
                    # This ensures we keep the latest date for each unique combination of primary keys
                    sort_cols = primary_keys + [date_field]
                    sort_descending = [False] * len(primary_keys) + [True]  # Ascending for primary keys, descending for date
                    deduplicated_df = df.sort(sort_cols, descending=sort_descending).unique(
                        subset=primary_keys, keep='first'
                    )
                    # Now sort back to a logical order (by date ascending)
                    if date_field in deduplicated_df.columns:
                        deduplicated_df = deduplicated_df.sort(date_field, descending=False)
                else:
                    # Fallback to 'first' strategy if date field is missing
                    self.logger.warning(f"Date field '{date_field}' not found, using 'first' strategy")
                    deduplicated_df = df.unique(subset=primary_keys, keep='first')
            else:
                # Default to 'first' strategy
                self.logger.warning(f"Unknown strategy '{strategy}', using 'first' strategy")
                deduplicated_df = df.unique(subset=primary_keys, keep='first')

            return deduplicated_df

        except Exception as e:
            self.logger.error(f"Error during deduplication: {str(e)}")
            self.stats.add_error(f"Deduplication error: {str(e)}")
            # Return original dataframe on error
            return df

    def get_hash(self, row: pl.Series, primary_keys: List[str]) -> str:
        """
        Generate a hash for a row based on primary key columns.

        Args:
            row: A row from the DataFrame as a Series
            primary_keys: The columns to use for hashing

        Returns:
            String hash of the row
        """
        hash_columns = self.config['hash_fields'] or primary_keys

        values = []
        for col in hash_columns:
            if col in row.index:
                val = row[col]
                if val is None or (isinstance(val, float) and val != val):  # Check for None or NaN
                    values.append('NULL')
                else:
                    values.append(str(val))
            else:
                values.append('MISSING')

        if not self.config['case_sensitive']:
            values = [str(v).lower() for v in values]

        hash_input = '|'.join(map(str, values))
        return hashlib.md5(hash_input.encode()).hexdigest()

    def reset_stats(self) -> None:
        """Reset statistics to zero."""
        self.stats = DedupStats()

    def get_stats(self) -> DedupStats:
        """Get current statistics."""
        return self.stats


def deduplicate_against_existing(
    new_data: pl.DataFrame,
    existing_data_path: str,
    primary_keys: Optional[List[str]] = None,
    deduplicator: Optional[DataDeduplicator] = None,
    **kwargs
) -> Tuple[pl.DataFrame, DedupStats]:
    """
    Deduplicate new data against existing data in a file.

    Args:
        new_data: New data to deduplicate
        existing_data_path: Path to existing data file (parquet format)
        primary_keys: Primary key columns for deduplication
        deduplicator: Optional existing deduplicator instance
        **kwargs: Additional arguments for deduplicator configuration

    Returns:
        Tuple of (deduplicated new data, statistics)
    """
    stats = DedupStats()
    start_time = time.time()

    # Initialize deduplicator if not provided
    if deduplicator is None:
        config = {**DataDeduplicator.DEFAULT_CONFIG, **kwargs}
        deduplicator = DataDeduplicator(config)

    try:
        # Check if existing file exists
        if not os.path.exists(existing_data_path):
            stats.add_warning(f"Existing file does not exist: {existing_data_path}")
            stats.output_rows = len(new_data)
            stats.processing_time_ms = (time.time() - start_time) * 1000
            return new_data, stats

        # Load existing data
        existing_df = pl.read_parquet(existing_data_path)
        stats.compared_rows = len(existing_df)

        if len(existing_df) == 0:
            stats.output_rows = len(new_data)
            stats.processing_time_ms = (time.time() - start_time) * 1000
            return new_data, stats

        # Determine primary keys
        keys_to_use = primary_keys or deduplicator.config['primary_keys']
        if isinstance(keys_to_use, str):
            keys_to_use = [keys_to_use]

        # Validate that primary keys exist in both DataFrames
        new_missing = [key for key in keys_to_use if key not in new_data.columns]
        existing_missing = [key for key in keys_to_use if key not in existing_df.columns]

        if new_missing or existing_missing:
            error_msg = f"Missing primary keys - new: {new_missing}, existing: {existing_missing}"
            stats.add_error(error_msg)
            return new_data, stats

        # Ensure join key types match - convert to string if needed
        # This handles cases like str vs cat type mismatch
        new_data_aligned = new_data.clone()
        existing_df_aligned = existing_df.clone()

        for key in keys_to_use:
            new_dtype = new_data_aligned[key].dtype
            existing_dtype = existing_df_aligned[key].dtype

            if new_dtype != existing_dtype:
                # Convert both to string for join comparison
                new_data_aligned = new_data_aligned.with_columns(
                    pl.col(key).cast(pl.String).alias(key)
                )
                existing_df_aligned = existing_df_aligned.with_columns(
                    pl.col(key).cast(pl.String).alias(key)
                )

        # Perform anti-join to filter out existing records
        comparison_start = time.time()

        # Join new data with existing data to identify duplicates
        joined = new_data_aligned.join(
            existing_df_aligned.select(keys_to_use).unique(),
            on=keys_to_use,
            how='anti'  # Keep only rows from new_data that don't exist in existing_data
        )

        # Update comparison time
        stats.comparison_time_ms = (time.time() - comparison_start) * 1000

        # Update stats
        stats.input_rows = len(new_data)
        stats.output_rows = len(joined)
        stats.removed_rows = stats.input_rows - stats.output_rows
        stats.processing_time_ms = (time.time() - start_time) * 1000

        # Add warning if no filtering occurred
        if stats.removed_rows == 0:
            stats.add_warning("No existing duplicates found")

        return joined, stats

    except Exception as e:
        error_msg = f"Error deduplicating against existing data: {str(e)}"
        stats.add_error(error_msg)
        return new_data, stats


# Convenience functions for common deduplication scenarios
def deduplicate_daily_data(df: pl.DataFrame) -> Tuple[pl.DataFrame, DedupStats]:
    """
    Deduplicate daily stock data using default settings for daily data.

    Args:
        df: DataFrame containing daily stock data

    Returns:
        Tuple of (deduplicated DataFrame, statistics)
    """
    deduplicator = DataDeduplicator({
        'primary_keys': ['ts_code', 'trade_date'],
        'keep_strategy': 'first',
        'date_field': 'trade_date'
    })
    return deduplicator.deduplicate(df)


def deduplicate_financial_data(df: pl.DataFrame) -> Tuple[pl.DataFrame, DedupStats]:
    """
    Deduplicate financial data using settings appropriate for financial statements.

    Args:
        df: DataFrame containing financial data

    Returns:
        Tuple of (deduplicated DataFrame, statistics)
    """
    deduplicator = DataDeduplicator({
        'primary_keys': ['ts_code', 'ann_date', 'f_ann_date'],
        'keep_strategy': 'latest_date',
        'date_field': 'ann_date'
    })
    return deduplicator.deduplicate(df)


def deduplicate_holders_data(df: pl.DataFrame) -> Tuple[pl.DataFrame, DedupStats]:
    """
    Deduplicate holders data using settings appropriate for shareholder data.

    Args:
        df: DataFrame containing holders data

    Returns:
        Tuple of (deduplicated DataFrame, statistics)
    """
    deduplicator = DataDeduplicator({
        'primary_keys': ['ts_code', 'ann_date', 'holder_name'],
        'keep_strategy': 'latest_date',
        'date_field': 'ann_date'
    })
    return deduplicator.deduplicate(df)


def deduplicate_by_date_range(df: pl.DataFrame,
                             start_date: str,
                             end_date: str) -> Tuple[pl.DataFrame, DedupStats]:
    """
    Deduplicate data filtered by date range.

    Args:
        df: Input DataFrame
        start_date: Start date in format 'YYYYMMDD'
        end_date: End date in format 'YYYYMMDD'

    Returns:
        Tuple of (deduplicated DataFrame, statistics)
    """
    date_field = 'trade_date'  # Default date field
    if date_field in df.columns:
        filtered_df = df.filter(
            pl.col(date_field) >= start_date,
            pl.col(date_field) <= end_date
        )
    else:
        filtered_df = df  # If date field not present, use all data

    deduplicator = DataDeduplicator({
        'primary_keys': ['ts_code', 'trade_date'],
        'keep_strategy': 'first'
    })
    return deduplicator.deduplicate(filtered_df)


if __name__ == "__main__":
    # Example usage and testing
    import polars as pl

    # Create sample data with duplicates
    sample_data = pl.DataFrame({
        'ts_code': ['000001.SZ', '000001.SZ', '000001.SZ', '000002.SZ', '000002.SZ'],
        'trade_date': ['20231001', '20231001', '20231002', '20231001', '20231001'],
        'close': [10.1, 10.2, 10.3, 15.1, 15.1],
        'volume': [1000, 1000, 2000, 1500, 1500]
    })

    print("Original data:")
    print(sample_data)
    print(f"Original rows: {len(sample_data)}")

    # Test basic deduplication
    dedup = DataDeduplicator()
    deduplicated, stats = dedup.deduplicate(sample_data)

    print("\nDeduplicated data:")
    print(deduplicated)
    print(f"Deduplicated rows: {len(deduplicated)}")
    print(f"Removed rows: {stats.removed_rows}")
    print(f"Deduplication rate: {stats.get_dedup_rate():.2f}%")

    # Test with different strategy
    dedup_latest = DataDeduplicator({'keep_strategy': 'latest_date'})
    deduplicated_latest, stats_latest = dedup_latest.deduplicate(sample_data)

    print("\nDeduplicated with latest date strategy:")
    print(deduplicated_latest)
    print(f"Removed rows: {stats_latest.removed_rows}")