#!/usr/bin/env python3
"""
分析接口下载去重问题并重新下载验证的脚本

功能：
1. 分析日志文件中的去重情况
2. 重新下载被去重的数据
3. 验证去重逻辑是否正确
"""

import re
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any
import polars as pl
import yaml


class DeduplicationAnalyzer:
    """去重问题分析器"""

    def __init__(self, log_dir: str):
        self.log_dir = Path(log_dir)
        self.dedup_issues = {}

    def parse_log_files(self) -> Dict[str, Any]:
        """解析日志文件，提取去重信息"""
        print(f"解析日志目录: {self.log_dir}")

        for log_file in self.log_dir.glob("*_update_output.txt"):
            print(f"\n处理日志文件: {log_file.name}")
            interface_name = log_file.stem.replace("_update_output", "")
            
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取去重信息
            dedup_info = self._extract_dedup_info(content, interface_name)
            
            if dedup_info['total_duplicates'] > 0:
                self.dedup_issues[interface_name] = dedup_info
                print(f"  发现去重: {dedup_info['total_duplicates']} 条")
                for period, info in dedup_info['periods'].items():
                    print(f"    - {period}: 下载 {info['downloaded']}, 去重 {info['duplicates']}, 保存 {info['saved']}")

        return self.dedup_issues

    def _extract_dedup_info(self, content: str, interface_name: str) -> Dict[str, Any]:
        """从日志内容中提取去重信息"""
        result = {
            'interface_name': interface_name,
            'total_duplicates': 0,
            'total_downloaded': 0,
            'total_saved': 0,
            'periods': {}
        }

        # 提取下载记录数
        downloaded_pattern = r'Downloaded (\d+) records for ' + re.escape(interface_name)
        downloaded_matches = re.findall(downloaded_pattern, content)
        
        # 提取保存记录数
        saved_pattern = r'\[' + re.escape(interface_name) + r'\] Saved (\d+) records for period (\d+)'
        saved_matches = re.findall(saved_pattern, content)
        
        # 提取去重警告
        duplicate_pattern = r'Found (\d+) duplicate records for interface ' + re.escape(interface_name)
        duplicate_matches = re.findall(duplicate_pattern, content)

        # 提取处理后的记录数
        processed_pattern = r'Processed (\d+) records for ' + re.escape(interface_name)
        processed_matches = re.findall(processed_pattern, content)

        # 组织数据
        saved_dict = {period: int(count) for count, period in saved_matches}
        
        # 匹配下载、去重、保存的数据
        idx = 0
        for i, downloaded_count in enumerate(downloaded_matches):
            downloaded_count = int(downloaded_count)
            period = None
            
            # 尝试找到对应的period
            if i < len(saved_matches):
                period = saved_matches[i][1]
            
            duplicate_count = 0
            if idx < len(duplicate_matches):
                duplicate_count = int(duplicate_matches[idx])
                idx += 1
            
            saved_count = saved_dict.get(period, downloaded_count - duplicate_count)
            
            if period:
                result['periods'][period] = {
                    'downloaded': downloaded_count,
                    'duplicates': duplicate_count,
                    'saved': saved_count
                }
                result['total_downloaded'] += downloaded_count
                result['total_duplicates'] += duplicate_count
                result['total_saved'] += saved_count

        return result

    def generate_report(self) -> str:
        """生成分析报告"""
        report = []
        report.append("=" * 80)
        report.append("去重问题分析报告")
        report.append("=" * 80)
        report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        if not self.dedup_issues:
            report.append("未发现去重问题")
            return "\n".join(report)

        report.append(f"发现 {len(self.dedup_issues)} 个接口存在去重问题:")
        report.append("")

        for interface_name, info in sorted(self.dedup_issues.items(), 
                                          key=lambda x: x[1]['total_duplicates'], 
                                          reverse=True):
            report.append(f"\n接口: {interface_name}")
            report.append(f"  总下载: {info['total_downloaded']} 条")
            report.append(f"  总去重: {info['total_duplicates']} 条 ({info['total_duplicates']/info['total_downloaded']*100:.2f}%)")
            report.append(f"  总保存: {info['total_saved']} 条")
            report.append("  各报告期详情:")
            
            for period, period_info in sorted(info['periods'].items()):
                dedup_rate = period_info['duplicates'] / period_info['downloaded'] * 100 if period_info['downloaded'] > 0 else 0
                report.append(f"    {period}: 下载 {period_info['downloaded']}, 去重 {period_info['duplicates']} ({dedup_rate:.2f}%), 保存 {period_info['saved']}")

        return "\n".join(report)


