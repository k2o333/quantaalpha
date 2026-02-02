#!/usr/bin/env python3
"""
测试脚本：下载Tushare的cyq_chips和cyq_perf数据
使用项目中的配置加载器获取tushare token和代理设置
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, '/home/quan/testdata/aspipe_v4/app4')

from core.config_loader import ConfigLoader


def test_cyq_chips_data(ts_code="000001.SZ", start_date=None, end_date=None):
    """
    测试下载cyq_chips（每日筹码分布）数据

    参数:
    - ts_code: 股票代码
    - start_date: 开始日期 (YYYYMMDD)
    - end_date: 结束日期 (YYYYMMDD)
    """
    try:
        import tushare as ts
        import os

        # 加载配置
        config_loader = ConfigLoader("/home/quan/testdata/aspipe_v4/app4/config")
        config = config_loader.get_global_config()

        # 设置tushare token
        token = config['tushare']['token']
        proxy_url = os.getenv('PROXY_URL', None)  # 从环境变量获取代理URL

        ts.set_token(token)

        pro = ts.pro_api()
        print("Tushare API 初始化完成")

        # 注意：如果需要使用代理，可以在系统级别设置，或通过tushare配置
        if proxy_url:
            print(f"检测到代理设置: {proxy_url}，但tushare可能需要额外配置才能使用代理")
        
        print(f"正在下载 {ts_code} 的筹码分布数据...")
        
        # 设置默认日期范围（最近一个月）
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        
        # 调用cyq_chips接口
        df = pro.cyq_chips(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )
        
        print(f"成功获取 {len(df)} 条筹码分布数据")
        print("数据列:", list(df.columns))
        print("\n前5行数据:")
        print(df.head())
        
        # 保存数据到CSV
        output_file = f"/home/quan/testdata/aspipe_v4/test/cyq/cyq_chips_{ts_code.replace('.', '_')}_{start_date}_{end_date}.csv"
        df.to_csv(output_file, index=False)
        print(f"\n数据已保存到: {output_file}")
        
        return df
        
    except Exception as e:
        print(f"下载cyq_chips数据时出错: {str(e)}")
        return None


def test_cyq_perf_data(ts_code="000001.SZ", start_date=None, end_date=None):
    """
    测试下载cyq_perf（每日筹码及胜率）数据

    参数:
    - ts_code: 股票代码
    - start_date: 开始日期 (YYYYMMDD)
    - end_date: 结束日期 (YYYYMMDD)
    """
    try:
        import tushare as ts
        import os

        # 加载配置
        config_loader = ConfigLoader("/home/quan/testdata/aspipe_v4/app4/config")
        config = config_loader.get_global_config()

        # 设置tushare token
        token = config['tushare']['token']
        proxy_url = os.getenv('PROXY_URL', None)  # 从环境变量获取代理URL

        ts.set_token(token)

        pro = ts.pro_api()
        print("Tushare API 初始化完成")

        # 注意：如果需要使用代理，可以在系统级别设置，或通过tushare配置
        if proxy_url:
            print(f"检测到代理设置: {proxy_url}，但tushare可能需要额外配置才能使用代理")
        
        print(f"正在下载 {ts_code} 的筹码及胜率数据...")
        
        # 设置默认日期范围（最近一个月）
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        
        # 调用cyq_perf接口
        df = pro.cyq_perf(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )
        
        print(f"成功获取 {len(df)} 条筹码及胜率数据")
        print("数据列:", list(df.columns))
        print("\n前5行数据:")
        print(df.head())
        
        # 保存数据到CSV
        output_file = f"/home/quan/testdata/aspipe_v4/test/cyq/cyq_perf_{ts_code.replace('.', '_')}_{start_date}_{end_date}.csv"
        df.to_csv(output_file, index=False)
        print(f"\n数据已保存到: {output_file}")
        
        return df
        
    except Exception as e:
        print(f"下载cyq_perf数据时出错: {str(e)}")
        return None


def main():
    """主函数，执行测试"""
    print("="*60)
    print("Tushare CYQ 数据下载测试")
    print("="*60)
    
    # 测试股票代码
    ts_code = "000001.SZ"  # 平安银行作为示例
    
    print(f"测试股票代码: {ts_code}")
    print()
    
    # 测试cyq_chips接口
    print("-" * 40)
    print("测试 cyq_chips (每日筹码分布)")
    print("-" * 40)
    chips_df = test_cyq_chips_data(ts_code=ts_code)
    
    print()
    
    # 测试cyq_perf接口
    print("-" * 40)
    print("测试 cyq_perf (每日筹码及胜率)")
    print("-" * 40)
    perf_df = test_cyq_perf_data(ts_code=ts_code)
    
    print()
    print("="*60)
    print("测试完成!")
    print("="*60)


if __name__ == "__main__":
    main()