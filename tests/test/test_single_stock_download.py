"""
测试单个股票各个接口的下载功能
下载600600.SH股票的全历史数据并统计每接口的数据条数
"""
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path

# Set up logging
log_dir = Path(__file__).parent.parent / 'log'
log_dir.mkdir(exist_ok=True)
log_file = log_dir / 'test_single_stock_download.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def test_single_stock_downloads():
    """测试单个股票各个接口的下载功能"""
    test_stock_code = "600600.SH"  # 青岛啤酒

    logger.info(f"开始测试单个股票 {test_stock_code} 的数据下载")
    logger.info("=" * 60)

    # 导入必要的模块
    from tushare_api import TuShareDownloader

    # 初始化下载器
    downloader = TuShareDownloader()

    results = {}

    # 1. 测试stk_rewards接口
    try:
        logger.info("测试stk_rewards接口...")
        from interfaces.holders_data import HoldersDataDownloader
        holders_downloader = HoldersDataDownloader(downloader.pro)
        stk_rewards_data = holders_downloader.download_stk_rewards(test_stock_code)
        results['stk_rewards'] = len(stk_rewards_data) if stk_rewards_data is not None else 0
        logger.info(f"stk_rewards数据条数: {results['stk_rewards']}")
    except Exception as e:
        logger.error(f"stk_rewards下载失败: {e}")
        results['stk_rewards'] = 0

    # 2. 测试top10_holders接口
    try:
        logger.info("测试top10_holders接口...")
        from interfaces.holders_data import HoldersDataDownloader
        holders_downloader = HoldersDataDownloader(downloader.pro)
        top10_holders_data = holders_downloader.download_top10_holders(test_stock_code)
        results['top10_holders'] = len(top10_holders_data) if top10_holders_data is not None else 0
        logger.info(f"top10_holders数据条数: {results['top10_holders']}")
    except Exception as e:
        logger.error(f"top10_holders下载失败: {e}")
        results['top10_holders'] = 0

    # 3. 测试pledge_detail接口（需要5000+积分）
    try:
        logger.info("测试pledge_detail接口...")
        from interfaces.holders_data import HoldersDataDownloader
        holders_downloader = HoldersDataDownloader(downloader.pro)
        pledge_detail_data = holders_downloader.download_pledge_detail(test_stock_code)
        results['pledge_detail'] = len(pledge_detail_data) if pledge_detail_data is not None else 0
        logger.info(f"pledge_detail数据条数: {results['pledge_detail']}")
    except Exception as e:
        logger.error(f"pledge_detail下载失败: {e}")
        results['pledge_detail'] = 0

    # 4. 测试fina_audit接口
    try:
        logger.info("测试fina_audit接口...")
        from interfaces.financial_data import FinancialDataDownloader
        financial_downloader = FinancialDataDownloader(downloader.pro)
        fina_audit_data = financial_downloader.download_fina_audit(ts_code=test_stock_code)
        results['fina_audit'] = len(fina_audit_data) if fina_audit_data is not None else 0
        logger.info(f"fina_audit数据条数: {results['fina_audit']}")
    except Exception as e:
        logger.error(f"fina_audit下载失败: {e}")
        results['fina_audit'] = 0

    # 5. 测试pro_bar接口
    try:
        logger.info("测试pro_bar接口...")
        from interfaces.daily_data import DailyDataDownloader
        daily_downloader = DailyDataDownloader(downloader.pro)
        # 先获取股票上市日期
        from interfaces.basic_data import BasicDataDownloader
        basic_downloader = BasicDataDownloader(downloader.pro)
        stock_info = basic_downloader.download_stock_basic()
        stock_row = stock_info[stock_info['ts_code'] == test_stock_code]

        if not stock_row.empty:
            list_date = stock_row.iloc[0]['list_date']
            end_date = datetime.now().strftime('%Y%m%d')

            pro_bar_data = daily_downloader.download_pro_bar(
                ts_code=test_stock_code,
                start_date=list_date,
                end_date=end_date,
                adj='qfq'  # 前复权
            )
            results['pro_bar'] = len(pro_bar_data) if pro_bar_data is not None else 0
            logger.info(f"pro_bar数据条数: {results['pro_bar']}")
        else:
            logger.warning(f"未找到股票 {test_stock_code} 的基本信息")
            results['pro_bar'] = 0
    except Exception as e:
        logger.error(f"pro_bar下载失败: {e}")
        results['pro_bar'] = 0

    # 输出汇总结果
    logger.info("=" * 60)
    logger.info("测试结果汇总:")
    total_records = 0
    for interface, count in results.items():
        logger.info(f"  {interface}: {count} 条记录")
        total_records += count

    logger.info(f"总计: {total_records} 条记录")
    logger.info("测试完成!")

    return results

if __name__ == "__main__":
    test_single_stock_downloads()