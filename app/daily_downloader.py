"""
Daily data download functionality for aspipe_v4
"""
from tushare_api import TuShareDownloader
from data_storage import save_to_parquet
from stock_basic_downloader import download_and_save_stock_basic
import logging
import pandas as pd
import time

logger = logging.getLogger(__name__)


def download_and_save_daily_data(stock_limit: int = 50, start_date: str = '20100101', end_date: str = '20231231'):
    """
    Download daily data for a limited number of stocks and save to Parquet format
    """
    logger.info(f"📈 开始下载日线数据（前{stock_limit}只股票）")

    try:
        # Initialize downloader
        downloader = TuShareDownloader()

        # Get stock list - if not already available, download it
        logger.info("📋 获取股票列表...")
        try:
            # Try to load existing stock basic data first
            from data_storage import load_from_parquet
            stock_basic_df = load_from_parquet('stock_basic')
        except:
            # If not available, download it now
            stock_basic_df = download_and_save_stock_basic()

        # Limit to specified number of stocks
        stock_codes = stock_basic_df['ts_code'].head(stock_limit).tolist()
        logger.info(f"🎯 下载 {len(stock_codes)} 只股票的日线数据: {stock_codes[:5]}... (显示前5只)")

        # Download daily data for each stock
        all_daily_data = []
        successful_downloads = 0
        failed_downloads = 0

        for i, ts_code in enumerate(stock_codes):
            try:
                logger.info(f"📊 [{i+1}/{len(stock_codes)}] 下载 {ts_code} ({ts_code.split('.')[0]})")

                # Download daily data for this stock
                daily_df = downloader.download_daily_data(ts_code, start_date, end_date)

                # Add stock code column if not present (for joining purposes later)
                if 'ts_code' not in daily_df.columns:
                    daily_df['ts_code'] = ts_code

                # Add to our collection
                all_daily_data.append(daily_df)
                successful_downloads += 1

                # Log progress
                logger.info(f"✅ {ts_code.split('.')[0]} 下载成功，{len(daily_df)} 条记录")

            except Exception as e:
                logger.error(f"❌ {ts_code} 下载失败: {e}")
                failed_downloads += 1

                # Continue to next stock
                continue

            # Small delay between stock downloads to be respectful to the API
            time.sleep(0.1)

        # Combine all daily data
        if all_daily_data:
            logger.info("🧩 合并所有日线数据...")
            combined_daily_df = pd.concat(all_daily_data, ignore_index=True)

            # Save to parquet
            logger.info("💾 保存合并后的日线数据到parquet文件...")
            file_path = save_to_parquet(combined_daily_df, 'daily_hfq')  # Using hfq (后复权) naming as specified in requirements

            logger.info(f"✅ 日线数据下载完成，总计 {len(combined_daily_df)} 条记录")
            logger.info(f"📊 成功下载: {successful_downloads} 只股票, 失败: {failed_downloads} 只股票")
            logger.info(f"📁 数据已保存至: {file_path}")

            return combined_daily_df
        else:
            logger.warning("⚠️ 没有成功下载任何日线数据")
            return pd.DataFrame()

    except Exception as e:
        logger.error(f"❌ 日线数据下载失败: {e}")
        raise