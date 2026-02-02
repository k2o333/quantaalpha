#!/usr/bin/env python3
"""
Tushare CYQ 数据下载测试脚本
用于测试cyq_chips和cyq_perf接口
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, '/home/quan/testdata/aspipe_v4/app4')

from core.config_loader import ConfigLoader


def validate_token():
    """验证token是否有效"""
    try:
        import tushare as ts
        
        # 加载配置
        config_loader = ConfigLoader("/home/quan/testdata/aspipe_v4/app4/config")
        config = config_loader.get_global_config()
        
        token = config['tushare']['token']
        print(f"Token前缀: {token[:10]}..." if len(token) > 10 else f"Token: {token}")
        
        # 尝试初始化API
        ts.set_token(token)
        pro = ts.pro_api()
        
        # 尝试获取基本信息验证token
        df = pro.query('trade_cal', exchange='', start_date='20230101', end_date='20230102')
        if len(df) > 0:
            print("✓ Token 验证成功")
            return pro, token
        else:
            print("✗ Token 验证失败: 无法获取交易日历数据")
            return None, token
            
    except Exception as e:
        print(f"✗ Token 验证失败: {str(e)}")
        return None, None


def test_cyq_chips_data(pro, ts_code="000001.SZ", start_date=None, end_date=None):
    """
    测试下载cyq_chips（每日筹码分布）数据
    
    参数:
    - pro: tushare api对象
    - ts_code: 股票代码
    - start_date: 开始日期 (YYYYMMDD)
    - end_date: 结束日期 (YYYYMMDD)
    """
    try:
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
        
        if df is not None and len(df) > 0:
            print(f"✓ 成功获取 {len(df)} 条筹码分布数据")
            print("数据列:", list(df.columns))
            print("\n前5行数据:")
            print(df.head())
            
            # 保存数据到CSV
            output_file = f"/home/quan/testdata/aspipe_v4/test/cyq/cyq_chips_{ts_code.replace('.', '_')}_{start_date}_{end_date}.csv"
            df.to_csv(output_file, index=False)
            print(f"\n数据已保存到: {output_file}")
        else:
            print("⚠ 未获取到筹码分布数据，可能是数据不存在或权限不足")
        
        return df
        
    except Exception as e:
        print(f"✗ 下载cyq_chips数据时出错: {str(e)}")
        return None


def test_cyq_perf_data(pro, ts_code="000001.SZ", start_date=None, end_date=None):
    """
    测试下载cyq_perf（每日筹码及胜率）数据
    
    参数:
    - pro: tushare api对象
    - ts_code: 股票代码
    - start_date: 开始日期 (YYYYMMDD)
    - end_date: 结束日期 (YYYYMMDD)
    """
    try:
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
        
        if df is not None and len(df) > 0:
            print(f"✓ 成功获取 {len(df)} 条筹码及胜率数据")
            print("数据列:", list(df.columns))
            print("\n前5行数据:")
            print(df.head())
            
            # 保存数据到CSV
            output_file = f"/home/quan/testdata/aspipe_v4/test/cyq/cyq_perf_{ts_code.replace('.', '_')}_{start_date}_{end_date}.csv"
            df.to_csv(output_file, index=False)
            print(f"\n数据已保存到: {output_file}")
        else:
            print("⚠ 未获取到筹码及胜率数据，可能是数据不存在或权限不足")
        
        return df
        
    except Exception as e:
        print(f"✗ 下载cyq_perf数据时出错: {str(e)}")
        return None


def main():
    """主函数，执行测试"""
    print("="*60)
    print("Tushare CYQ 数据下载测试")
    print("="*60)
    
    # 首先验证token
    pro, token = validate_token()
    
    if pro is None:
        print("\n错误: Token验证失败，无法继续测试。请检查:")
        print("1. TUSHARE_TOKEN 是否正确")
        print("2. 账户是否有足够的积分")
        print("3. 网络连接是否正常")
        return
    
    # 测试股票代码
    ts_code = "000001.SZ"  # 平安银行作为示例
    
    print(f"\n测试股票代码: {ts_code}")
    print()
    
    # 测试cyq_chips接口
    print("-" * 40)
    print("测试 cyq_chips (每日筹码分布)")
    print("-" * 40)
    chips_df = test_cyq_chips_data(pro, ts_code=ts_code)
    
    print()
    
    # 测试cyq_perf接口
    print("-" * 40)
    print("测试 cyq_perf (每日筹码及胜率)")
    print("-" * 40)
    perf_df = test_cyq_perf_data(pro, ts_code=ts_code)
    
    print()
    print("="*60)
    print("测试完成!")
    print("="*60)
    
    # 总结
    print("\n总结:")
    if chips_df is not None and len(chips_df) > 0:
        print("- cyq_chips 接口: 正常")
    else:
        print("- cyq_chips 接口: 异常或无数据")
        
    if perf_df is not None and len(perf_df) > 0:
        print("- cyq_perf 接口: 正常")
    else:
        print("- cyq_perf 接口: 异常或无数据")


if __name__ == "__main__":
    main()