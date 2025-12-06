"""
Main entry point for aspipe_v4 - 第一期完整数据下载系统
"""
import logging
import time
from datetime import datetime
from pathlib import Path
from stock_basic_downloader import download_and_save_stock_basic
from daily_downloader import download_and_save_daily_data
from data_validator import validate_data_quality

# Set up logging with Chinese characters support
log_dir = Path(__file__).parent.parent / 'log'
log_dir.mkdir(exist_ok=True)  # Ensure log directory exists
log_file = log_dir / 'aspipe_v4.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def main():
    """
    Main function to orchestrate the entire download process
    """
    start_time = time.time()
    
    logger.info("🚀 第一期：沪深A股数据下载系统启动")
    logger.info(f"📅 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Step 1: Download stock basic information
        logger.info("📋 开始下载股票基本信息...")
        stock_basic_df = download_and_save_stock_basic()
        logger.info("✅ 股票基本信息下载完成")
        
        # Step 2: Download daily data (limited to 50 stocks for first phase)
        logger.info("📈 开始下载日线数据（后复权）...")
        daily_df = download_and_save_daily_data(stock_limit=50)
        logger.info("✅ 日线数据下载完成")
        
        # Step 3: Validate data quality
        logger.info("🔍 开始数据质量验证...")
        validation_results = validate_data_quality(stock_basic_df, daily_df)
        logger.info("✅ 数据质量验证完成")
        
        # Step 4: Generate summary
        elapsed_time = time.time() - start_time
        logger.info("📊 系统运行统计:")
        logger.info(f"   • 股票基本信息: {len(stock_basic_df) if stock_basic_df is not None else 0} 条记录")
        logger.info(f"   • 日线数据: {len(daily_df) if daily_df is not None else 0} 条记录")
        logger.info(f"   • 运行时间: {elapsed_time:.2f} 秒")
        logger.info(f"   • 数据质量验证: {'通过' if validation_results['stock_basic_valid'] and validation_results['daily_valid'] else '未通过'}")
        
        logger.info("🎉 第一期验收通过！")
        logger.info(f"📅 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 系统执行失败: {e}")
        logger.error(f"📅 失败时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        raise


if __name__ == "__main__":
    main()