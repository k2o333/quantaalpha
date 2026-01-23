"""
下载速度和稳定性验证脚本
测试接口在大数据量处理时的性能和稳定性
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

def test_large_data_download():
    """
    测试接口处理大数据量的能力
    """
    logger.info("开始测试大数据量下载稳定性")

    # 测试1: 财务数据批量下载
    logger.info("测试财务数据批量下载...")
    start_time = time.time()
    try:
        # 使用VIP接口下载大量财务数据
        income_data = pro.income_vip(period='20231231', limit=3000, offset=0)
        logger.info(f"财务数据下载成功: {len(income_data)} 条记录")

        balancesheet_data = pro.balancesheet_vip(period='20231231', limit=3000, offset=0)
        logger.info(f"资产负债表数据下载成功: {len(balancesheet_data)} 条记录")

        cashflow_data = pro.cashflow_vip(period='20231231', limit=3000, offset=0)
        logger.info(f"现金流量表数据下载成功: {len(cashflow_data)} 条记录")

        logger.info(f"财务数据下载总耗时: {time.time() - start_time:.2f}s")
    except Exception as e:
        logger.error(f"财务数据下载失败: {e}")

    # 测试2: 研究数据批量下载
    logger.info("\n测试研究数据批量下载...")
    start_time = time.time()
    try:
        # 下载大量研究数据
        report_rc_data = pro.report_rc(period='20231231', limit=3000, offset=0)
        logger.info(f"卖方盈利预测数据下载成功: {len(report_rc_data)} 条记录")

        stk_surv_data = pro.stk_surv(period='20231231', limit=3000, offset=0)
        logger.info(f"机构调研数据下载成功: {len(stk_surv_data)} 条记录")

        broker_recommend_data = pro.broker_recommend(start_date='20230101', end_date='20231231', limit=3000, offset=0)
        logger.info(f"券商推荐数据下载成功: {len(broker_recommend_data)} 条记录")

        logger.info(f"研究数据下载总耗时: {time.time() - start_time:.2f}s")
    except Exception as e:
        logger.error(f"研究数据下载失败: {e}")

    # 测试3: 事件数据批量下载
    logger.info("\n测试事件数据批量下载...")
    start_time = time.time()
    try:
        # 下载大量事件数据
        dividend_data = pro.dividend(start_date='20220101', end_date='20231231', limit=3000, offset=0)
        logger.info(f"分红数据下载成功: {len(dividend_data)} 条记录")

        forecast_data = pro.forecast_vip(period='20231231', limit=3000, offset=0)
        logger.info(f"业绩预告数据下载成功: {len(forecast_data)} 条记录")

        express_data = pro.express_vip(period='20231231', limit=3000, offset=0)
        logger.info(f"业绩快报数据下载成功: {len(express_data)} 条记录")

        logger.info(f"事件数据下载总耗时: {time.time() - start_time:.2f}s")
    except Exception as e:
        logger.error(f"事件数据下载失败: {e}")

    # 测试4: 股东数据批量下载
    logger.info("\n测试股东数据批量下载...")
    start_time = time.time()
    try:
        # 测试单个股票的股东数据
        holder_data = pro.top10_holders(ts_code='000001.SZ', period='20231231')
        logger.info(f"前十大股东数据下载成功: {len(holder_data)} 条记录")

        floatholder_data = pro.top10_floatholders(ts_code='000001.SZ', period='20231231')
        logger.info(f"前十大流通股东数据下载成功: {len(floatholder_data)} 条记录")

        logger.info(f"股东数据下载总耗时: {time.time() - start_time:.2f}s")
    except Exception as e:
        logger.error(f"股东数据下载失败: {e}")

    logger.info("\n所有大数据量下载测试完成！")

def test_api_rate_limiting():
    """
    测试API频率限制
    """
    logger.info("开始测试API频率限制...")

    start_time = time.time()
    success_count = 0
    error_count = 0

    # 快速连续调用API以测试频率限制
    for i in range(10):
        try:
            # 调用一个简单的API (daily接口不支持limit参数)
            daily_data = pro.daily(trade_date='20231201')
            logger.debug(f"API调用 {i+1}: 成功获取 {len(daily_data)} 条记录")
            success_count += 1
        except Exception as e:
            logger.error(f"API调用 {i+1}: 失败 - {e}")
            error_count += 1
            # 如果遇到频率限制，稍作等待
            if "频率" in str(e) or "limit" in str(e).lower():
                time.sleep(1)

    total_time = time.time() - start_time
    logger.info(f"API频率测试完成: 成功 {success_count} 次, 失败 {error_count} 次, 总耗时 {total_time:.2f}s")

def run_performance_tests():
    """
    运行所有性能测试
    """
    logger.info("开始运行性能和稳定性测试")
    logger.info("=" * 50)

    test_large_data_download()
    logger.info("\n" + "=" * 50)
    test_api_rate_limiting()

    logger.info("\n" + "=" * 50)
    logger.info("所有性能测试完成！")

if __name__ == "__main__":
    run_performance_tests()