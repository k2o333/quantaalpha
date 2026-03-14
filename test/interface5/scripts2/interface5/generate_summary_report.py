#!/usr/bin/env python3
"""
生成去重问题分析总结报告
"""

import json
from pathlib import Path
from datetime import datetime

def generate_summary_report():
    """生成总结报告"""
    
    # 读取分析结果
    result_file = Path("/home/quan/testdata/aspipe_v4/p/interface5/redownload_validation/redownload_results_20260221_231927.json")
    
    with open(result_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    report = []
    report.append("=" * 80)
    report.append("去重问题分析总结报告")
    report.append("=" * 80)
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # 总体统计
    total_downloaded = sum(r['downloaded'] for r in results.values())
    total_unique = sum(r['unique'] for r in results.values())
    total_duplicates = sum(r['duplicates'] for r in results.values())
    
    report.append("总体统计:")
    report.append(f"  总下载数据: {total_downloaded} 条")
    report.append(f"  唯一记录: {total_unique} 条")
    report.append(f"  重复记录: {total_duplicates} 条 ({total_duplicates/total_downloaded*100:.2f}%)")
    report.append("")
    
    # 按接口分析
    report.append("=" * 80)
    report.append("按接口分析")
    report.append("=" * 80)
    
    interface_summary = {}
    for key, result in results.items():
        interface_name = result['interface_name']
        if interface_name not in interface_summary:
            interface_summary[interface_name] = {
                'downloaded': 0,
                'unique': 0,
                'duplicates': 0,
                'periods': []
            }
        interface_summary[interface_name]['downloaded'] += result['downloaded']
        interface_summary[interface_name]['unique'] += result['unique']
        interface_summary[interface_name]['duplicates'] += result['duplicates']
        interface_summary[interface_name]['periods'].append(result['period'])
    
    for interface_name, summary in sorted(interface_summary.items(),
                                        key=lambda x: x[1]['duplicates'],
                                        reverse=True):
        report.append(f"\n接口: {interface_name}")
        report.append(f"  报告期数: {len(summary['periods'])}")
        report.append(f"  总下载: {summary['downloaded']} 条")
        report.append(f"  唯一记录: {summary['unique']} 条")
        report.append(f"  重复记录: {summary['duplicates']} 条")
        
        if summary['downloaded'] > 0:
            dedup_rate = summary['duplicates'] / summary['downloaded'] * 100
            report.append(f"  重复率: {dedup_rate:.2f}%")
        
        # 标记问题接口
        if dedup_rate > 50:
            report.append(f"  ⚠️  严重问题: 重复率超过50%")
        elif dedup_rate > 10:
            report.append(f"  ⚠️  警告: 重复率超过10%")
    
    # 详细分析
    report.append("\n" + "=" * 80)
    report.append("详细分析")
    report.append("=" * 80)
    
    for key, result in sorted(results.items(),
                            key=lambda x: x[1]['duplicates'],
                            reverse=True):
        report.append(f"\n{result['interface_name']} - {result['period']}")
        report.append(f"  下载: {result['downloaded']} 条")
        report.append(f"  唯一: {result['unique']} 条")
        report.append(f"  重复: {result['duplicates']} 条")
        
        if result['downloaded'] > 0:
            dedup_rate = result['duplicates'] / result['downloaded'] * 100
            report.append(f"  重复率: {dedup_rate:.2f}%")
        
        if result['issues']:
            report.append(f"  问题: {len(result['issues'])} 个")
            for issue in result['issues']:
                report.append(f"    - {issue}")
    
    # 关键发现
    report.append("\n" + "=" * 80)
    report.append("关键发现")
    report.append("=" * 80)
    
    findings = []
    
    # 检查fina_mainbz_vip的严重问题
    fina_mainbz_20250630 = results.get('fina_mainbz_vip_20250630')
    if fina_mainbz_20250630:
        if fina_mainbz_20250630['duplicates'] > 8000:
            findings.append({
                'level': '严重',
                'issue': 'fina_mainbz_vip接口20250630报告期API返回数据存在大量重复',
                'detail': f"下载{fina_mainbz_20250630['downloaded']}条，只有{fina_mainbz_20250630['unique']}条唯一记录，重复率{fina_mainbz_20250630['duplicates']/fina_mainbz_20250630['downloaded']*100:.2f}%"
            })
    
    # 检查balancesheet_vip
    balancesheet_20250630 = results.get('balancesheet_vip_20250630')
    if balancesheet_20250630:
        if balancesheet_20250630['duplicates'] > 0:
            findings.append({
                'level': '警告',
                'issue': 'balancesheet_vip接口存在少量重复',
                'detail': f"下载{balancesheet_20250630['downloaded']}条，有{balancesheet_20250630['duplicates']}条重复记录"
            })
    
    # 检查forecast_vip
    forecast_20241231 = results.get('forecast_vip_20241231')
    if forecast_20241231:
        if forecast_20241231['duplicates'] > 0:
            findings.append({
                'level': '信息',
                'issue': 'forecast_vip接口存在少量重复',
                'detail': f"下载{forecast_20241231['downloaded']}条，有{forecast_20241231['duplicates']}条重复记录"
            })
    
    # 检查fina_mainbz_vip的20250331报告期
    fina_mainbz_20250331 = results.get('fina_mainbz_vip_20250331')
    if fina_mainbz_20250331:
        if fina_mainbz_20250331['downloaded'] == 639 and fina_mainbz_20250331['duplicates'] == 0:
            findings.append({
                'level': '异常',
                'issue': 'fina_mainbz_vip接口20250331报告期日志显示去重8851条，但实际下载只有639条',
                'detail': '可能是日志记录错误，或者去重逻辑存在问题'
            })
    
    # 输出发现
    for i, finding in enumerate(findings, 1):
        report.append(f"\n{i}. [{finding['level']}] {finding['issue']}")
        report.append(f"   {finding['detail']}")
    
    # 建议
    report.append("\n" + "=" * 80)
    report.append("建议")
    report.append("=" * 80)
    
    suggestions = [
        "1. 对于fina_mainbz_vip接口，需要调查为什么API会返回大量重复数据",
        "2. 检查API调用参数是否正确，特别是period参数",
        "3. 考虑在API层面进行去重，而不是在客户端",
        "4. 对于重复率高的接口，建议增加日志记录，记录重复记录的详细信息",
        "5. 验证去重逻辑是否正确，特别是主键的定义",
        "6. 检查日志记录是否准确，特别是去重数量的统计",
        "7. 对于fina_mainbz_vip接口，建议重新下载所有报告期的数据，并验证去重结果"
    ]
    
    for suggestion in suggestions:
        report.append(suggestion)
    
    report.append("\n" + "=" * 80)
    report.append("报告结束")
    report.append("=" * 80)
    
    return "\n".join(report)

if __name__ == "__main__":
    report = generate_summary_report()
    print(report)
    
    # 保存报告
    output_file = Path("/home/quan/testdata/aspipe_v4/p/interface5/dedup_summary_report.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n报告已保存到: {output_file}")
