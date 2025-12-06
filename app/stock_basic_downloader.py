"""
Stock basic download functionality for aspipe_v4
"""
from tushare_api import TuShareDownloader
from data_storage import save_to_parquet
import logging

logger = logging.getLogger(__name__)


def download_and_save_stock_basic():
    """
    Download stock basic information and save to Parquet format
    """
    logger.info("🚀 第一期：沪深A股数据下载系统启动")
    logger.info("📋 开始下载股票基本信息...")

    try:
        # Initialize downloader
        downloader = TuShareDownloader()
        logger.info("✅ TuShare API初始化完成")

        # Download stock basic data
        logger.info("📋 开始下载股票基本信息...")
        stock_basic_df = downloader.download_stock_basic()

        # Save to parquet
        logger.info("💾 保存股票基本信息到parquet文件...")
        file_path = save_to_parquet(stock_basic_df, 'stock_basic')

        logger.info(f"✅ 股票基本信息下载完成，共 {len(stock_basic_df)} 只股票")
        logger.info(f"📁 数据已保存至: {file_path}")

        return stock_basic_df

    except Exception as e:
        logger.error(f"❌ 股票基本信息下载失败: {e}")
        raise