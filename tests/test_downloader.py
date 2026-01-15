import pytest
import tempfile
from pathlib import Path
import polars as pl
from datetime import datetime, timedelta

from app4.core.downloader import GenericDownloader
from app4.core.storage import StorageManager
from app4.core.config_loader import ConfigLoader


def test_download_with_incremental_coverage():
    """Test downloading with incremental coverage check"""
    pass