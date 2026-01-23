"""
研究数据批量下载器
通过批量下载所有股票的数据来增加数据量，使其超过10000条
"""
import time
import pandas as pd
import logging
from typing import List, Optional
import tushare as ts
import os

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 初始化TuShare
token = os.environ.get('TUSHARE_TOKEN', 'your_token_here')
pro = ts.pro_api(token)


def download_all_report_rc(period: str = '20231231', limit: int = 3000, max_records: int = 15000) -> pd.DataFrame:
    """
    批量下载所有股票的卖方盈利预测数据，直到达到指定记录数
    """
    logger.info(f"开始批量下载卖方盈利预测数据，目标: {max_records} 条记录")

    all_data = []
    offset = 0

    while True:
        try:
            # 直接使用VIP接口分页下载（如果积分足够）
            try:
                df = pro.report_rc_vip(period=period, limit=limit, offset=offset)
            except:
                # 如果VIP接口不可用，使用普通接口
                df = pro.report_rc(period=period, limit=limit, offset=offset)

            if df is None or len(df) == 0:
                logger.info("已下载完所有数据或达到API限制")
                break

            all_data.append(df)
            current_total = sum(len(d) for d in all_data)
            logger.info(f"当前已下载: {current_total} 条记录 (offset: {offset})")

            if len(df) < limit or current_total >= max_records:
                logger.info("已达到数据末尾或目标记录数")
                break

            offset += limit
            time.sleep(0.2)  # 控制API调用频率

        except Exception as e:
            logger.error(f"下载报告预测数据失败 (offset {offset}): {e}")
            break

    if all_data:
        result = pd.concat(all_data, ignore_index=True)
        logger.info(f"卖方盈利预测批量下载完成，总计: {len(result)} 条记录")
        return result
    else:
        logger.warning("未能获取任何卖方盈利预测数据")
        return pd.DataFrame()


def download_all_stk_surv(period: str = '20231231', limit: int = 3000, max_records: int = 15000) -> pd.DataFrame:
    """
    批量下载所有股票的机构调研数据，直到达到指定记录数
    """
    logger.info(f"开始批量下载机构调研数据，目标: {max_records} 条记录")

    all_data = []
    offset = 0

    while True:
        try:
            # 直接使用VIP接口分页下载（如果积分足够）
            try:
                df = pro.stk_surv_vip(period=period, limit=limit, offset=offset)
            except:
                # 如果VIP接口不可用，使用普通接口
                df = pro.stk_surv(period=period, limit=limit, offset=offset)

            if df is None or len(df) == 0:
                logger.info("已下载完所有数据或达到API限制")
                break

            all_data.append(df)
            current_total = sum(len(d) for d in all_data)
            logger.info(f"当前已下载: {current_total} 条记录 (offset: {offset})")

            if len(df) < limit or current_total >= max_records:
                logger.info("已达到数据末尾或目标记录数")
                break

            offset += limit
            time.sleep(0.2)  # 控制API调用频率

        except Exception as e:
            logger.error(f"下载机构调研数据失败 (offset {offset}): {e}")
            break

    if all_data:
        result = pd.concat(all_data, ignore_index=True)
        logger.info(f"机构调研批量下载完成，总计: {len(result)} 条记录")
        return result
    else:
        logger.warning("未能获取任何机构调研数据")
        return pd.DataFrame()


