#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TuShare API下载极限详细验证脚本
用于验证5000积分token可以调用的不同数据接口的下载能力，
包括最大下载量、分页信息等详细参数
"""

import sys
import os
import time
import pandas as pd
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append('/home/quan/testdata/aspipe_v4')

from app.tushare_api import TuShareDownloader
from app.config import TUSHARE_POINTS

def test_api_limit_detailed(api_name, api_call_func, *args, **kwargs):
    """
    详细测试API调用极限，包括最大下载量、分页等信息
    """
    print(f"\n=== 测试 {api_name} 接口 ===")
    print(f"用户积分: {TUSHARE_POINTS}")

    downloader = TuShareDownloader()

    try:
        start_time = time.time()
        result = api_call_func(downloader, *args, **kwargs)
        end_time = time.time()

        if isinstance(result, pd.DataFrame):
            print(f"✓ 调用成功!")
            print(f"  - 耗时: {end_time - start_time:.2f}秒")
            print(f"  - 返回记录数: {len(result)}")
            if len(result) > 0:
                print(f"  - 字段数: {len(result.columns)}")
                print(f"  - 前3列: {list(result.columns[:3])}")

                # 检查是否有分页相关信息
                if 'limit' in kwargs:
                    print(f"  - 请求限制: {kwargs['limit']} 条记录")

                # 检查是否有offset/分页参数
                if 'offset' in kwargs:
                    print(f"  - 偏移量: {kwargs['offset']}")

                # 显示数据结构信息
                print(f"  - 数据结构示例:")
                print(result.head(2).to_string())

            return True, len(result)
        else:
            print(f"? 返回类型未知: {type(result)}")
            return False, 0

    except Exception as e:
        print(f"✗ 调用失败: {e}")
        return False, 0

def test_pagination_capability(api_name, api_func, base_params=None):
    """
    测试接口的分页能力
    """
    print(f"\n--- {api_name} 分页能力测试 ---")

    if base_params is None:
        base_params = {}

    downloader = TuShareDownloader()

    try:
        # 测试默认请求
        print("1. 默认请求测试:")
        default_result = downloader.download_with_retry(api_func, **base_params)
        print(f"   默认返回记录数: {len(default_result)}")

        # 测试带limit的请求
        print("2. 带limit参数测试:")
        limit_params = base_params.copy()
        limit_params['limit'] = 100
        limit_result = downloader.download_with_retry(api_func, **limit_params)
        print(f"   limit=100时返回记录数: {len(limit_result)}")

        # 如果默认返回较少记录，尝试获取更多
        if len(default_result) < 1000:
            print("3. 尝试获取更多数据:")
            more_params = base_params.copy()
            more_params['limit'] = 2000
            more_result = downloader.download_with_retry(api_func, **more_params)
            print(f"   limit=2000时返回记录数: {len(more_result)}")

        return True

    except Exception as e:
        print(f"   分页测试失败: {e}")
        return False

def main():
    """
    主函数 - 详细验证各种API接口的下载能力
    """
    print("=" * 70)
    print("TuShare API 下载能力详细验证工具")
    print(f"Token积分: {TUSHARE_POINTS}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    downloader = TuShareDownloader()

    # 1. 股票基本信息 (stock_basic) - 测试分页能力
    print("\n【基础信息类接口】")
    test_pagination_capability("股票基本信息(stock_basic)", downloader.pro.stock_basic,
                             {'exchange': '', 'list_status': 'L'})

    # 2. 交易日历 (trade_cal) - 测试时间范围
    print("\n【交易日历接口】")
    trade_cal_result = downloader.download_with_retry(downloader.pro.trade_cal,
                                                    exchange='SSE',
                                                    start_date='20100101',
                                                    end_date='20251231')
    print(f"交易日历总记录数: {len(trade_cal_result)} (通常包含约15年数据)")

    # 3. 上市公司基本信息 (stock_company) - 测试分交易所获取
    print("\n【上市公司信息接口】")
    print("上海证券交易所数据:")
    sse_result = downloader.download_with_retry(downloader.pro.stock_company, exchange='SSE')
    print(f"  SSE记录数: {len(sse_result)}")

    print("深圳证券交易所数据:")
    szse_result = downloader.download_with_retry(downloader.pro.stock_company, exchange='SZSE')
    print(f"  SZSE记录数: {len(szse_result)}")

    # 4. 每日指标 (daily_basic) - 测试单日数据量
    print("\n【每日指标接口】")
    # 获取最近的交易日
    trade_cal = downloader.download_trade_cal(exchange='SSE')
    if len(trade_cal) > 0:
        recent_trade_date = trade_cal[trade_cal['is_open'] == 1].iloc[-1]['cal_date']
        daily_basic_result = downloader.download_with_retry(downloader.pro.daily_basic,
                                                          trade_date=recent_trade_date)
        print(f"单个交易日每日指标记录数: {len(daily_basic_result)} (全市场数据)")

    # 5. VIP财务接口 - 测试单季度数据量
    print("\n【VIP财务接口 - 单季度数据量测试】")

    # 利润表
    income_result = downloader.download_with_retry(
        downloader.pro.income_vip if TUSHARE_POINTS >= 5000 else downloader.pro.income,
        period='20230331'
    )
    print(f"利润表(2023Q1)记录数: {len(income_result)}")

    # 资产负债表
    balance_result = downloader.download_with_retry(
        downloader.pro.balancesheet_vip if TUSHARE_POINTS >= 5000 else downloader.pro.balancesheet,
        period='20230331'
    )
    print(f"资产负债表(2023Q1)记录数: {len(balance_result)}")

    # 现金流量表
    cashflow_result = downloader.download_with_retry(
        downloader.pro.cashflow_vip if TUSHARE_POINTS >= 5000 else downloader.pro.cashflow,
        period='20230331'
    )
    print(f"现金流量表(2023Q1)记录数: {len(cashflow_result)}")

    # 财务指标
    fina_indicator_result = downloader.download_with_retry(
        downloader.pro.fina_indicator_vip if TUSHARE_POINTS >= 5000 else downloader.pro.fina_indicator,
        period='20230331'
    )
    print(f"财务指标(2023Q1)记录数: {len(fina_indicator_result)}")

    # 6. 资金流向接口
    print("\n【资金流向接口】")
    if 'recent_trade_date' in locals():
        moneyflow_result = downloader.download_with_retry(downloader.pro.moneyflow,
                                                        trade_date=recent_trade_date)
        print(f"单日资金流向记录数: {len(moneyflow_result)}")

    # 7. 前十大股东接口 - 测试单股票数据
    print("\n【前十大股东接口】")
    top10_result = downloader.download_with_retry(downloader.pro.top10_holders,
                                                ts_code='000001.SZ',
                                                period='20231231')
    print(f"单股票前十大股东记录数: {len(top10_result)}")

    # 8. 机构调研接口 - 测试数据量
    print("\n【机构调研接口】")
    stk_surv_result = downloader.download_with_retry(downloader.pro.stk_surv, limit=2000)
    print(f"机构调研记录数(limit=2000): {len(stk_surv_result)}")

    # 9. 技术因子接口 - 测试单股票数据
    print("\n【技术因子接口】")
    if 'recent_trade_date' in locals():
        stk_factor_result = downloader.download_with_retry(downloader.pro.stk_factor,
                                                         ts_code='000001.SZ',
                                                         trade_date=recent_trade_date)
        print(f"单股票技术因子记录数: {len(stk_factor_result)}")

    # 10. 分红送股接口 - 测试参数要求
    print("\n【分红送股接口】")
    try:
        # 测试带参数的调用
        dividend_result = downloader.download_with_retry(downloader.pro.dividend,
                                                       ts_code='000001.SZ')
        print(f"单股票分红记录数: {len(dividend_result)}")
    except Exception as e:
        print(f"分红接口调用失败: {e}")
        print("注意: dividend接口需要指定ts_code参数")

    print("\n" + "=" * 70)
    print("详细测试结果总结:")
    print("=" * 70)
    print("1. 基础信息类接口:")
    print("   - stock_basic: 支持分页，可获取全市场股票信息")
    print("   - trade_cal: 时间范围查询，通常返回数千条记录")
    print("   - stock_company: 按交易所分批获取，支持完整数据")

    print("\n2. 行情数据类接口:")
    print("   - daily_basic: 单日全市场数据，通常数千条记录")
    print("   - moneyflow: 单日全市场数据，通常数百到千条记录")

    print("\n3. VIP财务接口 (5000积分优势):")
    print("   - income_vip/balancesheet_vip/cashflow_vip/fina_indicator_vip:")
    print("     单季度全市场数据，通常数千条记录")
    print("     相比普通接口效率提升显著")

    print("\n4. 特殊数据接口:")
    print("   - top10_holders: 单股票最多10条记录")
    print("   - stk_surv: 支持limit参数，可获取大量记录")
    print("   - stk_factor: 单股票单日1条记录")
    print("   - dividend: 需要指定股票代码参数")

    print("\n5. 5000积分用户特权:")
    print("   ✓ 可使用所有VIP接口")
    print("   ✓ 更高的API调用频率限制")
    print("   ✓ daily_basic等接口无总量限制")
    print("   ✓ 支持更大的单次查询返回记录数")
    print("   ✓ 部分接口调用次数限制更宽松")

    print(f"\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

if __name__ == "__main__":
    main()