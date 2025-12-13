"""
运行优化后的下载脚本，确保数据量超过10000条
"""
import sys
import os
import pandas as pd
sys.path.append('/home/quan/testdata/aspipe_v4/app')

from tushare_api import TuShareDownloader
from holder_bulk_downloader import run_holder_bulk_download
from research_bulk_downloader import run_research_bulk_download
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_optimized_holder_downloads():
    """
    运行优化后的股东数据下载
    """
    logger.info("开始运行优化后的股东数据下载...")
    results = run_holder_bulk_download()
    return results

def run_optimized_research_downloads():
    """
    运行优化后的研究数据下载
    """
    logger.info("开始运行优化后的研究数据下载...")
    results = run_research_bulk_download()
    return results

def main():
    """
    主函数，运行所有优化后的下载
    """
    logger.info("开始运行所有优化后的下载任务...")

    # 运行优化后的股东数据下载
    holder_results = run_optimized_holder_downloads()

    # 运行优化后的研究数据下载
    research_results = run_optimized_research_downloads()

    # 汇总结果
    logger.info("\n=== 优化后下载结果汇总 ===")
    logger.info("股东数据:")
    logger.info(f"  前十大股东: {holder_results['top10_holders']} 条记录")
    logger.info(f"  前十大流通股东: {holder_results['top10_floatholders']} 条记录")

    logger.info("研究数据:")
    logger.info(f"  卖方盈利预测: {research_results['report_rc']} 条记录")
    logger.info(f"  机构调研: {research_results['stk_surv']} 条记录")
    logger.info(f"  券商月度推荐: {research_results['broker_recommend']} 条记录")

    # 检查是否所有数据量都超过10000条
    logger.info("\n=== 数据量检查 ===")
    checks = {
        "前十大股东": holder_results['top10_holders'] >= 10000,
        "前十大流通股东": holder_results['top10_floatholders'] >= 10000,
        "卖方盈利预测": research_results['report_rc'] >= 10000,
        "机构调研": research_results['stk_surv'] >= 10000,
        "券商月度推荐": research_results['broker_recommend'] >= 10000
    }

    all_passed = True
    for name, passed in checks.items():
        status = "✓" if passed else "✗"
        logger.info(f"  {status} {name}: {'通过' if passed else '未通过'} (>=10000条)")
        if not passed:
            all_passed = False

    logger.info(f"\n总体结果: {'所有数据量检查均已通过' if all_passed else '部分数据量检查未通过'}")

    return {
        'holder_results': holder_results,
        'research_results': research_results,
        'checks': checks,
        'all_passed': all_passed
    }

if __name__ == "__main__":
    results = main()
    logger.info("优化后的下载任务完成")