def load_interface_config(config_dir: str, interface_name: str) -> Dict[str, Any]:
    """加载接口配置"""
    config_file = Path(config_dir) / "interfaces" / f"{interface_name}.yaml"
    if not config_file.exists():
        return None
    
    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def analyze_duplicate_records(raw_data: List[Dict[str, Any]], 
                             primary_keys: List[str]) -> Dict[str, Any]:
    """
    分析被去重的记录，检查是否有重要字段值不同

    Args:
        raw_data: 原始数据
        primary_keys: 主键列表

    Returns:
        分析结果
    """
    df = pl.DataFrame(raw_data)
    
    result = {
        'total_records': len(df),
        'unique_records': 0,
        'duplicate_groups': 0,
        'issues': []
    }
    
    if not primary_keys:
        result['issues'].append('未配置主键')
        return result
    
    # 找出存在于DataFrame中的主键
    existing_keys = [key for key in primary_keys if key in df.columns]
    
    if not existing_keys:
        result['issues'].append('主键字段不存在于数据中')
        return result
    
    # 找出有重复主键的记录
    unique_df = df.unique(subset=existing_keys)
    result['unique_records'] = len(unique_df)
    result['duplicate_groups'] = len(df) - len(unique_df)
    
    if result['duplicate_groups'] == 0:
        return result
    
    # 按主键分组，检查每组重复记录的字段差异
    duplicates = df.filter(
        df.is_duplicated(subset=existing_keys)
    )
    
    # 获取重复的主键组合（只检查前20组）
    grouped = duplicates.group_by(existing_keys).agg(
        pl.all().count().alias('count')
    )
    
    duplicate_keys = grouped.filter(pl.col('count') > 1).select(existing_keys).to_dicts()[:20]
    
    # 检查每组重复记录的字段差异
    for key_dict in duplicate_keys:
        filter_expr = pl.all_horizontal(
            [pl.col(key) == value for key, value in key_dict.items()]
        )
        group_records = df.filter(filter_expr)
        
        if len(group_records) > 1:
            # 检查非主键字段是否有差异
            non_key_fields = [col for col in df.columns if col not in existing_keys]
            
            field_diffs = []
            for field in non_key_fields:
                unique_values = group_records[field].unique()
                if len(unique_values) > 1:
                    field_diffs.append({
                        'field': field,
                        'values': unique_values.to_list()
                    })
            
            if field_diffs:
                result['issues'].append({
                    'type': 'duplicate_with_different_values',
                    'primary_key': key_dict,
                    'field_differences': field_diffs
                })
                
                # 如果有重要字段（如金额、数量等）不同，标记为严重问题
                important_fields = ['bz_sales', 'bz_profit', 'bz_cost', 'total_assets', 
                                  'total_liab', 'net_profit', 'revenue', 'total_share',
                                  'total_cur_liab', 'const_materials', 'r_and_d']
                for diff in field_diffs:
                    if diff['field'] in important_fields:
                        result['issues'].append(
                            f'严重问题: 重复记录的重要字段 {diff["field"]} 值不同: {diff["values"]}'
                        )
    
    return result


