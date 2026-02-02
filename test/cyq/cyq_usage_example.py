#!/usr/bin/env python3
"""
Tushare CYQ 接口使用示例
展示如何使用cyq_chips和cyq_perf接口
"""

import tushare as ts
import os
from datetime import datetime, timedelta


def get_cyq_data_example():
    """
    使用示例：获取筹码分布和筹码胜率数据
    """
    # 从环境变量获取token
    token = os.getenv('TUSHARE_TOKEN')
    
    if not token:
        print("错误: 未找到TUSHARE_TOKEN环境变量")
        print("请确保已设置环境变量或检查配置文件")
        return
    
    # 设置token并初始化API
    ts.set_token(token)
    pro = ts.pro_api()
    
    # 定义股票代码和日期范围
    ts_code = "000001.SZ"  # 平安银行
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
    
    print(f"正在获取 {ts_code} 从 {start_date} 到 {end_date} 的数据...")
    
    # 获取筹码分布数据 (cyq_chips)
    print("\n1. 获取筹码分布数据 (cyq_chips)...")
    try:
        df_chips = pro.cyq_chips(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )
        
        if df_chips is not None and not df_chips.empty:
            print(f"   ✓ 成功获取 {len(df_chips)} 条筹码分布数据")
            print(f"   数据列: {list(df_chips.columns)}")
            print(f"   示例数据:\n{df_chips.head()}")
        else:
            print("   ⚠ 未获取到筹码分布数据")
    except Exception as e:
        print(f"   ✗ 获取筹码分布数据失败: {str(e)}")
    
    # 获取筹码及胜率数据 (cyq_perf)
    print("\n2. 获取筹码及胜率数据 (cyq_perf)...")
    try:
        df_perf = pro.cyq_perf(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )
        
        if df_perf is not None and not df_perf.empty:
            print(f"   ✓ 成功获取 {len(df_perf)} 条筹码及胜率数据")
            print(f"   数据列: {list(df_perf.columns)}")
            print(f"   示例数据:\n{df_perf.head()}")
        else:
            print("   ⚠ 未获取到筹码及胜率数据")
    except Exception as e:
        print(f"   ✗ 获取筹码及胜率数据失败: {str(e)}")


if __name__ == "__main__":
    print("="*60)
    print("Tushare CYQ 接口使用示例")
    print("="*60)
    
    get_cyq_data_example()
    
    print("\n" + "="*60)
    print("示例完成!")
    print("="*60)
    print("\n注意: 要成功运行此示例，您需要:")
    print("1. 有效的Tushare token")
    print("2. 足够的积分权限访问cyq_chips和cyq_perf接口")
    print("3. 网络连接正常")