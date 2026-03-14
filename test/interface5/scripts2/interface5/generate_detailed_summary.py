#!/usr/bin/env python3
"""
生成全字段去重保留记录的详细分析总结报告
"""

import json
from pathlib import Path
from datetime import datetime


def generate_summary_report():
    """生成总结报告"""
    
    # 读取分析结果
    result_file = "/home/quan/testdata/aspipe_v4/p/interface5/redownload_validation/redownload_results_20260221_233601.json"
    duplicate_groups_file = "/home/quan/testdata/aspipe_v4/p/interface5/duplicate_groups.json"
    
    with open(result_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    with open(duplicate_groups_file, 'r', encoding='utf-8') as f:
        duplicate_groups = json.load(f)
    
    report = []
    report.append("=" * 80)
    report.append("全字段去重保留记录的详细分析总结报告")
    report.append("=" * 80)
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # 总体统计
    total_diff = sum(r['difference'] for r in results.values())
    total_groups = sum(len(g['duplicate_groups']) for g in duplicate_groups.values())
    
    report.append("总体统计:")
    report.append(f"  主键去重比全字段去重多去除: {total_diff} 条记录")
    report.append(f"  发现同一主键的多个记录组数: {total_groups} 组")
    report.append("")
    
    # 按接口分析
    report.append("=" * 80)
    report.append("按接口详细分析")
    report.append("=" * 80)
    
    for key, result in sorted(results.items(),
                            key=lambda x: x[1]['difference'],
                            reverse=True):
        if result['difference'] <= 0:
            continue
        
        interface_name = result['interface_name']
        period = result['period']
        diff_key = f"{interface_name}_{period}"
        
        report.append(f"\n{'='*80}")
        report.append(f"{interface_name} - {period}")
        report.append(f"{'='*80}")
        report.append(f"差异记录数: {result['difference']} 条")
        report.append(f"主键去重后: {result['pk_unique']} 条")
        report.append(f"全字段去重后: {result['all_fields_unique']} 条")
        
        if diff_key in duplicate_groups:
            groups = duplicate_groups[diff_key]['duplicate_groups']
            if groups:
                report.append(f"\n✗ 发现 {len(groups)} 组同一主键的多个记录")
                report.append("  ⚠️  主键设置存在问题！")
                
                for i, group in enumerate(groups, 1):
                    report.append(f"\n  重复组 {i}:")
                    report.append(f"    主键: {group['primary_key']}")
                    report.append(f"    记录数: {group['record_count']}")
                    
                    # 找出重要字段差异
                    important_fields = ['bz_sales', 'bz_profit', 'bz_cost', 'total_assets', 
                                    'total_liab', 'net_profit', 'revenue', 'type',
                                    'p_change_min', 'p_change_max', 'net_profit_min', 
                                    'net_profit_max', 'total_share', 'update_flag']
                    
                    important_diffs = {k: v for k, v in group['field_differences'].items() 
                                    if k in important_fields}
                    
                    if important_diffs:
                        report.append(f"    重要字段差异:")
                        for field, values in important_diffs.items():
                            report.append(f"      {field}:")
                            for j, value in enumerate(values, 1):
                                report.append(f"        记录{j}: {value}")
            else:
                report.append(f"\n✓ 未发现同一主键的多个记录")
                report.append("  ✓ 主键设置是合理的")
                report.append("  ℹ️  差异来自API返回的完全重复记录")
                report.append("  ℹ️  全字段去重保留的记录是因为它们的全字段值不同")
    
    # 关键发现
    report.append("\n" + "=" * 80)
    report.append("关键发现")
    report.append("=" * 80)
    
    findings = []
    
    # forecast_vip接口的问题
    forecast_key = 'forecast_vip_20241231'
    if forecast_key in duplicate_groups and duplicate_groups[forecast_key]['duplicate_groups']:
        findings.append({
            'level': '严重',
            'issue': 'forecast_vip接口的主键设置不合理',
            'detail': '发现4组同一主键的多个记录，type字段不同（扭亏/续亏/不确定/略增）',
            'recommendation': '将type字段加入主键：[ts_code, ann_date, end_date, update_flag, type]'
        })
    
    # balancesheet_vip接口的问题
    balancesheet_key = 'balancesheet_vip_20250930'
    if balancesheet_key in duplicate_groups and duplicate_groups[balancesheet_key]['duplicate_groups']:
        findings.append({
            'level': '警告',
            'issue': 'balancesheet_vip接口存在微小数据差异',
            'detail': '发现1组同一主键的多个记录，total_assets、total_liab有微小差异',
            'recommendation': '可能是数据更新的结果，建议保留最新版本'
        })
    
    # fina_mainbz_vip接口的情况
    fina_mainbz_key = 'fina_mainbz_vip_20241231'
    if fina_mainbz_key in results and results[fina_mainbz_key]['difference'] > 0:
        if fina_mainbz_key not in duplicate_groups or not duplicate_groups[fina_mainbz_key]['duplicate_groups']:
            findings.append({
                'level': '正常',
                'issue': 'fina_mainbz_vip接口的主键设置合理',
                'detail': '虽然主键去重比全字段去重重除了14条记录，但未发现同一主键的多个记录',
                'recommendation': '差异来自API返回的完全重复记录，主键设置无需调整'
            })
    
    # 输出发现
    for i, finding in enumerate(findings, 1):
        report.append(f"\n{i}. [{finding['level']}] {finding['issue']}")
        report.append(f"   {finding['detail']}")
        report.append(f"   建议: {finding['recommendation']}")
    
    # 具体示例分析
    report.append("\n" + "=" * 80)
    report.append("具体示例分析")
    report.append("=" * 80)
    
    # forecast_vip的示例
    if forecast_key in duplicate_groups and duplicate_groups[forecast_key]['duplicate_groups']:
        report.append("\n【forecast_vip - 20241231】")
        report.append("示例1: 股票600588.SH")
        report.append("  主键: ts_code=600588.SH, ann_date=20250124, end_date=20241231, update_flag=0")
        report.append("  记录1:")
        report.append("    type: 扭亏")
        report.append("    net_profit_min: 172000.0")
        report.append("    net_profit_max: 192000.0")
        report.append("    summary: 预计净利润172000-192000万")
        report.append("  记录2:")
        report.append("    type: 续亏")
        report.append("    net_profit_min: -192000.0")
        report.append("    net_profit_max: -172000.0")
        report.append("    summary: 预计:净利润-192000--172000")
        report.append("  ⚠️  两条记录的type字段完全不同，但主键相同")
        report.append("  ⚠️  主键去重会丢弃其中一条，导致数据丢失")
    
    # balancesheet_vip的示例
    if balancesheet_key in duplicate_groups and duplicate_groups[balancesheet_key]['duplicate_groups']:
        report.append("\n【balancesheet_vip - 20250930】")
        report.append("示例1: 股票874382.BJ")
        report.append("  主键: ts_code=874382.BJ, ann_date=20251030, end_date=20250930, update_flag=1")
        report.append("  记录1:")
        report.append("    total_assets: 1623982591.72")
        report.append("    total_liab: 485595272.05")
        report.append("  记录2:")
        report.append("    total_assets: 1624032908.64")
        report.append("    total_liab: 485537018.2")
        report.append("  ℹ️  两条记录的财务数据有微小差异")
        report.append("  ℹ️  可能是数据更新的结果")
    
    # 建议
    report.append("\n" + "=" * 80)
    report.append("建议")
    report.append("=" * 80)
    
    suggestions = [
        "1. forecast_vip接口：将type字段加入主键",
        "   当前主键: [ts_code, ann_date, end_date, update_flag]",
        "   建议主键: [ts_code, ann_date, end_date, update_flag, type]",
        "",
        "2. balancesheet_vip接口：考虑增加版本字段或时间戳",
        "   当前主键: [ts_code, ann_date, end_date, update_flag]",
        "   建议主键: [ts_code, ann_date, end_date, update_flag] + [版本字段]",
        "   或者采用保留最新版本的策略",
        "",
        "3. fina_mainbz_vip接口：主键设置合理，无需调整",
        "   当前主键: [ts_code, end_date, bz_item]",
        "   差异来自API返回的完全重复记录",
        "",
        "4. 对于所有接口，建议增加更详细的去重日志",
        "   记录被去重的记录详情",
        "   记录去重的原因（主键重复/全字段重复）",
        "",
        "5. 考虑在API层面进行去重，减少客户端处理",
        "",
        "6. 对于重要字段不同的记录，不应该简单去重",
        "   考虑采用保留所有版本或保留最新版本的策略",
        "",
        "7. 定期检查API返回的数据质量",
        "   监控重复率",
        "   监控主键相同但其他字段不同的情况"
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
    output_file = Path("/home/quan/testdata/aspipe_v4/p/interface5/detailed_analysis_summary.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n报告已保存到: {output_file}")
