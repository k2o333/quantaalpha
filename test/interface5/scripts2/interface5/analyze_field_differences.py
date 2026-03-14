#!/usr/bin/env python3
"""
分析全字段去重保留的记录与主键去重丢弃的记录之间的字段差异
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple
import polars as pl


def analyze_field_differences(result_file: str) -> Dict[str, Any]:
    """
    分析字段差异

    Args:
        result_file: 结果文件路径

    Returns:
        分析结果
    """
    with open(result_file, 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    analysis = {}
    
    for key, result in results.items():
        interface_name = result['interface_name']
        period = result['period']
        
        if result['difference'] <= 0:
            continue
        
        analysis_key = f"{interface_name}_{period}"
        analysis[analysis_key] = {
            'interface_name': interface_name,
            'period': period,
            'difference': result['difference'],
            'primary_keys': [],
            'field_differences': []
        }
        
        # 获取主键配置
        if interface_name == 'fina_mainbz_vip':
            primary_keys = ['ts_code', 'end_date', 'bz_item']
        elif interface_name == 'balancesheet_vip':
            primary_keys = ['ts_code', 'ann_date', 'end_date', 'update_flag']
        elif interface_name == 'forecast_vip':
            primary_keys = ['ts_code', 'ann_date', 'end_date', 'update_flag']
        else:
            continue
        
        analysis[analysis_key]['primary_keys'] = primary_keys
        
        # 分析被保留的记录
        if 'sample_preserved_records' in result and result['sample_preserved_records']:
            preserved_records = result['sample_preserved_records']
            
            # 按主键分组
            pk_groups = {}
            for record in preserved_records:
                pk_tuple = tuple(record.get(pk) for pk in primary_keys)
                if pk_tuple not in pk_groups:
                    pk_groups[pk_tuple] = []
                pk_groups[pk_tuple].append(record)
            
            # 分析每个主键组的字段差异
            for pk_tuple, records in pk_groups.items():
                if len(records) < 2:
                    continue
                
                # 找出字段差异
                all_fields = set()
                for record in records:
                    all_fields.update(record.keys())
                
                # 排除内部字段
                all_fields = {f for f in all_fields if not f.startswith('_')}
                
                field_diffs = {}
                for field in all_fields:
                    values = set()
                    for record in records:
                        value = record.get(field)
                        if value is not None:
                            values.add(str(value))
                    if len(values) > 1:
                        field_diffs[field] = sorted(list(values))
                
                if field_diffs:
                    analysis[analysis_key]['field_differences'].append({
                        'primary_key': dict(zip(primary_keys, pk_tuple)),
                        'record_count': len(records),
                        'field_differences': field_diffs
                    })
    
    return analysis


def generate_detailed_report(analysis: Dict[str, Any]) -> str:
    """生成详细报告"""
    report = []
    report.append("=" * 80)
    report.append("全字段去重保留记录与主键去重丢弃记录的字段差异分析")
    report.append("=" * 80)
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    for key, data in sorted(analysis.items(),
                            key=lambda x: x[1]['difference'],
                            reverse=True):
        report.append(f"\n{'='*80}")
        report.append(f"{data['interface_name']} - {data['period']}")
        report.append(f"{'='*80}")
        report.append(f"主键: {data['primary_keys']}")
        report.append(f"差异记录数: {data['difference']} 条")
        report.append(f"发现 {len(data['field_differences'])} 组有字段差异的记录")
        
        for i, diff_group in enumerate(data['field_differences'], 1):
            report.append(f"\n--- 差异组 {i} ---")
            report.append(f"主键: {diff_group['primary_key']}")
            report.append(f"记录数: {diff_group['record_count']}")
            report.append(f"字段差异:")
            
            # 按重要性排序字段
            important_fields = ['bz_sales', 'bz_profit', 'bz_cost', 'total_assets', 
                            'total_liab', 'net_profit', 'revenue', 'type',
                            'p_change_min', 'p_change_max', 'net_profit_min', 
                            'net_profit_max', 'total_share', 'update_flag']
            
            sorted_fields = sorted(diff_group['field_differences'].items(),
                               key=lambda x: 0 if x[0] in important_fields else 1)
            
            for field, values in sorted_fields:
                importance = "⚠️ 重要" if field in important_fields else "  普通"
                report.append(f"  {importance} {field}:")
                for value in values:
                    report.append(f"    - {value}")
    
    return "\n".join(report)


def main():
    """主函数"""
    print("=" * 80)
    print("分析全字段去重保留记录与主键去重丢弃记录的字段差异")
    print("=" * 80)
    
    # 读取结果文件
    result_file = "/home/quan/testdata/aspipe_v4/p/interface5/redownload_validation/redownload_results_20260221_233601.json"
    
    # 分析字段差异
    analysis = analyze_field_differences(result_file)
    
    # 生成报告
    report = generate_detailed_report(analysis)
    print(report)
    
    # 保存报告
    output_file = Path("/home/quan/testdata/aspipe_v4/p/interface5/field_differences_report.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n报告已保存到: {output_file}")
    
    # 保存JSON格式的详细数据
    json_output_file = Path("/home/quan/testdata/aspipe_v4/p/interface5/field_differences.json")
    with open(json_output_file, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    print(f"详细数据已保存到: {json_output_file}")


if __name__ == "__main__":
    main()
