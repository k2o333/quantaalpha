"""
验证优化计划的实现情况
验证以下几点：
1. top10_holders 和 top10_floatholders 的全股票批量下载方法是否存在
2. 研究数据优化 (report_rc, stk_surv, broker_recommend) 是否已实现
3. 日期范围功能是否充分利用
"""
import inspect
import sys
import os
import pandas as pd

# 将app目录添加到路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from tushare_api import TuShareDownloader
from score_based_downloader import ScoreBasedDownloader


def check_holder_bulk_download_methods():
    """
    检查股东数据批量下载方法是否存在
    """
    print("🔍 验证股东数据批量下载方法...")
    
    downloader = TuShareDownloader()
    
    # 检查是否存在批量下载所有股票的方法
    methods_to_check = [
        'download_top10_holders_for_all_stocks',
        'download_top10_floatholders_for_all_stocks'
    ]
    
    missing_methods = []
    existing_methods = []
    
    for method_name in methods_to_check:
        if hasattr(downloader, method_name):
            existing_methods.append(method_name)
            print(f"  ✅ {method_name} 存在")
        else:
            missing_methods.append(method_name)
            print(f"  ❌ {method_name} 不存在")
    
    # 检查是否只有单股票下载方法
    if hasattr(downloader, 'download_top10_holders'):
        print(f"  ⚠️  仅有单股票下载方法: download_top10_holders")
    
    if hasattr(downloader, 'download_top10_floatholders'):
        print(f"  ⚠️  仅有单股票下载方法: download_top10_floatholders")
    
    print(f"  总结: 找到 {len(existing_methods)} 个批量下载方法, {len(missing_methods)} 个缺失")
    return missing_methods


def check_research_data_optimization():
    """
    检查研究数据优化是否已实现
    """
    print("\n🔍 验证研究数据优化方法...")
    
    downloader = TuShareDownloader()
    
    # 检查研究数据批量下载方法
    methods_to_check = [
        'download_report_rc_for_all_stocks',
        'download_stk_surv_for_all_stocks',
        'download_report_rc_with_pagination',
        'download_stk_surv_with_pagination'
    ]
    
    missing_methods = []
    existing_methods = []
    
    for method_name in methods_to_check:
        if hasattr(downloader, method_name):
            existing_methods.append(method_name)
            print(f"  ✅ {method_name} 存在")
        else:
            missing_methods.append(method_name)
            print(f"  ❌ {method_name} 不存在")
    
    # 检查分页下载方法
    paginated_methods = [
        'download_report_rc_paginated',
        'download_stk_surv_paginated'
    ]
    
    for method_name in paginated_methods:
        if hasattr(downloader, method_name):
            existing_methods.append(method_name)
            print(f"  ✅ {method_name} 存在 (分页下载)")
        else:
            missing_methods.append(method_name)
            print(f"  ❌ {method_name} 不存在 (分页下载)")
    
    # 检查券商推荐的日期范围方法
    broker_methods = [
        'download_broker_recommend_date_range',
        'download_broker_recommend_with_date_range'
    ]
    
    for method_name in broker_methods:
        if hasattr(downloader, method_name):
            existing_methods.append(method_name)
            print(f"  ✅ {method_name} 存在")
        else:
            missing_methods.append(method_name)
            print(f"  ❌ {method_name} 不存在")
    
    print(f"  总结: 找到 {len(existing_methods)} 个研究数据优化方法, {len(missing_methods)} 个缺失")
    return missing_methods


def check_date_range_functionality():
    """
    检查日期范围功能是否充分利用
    """
    print("\n🔍 验证日期范围功能的使用情况...")
    
    downloader = TuShareDownloader()
    
    # 检查是否有大量数据接口支持日期范围
    date_range_methods = [
        'download_daily_data',           # 已支持日期范围
        'download_daily_moneyflow_range', # 已支持日期范围
        'download_new_share',            # 已支持日期范围
        'download_trade_cal',            # 已支持日期范围
        'download_cyq_chips_with_date_range', # 已支持日期范围
        'download_namechange_with_period_split' # 已支持日期范围
    ]
    
    supported_methods = []
    unsupported_methods = []
    
    for method_name in date_range_methods:
        if hasattr(downloader, method_name):
            supported_methods.append(method_name)
            print(f"  ✅ {method_name} 支持日期范围")
        else:
            unsupported_methods.append(method_name)
            print(f"  ❌ {method_name} 不支持日期范围")
    
    # 检查一些可能应该支持日期范围但没有支持的接口
    other_methods_to_check = [
        'download_report_rc',
        'download_stk_surv', 
        'download_forecast',
        'download_express',
        'download_dividend'
    ]
    
    print("\n  检查其他可能需要日期范围支持的方法:")
    for method_name in other_methods_to_check:
        if hasattr(downloader, method_name):
            sig = inspect.signature(getattr(downloader, method_name))
            params = list(sig.parameters.keys())
            if 'start_date' in params and 'end_date' in params:
                print(f"    ✅ {method_name} 已支持日期范围参数")
                supported_methods.append(method_name)
            else:
                print(f"    ⚠️  {method_name} 不支持日期范围参数")
                unsupported_methods.append(method_name)
    
    print(f"  总结: {len(supported_methods)} 个方法支持日期范围, {len(unsupported_methods)} 个方法不支持")
    return unsupported_methods


