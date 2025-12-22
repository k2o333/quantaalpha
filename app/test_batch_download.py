"""
测试批量下载功能
测试top10_holders、fina_audit、pledge_detail三个接口的批量下载性能（50只股票）
使用现有的单个股票下载方法进行批量测试
"""
import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Set up logging
log_dir = Path(__file__).parent.parent / 'log'
log_dir.mkdir(exist_ok=True)
log_file = log_dir / 'test_batch_download.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def download_single_stock_top10_holders(downloader, ts_code):
    """下载单个股票的top10_holders数据"""
    from interfaces.holders_data import HoldersDataDownloader
    holders_downloader = HoldersDataDownloader(downloader.pro)
    try:
        data = holders_downloader.download_top10_holders(ts_code)
        if data is not None and not data.empty:
            return data, ts_code
        else:
            return pd.DataFrame(), ts_code
    except Exception as e:
        logger.warning(f"下载 {ts_code} top10_holders 失败: {e}")
        return pd.DataFrame(), ts_code

def download_single_stock_fina_audit(downloader, ts_code):
    """下载单个股票的fina_audit数据"""
    from interfaces.financial_data import FinancialDataDownloader
    financial_downloader = FinancialDataDownloader(downloader.pro)
    try:
        data = financial_downloader.download_fina_audit(ts_code=ts_code)
        if data is not None and not data.empty:
            return data, ts_code
        else:
            return pd.DataFrame(), ts_code
    except Exception as e:
        logger.warning(f"下载 {ts_code} fina_audit 失败: {e}")
        return pd.DataFrame(), ts_code

def download_single_stock_pledge_detail(downloader, ts_code):
    """下载单个股票的pledge_detail数据"""
    from interfaces.holders_data import HoldersDataDownloader
    holders_downloader = HoldersDataDownloader(downloader.pro)
    try:
        data = holders_downloader.download_pledge_detail(ts_code)
        if data is not None and not data.empty:
            return data, ts_code
        else:
            return pd.DataFrame(), ts_code
    except Exception as e:
        logger.warning(f"下载 {ts_code} pledge_detail 失败: {e}")
        return pd.DataFrame(), ts_code

def download_interface_parallel(downloader, test_stocks, download_func, max_workers=5):
    """并行下载接口数据"""
    all_data = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_stock = {
            executor.submit(download_func, downloader, ts_code): ts_code
            for ts_code in test_stocks
        }

        # 处理完成的任务
        completed = 0
        for future in as_completed(future_to_stock):
            data, ts_code = future.result()
            if not data.empty:
                all_data.append(data)

            completed += 1
            if completed % 10 == 0:
                logger.info(f"  已完成 {completed}/{len(test_stocks)} 只股票")

    return all_data

def test_batch_downloads():
    """测试批量下载功能"""
    logger.info("开始测试批量下载功能")
    logger.info("=" * 60)

    # 导入必要的模块
    from tushare_api import TuShareDownloader
    from config import TUSHARE_POINTS

    # 初始化下载器
    downloader = TuShareDownloader()

    # 获取前50只股票
    from interfaces.basic_data import BasicDataDownloader
    basic_downloader = BasicDataDownloader(downloader.pro)
    stock_list = basic_downloader.download_stock_basic()

    if stock_list.empty:
        logger.error("无法获取股票列表")
        return

    # 取前50只股票
    test_stocks = stock_list.head(50)['ts_code'].tolist()
    logger.info(f"测试股票数量: {len(test_stocks)}")
    logger.info(f"测试股票代码: {', '.join(test_stocks[:5])}...")

    results = {}

    # 1. 测试top10_holders批量下载（使用并行处理）
    try:
        logger.info("测试top10_holders批量下载（并行处理）...")
        start_time = datetime.now()

        all_data = download_interface_parallel(
            downloader, test_stocks, download_single_stock_top10_holders, max_workers=5
        )

        if all_data:
            batch_data = pd.concat(all_data, ignore_index=True)
            total_records = len(batch_data)
        else:
            batch_data = pd.DataFrame()
            total_records = 0

        end_time = datetime.now()

        results['top10_holders_batch'] = {
            'records': total_records,
            'time_seconds': (end_time - start_time).total_seconds(),
            'stocks_processed': len(test_stocks)
        }
        logger.info(f"top10_holders批量下载完成: {results['top10_holders_batch']['records']} 条记录, 处理 {len(test_stocks)} 只股票, 耗时: {results['top10_holders_batch']['time_seconds']:.2f}秒")
    except Exception as e:
        logger.error(f"top10_holders批量下载失败: {e}")
        results['top10_holders_batch'] = {'records': 0, 'time_seconds': 0, 'stocks_processed': 0}

    # 2. 测试fina_audit批量下载（使用并行处理）
    try:
        logger.info("测试fina_audit批量下载（并行处理）...")
        start_time = datetime.now()

        all_data = download_interface_parallel(
            downloader, test_stocks, download_single_stock_fina_audit, max_workers=5
        )

        if all_data:
            batch_data = pd.concat(all_data, ignore_index=True)
            total_records = len(batch_data)
        else:
            batch_data = pd.DataFrame()
            total_records = 0

        end_time = datetime.now()

        results['fina_audit_batch'] = {
            'records': total_records,
            'time_seconds': (end_time - start_time).total_seconds(),
            'stocks_processed': len(test_stocks)
        }
        logger.info(f"fina_audit批量下载完成: {results['fina_audit_batch']['records']} 条记录, 处理 {len(test_stocks)} 只股票, 耗时: {results['fina_audit_batch']['time_seconds']:.2f}秒")
    except Exception as e:
        logger.error(f"fina_audit批量下载失败: {e}")
        results['fina_audit_batch'] = {'records': 0, 'time_seconds': 0, 'stocks_processed': 0}

    # 3. 测试pledge_detail批量下载（需要5000+积分）
    try:
        logger.info("测试pledge_detail批量下载（并行处理）...")
        if TUSHARE_POINTS >= 5000:
            start_time = datetime.now()

            all_data = download_interface_parallel(
                downloader, test_stocks, download_single_stock_pledge_detail, max_workers=5
            )

            if all_data:
                batch_data = pd.concat(all_data, ignore_index=True)
                total_records = len(batch_data)
            else:
                batch_data = pd.DataFrame()
                total_records = 0

            end_time = datetime.now()

            results['pledge_detail_batch'] = {
                'records': total_records,
                'time_seconds': (end_time - start_time).total_seconds(),
                'stocks_processed': len(test_stocks)
            }
            logger.info(f"pledge_detail批量下载完成: {results['pledge_detail_batch']['records']} 条记录, 处理 {len(test_stocks)} 只股票, 耗时: {results['pledge_detail_batch']['time_seconds']:.2f}秒")
        else:
            logger.warning("pledge_detail接口需要5000+积分，当前积分不足")
            results['pledge_detail_batch'] = {'records': 0, 'time_seconds': 0, 'stocks_processed': 0}
    except Exception as e:
        logger.error(f"pledge_detail批量下载失败: {e}")
        results['pledge_detail_batch'] = {'records': 0, 'time_seconds': 0, 'stocks_processed': 0}

    # 输出汇总结果
    logger.info("=" * 60)
    logger.info("批量下载测试结果汇总:")
    for interface, data in results.items():
        logger.info(f"  {interface}: {data['records']} 条记录, 处理 {data.get('stocks_processed', 0)} 只股票, 耗时: {data['time_seconds']:.2f}秒")

    logger.info("批量下载测试完成!")
    return results

if __name__ == "__main__":
    test_batch_downloads()