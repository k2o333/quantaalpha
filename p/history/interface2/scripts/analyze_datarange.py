#!/usr/bin/env python3
"""分析data range接口测试日志，生成汇总表格"""
import os
import re

OUTPUT_DIR = "/home/quan/testdata/aspipe_v4/p/interface2/output_datarange"

def analyze_log_file(filepath):
    """分析单个日志文件"""
    interface = os.path.basename(filepath).replace('.txt', '')
    
    result = {
        'interface': interface,
        'has_download': False,
        'downloaded_records': 0,
        'has_save': False,
        'saved_records': 0,
        'dedup_input': 0,
        'dedup_removed': 0,
        'dedup_rate': 0.0,
        'all_exist_skipped': False,
        'error_msg': None
    }
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        result['error_msg'] = str(e)
        return result
    
    # 检查是否有数据下载
    download_pattern = rf'Successfully downloaded (\d+) records for {interface}'
    download_match = re.search(download_pattern, content)
    if download_match:
        result['has_download'] = True
        result['downloaded_records'] = int(download_match.group(1))
    
    # 检查是否有数据保存
    save_pattern = rf'Wrote (\d+) records to data/{interface}/'
    save_match = re.search(save_pattern, content)
    if save_match:
        result['has_save'] = True
        result['saved_records'] = int(save_match.group(1))
    
    # 检查去重信息
    dedup_pattern = rf'Deduplication completed for {interface}: input=(\d+), compared=(\d+), output=(\d+), removed=(\d+), dedup_rate=([\d.]+)%'
    dedup_match = re.search(dedup_pattern, content)
    if dedup_match:
        result['has_download'] = True
        result['dedup_input'] = int(dedup_match.group(1))
        result['dedup_removed'] = int(dedup_match.group(4))
        result['dedup_rate'] = float(dedup_match.group(5))
    
    # 检查是否因为全部重复而跳过保存
    all_exist_pattern = rf'All records already exist for {interface}, skipping save'
    all_exist_match = re.search(all_exist_pattern, content)
    if all_exist_match:
        result['all_exist_skipped'] = True
        result['has_download'] = True
    
    return result

def main():
    print("=" * 140)
    print(f"Data Range 接口测试结果汇总 (查询日期: 2026-02-02)")
    print("=" * 140)
    print()
    
    # 表头
    print(f"{'接口名':<22} | {'有下载':<8} | {'下载记录':<10} | {'有保存':<8} | {'保存记录':<10} | {'去重输入':<10} | {'去重移除':<10} | {'去重率':<10} | {'全重复跳过':<10}")
    print("-" * 140)
    
    interfaces = [
        "cyq_perf", "report_rc", "new_share", "stk_surv", "daily_basic",
        "moneyflow_cnt_ths", "cyq_chips", "moneyflow_mkt_dc", "stk_holdertrade",
        "stk_premarket", "daily", "suspend_d", "block_trade", "moneyflow_ind_dc",
        "moneyflow", "repurchase", "share_float", "moneyflow_dc", "stk_managers",
        "stock_hsgt", "moneyflow_ind_ths", "moneyflow_ths", "stock_st", "trade_cal"
    ]
    
    results = []
    for interface in interfaces:
        filepath = os.path.join(OUTPUT_DIR, f"{interface}.txt")
        if os.path.exists(filepath):
            result = analyze_log_file(filepath)
            results.append(result)
        else:
            results.append({
                'interface': interface,
                'error_msg': 'File not found'
            })
    
    for r in results:
        if r.get('error_msg'):
            print(f"{r['interface']:<22} | {'ERROR':<8} | {r['error_msg']:<60}")
            continue
        
        has_download = "✓" if r['has_download'] else "✗"
        has_save = "✓" if r['has_save'] else "✗"
        skipped = "✓" if r['all_exist_skipped'] else "-"
        dedup_rate = f"{r['dedup_rate']:.2f}%" if r['dedup_rate'] > 0 else "-"
        
        print(f"{r['interface']:<22} | {has_download:<8} | {r['downloaded_records']:<10} | {has_save:<8} | {r['saved_records']:<10} | {r['dedup_input']:<10} | {r['dedup_removed']:<10} | {dedup_rate:<10} | {skipped:<10}")
    
    print("-" * 140)
    print()
    
    # 统计汇总
    total = len(interfaces)
    with_download = sum(1 for r in results if r.get('has_download'))
    with_save = sum(1 for r in results if r.get('has_save'))
    skipped_save = sum(1 for r in results if r.get('all_exist_skipped'))
    total_downloaded = sum(r.get('downloaded_records', 0) for r in results)
    total_saved = sum(r.get('saved_records', 0) for r in results)
    total_dedup_removed = sum(r.get('dedup_removed', 0) for r in results)
    
    print("📊 统计汇总:")
    print(f"   总接口数: {total}")
    print(f"   有数据下载: {with_download} 个")
    print(f"   有数据保存: {with_save} 个")
    print(f"   因去重跳过保存: {skipped_save} 个")
    print(f"   总下载记录数: {total_downloaded} 条")
    print(f"   总保存记录数: {total_saved} 条")
    print(f"   总共去重移除记录: {total_dedup_removed} 条")
    print()
    
    # 详细信息
    print("📝 详细信息:")
    for r in results:
        if r.get('has_download') and (r.get('downloaded_records', 0) > 0 or r.get('dedup_input', 0) > 0):
            if r.get('all_exist_skipped'):
                print(f"   - {r['interface']}: 下载{r['downloaded_records'] or r['dedup_input']}条，因全部重复未保存")
            elif r.get('dedup_removed', 0) > 0:
                print(f"   - {r['interface']}: 下载{r['downloaded_records']}条，去重移除{r['dedup_removed']}条，保存{r['saved_records']}条")
            else:
                print(f"   - {r['interface']}: 下载{r['downloaded_records']}条，保存{r['saved_records']}条")
        elif r.get('downloaded_records', 0) == 0 and not r.get('all_exist_skipped'):
            print(f"   - {r['interface']}: 无数据下载")

if __name__ == "__main__":
    main()
