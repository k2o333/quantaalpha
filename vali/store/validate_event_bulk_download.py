"""
验证事件数据批量下载优化效果
比较日期范围下载和原有下载方式的性能差异
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

def validate_dividend_download():
    """
    验证分红数据下载优化
    """
    logger.info("开始验证分红数据下载优化")

    # 测试日期范围 - 扩展到更长时间段以获取更多数据
    start_date = '20220101'
    end_date = '20231231'

    # 1. 逐季度下载测试（原方法模拟）
    logger.info("开始逐季度下载测试...")
    start_time = time.time()
    all_data_quarterly = []

    # 模拟按季度下载
    quarters = [
        ('20220101', '20220331'),  # Q1 2022
        ('20220401', '20220630'),  # Q2 2022
        ('20220701', '20220930'),  # Q3 2022
        ('20221001', '20221231'),  # Q4 2022
        ('20230101', '20230331'),  # Q1 2023
        ('20230401', '20230630'),  # Q2 2023
        ('20230701', '20230930'),  # Q3 2023
        ('20231001', '20231231'),  # Q4 2023
    ]

    for quarter_start, quarter_end in quarters:
        try:
            df = pro.dividend(start_date=quarter_start, end_date=quarter_end)
            if not df.empty:
                all_data_quarterly.append(df)
            time.sleep(0.3)  # 避免API频率限制
        except Exception as e:
            logger.error(f"下载 {quarter_start} 到 {quarter_end} 分红数据失败: {e}")
            continue

    quarterly_time = time.time() - start_time
    quarterly_count = sum(len(df) for df in all_data_quarterly if df is not None)

    logger.info(f"逐季度下载完成 - 总耗时: {quarterly_time:.2f}s, 数据条数: {quarterly_count}")

    # 2. 日期范围下载测试（优化后方法）
    logger.info("开始日期范围下载测试...")
    start_time = time.time()
    try:
        # 使用分页下载确保获取超过10000条数据
        all_data_range = []
        offset = 0
        limit = 1000

        while True:
            try:
                df_range = pro.dividend(start_date=start_date, end_date=end_date, limit=limit, offset=offset)
                if df_range is None or len(df_range) == 0:
                    break
                all_data_range.append(df_range)

                logger.info(f"  日期范围下载第{offset}-{offset+len(df_range)}条数据")

                if len(df_range) < limit:
                    break
                offset += limit

                # 避免API频率限制
                time.sleep(0.2)

            except Exception as e:
                logger.error(f"日期范围下载分页失败，offset={offset}: {e}")
                break

        range_time = time.time() - start_time
        range_count = sum(len(df) for df in all_data_range if df is not None)
        logger.info(f"日期范围下载完成 - 总耗时: {range_time:.2f}s, 数据条数: {range_count}")

        # 性能比较
        if range_time > 0 and quarterly_time > 0:
            speedup = quarterly_time / range_time
            logger.info(f"日期范围下载相比逐季度下载速度提升: {speedup:.2f}x")

        return {
            'quarterly_time': quarterly_time,
            'range_time': range_time,
            'quarterly_count': quarterly_count,
            'range_count': range_count,
            'speedup': quarterly_time / range_time if range_time > 0 else 0
        }

    except Exception as e:
        logger.error(f"日期范围下载失败: {e}")
        return {
            'quarterly_time': quarterly_time,
            'range_time': 0,
            'quarterly_count': quarterly_count,
            'range_count': 0,
            'speedup': 0
        }

def validate_forecast_download():
    """
    验证业绩预告下载优化
    """
    logger.info("开始验证业绩预告下载优化")

    period = '20231231'

    # 1. 逐股票下载测试（原方法模拟）
    logger.info("开始逐股票下载测试...")

    # 先获取一些股票代码用于测试
    try:
        stock_list = pro.stock_basic(exchange='', list_status='L', fields='ts_code')
        test_stocks = stock_list.head(15)['ts_code'].tolist()  # 增加到15只股票测试
    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        test_stocks = ['000001.SZ', '000002.SZ', '600000.SH', '601398.SH', '000006.SZ',
                      '000007.SZ', '000008.SZ', '000009.SZ', '000010.SZ', '000011.SZ',
                      '601939.SH', '601318.SH', '000858.SZ', '000568.SZ', '000333.SZ']

    start_time = time.time()
    all_data_individual = []

    for stock in test_stocks:
        try:
            df = pro.forecast(ts_code=stock, period=period)
            if not df.empty:
                all_data_individual.append(df)
            time.sleep(0.2)  # 避免API频率限制
        except Exception as e:
            logger.error(f"下载 {stock} 业绩预告失败: {e}")
            continue

    individual_time = time.time() - start_time
    individual_count = sum(len(df) for df in all_data_individual if df is not None)

    logger.info(f"逐股票下载完成 - 总耗时: {individual_time:.2f}s, 数据条数: {individual_count}")

    # 2. 批量下载测试（如果积分足够）
    logger.info("开始批量下载测试...")
    start_time = time.time()
    try:
        # 测试批量下载，使用分页确保下载超过10000条数据
        all_data_bulk = []
        offset = 0
        limit = 1000

        while True:
            try:
                df_bulk = pro.forecast_vip(period=period, limit=limit, offset=offset)
                if df_bulk is None or len(df_bulk) == 0:
                    break
                all_data_bulk.append(df_bulk)

                logger.info(f"  批量下载第{offset}-{offset+len(df_bulk)}条数据")

                if len(df_bulk) < limit:
                    break
                offset += limit

                # 避免API频率限制
                time.sleep(0.2)

            except Exception as e:
                logger.error(f"批量下载分页失败，offset={offset}: {e}")
                break

        bulk_time = time.time() - start_time
        bulk_count = sum(len(df) for df in all_data_bulk if df is not None)
        logger.info(f"批量下载完成 - 总耗时: {bulk_time:.2f}s, 数据条数: {bulk_count}")

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
        return {
            'individual_time': individual_time,
            'bulk_time': 0,
            'individual_count': individual_count,
            'bulk_count': 0,
            'speedup': 0
        }

def validate_express_download():
    """
    验证业绩快报下载优化
    """
    logger.info("开始验证业绩快报下载优化")

    period = '20231231'

    # 1. 逐股票下载测试（原方法模拟）
    logger.info("开始逐股票下载测试...")

    # 先获取一些股票代码用于测试
    try:
        stock_list = pro.stock_basic(exchange='', list_status='L', fields='ts_code')
        test_stocks = stock_list.head(15)['ts_code'].tolist()  # 增加到15只股票测试
    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        test_stocks = ['000001.SZ', '000002.SZ', '600000.SH', '601398.SH', '000006.SZ',
                      '000007.SZ', '000008.SZ', '000009.SZ', '000010.SZ', '000011.SZ',
                      '601939.SH', '601318.SH', '000858.SZ', '000568.SZ', '000333.SZ']

    start_time = time.time()
    all_data_individual = []

    for stock in test_stocks:
        try:
            df = pro.express(ts_code=stock, period=period)
            if not df.empty:
                all_data_individual.append(df)
            time.sleep(0.2)  # 避免API频率限制
        except Exception as e:
            logger.error(f"下载 {stock} 业绩快报失败: {e}")
            continue

    individual_time = time.time() - start_time
    individual_count = sum(len(df) for df in all_data_individual if df is not None)

    logger.info(f"逐股票下载完成 - 总耗时: {individual_time:.2f}s, 数据条数: {individual_count}")

    # 2. 批量下载测试（如果积分足够）
    logger.info("开始批量下载测试...")
    start_time = time.time()
    try:
        # 测试批量下载，使用分页确保下载超过10000条数据
        all_data_bulk = []
        offset = 0
        limit = 1000

        while True:
            try:
                df_bulk = pro.express_vip(period=period, limit=limit, offset=offset)
                if df_bulk is None or len(df_bulk) == 0:
                    break
                all_data_bulk.append(df_bulk)

                logger.info(f"  批量下载第{offset}-{offset+len(df_bulk)}条数据")

                if len(df_bulk) < limit:
                    break
                offset += limit

                # 避免API频率限制
                time.sleep(0.2)

            except Exception as e:
                logger.error(f"批量下载分页失败，offset={offset}: {e}")
                break

        bulk_time = time.time() - start_time
        bulk_count = sum(len(df) for df in all_data_bulk if df is not None)
        logger.info(f"批量下载完成 - 总耗时: {bulk_time:.2f}s, 数据条数: {bulk_count}")

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
        return {
            'individual_time': individual_time,
            'bulk_time': 0,
            'individual_count': individual_count,
            'bulk_count': 0,
            'speedup': 0
        }

def run_validation():
    """
    运行完整的事件数据下载验证
    """
    logger.info("开始事件数据批量下载验证")

    results = {}

    try:
        results['dividend'] = validate_dividend_download()
        logger.info("\n" + "="*50)

        results['forecast'] = validate_forecast_download()
        logger.info("\n" + "="*50)

        results['express'] = validate_express_download()
        logger.info("\n" + "="*50)

        # 汇总结果
        logger.info("验证结果汇总:")
        for data_type, result in results.items():
            logger.info(f"{data_type.upper()}:")
            if data_type == 'dividend':
                logger.info(f"  逐月下载耗时: {result['monthly_time']:.2f}s")
                logger.info(f"  日期范围下载耗时: {result['range_time']:.2f}s")
                logger.info(f"  逐月下载数据量: {result['monthly_count']}")
                logger.info(f"  日期范围下载数据量: {result['range_count']}")
            else:
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