def main():
    """主函数"""
    print("=" * 80)
    print("接口下载去重问题分析与验证工具")
    print("=" * 80)

    # 配置路径
    log_dir = "/home/quan/testdata/aspipe_v4/p/interface5/outputperiod"
    output_dir = "/home/quan/testdata/aspipe_v4/p/interface5/dedup_validation"
    config_dir = "/home/quan/testdata/aspipe_v4/app4/config"

    # 创建输出目录
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 1. 分析日志文件
    print("\n步骤1: 分析日志文件中的去重情况")
    analyzer = DeduplicationAnalyzer(log_dir)
    dedup_issues = analyzer.parse_log_files()

    # 生成并保存报告
    report = analyzer.generate_report()
    print("\n" + report)
    
    report_file = Path(output_dir) / f"dedup_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n分析报告已保存到: {report_file}")

    # 保存JSON格式的详细数据
    json_file = Path(output_dir) / f"dedup_issues_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(dedup_issues, f, ensure_ascii=False, indent=2)
    print(f"详细数据已保存到: {json_file}")

    # 2. 如果有去重问题，分析重复记录
    if dedup_issues:
        print("\n步骤2: 分析重复记录（需要从已保存的parquet文件中读取）")
        
        analysis_results = {}
        
        for interface_name, info in dedup_issues.items():
            print(f"\n分析接口: {interface_name}")
            
            # 加载接口配置
            interface_config = load_interface_config(config_dir, interface_name)
            if not interface_config:
                print(f"  警告: 无法加载接口配置")
                continue
            
            primary_keys = interface_config.get('output', {}).get('primary_key', [])
            
            # 查找已保存的parquet文件
            data_dir = Path("/home/quan/testdata/aspipe_v4/data") / interface_name
            if not data_dir.exists():
                print(f"  警告: 数据目录不存在: {data_dir}")
                continue
            
            parquet_files = list(data_dir.glob("*.parquet"))
            if not parquet_files:
                print(f"  警告: 未找到parquet文件")
                continue
            
            print(f"  找到 {len(parquet_files)} 个parquet文件")
            
            # 读取所有parquet文件并分析
            all_data = []
            for parquet_file in parquet_files:
                try:
                    df = pl.read_parquet(parquet_file)
                    all_data.extend(df.to_dicts())
                except Exception as e:
                    print(f"  读取文件失败 {parquet_file.name}: {str(e)}")
            
            if not all_data:
                print(f"  警告: 未读取到数据")
                continue
            
            print(f"  总共读取 {len(all_data)} 条记录")
            
            # 分析重复记录
            analysis = analyze_duplicate_records(all_data, primary_keys)
            analysis_results[interface_name] = analysis
            
            print(f"  唯一记录: {analysis['unique_records']}")
            print(f"  重复组数: {analysis['duplicate_groups']}")
            
            if analysis['issues']:
                print(f"  发现 {len(analysis['issues'])} 个问题:")
                for issue in analysis['issues'][:5]:  # 只显示前5个
                    if isinstance(issue, str):
                        print(f"    - {issue}")
                    elif isinstance(issue, dict):
                        print(f"    - {issue.get('type', '未知问题')}")
                        if 'primary_key' in issue:
                            print(f"      主键: {issue['primary_key']}")
                        if 'field_differences' in issue:
                            print(f"      字段差异:")
                            for diff in issue['field_differences'][:3]:
                                print(f"        {diff['field']}: {diff['values']}")
        
        # 保存分析结果
        analysis_file = Path(output_dir) / f"duplicate_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(analysis_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_results, f, ensure_ascii=False, indent=2)
        print(f"\n重复记录分析结果已保存到: {analysis_file}")
        
        # 生成详细报告
        detailed_report = generate_detailed_report(dedup_issues, analysis_results)
        detailed_report_file = Path(output_dir) / f"detailed_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(detailed_report_file, 'w', encoding='utf-8') as f:
            f.write(detailed_report)
        print(f"详细报告已保存到: {detailed_report_file}")
        print("\n" + detailed_report)
    else:
        print("\n未发现去重问题，无需进一步分析")

    print("\n" + "=" * 80)
    print("分析完成")
    print("=" * 80)


def generate_detailed_report(dedup_issues: Dict[str, Any], 
                            analysis_results: Dict[str, Any]) -> str:
    """生成详细报告"""
    report = []
    report.append("=" * 80)
    report.append("去重问题详细分析报告")
    report.append("=" * 80)
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    if not dedup_issues:
        report.append("无去重问题")
        return "\n".join(report)

    for interface_name, info in sorted(dedup_issues.items(), 
                                      key=lambda x: x[1]['total_duplicates'], 
                                      reverse=True):
        report.append(f"\n{'='*80}")
        report.append(f"接口: {interface_name}")
        report.append(f"{'='*80}")
        report.append(f"总下载: {info['total_downloaded']} 条")
        report.append(f"总去重: {info['total_duplicates']} 条 ({info['total_duplicates']/info['total_downloaded']*100:.2f}%)")
        report.append(f"总保存: {info['total_saved']} 条")
        report.append("")

        # 报告期详情
        report.append("各报告期详情:")
        for period, period_info in sorted(info['periods'].items()):
            dedup_rate = period_info['duplicates'] / period_info['downloaded'] * 100 if period_info['downloaded'] > 0 else 0
            report.append(f"  {period}:")
            report.append(f"    下载: {period_info['downloaded']} 条")
            report.append(f"    去重: {period_info['duplicates']} 条 ({dedup_rate:.2f}%)")
            report.append(f"    保存: {period_info['saved']} 条")
        
        # 重复记录分析
        if interface_name in analysis_results:
            analysis = analysis_results[interface_name]
            report.append("")
            report.append("重复记录分析:")
            report.append(f"  唯一记录: {analysis['unique_records']} 条")
            report.append(f"  重复组数: {analysis['duplicate_groups']} 组")
            
            if analysis['issues']:
                report.append("")
                report.append(f"发现 {len(analysis['issues'])} 个问题:")
                for issue in analysis['issues']:
                    if isinstance(issue, str):
                        report.append(f"  - {issue}")
                    elif isinstance(issue, dict):
                        report.append(f"  - {issue.get('type', '未知问题')}")
                        if 'primary_key' in issue:
                            report.append(f"    主键: {issue['primary_key']}")
                        if 'field_differences' in issue:
                            report.append(f"    字段差异:")
                            for diff in issue['field_differences']:
                                report.append(f"      {diff['field']}: {diff['values']}")
            else:
                report.append("")
                report.append("  未发现异常问题")

    return "\n".join(report)


if __name__ == "__main__":
    main()
