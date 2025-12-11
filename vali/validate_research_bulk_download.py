"""
验证研究数据批量下载优化效果
比较分页下载和普通下载的性能差异
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

def validate_report_rc_download():
    """
    验证卖方盈利预测数据下载优化
    """
    logger.info("开始验证卖方盈利预测数据下载优化")

    period = '20231231'

    # 1. 普通下载测试
    logger.info("开始普通下载测试...")
    start_time = time.time()
    try:
        # 普通下载会获取所有数据（限制为1000条，为测试目的）
        all_data_normal = []
        offset = 0
        limit = 1000  # 使用较大限制来模拟普通下载
        while True:
            try:
                df = pro.report_rc(period=period, limit=limit, offset=offset)
                if df is None or len(df) == 0:
                    break
                all_data_normal.append(df)

                if len(df) < limit:
                    break
                offset += limit
                time.sleep(0.1)  # 避免API频率限制
            except Exception as e:
                logger.error(f"普通下载分页失败，offset={offset}: {e}")
                break

        normal_time = time.time() - start_time
        normal_count = sum(len(df) for df in all_data_normal if df is not None)
        logger.info(f"普通下载完成 - 总耗时: {normal_time:.2f}s, 数据条数: {normal_count}")

        # 2. 分页下载测试（优化后方法）- 目标超过10000条数据
        logger.info("开始分页下载测试（目标超过10000条数据）...")
        start_time = time.time()

        all_data_paged = []
        offset = 0
        limit = 3000  # 每页大小增加到3000条

        # 继续下载直到达到10000条以上
        while True:
            try:
                # 尝试使用VIP接口获取更多数据
                try:
                    df = pro.report_rc_vip(period=period, limit=limit, offset=offset)
                except:
                    # 如果VIP接口不可用，使用普通接口
                    df = pro.report_rc(period=period, limit=limit, offset=offset)

                if df is None or len(df) == 0:
                    break
                all_data_paged.append(df)

                current_total = sum(len(d) for d in all_data_paged)
                logger.info(f"  当前已下载: {current_total} 条记录 (offset: {offset})")

                # 如果返回的数据少于请求量，说明已到达最后一页
                if len(df) < limit:
                    logger.info("已到达数据末尾")
                    break

                # 如果已达到10000条以上，停止下载
                if current_total >= 10000:
                    logger.info(f"已达到目标数据量: {current_total} 条记录")
                    break

                offset += limit
                time.sleep(0.2)  # 避免API频率限制

            except Exception as e:
                logger.error(f"分页下载失败，offset={offset}: {e}")
                break

        paged_time = time.time() - start_time
        paged_count = sum(len(df) for df in all_data_paged if df is not None)
        logger.info(f"分页下载完成 - 总耗时: {paged_time:.2f}s, 数据条数: {paged_count}")

        # 性能比较
        if paged_time > 0 and normal_time > 0:
            speedup = normal_time / paged_time if normal_time > paged_time else paged_time / normal_time
            comparison_type = "分页下载相比普通下载" if paged_time < normal_time else "普通下载相比分页下载"
            speedup = normal_time / paged_time if normal_time > paged_time else paged_time / normal_time if paged_time > 0 else 0
            logger.info(f"{comparison_type}速度: {speedup:.2f}x")

        return {
            'normal_time': normal_time,
            'paged_time': paged_time,
            'normal_count': normal_count,
            'paged_count': paged_count,
            'speedup': normal_time / paged_time if paged_time > 0 else 0
        }

    except Exception as e:
        logger.error(f"下载失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            'normal_time': 0,
            'paged_time': 0,
            'normal_count': 0,
            'paged_count': 0,
            'speedup': 0
        }

def validate_stk_surv_download():
    """
    验证机构调研数据下载优化
    """
    logger.info("开始验证机构调研数据下载优化")

    period = '20231231'

    # 1. 普通下载测试
    logger.info("开始普通下载测试...")
    start_time = time.time()
    try:
        # 普通下载会获取所有数据（限制为1000条，为测试目的）
        all_data_normal = []
        offset = 0
        limit = 1000  # 使用较大限制来模拟普通下载
        while True:
            try:
                df = pro.stk_surv(period=period, limit=limit, offset=offset)
                if df is None or len(df) == 0:
                    break
                all_data_normal.append(df)

                if len(df) < limit:
                    break
                offset += limit
                time.sleep(0.1)  # 避免API频率限制
            except Exception as e:
                logger.error(f"普通下载分页失败，offset={offset}: {e}")
                break

        normal_time = time.time() - start_time
        normal_count = sum(len(df) for df in all_data_normal if df is not None)
        logger.info(f"普通下载完成 - 总耗时: {normal_time:.2f}s, 数据条数: {normal_count}")

        # 2. 分页下载测试（优化后方法）- 目标超过10000条数据
        logger.info("开始分页下载测试（目标超过10000条数据）...")
        start_time = time.time()

        all_data_paged = []
        offset = 0
        limit = 3000  # 每页大小增加到3000条

        # 继续下载直到达到10000条以上
        while True:
            try:
                # 尝试使用VIP接口获取更多数据
                try:
                    df = pro.stk_surv_vip(period=period, limit=limit, offset=offset)
                except:
                    # 如果VIP接口不可用，使用普通接口
                    df = pro.stk_surv(period=period, limit=limit, offset=offset)

                if df is None or len(df) == 0:
                    break
                all_data_paged.append(df)

                current_total = sum(len(d) for d in all_data_paged)
                logger.info(f"  当前已下载: {current_total} 条记录 (offset: {offset})")

                # 如果返回的数据少于请求量，说明已到达最后一页
                if len(df) < limit:
                    logger.info("已到达数据末尾")
                    break

                # 如果已达到10000条以上，停止下载
                if current_total >= 10000:
                    logger.info(f"已达到目标数据量: {current_total} 条记录")
                    break

                offset += limit
                time.sleep(0.2)  # 避免API频率限制

            except Exception as e:
                logger.error(f"分页下载失败，offset={offset}: {e}")
                break

        paged_time = time.time() - start_time
        paged_count = sum(len(df) for df in all_data_paged if df is not None)
        logger.info(f"分页下载完成 - 总耗时: {paged_time:.2f}s, 数据条数: {paged_count}")

        # 性能比较
        if paged_time > 0 and normal_time > 0:
            speedup = normal_time / paged_time if normal_time > paged_time else paged_time / normal_time
            comparison_type = "分页下载相比普通下载" if paged_time < normal_time else "普通下载相比分页下载"
            speedup = normal_time / paged_time if normal_time > paged_time else paged_time / normal_time if paged_time > 0 else 0
            logger.info(f"{comparison_type}速度: {speedup:.2f}x")

        return {
            'normal_time': normal_time,
            'paged_time': paged_time,
            'normal_count': normal_count,
            'paged_count': paged_count,
            'speedup': normal_time / paged_time if paged_time > 0 else 0
        }

    except Exception as e:
        logger.error(f"下载失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            'normal_time': 0,
            'paged_time': 0,
            'normal_count': 0,
            'paged_count': 0,
            'speedup': 0
        }

def validate_broker_recommend_download():
    """
    验证券商月度股票推荐数据下载优化
    """
    logger.info("开始验证券商月度股票推荐数据下载优化")

    # 使用日期范围而非单个月份，以便获取更多数据
    start_date = '20230101'
    end_date = '20231231'

    # 1. 普通下载测试
    logger.info("开始普通下载测试...")
    start_time = time.time()
    try:
        # 普通下载会获取所有数据（限制为1000条，为测试目的）
        all_data_normal = []
        offset = 0
        limit = 1000  # 使用较大限制来模拟普通下载
        while True:
            try:
                df = pro.broker_recommend(start_date=start_date, end_date=end_date, limit=limit, offset=offset)
                if df is None or len(df) == 0:
                    break
                all_data_normal.append(df)

                if len(df) < limit:
                    break
                offset += limit
                time.sleep(0.1)  # 避免API频率限制
            except Exception as e:
                logger.error(f"普通下载分页失败，offset={offset}: {e}")
                break

        normal_time = time.time() - start_time
        normal_count = sum(len(df) for df in all_data_normal if df is not None)
        logger.info(f"普通下载完成 - 总耗时: {normal_time:.2f}s, 数据条数: {normal_count}")

        # 2. 分页下载测试（优化后方法）- 目标超过10000条数据
        logger.info("开始分页下载测试（目标超过10000条数据）...")
        start_time = time.time()

        all_data_paged = []
        offset = 0
        limit = 3000  # 每页大小增加到3000条

        # 继续下载直到达到10000条以上
        while True:
            try:
                df = pro.broker_recommend(start_date=start_date, end_date=end_date, limit=limit, offset=offset)
                if df is None or len(df) == 0:
                    break
                all_data_paged.append(df)

                current_total = sum(len(d) for d in all_data_paged)
                logger.info(f"  当前已下载: {current_total} 条记录 (offset: {offset})")

                # 如果返回的数据少于请求量，说明已到达最后一页
                if len(df) < limit:
                    logger.info("已到达数据末尾")
                    break

                # 如果已达到10000条以上，停止下载
                if current_total >= 10000:
                    logger.info(f"已达到目标数据量: {current_total} 条记录")
                    break

                offset += limit
                time.sleep(0.2)  # 避免API频率限制

            except Exception as e:
                logger.error(f"分页下载失败，offset={offset}: {e}")
                break

        paged_time = time.time() - start_time
        paged_count = sum(len(df) for df in all_data_paged if df is not None)
        logger.info(f"分页下载完成 - 总耗时: {paged_time:.2f}s, 数据条数: {paged_count}")

        # 性能比较
        if paged_time > 0 and normal_time > 0:
            speedup = normal_time / paged_time if normal_time > paged_time else paged_time / normal_time
            comparison_type = "分页下载相比普通下载" if paged_time < normal_time else "普通下载相比分页下载"
            speedup = normal_time / paged_time if normal_time > paged_time else paged_time / normal_time if paged_time > 0 else 0
            logger.info(f"{comparison_type}速度: {speedup:.2f}x")

        return {
            'normal_time': normal_time,
            'paged_time': paged_time,
            'normal_count': normal_count,
            'paged_count': paged_count,
            'speedup': normal_time / paged_time if paged_time > 0 else 0
        }

    except Exception as e:
        logger.error(f"下载失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            'normal_time': 0,
            'paged_time': 0,
            'normal_count': 0,
            'paged_count': 0,
            'speedup': 0
        }

def run_validation():
    """
    运行完整的研究数据下载验证
    """
    logger.info("开始研究数据批量下载验证")

    results = {}

    try:
        results['report_rc'] = validate_report_rc_download()
        logger.info("\n" + "="*50)

        results['stk_surv'] = validate_stk_surv_download()
        logger.info("\n" + "="*50)

        results['broker_recommend'] = validate_broker_recommend_download()
        logger.info("\n" + "="*50)

        # 汇总结果
        logger.info("验证结果汇总:")
        for data_type, result in results.items():
            logger.info(f"{data_type.upper()}:")
            logger.info(f"  普通下载耗时: {result['normal_time']:.2f}s")
            logger.info(f"  分页下载耗时: {result['paged_time']:.2f}s")
            logger.info(f"  普通下载数据量: {result['normal_count']}")
            logger.info(f"  分页下载数据量: {result['paged_count']}")
            logger.info(f"  速度提升倍数: {result['speedup']:.2f}x")
            logger.info("")

    except Exception as e:
        logger.error(f"验证过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_validation()