def download_all_broker_recommend(start_date: str = '20230101', end_date: str = '20231231',
                                 limit: int = 3000, max_records: int = 15000) -> pd.DataFrame:
    """
    批量下载券商月度推荐数据，直到达到指定记录数
    """
    logger.info(f"开始批量下载券商月度推荐数据，日期范围: {start_date} 到 {end_date}")

    all_data = []
    offset = 0

    while True:
        try:
            # 分页下载券商推荐数据
            df = pro.broker_recommend(start_date=start_date, end_date=end_date,
                                    limit=limit, offset=offset)

            if df is None or len(df) == 0:
                logger.info("已下载完所有数据或达到API限制")
                break

            all_data.append(df)
            current_total = sum(len(d) for d in all_data)
            logger.info(f"当前已下载: {current_total} 条记录 (offset: {offset})")

            if len(df) < limit or current_total >= max_records:
                logger.info("已达到数据末尾或目标记录数")
                break

            offset += limit
            time.sleep(0.2)  # 控制API调用频率

        except Exception as e:
            logger.error(f"下载券商推荐数据失败 (offset {offset}): {e}")
            break

    if all_data:
        result = pd.concat(all_data, ignore_index=True)
        logger.info(f"券商月度推荐批量下载完成，总计: {len(result)} 条记录")
        return result
    else:
        logger.warning("未能获取任何券商月度推荐数据")
        return pd.DataFrame()