def validate_bulk_download_capabilities():
    """
    验证批量下载能力
    """
    print("\n🔍 验证批量下载能力...")
    
    downloader = TuShareDownloader()
    
    # 检查是否实现了循环遍历所有股票下载数据的功能
    all_stock_methods = [
        'download_cyq_chips_for_all_stocks',  # 已实现
        'download_top10_holders_for_all_stocks',  # 缺失
        'download_top10_floatholders_for_all_stocks',  # 缺失
        'download_report_rc_for_all_stocks',  # 缺失
        'download_stk_surv_for_all_stocks'  # 缺失
    ]
    
    implemented = []
    missing = []
    
    for method_name in all_stock_methods:
        if hasattr(downloader, method_name):
            implemented.append(method_name)
            print(f"  ✅ {method_name} 已实现")
        else:
            missing.append(method_name)
            print(f"  ❌ {method_name} 缺失")
    
    print(f"  批量下载能力: {len(implemented)} 个已实现, {len(missing)} 个缺失")
    return missing


def run_validation():
    """
    运行完整验证
    """
    print("="*60)
    print("AsPipe v4 下载优化计划实现情况验证")
    print("="*60)
    
    missing_holder_methods = check_holder_bulk_download_methods()
    missing_research_methods = check_research_data_optimization()
    unsupported_date_range = check_date_range_functionality()
    missing_bulk_download = validate_bulk_download_capabilities()
    
    print("\n" + "="*60)
    print("验证结果总结:")
    print("="*60)
    
    total_missing = len(missing_holder_methods) + len(missing_research_methods) + \
                   len(unsupported_date_range) + len(missing_bulk_download)
    
    print(f"🔍 发现 {total_missing} 个需要改进的地方:")
    
    if missing_holder_methods:
        print(f"\n1. 股东数据批量下载缺失: {len(missing_holder_methods)} 个")
        for method in missing_holder_methods:
            print(f"   - {method}")
    
    if missing_research_methods:
        print(f"\n2. 研究数据优化缺失: {len(missing_research_methods)} 个")
        for method in missing_research_methods:
            print(f"   - {method}")
    
    if unsupported_date_range:
        print(f"\n3. 日期范围功能未充分利用: {len(unsupported_date_range)} 个接口")
        for method in unsupported_date_range:
            print(f"   - {method}")
    
    if missing_bulk_download:
        print(f"\n4. 批量下载能力缺失: {len(missing_bulk_download)} 个")
        for method in missing_bulk_download:
            print(f"   - {method}")
    
    print(f"\n📊 当前实现状态: {total_missing} 个优化点待实现")
    
    if total_missing == 0:
        print("\n🎉 所有优化计划已实现!")
    else:
        print(f"\n💡 建议: 需要实现缺失的批量下载和优化功能")
    
    return {
        'missing_holder_methods': missing_holder_methods,
        'missing_research_methods': missing_research_methods,
        'unsupported_date_range': unsupported_date_range,
        'missing_bulk_download': missing_bulk_download,
        'total_missing': total_missing
    }


def demonstrate_current_vs_optimized():
    """
    展示当前实现与优化后的对比
    """
    print("\n" + "="*60)
    print("当前实现 vs 优化后实现 对比演示")
    print("="*60)
    
    downloader = TuShareDownloader()
    
    print("\n📋 当前实现 (单股票下载):")
    print("  - download_top10_holders(ts_code, period) - 只能下载单个股票")
    print("  - download_top10_floatholders(ts_code, period) - 只能下载单个股票")
    print("  - 需要手动循环遍历股票列表")
    print("  - API调用次数多，效率较低")
    
    print("\n🚀 优化后实现 (批量下载):")
    print("  - download_top10_holders_for_all_stocks(period) - 下载所有股票")
    print("  - download_top10_floatholders_for_all_stocks(period) - 下载所有股票")
    print("  - 内置股票列表遍历，自动处理分页")
    print("  - API调用优化，效率更高")
    
    print("\n📈 数据量对比:")
    print("  - 当前: 每个股票少量数据，总数据量有限")
    print("  - 优化后: 全市场数据，数据量显著增加")


if __name__ == "__main__":
    results = run_validation()
    demonstrate_current_vs_optimized()