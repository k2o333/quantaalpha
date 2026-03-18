#!/usr/bin/env python3
"""
重新下载并验证去重问题的脚本

针对 fina_mainbz_vip 接口的去重问题进行深入分析
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import polars as pl
import yaml

# 添加app4目录到Python路径
app4_dir = Path(__file__).parent.parent / "app4"
sys.path.insert(0, str(app4_dir))

from core.config_loader import ConfigLoader
from core.downloader import GenericDownloader
from core.processor import DataProcessor
from core.schema_manager import SchemaManager


def analyze_deduplication_with_all_fields(raw_df: pl.DataFrame, 
                                          primary_keys: List[str]) -> Dict[str, Any]:
    """
    使用所有字段进行去重，并与主键去重结果对比

    Args:
        raw_df: 原始数据DataFrame
        primary_keys: 主键列表

    Returns:
        分析结果
    """
    result = {
        'total_records': len(raw_df),
        'pk_unique': 0,
        'pk_duplicates': 0,
        'all_fields_unique': 0,
        'all_fields_duplicates': 0,
        'difference': 0,
        'issues': []
    }
    
    # 使用主键去重
    if primary_keys:
        existing_keys = [key for key in primary_keys if key in raw_df.columns]
        if existing_keys:
            pk_unique_df = raw_df.unique(subset=existing_keys)
            result['pk_unique'] = len(pk_unique_df)
            result['pk_duplicates'] = result['total_records'] - result['pk_unique']
    
    # 使用所有字段去重
    all_fields_unique_df = raw_df.unique()
    result['all_fields_unique'] = len(all_fields_unique_df)
    result['all_fields_duplicates'] = result['total_records'] - result['all_fields_unique']
    
    # 计算差异
    result['difference'] = result['pk_duplicates'] - result['all_fields_duplicates']
    
    # 分析差异原因
    if result['difference'] > 0:
        result['issues'].append(
            f"主键去重比全字段去重多去除了{result['difference']}条记录"
        )
        result['issues'].append(
            "说明存在主键相同但其他字段不同的记录"
        )
        
        # 找出这些记录
        if primary_keys:
            existing_keys = [key for key in primary_keys if key in raw_df.columns]
            if existing_keys:
                # 标记主键重复但全字段不重复的记录
                df_with_pk_dup = raw_df.with_columns(
                    pl.struct(existing_keys).alias('_pk')
                )
                df_with_pk_dup = df_with_pk_dup.with_columns(
                    pl.col('_pk').is_duplicated().alias('_is_pk_dup')
                )
                
                # 找出主键重复的记录
                pk_dup_records = df_with_pk_dup.filter(pl.col('_is_pk_dup'))
                
                # 检查这些记录在全字段去重后是否还存在
                all_fields_unique_hashes = set()
                for row in all_fields_unique_df.to_dicts():
                    # 使用所有字段创建hash
                    row_tuple = tuple(str(row.get(col, '')) for col in raw_df.columns)
                    all_fields_unique_hashes.add(hash(row_tuple))
                
                # 找出被主键去重但全字段去重保留的记录
                preserved_records = []
                for row_dict in pk_dup_records.to_dicts()[:20]:  # 只检查前20条
                    row_tuple = tuple(str(row_dict.get(col, '')) for col in raw_df.columns)
                    if hash(row_tuple) in all_fields_unique_hashes:
                        preserved_records.append(row_dict)
                
                if preserved_records:
                    result['sample_preserved_records'] = preserved_records
                    result['issues'].append(
                        f"找到{len(preserved_records)}条被主键去重但全字段去重会保留的记录"
                    )
    
    elif result['difference'] < 0:
        result['issues'].append(
            f"全字段去重比主键去重多去除了{abs(result['difference'])}条记录"
        )
        result['issues'].append(
            "说明存在主键不同但其他字段完全相同的记录"
        )
    
    return result


def download_and_analyze(interface_name: str, period: str, 
                        config_loader: ConfigLoader) -> Dict[str, Any]:
    """
    下载并分析指定接口和报告期的数据

    Args:
        interface_name: 接口名称
        period: 报告期
        config_loader: 配置加载器

    Returns:
        分析结果
    """
    print(f"\n{'='*80}")
    print(f"分析接口: {interface_name}, 报告期: {period}")
    print(f"{'='*80}")

    result = {
        'interface_name': interface_name,
        'period': period,
        'downloaded': 0,
        'pk_unique': 0,
        'pk_duplicates': 0,
        'all_fields_unique': 0,
        'all_fields_duplicates': 0,
        'difference': 0,
        'issues': [],
        'sample_duplicates': [],
        'sample_preserved_records': []
    }

    try:
        # 获取接口配置
        interface_config = config_loader.get_interface_config(interface_name)
        if not interface_config:
            result['issues'].append(f'接口配置不存在: {interface_name}')
            return result

        primary_keys = interface_config.get('output', {}).get('primary_key', [])
        print(f"主键: {primary_keys}")

        # 创建下载器
        downloader = GenericDownloader(config_loader)

        # 下载数据
        print(f"\n开始下载数据...")
        params = {'period': period}
        raw_data = downloader.download(interface_name, params)

        if not raw_data:
            result['issues'].append('下载失败或无数据')
            return result

        result['downloaded'] = len(raw_data)
        print(f"下载原始数据: {result['downloaded']} 条")

        # 转换为DataFrame进行分析
        try:
            raw_df = pl.DataFrame(raw_data, infer_schema_length=10000)
        except Exception as e:
            print(f"使用默认schema推断: {str(e)}")
            raw_df = pl.DataFrame(raw_data)
        print(f"原始数据字段: {raw_df.columns}")

        # 使用全字段去重对比分析
        print(f"\n开始对比主键去重和全字段去重...")
        dedup_comparison = analyze_deduplication_with_all_fields(raw_df, primary_keys)
        
        result.update(dedup_comparison)
        
        # 输出对比结果
        print(f"\n{'='*60}")
        print(f"去重对比结果:")
        print(f"{'='*60}")
        print(f"总记录数: {dedup_comparison['total_records']} 条")
        print(f"\n主键去重:")
        print(f"  唯一记录: {dedup_comparison['pk_unique']} 条")
        print(f"  重复记录: {dedup_comparison['pk_duplicates']} 条")
        print(f"  重复率: {dedup_comparison['pk_duplicates']/dedup_comparison['total_records']*100:.2f}%")
        print(f"\n全字段去重:")
        print(f"  唯一记录: {dedup_comparison['all_fields_unique']} 条")
        print(f"  重复记录: {dedup_comparison['all_fields_duplicates']} 条")
        print(f"  重复率: {dedup_comparison['all_fields_duplicates']/dedup_comparison['total_records']*100:.2f}%")
        print(f"\n差异:")
        print(f"  主键去重多去除: {dedup_comparison['difference']} 条")
        
        if dedup_comparison['difference'] > 0:
            print(f"  ⚠️  说明存在主键相同但其他字段不同的记录")
        elif dedup_comparison['difference'] < 0:
            print(f"  ℹ️  说明存在主键不同但其他字段完全相同的记录")
        else:
            print(f"  ✓  两种去重方式结果一致")
        
        if dedup_comparison['issues']:
            print(f"\n问题:")
            for issue in dedup_comparison['issues']:
                print(f"  - {issue}")
        
        # 如果有被主键去重但全字段去重保留的记录，显示示例
        if 'sample_preserved_records' in dedup_comparison and dedup_comparison['sample_preserved_records']:
            print(f"\n被主键去重但全字段去重保留的记录示例 (前3条):")
            for i, record in enumerate(dedup_comparison['sample_preserved_records'][:3], 1):
                print(f"\n  示例 {i}:")
                for key, value in record.items():
                    print(f"    {key}: {value}")

    except Exception as e:
        result['issues'].append(f'处理过程中发生错误: {str(e)}')
        import traceback
        traceback.print_exc()

    return result


def main():
    """主函数"""
    print("=" * 80)
    print("重新下载并验证去重问题")
    print("=" * 80)

    # 配置
    config_dir = "/home/quan/testdata/aspipe_v4/app4/config"
    output_dir = "/home/quan/testdata/aspipe_v4/p/interface5/redownload_validation"

    # 创建输出目录
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 初始化配置加载器
    config_loader = ConfigLoader(config_dir=config_dir)

    # 分析有去重问题的接口和报告期
    test_cases = [
        ('fina_mainbz_vip', '20250630'),  # 最严重的去重问题
        ('fina_mainbz_vip', '20250331'),
        ('fina_mainbz_vip', '20241231'),
        ('balancesheet_vip', '20250630'),
        ('balancesheet_vip', '20250930'),
        ('forecast_vip', '20241231'),
    ]

    all_results = {}

    for interface_name, period in test_cases:
        result = download_and_analyze(interface_name, period, config_loader)
        all_results[f"{interface_name}_{period}"] = result

    # 保存结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    result_file = Path(output_dir) / f"redownload_results_{timestamp}.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {result_file}")

    # 生成报告
    report = generate_redownload_report(all_results)
    report_file = Path(output_dir) / f"redownload_report_{timestamp}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"报告已保存到: {report_file}")
    print("\n" + report)

    print("\n" + "=" * 80)
    print("分析完成")
    print("=" * 80)


def generate_redownload_report(results: Dict[str, Any]) -> str:
    """生成重新下载报告"""
    report = []
    report.append("=" * 80)
    report.append("重新下载验证报告（主键去重 vs 全字段去重）")
    report.append("=" * 80)
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    for key, result in results.items():
        report.append(f"\n{'='*80}")
        report.append(f"{result['interface_name']} - {result['period']}")
        report.append(f"{'='*80}")
        report.append(f"下载记录: {result['downloaded']} 条")
        
        # 主键去重结果
        report.append(f"\n主键去重:")
        report.append(f"  唯一记录: {result['pk_unique']} 条")
        report.append(f"  重复记录: {result['pk_duplicates']} 条")
        
        if result['downloaded'] > 0:
            pk_dedup_rate = result['pk_duplicates'] / result['downloaded'] * 100
            report.append(f"  重复率: {pk_dedup_rate:.2f}%")
        
        # 全字段去重结果
        report.append(f"\n全字段去重:")
        report.append(f"  唯一记录: {result['all_fields_unique']} 条")
        report.append(f"  重复记录: {result['all_fields_duplicates']} 条")
        
        if result['downloaded'] > 0:
            all_fields_dedup_rate = result['all_fields_duplicates'] / result['downloaded'] * 100
            report.append(f"  重复率: {all_fields_dedup_rate:.2f}%")
        
        # 对比结果
        report.append(f"\n对比结果:")
        report.append(f"  主键去重多去除: {result['difference']} 条")
        
        if result['difference'] > 0:
            report.append(f"  ⚠️  说明存在主键相同但其他字段不同的记录")
            report.append(f"  ⚠️  主键设置可能不合理！")
        elif result['difference'] < 0:
            report.append(f"  ℹ️  说明存在主键不同但其他字段完全相同的记录")
        else:
            report.append(f"  ✓  两种去重方式结果一致")

        # 问题列表
        if result['issues']:
            report.append(f"\n发现 {len(result['issues'])} 个问题:")
            for issue in result['issues']:
                report.append(f"  - {issue}")
        else:
            report.append("\n未发现问题")

        # 被主键去重但全字段去重保留的记录示例
        if 'sample_preserved_records' in result and result['sample_preserved_records']:
            report.append(f"\n被主键去重但全字段去重保留的记录示例 (前3条):")
            for i, record in enumerate(result['sample_preserved_records'][:3], 1):
                report.append(f"\n  示例 {i}:")
                for key, value in record.items():
                    report.append(f"    {key}: {value}")

    return "\n".join(report)


if __name__ == "__main__":
    main()