def download_research_data_for_multiple_periods(periods: List[str], max_records: int = 15000) -> pd.DataFrame:
    """
    为多个报告期下载研究数据
    """
    logger.info(f"开始下载多期研究数据，涉及 {len(periods)} 个报告期")

    all_data = []
    total_records = 0

    for period in periods:
        logger.info(f"处理报告期: {period}")

        # 下载报告预测数据
        try:
            report_df = download_all_report_rc(period=period, max_records=max_records//len(periods))
            if not report_df.empty:
                all_data.append(report_df)
                total_records += len(report_df)
                logger.info(f"  报告预测数据: {len(report_df)} 条记录")
        except Exception as e:
            logger.error(f"下载报告预测数据失败 {period}: {e}")

        # 下载机构调研数据
        try:
            surv_df = download_all_stk_surv(period=period, max_records=max_records//len(periods))
            if not surv_df.empty:
                all_data.append(surv_df)
                total_records += len(surv_df)
                logger.info(f"  机构调研数据: {len(surv_df)} 条记录")
        except Exception as e:
            logger.error(f"下载机构调研数据失败 {period}: {e}")

        if total_records >= max_records:
            logger.info("已达到目标记录数")
            break

        time.sleep(1)  # 控制API调用频率

    if all_data:
        result = pd.concat(all_data, ignore_index=True)
        logger.info(f"多期研究数据下载完成，总计: {len(result)} 条记录")
        return result
    else:
        logger.warning("未能获取任何研究数据")
        return pd.DataFrame()


def run_research_bulk_download():
    """
    运行研究数据批量下载
    """
    logger.info("开始研究数据批量下载...")

    try:
        # 下载卖方盈利预测数据 (目标超过10000条)
        report_rc_df = download_all_report_rc()
        logger.info(f"卖方盈利预测数据: {len(report_rc_df)} 条记录")

        # 下载机构调研数据 (目标超过10000条)
        stk_surv_df = download_all_stk_surv()
        logger.info(f"机构调研数据: {len(stk_surv_df)} 条记录")

        # 下载券商月度推荐数据 (目标超过10000条)
        broker_recommend_df = download_all_broker_recommend()
        logger.info(f"券商月度推荐数据: {len(broker_recommend_df)} 条记录")

        # 如果总数据量仍不足，尝试多期数据下载
        total_current = len(report_rc_df) + len(stk_surv_df) + len(broker_recommend_df)
        if total_current < 10000:
            logger.info(f"当前数据量 {total_current} 不足10000条，尝试多期数据下载...")

            periods = ['20231231', '20230930', '20230630', '20230331',
                      '20221231', '20220930', '20220630', '20220331']

            additional_data = download_research_data_for_multiple_periods(periods)
            if not additional_data.empty:
                # 合并额外数据
                if not report_rc_df.empty:
                    report_rc_df = pd.concat([report_rc_df, additional_data[additional_data['数据类型'] == 'report_rc']], ignore_index=True)
                if not stk_surv_df.empty:
                    stk_surv_df = pd.concat([stk_surv_df, additional_data[additional_data['数据类型'] == 'stk_surv']], ignore_index=True)
                if not broker_recommend_df.empty:
                    broker_recommend_df = pd.concat([broker_recommend_df, additional_data[additional_data['数据类型'] == 'broker_recommend']], ignore_index=True)

        # 重新计算总计
        total_report_rc = len(report_rc_df) if not report_rc_df.empty else 0
        total_stk_surv = len(stk_surv_df) if not stk_surv_df.empty else 0
        total_broker_recommend = len(broker_recommend_df) if not broker_recommend_df.empty else 0

        logger.info(f"最终卖方盈利预测数据: {total_report_rc} 条记录")
        logger.info(f"最终机构调研数据: {total_stk_surv} 条记录")
        logger.info(f"最终券商月度推荐数据: {total_broker_recommend} 条记录")

        # 保存数据
        if not report_rc_df.empty:
            report_rc_df.to_csv('/tmp/report_rc_bulk.csv', index=False)
            logger.info("卖方盈利预测数据已保存到 /tmp/report_rc_bulk.csv")

        if not stk_surv_df.empty:
            stk_surv_df.to_csv('/tmp/stk_surv_bulk.csv', index=False)
            logger.info("机构调研数据已保存到 /tmp/stk_surv_bulk.csv")

        if not broker_recommend_df.empty:
            broker_recommend_df.to_csv('/tmp/broker_recommend_bulk.csv', index=False)
            logger.info("券商月度推荐数据已保存到 /tmp/broker_recommend_bulk.csv")

        return {
            'report_rc': total_report_rc,
            'stk_surv': total_stk_surv,
            'broker_recommend': total_broker_recommend
        }

    except Exception as e:
        logger.error(f"研究数据批量下载失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            'report_rc': 0,
            'stk_surv': 0,
            'broker_recommend': 0
        }


def download_research_data_with_pagination(data_type: str, period: str = '20231231',
                                         start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    使用分页方式下载研究数据
    """
    logger.info(f"开始使用分页方式下载 {data_type} 数据")

    all_data = []
    offset = 0
    limit = 3000

    while True:
        try:
            if data_type == 'report_rc':
                df = pro.report_rc(period=period, limit=limit, offset=offset)
            elif data_type == 'stk_surv':
                df = pro.stk_surv(period=period, limit=limit, offset=offset)
            elif data_type == 'broker_recommend':
                # 为券商推荐使用日期范围而非分页，如果提供日期
                if start_date and end_date:
                    df = pro.broker_recommend(start_date=start_date, end_date=end_date,
                                            limit=limit, offset=offset)
                else:
                    df = pro.broker_recommend(month=period[:6], limit=limit, offset=offset)  # 使用YYYYMM格式
            else:
                logger.error(f"未知的数据类型: {data_type}")
                break

            if df is None or len(df) == 0:
                logger.info(f"下载 {data_type} 数据完成")
                break

            all_data.append(df)
            current_total = sum(len(d) for d in all_data)
            logger.info(f"已下载 {data_type}: {current_total} 条记录 (offset: {offset})")

            # 如果返回的数据少于limit，说明已到达最后一页
            if len(df) < limit:
                logger.info(f"已到达 {data_type} 数据末尾")
                break

            offset += limit
            time.sleep(0.2)  # 控制API调用频率

        except Exception as e:
            logger.error(f"分页下载 {data_type} 数据失败 (offset {offset}): {e}")
            break

    if all_data:
        result = pd.concat(all_data, ignore_index=True)
        logger.info(f"{data_type} 分页下载完成，总计: {len(result)} 条记录")
        return result
    else:
        logger.warning(f"未能获取任何 {data_type} 数据")
        return pd.DataFrame()


if __name__ == "__main__":
    results = run_research_bulk_download()
    logger.info("研究数据批量下载结果:")
    logger.info(f"  卖方盈利预测: {results['report_rc']} 条记录")
    logger.info(f"  机构调研: {results['stk_surv']} 条记录")
    logger.info(f"  券商月度推荐: {results['broker_recommend']} 条记录")