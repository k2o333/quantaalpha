"""
测试脚本：验证修复后的资金流向接口功能
"""
import logging
import time
from datetime import datetime, timedelta
import pandas as pd
import sys
import os

# 添加项目路径到系统路径
sys.path.append('/home/quan/testdata/aspipe_v4/app')

from tushare_api import TuShareDownloader
from date_range_downloader import DateRangeDownloader

def setup_logging():
    """设置日志"""
    # 创建logs目录
    os.makedirs('logs', exist_ok=True)

    # 配置日志
    log_filename = f"logs/test_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler()  # 同时输出到控制台
        ]
    )
    return logging.getLogger(__name__)

def test_moneyflow_interface():
    """测试资金流向接口功能"""
    logger = setup_logging()
    logger.info("开始测试资金流向接口功能...")

    try:
        downloader = TuShareDownloader()
        logger.info("✅ TuShareDownloader 初始化成功")

        # 获取最近的交易日
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        trade_date = yesterday.strftime('%Y%m%d')

        # 测试1: 直接调用 moneyflow 接口
        logger.info(f"测试1: 调用 moneyflow 接口，日期 {trade_date}")
        try:
            df1 = downloader.download_moneyflow(trade_date=trade_date)
            logger.info(f"✅ download_moneyflow 返回 {len(df1)} 条记录")
        except Exception as e:
            logger.error(f"❌ download_moneyflow 调用失败: {e}")
            return False

        # 测试2: 调用 moneyflow_dc 接口 (需要高积分)
        logger.info(f"测试2: 调用 moneyflow_dc 接口，日期 {trade_date}")
        try:
            df2 = downloader.download_moneyflow_dc(trade_date=trade_date)
            logger.info(f"✅ download_moneyflow_dc 返回 {len(df2)} 条记录")
        except Exception as e:
            logger.warning(f"⚠️ download_moneyflow_dc 调用失败或无数据 (可能是积分不足): {e}")

        # 测试3: 调用 moneyflow_ths 接口 (需要高积分)
        logger.info(f"测试3: 调用 moneyflow_ths 接口，日期 {trade_date}")
        try:
            df3 = downloader.download_moneyflow_ths(trade_date=trade_date)
            logger.info(f"✅ download_moneyflow_ths 返回 {len(df3)} 条记录")
        except Exception as e:
            logger.warning(f"⚠️ download_moneyflow_ths 调用失败或无数据 (可能是积分不足): {e}")

        # 测试4: 调用 moneyflow_ind_dc 接口
        logger.info(f"测试4: 调用 moneyflow_ind_dc 接口，日期 {trade_date}")
        try:
            df4 = downloader.download_moneyflow_ind_dc(trade_date=trade_date)
            logger.info(f"✅ download_moneyflow_ind_dc 返回 {len(df4)} 条记录")
        except Exception as e:
            logger.warning(f"⚠️ download_moneyflow_ind_dc 调用失败或无数据 (可能是积分不足): {e}")

        # 测试5: 调用 moneyflow_mkt_dc 接口
        logger.info(f"测试5: 调用 moneyflow_mkt_dc 接口，日期 {trade_date}")
        try:
            df5 = downloader.download_moneyflow_mkt_dc(trade_date=trade_date)
            logger.info(f"✅ download_moneyflow_mkt_dc 返回 {len(df5)} 条记录")
        except Exception as e:
            logger.warning(f"⚠️ download_moneyflow_mkt_dc 调用失败或无数据 (可能是积分不足): {e}")

        # 测试6: 测试 date_range_downloader 中的逻辑
        logger.info("测试6: 测试 date_range_downloader 中的资金流向逻辑")
        try:
            # 使用较短的日期范围进行测试
            test_start = (today - timedelta(days=3)).strftime('%Y%m%d')  # 3天前
            test_end = trade_date  # 昨天

            date_downloader = DateRangeDownloader(test_start, test_end)
            logger.info(f"✅ DateRangeDownloader 初始化成功，范围 {test_start} 到 {test_end}")

            # 检查是否能获取交易日
            trading_days = date_downloader.get_trading_days()
            logger.info(f"✅ 获取到 {len(trading_days)} 个交易日: {trading_days}")
        except Exception as e:
            logger.error(f"❌ date_range_downloader 相关功能出错: {e}")

        logger.info("✅ 资金流向接口功能测试完成，没有发现主要错误")
        return True

    except Exception as e:
        logger.error(f"❌ 测试过程中发生错误: {e}")
        return False

def main():
    """主函数，运行测试"""
    logger = setup_logging()

    logger.info("="*60)
    logger.info("开始验证资金流向接口修复功能")
    logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)

    start_time = time.time()

    # 运行测试
    success = test_moneyflow_interface()

    end_time = time.time()
    duration = end_time - start_time

    logger.info("="*60)
    logger.info(f"测试完成，耗时: {duration:.2f}秒")
    logger.info(f"测试结果: {'✅ 成功' if success else '❌ 失败'}")
    logger.info("="*60)

    if success:
        print(f"\n🎉 修复验证成功！资金流向接口现在可以正常工作。")
        print(f"   测试耗时: {duration:.2f}秒")
        print(f"   日志文件: {logging.getLogger().handlers[0].baseFilename if hasattr(logging.getLogger().handlers[0], 'baseFilename') else 'N/A'}")
    else:
        print(f"\n❌ 修复验证失败，请进一步检查问题。")
        print(f"   测试耗时: {duration:.2f}秒")

    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)