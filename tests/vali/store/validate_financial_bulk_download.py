"""
验证财务数据批量下载优化效果
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

def validate_income_download():
    """
    验证收入表下载优化
    """
    logger.info("开始验证收入表下载优化")

    # 测试数据：选择几个股票进行逐个下载测试
    test_stocks = ['000001.SZ', '000002.SZ', '600000.SH', '601398.SH', '000006.SZ',
                   '000007.SZ', '000008.SZ', '000009.SZ', '000010.SZ', '000011.SZ',
                   '601939.SH', '601318.SH', '000858.SZ', '000568.SZ', '000333.SZ']
    period = '20231231'

    # 1. 逐股票下载测试
    logger.info("开始逐股票下载测试...")
    start_time = time.time()
    all_data_individual = []

    for stock in test_stocks:
        try:
            df = pro.income(ts_code=stock, period=period)
            if not df.empty:
                all_data_individual.append(df)
            time.sleep(0.1)  # 避免API频率限制
        except Exception as e:
            logger.error(f"下载 {stock} 收入表失败: {e}")
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
                df_bulk = pro.income_vip(period=period, limit=limit, offset=offset)
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

def validate_balancesheet_download():
    """
    验证资产负债表下载优化
    """
    logger.info("开始验证资产负债表下载优化")

    test_stocks = ['000001.SZ', '000002.SZ', '600000.SH', '601398.SH', '000006.SZ',
                   '000007.SZ', '000008.SZ', '000009.SZ', '000010.SZ', '000011.SZ',
                   '601939.SH', '601318.SH', '000858.SZ', '000568.SZ', '000333.SZ']
    period = '20231231'

    # 1. 逐股票下载测试
    logger.info("开始逐股票下载测试...")
    start_time = time.time()
    all_data_individual = []

    for stock in test_stocks:
        try:
            df = pro.balancesheet(ts_code=stock, period=period)
            if not df.empty:
                all_data_individual.append(df)
            time.sleep(0.1)  # 避免API频率限制
        except Exception as e:
            logger.error(f"下载 {stock} 资产负债表失败: {e}")
            continue

    individual_time = time.time() - start_time
    individual_count = sum(len(df) for df in all_data_individual if df is not None)

    logger.info(f"逐股票下载完成 - 总耗时: {individual_time:.2f}s, 数据条数: {individual_count}")

    # 2. 批量下载测试
    logger.info("开始批量下载测试...")
    start_time = time.time()
    try:
        # 测试批量下载，使用分页确保下载超过10000条数据
        all_data_bulk = []
        offset = 0
        limit = 1000

        while True:
            try:
                df_bulk = pro.balancesheet_vip(period=period, limit=limit, offset=offset)
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

def validate_cashflow_download():
    """
    验证现金流量表下载优化
    """
    logger.info("开始验证现金流量表下载优化")

    test_stocks = ['000001.SZ', '000002.SZ', '600000.SH', '601398.SH', '000006.SZ',
                   '000007.SZ', '000008.SZ', '000009.SZ', '000010.SZ', '000011.SZ',
                   '601939.SH', '601318.SH', '000858.SZ', '000568.SZ', '000333.SZ']
    period = '20231231'

    # 1. 逐股票下载测试
    logger.info("开始逐股票下载测试...")
    start_time = time.time()
    all_data_individual = []

    for stock in test_stocks:
        try:
            df = pro.cashflow(ts_code=stock, period=period)
            if not df.empty:
                all_data_individual.append(df)
            time.sleep(0.1)  # 避免API频率限制
        except Exception as e:
            logger.error(f"下载 {stock} 现金流量表失败: {e}")
            continue

    individual_time = time.time() - start_time
    individual_count = sum(len(df) for df in all_data_individual if df is not None)

    logger.info(f"逐股票下载完成 - 总耗时: {individual_time:.2f}s, 数据条数: {individual_count}")

    # 2. 批量下载测试
    logger.info("开始批量下载测试...")
    start_time = time.time()
    try:
        # 测试批量下载，使用分页确保下载超过10000条数据
        all_data_bulk = []
        offset = 0
        limit = 1000

        while True:
            try:
                df_bulk = pro.cashflow_vip(period=period, limit=limit, offset=offset)
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
    运行完整的财务数据下载验证
    """
    logger.info("开始财务数据批量下载验证")

    results = {}

    try:
        results['income'] = validate_income_download()
        logger.info("\n" + "="*50)

        results['balancesheet'] = validate_balancesheet_download()
        logger.info("\n" + "="*50)

        results['cashflow'] = validate_cashflow_download()
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