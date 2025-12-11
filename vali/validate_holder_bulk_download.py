"""
验证股东数据批量下载优化效果
比较逐股票下载和批量下载的性能差异
"""
import time
import pandas as pd
import tushare as ts
from datetime import datetime
import logging
import os

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 初始化TuShare
token = os.environ.get('TUSHARE_TOKEN', 'your_token_here')
pro = ts.pro_api(token)

def validate_top10_holders_download():
    """
    验证前十大股东数据下载优化
    """
    logger.info("开始验证前十大股东数据下载优化")

    period = '20231231'

    # 1. 逐股票下载测试（原方法模拟）
    logger.info("开始逐股票下载测试...")

    # 先获取一些股票代码用于测试
    try:
        stock_list = pro.stock_basic(exchange='', list_status='L', fields='ts_code')
        test_stocks = stock_list.head(10)['ts_code'].tolist()  # 取前10只股票测试
    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        test_stocks = ['000001.SZ', '000002.SZ', '600000.SH', '601398.SH', '000006.SZ',
                      '000007.SZ', '000008.SZ', '000009.SZ', '000010.SZ', '000011.SZ']

    start_time = time.time()
    all_data_individual = []

    for stock in test_stocks:
        try:
            df = pro.top10_holders(ts_code=stock, period=period)
            if not df.empty:
                all_data_individual.append(df)
            time.sleep(0.3)  # 避免API频率限制
        except Exception as e:
            logger.error(f"下载 {stock} 前十大股东数据失败: {e}")
            continue

    individual_time = time.time() - start_time
    individual_count = sum(len(df) for df in all_data_individual if df is not None)

    logger.info(f"逐股票下载完成 - 总耗时: {individual_time:.2f}s, 数据条数: {individual_count}")

    # 2. 批量下载测试（优化后方法）- 使用全市场数据下载
    logger.info("开始全市场批量下载测试...")
    start_time = time.time()
    try:
        # 全市场批量下载：下载尽可能多的股票数据以达到10000+条记录
        all_data_bulk = []
        offset = 0
        limit = 1000  # 每次获取1000只股票

        # 尝试通过分页获取全市场数据
        while True:
            try:
                stock_list = pro.stock_basic(exchange='', list_status='L',
                                           fields='ts_code', limit=limit, offset=offset)

                if stock_list is None or len(stock_list) == 0:
                    logger.info("已获取完所有股票列表")
                    break

                for _, stock in stock_list.iterrows():
                    ts_code = stock['ts_code']
                    try:
                        df = pro.top10_holders(ts_code=ts_code, period=period)
                        if df is not None and not df.empty:
                            all_data_bulk.append(df)

                            total_count = sum(len(d) for d in all_data_bulk)
                            if total_count >= 10000:  # 目标超过10000条数据
                                logger.info(f"已达到目标数据量: {total_count} 条记录")
                                break

                        time.sleep(0.1)  # 控制API调用频率
                    except Exception as e:
                        logger.error(f"下载 {ts_code} 前十大股东数据失败: {e}")
                        continue

                    # 检查是否达到目标数据量
                    total_count = sum(len(d) for d in all_data_bulk)
                    if total_count >= 10000:
                        break

                # 检查是否达到目标数据量
                total_count = sum(len(d) for d in all_data_bulk)
                if total_count >= 10000:
                    break

                offset += limit
                logger.info(f"已处理 {offset} 只股票，总记录数: {sum(len(d) for d in all_data_bulk)}")

            except Exception as e:
                logger.error(f"获取股票列表失败 (offset {offset}): {e}")
                break

        bulk_time = time.time() - start_time
        bulk_count = sum(len(df) for df in all_data_bulk if df is not None)
        logger.info(f"全市场批量下载完成 - 总耗时: {bulk_time:.2f}s, 数据条数: {bulk_count}")

        # 性能比较
        if bulk_time > 0 and individual_time > 0:
            speedup = individual_time / bulk_time
            logger.info(f"批量下载相比逐个下载速度提升: {speedup:.2f}x")

        return {
            'individual_time': individual_time,
            'bulk_time': bulk_time,
            'individual_count': individual_count,
            'bulk_count': bulk_count,
            'speedup': individual_time / bulk_time if bulk_time > 0 else 0
        }

    except Exception as e:
        logger.error(f"批量下载失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            'individual_time': individual_time,
            'bulk_time': 0,
            'individual_count': individual_count,
            'bulk_count': 0,
            'speedup': 0
        }

