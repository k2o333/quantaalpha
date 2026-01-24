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