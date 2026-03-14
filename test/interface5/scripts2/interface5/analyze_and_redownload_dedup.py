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

# 添加项目路径
project_root = Path(__file__).parent.parent
app4_path = project_root / "app4"
sys.path.insert(0, str(app4_path))

from core.downloader import GenericDownloader
from core.config_loader import ConfigLoader
from core.processor import DataProcessor
from core.storage import StorageManager
from core.schema_manager import SchemaManager


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


class DataReDownloader:
    """数据重新下载器"""

    def __init__(self, config_loader: ConfigLoader):
        self.config_loader = config_loader
        self.downloader = GenericDownloader(config_loader)
        self.processor = DataProcessor()
        self.storage = StorageManager(config_loader)

    def redownload_and_validate(self, interface_name: str, periods: List[str]) -> Dict[str, Any]:
        """
        重新下载并验证数据

        Args:
            interface_name: 接口名称
            periods: 需要重新下载的报告期列表

        Returns:
            验证结果字典
        """
        print(f"\n重新下载接口: {interface_name}")
        print(f"报告期: {periods}")

        interface_config = self.config_loader.get_interface_config(interface_name)
        if not interface_config:
            return {'error': f'接口配置不存在: {interface_name}'}

        results = {
            'interface_name': interface_name,
            'periods': {},
            'total_downloaded': 0,
            'total_saved': 0,
            'total_duplicates': 0,
            'validation_results': {}
        }

        for period in periods:
            print(f"\n  处理报告期: {period}")
            
            try:
                # 下载原始数据
                raw_data = self._download_period_data(interface_config, period)
                
                if not raw_data:
                    results['periods'][period] = {
                        'status': 'no_data',
                        'downloaded': 0,
                        'saved': 0,
                        'duplicates': 0
                    }
                    continue

                downloaded_count = len(raw_data)
                print(f"    下载原始数据: {downloaded_count} 条")

                # 处理数据（包括去重）
                processed_df = self.processor.process_data(raw_data, interface_config)
                
                if processed_df.is_empty():
                    results['periods'][period] = {
                        'status': 'empty_after_processing',
                        'downloaded': downloaded_count,
                        'saved': 0,
                        'duplicates': downloaded_count
                    }
                    continue

                saved_count = len(processed_df)
                duplicate_count = downloaded_count - saved_count
                
                print(f"    处理后保存: {saved_count} 条")
                print(f"    去重: {duplicate_count} 条")

                # 验证去重逻辑
                validation = self._validate_deduplication(
                    raw_data, 
                    processed_df, 
                    interface_config
                )

                results['periods'][period] = {
                    'status': 'success',
                    'downloaded': downloaded_count,
                    'saved': saved_count,
                    'duplicates': duplicate_count,
                    'validation': validation
                }

                results['total_downloaded'] += downloaded_count
                results['total_saved'] += saved_count
                results['total_duplicates'] += duplicate_count
                results['validation_results'][period] = validation

            except Exception as e:
                print(f"    错误: {str(e)}")
                results['periods'][period] = {
                    'status': 'error',
                    'error': str(e)
                }

        return results

    def _download_period_data(self, interface_config: Dict[str, Any], period: str) -> List[Dict[str, Any]]:
        """下载指定报告期的数据"""
        api_name = interface_config['api_name']
        
        # 构建请求参数
        params = {'period': period}
        
        # 添加其他必需参数
        for param_name, param_config in interface_config.get('parameters', {}).items():
            if param_name not in params and param_config.get('required', False):
                # 这里可能需要根据实际情况设置默认值
                pass

        try:
            data = self.downloader.download(api_name, params)
            return data
        except Exception as e:
            print(f"    下载失败: {str(e)}")
            return []

    def _validate_deduplication(self, raw_data: List[Dict[str, Any]], 
                                processed_df: pl.DataFrame,
                                interface_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证去重逻辑是否正确

        Args:
            raw_data: 原始下载数据
            processed_df: 处理后的DataFrame
            interface_config: 接口配置

        Returns:
            验证结果
        """
        validation = {
            'is_valid': True,
            'issues': [],
            'primary_key_analysis': {}
        }

        # 获取主键配置
        primary_keys = interface_config.get('output', {}).get('primary_key', [])

        if not primary_keys:
            validation['is_valid'] = False
            validation['issues'].append('未配置主键')
            return validation

        # 分析原始数据中的主键重复情况
        raw_df = pl.DataFrame(raw_data)
        
        # 统计主键重复
        if primary_keys:
            existing_keys = [key for key in primary_keys if key in raw_df.columns]
            
            if existing_keys:
                # 计算原始数据中的重复数
                raw_count = len(raw_df)
                unique_count = raw_df.unique(subset=existing_keys).height
                raw_duplicates = raw_count - unique_count
                
                # 计算处理后数据的重复数
                processed_count = len(processed_df)
                processed_unique = processed_df.unique(subset=existing_keys).height
                processed_duplicates = processed_count - processed_unique
                
                validation['primary_key_analysis'] = {
                    'primary_keys': existing_keys,
                    'raw_count': raw_count,
                    'raw_unique': unique_count,
                    'raw_duplicates': raw_duplicates,
                    'processed_count': processed_count,
                    'processed_unique': processed_unique,
                    'processed_duplicates': processed_duplicates
                }

                # 验证：处理后数据不应该有重复的主键
                if processed_duplicates > 0:
                    validation['is_valid'] = False
                    validation['issues'].append(
                        f'处理后数据仍有 {processed_duplicates} 条主键重复'
                    )

                # 验证：去重数应该与原始重复数匹配
                expected_duplicates = raw_duplicates
                actual_duplicates = raw_count - processed_count
                
                if actual_duplicates != expected_duplicates:
                    validation['issues'].append(
                        f'去重数量不匹配: 预期 {expected_duplicates}, 实际 {actual_duplicates}'
                    )

                # 检查被去重的记录是否有不同的非主键字段值
                if raw_duplicates > 0:
                    self._analyze_duplicate_records(
                        raw_data, 
                        existing_keys, 
                        validation
                    )

        return validation

    def _analyze_duplicate_records(self, raw_data: List[Dict[str, Any]], 
                                  primary_keys: List[str],
                                  validation: Dict[str, Any]):
        """
        分析被去重的记录，检查是否有重要字段值不同

        Args:
            raw_data: 原始数据
            primary_keys: 主键列表
            validation: 验证结果字典
        """
        df = pl.DataFrame(raw_data)
        
        # 找出有重复主键的记录
        duplicates = df.filter(
            df.is_duplicated(subset=primary_keys)
        )
        
        if len(duplicates) == 0:
            return

        # 按主键分组，检查每组重复记录的字段差异
        grouped = duplicates.group_by(primary_keys).agg(
            pl.all().count().alias('count')
        )
        
        # 获取重复的主键组合
        duplicate_keys = grouped.filter(pl.col('count') > 1).select(primary_keys).to_dicts()

        # 检查每组重复记录的字段差异
        for key_dict in duplicate_keys[:10]:  # 只检查前10组
            filter_expr = pl.all_horizontal(
                [pl.col(key) == value for key, value in key_dict.items()]
            )
            group_records = df.filter(filter_expr)
            
            if len(group_records) > 1:
                # 检查非主键字段是否有差异
                non_key_fields = [col for col in df.columns if col not in primary_keys]
                
                field_diffs = []
                for field in non_key_fields:
                    unique_values = group_records[field].unique()
                    if len(unique_values) > 1:
                        field_diffs.append({
                            'field': field,
                            'values': unique_values.to_list()
                        })

                if field_diffs:
                    validation['issues'].append({
                        'type': 'duplicate_with_different_values',
                        'primary_key': key_dict,
                        'field_differences': field_diffs
                    })

                    # 如果有重要字段（如金额、数量等）不同，标记为严重问题
                    important_fields = ['bz_sales', 'bz_profit', 'bz_cost', 'total_assets', 
                                      'total_liab', 'net_profit', 'revenue']
                    for diff in field_diffs:
                        if diff['field'] in important_fields:
                            validation['is_valid'] = False
                            validation['issues'].append(
                                f'严重问题: 重复记录的重要字段 {diff["field"]} 值不同: {diff["values"]}'
                            )


def main():
    """主函数"""
    print("=" * 80)
    print("接口下载去重问题分析与验证工具")
    print("=" * 80)

    # 配置路径
    log_dir = "/home/quan/testdata/aspipe_v4/p/interface5/outputperiod"
    output_dir = "/home/quan/testdata/aspipe_v4/p/interface5/dedup_validation"

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

    # 2. 如果有去重问题，重新下载验证
    if dedup_issues:
        print("\n步骤2: 重新下载并验证数据")
        
        # 初始化配置加载器
        config_loader = ConfigLoader(config_dir="../app4/config")
        re_downloader = DataReDownloader(config_loader)

        # 对每个有去重问题的接口进行验证
        validation_results = {}
        
        for interface_name, info in dedup_issues.items():
            # 只验证去重比例超过10%的报告期
            periods_to_validate = []
            for period, period_info in info['periods'].items():
                dedup_rate = period_info['duplicates'] / period_info['downloaded'] * 100 if period_info['downloaded'] > 0 else 0
                if dedup_rate > 10:
                    periods_to_validate.append(period)
            
            if periods_to_validate:
                print(f"\n验证接口 {interface_name} 的 {len(periods_to_validate)} 个报告期")
                result = re_downloader.redownload_and_validate(interface_name, periods_to_validate)
                validation_results[interface_name] = result

        # 保存验证结果
        validation_file = Path(output_dir) / f"validation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(validation_file, 'w', encoding='utf-8') as f:
            json.dump(validation_results, f, ensure_ascii=False, indent=2)
        print(f"\n验证结果已保存到: {validation_file}")

        # 生成验证报告
        validation_report = generate_validation_report(validation_results)
        validation_report_file = Path(output_dir) / f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(validation_report_file, 'w', encoding='utf-8') as f:
            f.write(validation_report)
        print(f"验证报告已保存到: {validation_report_file}")
        print("\n" + validation_report)
    else:
        print("\n未发现去重问题，无需重新验证")

    print("\n" + "=" * 80)
    print("分析完成")
    print("=" * 80)


def generate_validation_report(validation_results: Dict[str, Any]) -> str:
    """生成验证报告"""
    report = []
    report.append("=" * 80)
    report.append("去重验证报告")
    report.append("=" * 80)
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    if not validation_results:
        report.append("无验证结果")
        return "\n".join(report)

    for interface_name, result in validation_results.items():
        report.append(f"\n接口: {interface_name}")
        report.append(f"  总下载: {result['total_downloaded']} 条")
        report.append(f"  总保存: {result['total_saved']} 条")
        report.append(f"  总去重: {result['total_duplicates']} 条")
        report.append("")

        for period, period_result in result['periods'].items():
            report.append(f"  报告期 {period}:")
            report.append(f"    状态: {period_result['status']}")
            
            if period_result['status'] == 'success':
                report.append(f"    下载: {period_result['downloaded']} 条")
                report.append(f"    保存: {period_result['saved']} 条")
                report.append(f"    去重: {period_result['duplicates']} 条")
                
                validation = period_result.get('validation', {})
                if validation:
                    report.append(f"    验证结果: {'通过' if validation.get('is_valid', False) else '失败'}")
                    
                    if validation.get('issues'):
                        report.append("    问题:")
                        for issue in validation['issues']:
                            if isinstance(issue, str):
                                report.append(f"      - {issue}")
                            elif isinstance(issue, dict):
                                report.append(f"      - {issue.get('type', '未知问题')}")
                                if 'primary_key' in issue:
                                    report.append(f"        主键: {issue['primary_key']}")
                                if 'field_differences' in issue:
                                    report.append(f"        字段差异:")
                                    for diff in issue['field_differences']:
                                        report.append(f"          {diff['field']}: {diff['values']}")

    return "\n".join(report)


if __name__ == "__main__":
    main()