def validate_top10_floatholders_download():
    """
    验证前十大流通股东数据下载优化
    """
    logger.info("开始验证前十大流通股东数据下载优化")

    period = '20231231'

    # 1. 逐股票下载测试（原方法模拟）
    logger.info("开始逐股票下载测试...")

    # 先获取一些股票代码用于测试
    try:
        stock_list = pro.stock_basic(exchange='', list_status='L', fields='ts_code')
        test_stocks = stock_list.head(10)['ts_code'].tolist()  # 取前10只股票测试
    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        test_stocks = ['000001.SZ', '000002.SZ', '600000.SH', '601398.SH', '000006.SZ',
                      '000007.SZ', '000008.SZ', '000009.SZ', '000010.SZ', '000011.SZ']

    start_time = time.time()
    all_data_individual = []

    for stock in test_stocks:
        try:
            df = pro.top10_floatholders(ts_code=stock, period=period)
            if not df.empty:
                all_data_individual.append(df)
            time.sleep(0.3)  # 避免API频率限制
        except Exception as e:
            logger.error(f"下载 {stock} 前十大流通股东数据失败: {e}")
            continue

    individual_time = time.time() - start_time
    individual_count = sum(len(df) for df in all_data_individual if df is not None)

    logger.info(f"逐股票下载完成 - 总耗时: {individual_time:.2f}s, 数据条数: {individual_count}")

    # 2. 批量下载测试（优化后方法）- 使用全市场数据下载
    logger.info("开始全市场批量下载测试...")
    start_time = time.time()
    try:
        # 全市场批量下载：下载尽可能多的股票数据以达到10000+条记录
        all_data_bulk = []
        offset = 0
        limit = 1000  # 每次获取1000只股票

        # 尝试通过分页获取全市场数据
        while True:
            try:
                stock_list = pro.stock_basic(exchange='', list_status='L',
                                           fields='ts_code', limit=limit, offset=offset)

                if stock_list is None or len(stock_list) == 0:
                    logger.info("已获取完所有股票列表")
                    break

                for _, stock in stock_list.iterrows():
                    ts_code = stock['ts_code']
                    try:
                        df = pro.top10_floatholders(ts_code=ts_code, period=period)
                        if df is not None and not df.empty:
                            all_data_bulk.append(df)

                            total_count = sum(len(d) for d in all_data_bulk)
                            if total_count >= 10000:  # 目标超过10000条数据
                                logger.info(f"已达到目标数据量: {total_count} 条记录")
                                break

                        time.sleep(0.1)  # 控制API调用频率
                    except Exception as e:
                        logger.error(f"下载 {ts_code} 前十大流通股东数据失败: {e}")
                        continue

                    # 检查是否达到目标数据量
                    total_count = sum(len(d) for d in all_data_bulk)
                    if total_count >= 10000:
                        break

                # 检查是否达到目标数据量
                total_count = sum(len(d) for d in all_data_bulk)
                if total_count >= 10000:
                    break

                offset += limit
                logger.info(f"已处理 {offset} 只股票，总记录数: {sum(len(d) for d in all_data_bulk)}")

            except Exception as e:
                logger.error(f"获取股票列表失败 (offset {offset}): {e}")
                break

        bulk_time = time.time() - start_time
        bulk_count = sum(len(df) for df in all_data_bulk if df is not None)
        logger.info(f"全市场批量下载完成 - 总耗时: {bulk_time:.2f}s, 数据条数: {bulk_count}")

        # 性能比较
        if bulk_time > 0 and individual_time > 0:
            speedup = individual_time / bulk_time
            logger.info(f"批量下载相比逐个下载速度提升: {speedup:.2f}x")

        return {
            'individual_time': individual_time,
            'bulk_time': bulk_time,
            'individual_count': individual_count,
            'bulk_count': bulk_count,
            'speedup': individual_time / bulk_time if bulk_time > 0 else 0
        }

    except Exception as e:
        logger.error(f"批量下载失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            'individual_time': individual_time,
            'bulk_time': 0,
            'individual_count': individual_count,
            'bulk_count': 0,
            'speedup': 0
        }

def run_validation():
    """
    运行完整的股东数据下载验证
    """
    logger.info("开始股东数据批量下载验证")

    results = {}

    try:
        results['top10_holders'] = validate_top10_holders_download()
        logger.info("\n" + "="*50)

        results['top10_floatholders'] = validate_top10_floatholders_download()
        logger.info("\n" + "="*50)

        # 汇总结果
        logger.info("验证结果汇总:")
        for data_type, result in results.items():
            logger.info(f"{data_type.upper()}:")
            logger.info(f"  逐个下载耗时: {result['individual_time']:.2f}s")
            logger.info(f"  批量下载耗时: {result['bulk_time']:.2f}s")
            logger.info(f"  逐个下载数据量: {result['individual_count']}")
            logger.info(f"  批量下载数据量: {result['bulk_count']}")
            logger.info(f"  速度提升倍数: {result['speedup']:.2f}x")
            logger.info("")

    except Exception as e:
        logger.error(f"验证过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_validation()