#!/usr/bin/env python3
"""
生成主键去重 vs 全字段去重对比分析报告
"""

import json
from pathlib import Path
from datetime import datetime

def generate_comparison_report():
    """生成对比分析报告"""
    
    # 读取最新的分析结果
    result_file = Path("/home/quan/testdata/aspipe_v4/p/interface5/redownload_validation/redownload_results_20260221_233601.json")
    
    with open(result_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    report = []
    report.append("=" * 80)
    report.append("主键去重 vs 全字段去重对比分析报告")
    report.append("=" * 80)
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # 总体统计
    total_downloaded = sum(r['downloaded'] for r in results.values())
    total_pk_unique = sum(r['pk_unique'] for r in results.values())
    total_all_fields_unique = sum(r['all_fields_unique'] for r in results.values())
    
    report.append("总体统计:")
    report.append(f"  总下载数据: {total_downloaded} 条")
    report.append(f"  主键去重后: {total_pk_unique} 条")
    report.append(f"  全字段去重后: {total_all_fields_unique} 条")
    report.append(f"  差异: {total_pk_unique - total_all_fields_unique} 条")
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
                'pk_unique': 0,
                'all_fields_unique': 0,
                'difference': 0,
                'periods': []
            }
        interface_summary[interface_name]['downloaded'] += result['downloaded']
        interface_summary[interface_name]['pk_unique'] += result['pk_unique']
        interface_summary[interface_name]['all_fields_unique'] += result['all_fields_unique']
        interface_summary[interface_name]['difference'] += result['difference']
        interface_summary[interface_name]['periods'].append(result['period'])
    
    for interface_name, summary in sorted(interface_summary.items(),
                                        key=lambda x: x[1]['difference'],
                                        reverse=True):
        report.append(f"\n接口: {interface_name}")
        report.append(f"  报告期数: {len(summary['periods'])}")
        report.append(f"  总下载: {summary['downloaded']} 条")
        report.append(f"  主键去重后: {summary['pk_unique']} 条")
        report.append(f"  全字段去重后: {summary['all_fields_unique']} 条")
        report.append(f"  差异: {summary['difference']} 条")
        
        if summary['difference'] > 0:
            report.append(f"  ⚠️  主键去重比全字段去重多去除{summary['difference']}条记录")
            report.append(f"  ⚠️  说明存在主键相同但其他字段不同的记录")
            report.append(f"  ⚠️  主键设置可能不合理！")
        elif summary['difference'] < 0:
            report.append(f"  ℹ️  全字段去重比主键去重多去除{abs(summary['difference'])}条记录")
        else:
            report.append(f"  ✓  两种去重方式结果一致，主键设置合理")
    
    # 详细分析
    report.append("\n" + "=" * 80)
    report.append("详细分析")
    report.append("=" * 80)
    
    for key, result in sorted(results.items(),
                            key=lambda x: x[1]['difference'],
                            reverse=True):
        report.append(f"\n{result['interface_name']} - {result['period']}")
        report.append(f"  下载: {result['downloaded']} 条")
        report.append(f"\n  主键去重:")
        report.append(f"    唯一: {result['pk_unique']} 条")
        report.append(f"    重复: {result['pk_duplicates']} 条")
        if result['downloaded'] > 0:
            report.append(f"    重复率: {result['pk_duplicates']/result['downloaded']*100:.2f}%")
        
        report.append(f"\n  全字段去重:")
        report.append(f"    唯一: {result['all_fields_unique']} 条")
        report.append(f"    重复: {result['all_fields_duplicates']} 条")
        if result['downloaded'] > 0:
            report.append(f"    重复率: {result['all_fields_duplicates']/result['downloaded']*100:.2f}%")
        
        report.append(f"\n  对比结果:")
        report.append(f"    差异: {result['difference']} 条")
        
        if result['difference'] > 0:
            report.append(f"    ⚠️  主键去重比全字段去重多去除{result['difference']}条记录")
            report.append(f"    ⚠️  说明存在主键相同但其他字段不同的记录")
            report.append(f"    ⚠️  主键设置可能不合理！")
        elif result['difference'] < 0:
            report.append(f"    ℹ️  全字段去重比主键去重多去除{abs(result['difference'])}条记录")
        else:
            report.append(f"    ✓  两种去重方式结果一致")
        
        if result['issues']:
            report.append(f"\n  问题:")
            for issue in result['issues']:
                report.append(f"    - {issue}")
    
    # 关键发现
    report.append("\n" + "=" * 80)
    report.append("关键发现")
    report.append("=" * 80)
    
    findings = []
    
    # 检查fina_mainbz_vip
    fina_mainbz_total_diff = sum(
        r['difference'] for r in results.values() 
        if r['interface_name'] == 'fina_mainbz_vip'
    )
    
    if fina_mainbz_total_diff > 0:
        findings.append({
            'level': '严重',
            'issue': 'fina_mainbz_vip接口存在主键相同但其他字段不同的记录',
            'detail': f"主键去重比全字段去重多去除{fina_mainbz_total_diff}条记录"
        })
    
    # 检查balancesheet_vip
    balancesheet_total_diff = sum(
        r['difference'] for r in results.values() 
        if r['interface_name'] == 'balancesheet_vip'
    )
    
    if balancesheet_total_diff > 0:
        findings.append({
            'level': '警告',
            'issue': 'balancesheet_vip接口存在主键相同但其他字段不同的记录',
            'detail': f"主键去重比全字段去重多去除{balancesheet_total_diff}条记录"
        })
    
    # 检查forecast_vip
    forecast_total_diff = sum(
        r['difference'] for r in results.values() 
        if r['interface_name'] == 'forecast_vip'
    )
    
    if forecast_total_diff > 0:
        findings.append({
            'level': '警告',
            'issue': 'forecast_vip接口存在主键相同但其他字段不同的记录',
            'detail': f"主键去重比全字段去重多去除{forecast_total_diff}条记录"
        })
    
    # 输出发现
    for i, finding in enumerate(findings, 1):
        report.append(f"\n{i}. [{finding['level']}] {finding['issue']}")
        report.append(f"   {finding['detail']}")
    
    # 建议
    report.append("\n" + "=" * 80)
    report.append("建议")
    report.append("=" * 80)
    
    suggestions = []
    
    if fina_mainbz_total_diff > 0:
        suggestions.append("1. fina_mainbz_vip接口的主键设置可能不合理，需要重新评估")
        suggestions.append("2. 检查被主键去重但全字段去重保留的记录，分析字段差异")
        suggestions.append("3. 考虑是否需要调整主键，或者采用其他去重策略")
        suggestions.append("4. 对于重要字段（如bz_sales、bz_profit、bz_cost）不同的记录，应该保留")
    
    if balancesheet_total_diff > 0:
        suggestions.append("5. balancesheet_vip接口的主键设置可能需要调整")
        suggestions.append("6. 检查update_flag字段的作用，是否应该包含在主键中")
    
    if forecast_total_diff > 0:
        suggestions.append("7. forecast_vip接口的主键设置可能需要调整")
        suggestions.append("8. 检查type字段是否应该包含在主键中")
    
    suggestions.append("9. 对于所有接口，建议增加更详细的去重日志")
    suggestions.append("10. 考虑在API层面进行去重，减少客户端处理")
    
    for suggestion in suggestions:
        report.append(suggestion)
    
    report.append("\n" + "=" * 80)
    report.append("报告结束")
    report.append("=" * 80)
    
    return "\n".join(report)

if __name__ == "__main__":
    report = generate_comparison_report()
    print(report)
    
    # 保存报告
    output_file = Path("/home/quan/testdata/aspipe_v4/p/interface5/dedup_comparison_report.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n报告已保存到: {output_file}")
