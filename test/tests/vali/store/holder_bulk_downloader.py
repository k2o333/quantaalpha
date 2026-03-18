"""
股东数据批量下载器
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


def download_all_top10_holders(period: str = '20231231', limit: int = 1000, max_records: int = 15000) -> pd.DataFrame:
    """
    批量下载所有股票的前十大股东数据，直到达到指定记录数
    """
    logger.info(f"开始批量下载前十大股东数据，目标: {max_records} 条记录")

    all_data = []
    offset = 0

    while len(all_data) < max_records:
        try:
            # 分页获取股票基本信息
            stock_list = pro.stock_basic(exchange='', list_status='L',
                                        fields='ts_code', limit=limit, offset=offset)

            if stock_list is None or len(stock_list) == 0:
                logger.info("已获取完所有股票列表")
                break

            logger.info(f"正在处理 {len(stock_list)} 只股票 (偏移量: {offset})")

            for idx, stock in stock_list.iterrows():
                ts_code = stock['ts_code']

                try:
                    # 获取该股票的前十大股东数据
                    holder_data = pro.top10_holders(ts_code=ts_code, period=period)

                    if holder_data is not None and not holder_data.empty:
                        holder_data['ts_code'] = ts_code  # 添加股票代码标识
                        all_data.append(holder_data)

                        total_records = sum(len(df) for df in all_data)
                        logger.info(f"  {ts_code}: {len(holder_data)} 条记录, 总计: {total_records}")

                        if total_records >= max_records:
                            logger.info(f"已达到目标记录数 {max_records}")
                            break
                    else:
                        logger.debug(f"  {ts_code}: 无数据")

                    # 避免API频率限制
                    time.sleep(0.1)

                except Exception as e:
                    logger.error(f"下载 {ts_code} 的前十大股东失败: {e}")
                    continue

                if sum(len(df) for df in all_data) >= max_records:
                    break

            if sum(len(df) for df in all_data) >= max_records:
                break

            offset += limit
            logger.info(f"继续处理下一批股票，总记录数: {sum(len(df) for df in all_data)}")

        except Exception as e:
            logger.error(f"获取股票列表失败 (偏移量 {offset}): {e}")
            break

    if all_data:
        result = pd.concat(all_data, ignore_index=True)
        logger.info(f"前十大股东批量下载完成，总计: {len(result)} 条记录")
        return result
    else:
        logger.warning("未能获取任何前十大股东数据")
        return pd.DataFrame()


def download_all_top10_floatholders(period: str = '20231231', limit: int = 1000, max_records: int = 15000) -> pd.DataFrame:
    """
    批量下载所有股票的前十大流通股东数据，直到达到指定记录数
    """
    logger.info(f"开始批量下载前十大流通股东数据，目标: {max_records} 条记录")

    all_data = []
    offset = 0

    while len(all_data) < max_records:
        try:
            # 分页获取股票基本信息
            stock_list = pro.stock_basic(exchange='', list_status='L',
                                        fields='ts_code', limit=limit, offset=offset)

            if stock_list is None or len(stock_list) == 0:
                logger.info("已获取完所有股票列表")
                break

            logger.info(f"正在处理 {len(stock_list)} 只股票 (偏移量: {offset})")

            for idx, stock in stock_list.iterrows():
                ts_code = stock['ts_code']

                try:
                    # 获取该股票的前十大流通股东数据
                    holder_data = pro.top10_floatholders(ts_code=ts_code, period=period)

                    if holder_data is not None and not holder_data.empty:
                        holder_data['ts_code'] = ts_code  # 添加股票代码标识
                        all_data.append(holder_data)

                        total_records = sum(len(df) for df in all_data)
                        logger.info(f"  {ts_code}: {len(holder_data)} 条记录, 总计: {total_records}")

                        if total_records >= max_records:
                            logger.info(f"已达到目标记录数 {max_records}")
                            break
                    else:
                        logger.debug(f"  {ts_code}: 无数据")

                    # 避免API频率限制
                    time.sleep(0.1)

                except Exception as e:
                    logger.error(f"下载 {ts_code} 的前十大流通股东失败: {e}")
                    continue

                if sum(len(df) for df in all_data) >= max_records:
                    break

            if sum(len(df) for df in all_data) >= max_records:
                break

            offset += limit
            logger.info(f"继续处理下一批股票，总记录数: {sum(len(df) for df in all_data)}")

        except Exception as e:
            logger.error(f"获取股票列表失败 (偏移量 {offset}): {e}")
            break

    if all_data:
        result = pd.concat(all_data, ignore_index=True)
        logger.info(f"前十大流通股东批量下载完成，总计: {len(result)} 条记录")
        return result
    else:
        logger.warning("未能获取任何前十大流通股东数据")
        return pd.DataFrame()


def download_holder_data_for_multiple_periods(stock_codes: List[str], periods: List[str],
                                            holder_type: str = 'top10_holders') -> pd.DataFrame:
    """
    为指定股票下载多个报告期的股东数据
    """
    logger.info(f"开始下载 {holder_type} 的多期数据，涉及 {len(stock_codes)} 只股票，{len(periods)} 个报告期")

    all_data = []

    for period in periods:
        logger.info(f"处理报告期: {period}")

        for ts_code in stock_codes:
            try:
                if holder_type == 'top10_holders':
                    data = pro.top10_holders(ts_code=ts_code, period=period)
                elif holder_type == 'top10_floatholders':
                    data = pro.top10_floatholders(ts_code=ts_code, period=period)
                else:
                    logger.error(f"未知的股东类型: {holder_type}")
                    continue

                if data is not None and not data.empty:
                    data['ts_code'] = ts_code
                    data['period'] = period
                    all_data.append(data)

                    total_records = sum(len(df) for df in all_data)
                    logger.info(f"  {ts_code} {period}: {len(data)} 条记录, 总计: {total_records}")

                    if total_records >= 10000:  # 达到10000条记录后提前停止
                        logger.info("已达到10000条记录目标，提前停止")
                        break
                else:
                    logger.debug(f"  {ts_code} {period}: 无数据")

                # 避免API频率限制
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"下载 {ts_code} {period} {holder_type} 失败: {e}")
                continue

        if sum(len(df) for df in all_data) >= 10000:  # 达到10000条记录后提前停止
            break

    if all_data:
        result = pd.concat(all_data, ignore_index=True)
        logger.info(f"{holder_type} 多期数据下载完成，总计: {len(result)} 条记录")
        return result
    else:
        logger.warning(f"未能获取任何 {holder_type} 数据")
        return pd.DataFrame()


def run_holder_bulk_download():
    """
    运行股东数据批量下载
    """
    logger.info("开始股东数据批量下载...")

    try:
        # 下载前十大股东数据 (目标超过10000条)
        top10_holders_df = download_all_top10_holders()
        logger.info(f"前十大股东数据: {len(top10_holders_df)} 条记录")

        # 下载前十大流通股东数据 (目标超过10000条)
        top10_floatholders_df = download_all_top10_floatholders()
        logger.info(f"前十大流通股东数据: {len(top10_floatholders_df)} 条记录")

        # 如果积分足够，也可以尝试多期数据下载增加数据量
        if top10_holders_df.empty or len(top10_holders_df) < 10000:
            logger.info("数据量不足10000条，尝试多期数据下载...")
            # 获取部分股票代码
            try:
                stock_list = pro.stock_basic(exchange='', list_status='L', fields='ts_code')
                sample_stocks = stock_list.head(50)['ts_code'].tolist()  # 获取前50只股票
                periods = ['20231231', '20230930', '20230630', '20230331',
                          '20221231', '20220930', '20220630', '20220331']

                additional_top10 = download_holder_data_for_multiple_periods(sample_stocks, periods, 'top10_holders')
                if not additional_top10.empty:
                    top10_holders_df = pd.concat([top10_holders_df, additional_top10], ignore_index=True)

                additional_float = download_holder_data_for_multiple_periods(sample_stocks, periods, 'top10_floatholders')
                if not additional_float.empty:
                    top10_floatholders_df = pd.concat([top10_floatholders_df, additional_float], ignore_index=True)

            except Exception as e:
                logger.error(f"多期数据下载失败: {e}")

        logger.info(f"最终前十大股东数据: {len(top10_holders_df)} 条记录")
        logger.info(f"最终前十大流通股东数据: {len(top10_floatholders_df)} 条记录")

        # 保存数据
        if not top10_holders_df.empty:
            top10_holders_df.to_csv('/tmp/top10_holders_bulk.csv', index=False)
            logger.info("前十大股东数据已保存到 /tmp/top10_holders_bulk.csv")

        if not top10_floatholders_df.empty:
            top10_floatholders_df.to_csv('/tmp/top10_floatholders_bulk.csv', index=False)
            logger.info("前十大流通股东数据已保存到 /tmp/top10_floatholders_bulk.csv")

        return {
            'top10_holders': len(top10_holders_df),
            'top10_floatholders': len(top10_floatholders_df)
        }

    except Exception as e:
        logger.error(f"股东数据批量下载失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            'top10_holders': 0,
            'top10_floatholders': 0
        }


if __name__ == "__main__":
    results = run_holder_bulk_download()
    logger.info("股东数据批量下载结果:")
    logger.info(f"  前十大股东: {results['top10_holders']} 条记录")
    logger.info(f"  前十大流通股东: {results['top10_floatholders']} 条记录")