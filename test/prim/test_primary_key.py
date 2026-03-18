#!/usr/bin/env python3
"""
Primary Key有效性验证测试脚本
根据 /home/quan/testdata/aspipe_v4/p/2026-1-30/primary_key_test_plan.md 实现
"""
import os
import sys
import json
import yaml
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd
import polars as pl

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 基础目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
REPORT_DIR = os.path.join(BASE_DIR, 'reports')
CONFIG_DIR = os.path.join(BASE_DIR, '..', '..', 'app4', 'config', 'interfaces')

def load_interface_config(interface_name: str) -> Dict[str, Any]:
    """加载接口配置"""
    config_path = os.path.join(CONFIG_DIR, f"{interface_name}.yaml")
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def test_primary_key_comprehensive(df: pl.DataFrame, primary_key: List[str]) -> Dict[str, Any]:
    """
    全面检查 primary key 的有效性
    
    检查所有非主键字段，不只是预设的某些字段
    
    Args:
        df: 数据DataFrame
        primary_key: 主键字段列表
    
    Returns:
        测试结果字典
    """
    result = {
        'total_records': len(df),
        'primary_key': primary_key,
        'duplicate_groups': 0,
        'problematic_groups': 0,
        'samples': []
    }
    
    if df.is_empty():
        return result
    
    # 检查主键字段是否都存在
    missing_keys = [k for k in primary_key if k not in df.columns]
    if missing_keys:
        result['error'] = f"主键字段不存在: {missing_keys}"
        return result
    
    # 找出重复组（primary key 相同的记录）
    dup_counts = df.group_by(primary_key).len()
    dup_groups = dup_counts.filter(pl.col('len') > 1)
    
    result['duplicate_groups'] = len(dup_groups)
    
    if len(dup_groups) == 0:
        logger.info("  没有发现重复组，主键定义正确")
        return result
    
    logger.info(f"  发现 {len(dup_groups)} 个重复组")
    
    # 获取非主键字段
    non_key_fields = [f for f in df.columns if f not in primary_key]
    
    # 限制检查的重复组数量，避免报告过大
    max_groups_to_check = min(len(dup_groups), 100)
    
    # 检查每个重复组的所有非主键字段
    for i, row in enumerate(dup_groups.head(max_groups_to_check).iter_rows(named=True)):
        # 构建过滤条件
        mask = pl.lit(True)
        pk_values = {}
        for pk_field in primary_key:
            pk_values[pk_field] = row[pk_field]
            mask = mask & (pl.col(pk_field) == row[pk_field])
        
        group = df.filter(mask)
        
        # 检查所有非主键字段
        conflicts = []
        for field in non_key_fields:
            if field not in df.columns:
                continue
                
            # 获取唯一值（排除null）
            unique_values = group[field].drop_nulls().unique().to_list()
            
            # 如果有多个不同值，说明该字段导致数据不同
            if len(unique_values) > 1:
                # 限制显示数量
                display_values = unique_values[:5]
                conflicts.append({
                    'field': field,
                    'values': display_values,
                    'value_count': len(unique_values)
                })
        
        # 如果有任何字段存在冲突，记录问题
        if conflicts:
            result['problematic_groups'] += 1
            
            # 只记录前10个样本
            if len(result['samples']) < 10:
                result['samples'].append({
                    'primary_key_value': pk_values,
                    'record_count': len(group),
                    'conflict_fields': conflicts
                })
    
    return result

def analyze_interface(interface_name: str) -> Dict[str, Any]:
    """分析单个接口的primary key"""
    logger.info(f"\n{'='*60}")
    logger.info(f"分析接口: {interface_name}")
    logger.info(f"{'='*60}")
    
    result = {
        'interface': interface_name,
        'status': 'unknown',
        'details': {}
    }
    
    # 加载配置
    try:
        config = load_interface_config(interface_name)
        primary_key = config.get('output', {}).get('primary_key', [])
        result['primary_key'] = primary_key
        logger.info(f"配置的主键: {primary_key}")
    except Exception as e:
        result['status'] = 'error'
        result['error'] = f"加载配置失败: {e}"
        logger.error(f"加载配置失败: {e}")
        return result
    
    if not primary_key:
        result['status'] = 'error'
        result['error'] = "配置中没有定义primary_key"
        logger.error("配置中没有定义primary_key")
        return result
    
    # 加载数据
    data_file = os.path.join(DATA_DIR, f"{interface_name}.parquet")
    if not os.path.exists(data_file):
        result['status'] = 'no_data'
        result['error'] = f"数据文件不存在: {data_file}"
        logger.warning(f"数据文件不存在: {data_file}")
        return result
    
    try:
        # 尝试用 pandas 读取（因为下载脚本使用 pandas 保存）
        try:
            pdf = pd.read_parquet(data_file)
            df = pl.from_pandas(pdf)
        except:
            # 回退到 polars 读取
            df = pl.read_parquet(data_file)
        logger.info(f"加载数据: {len(df)} 条记录, {len(df.columns)} 个字段")
        
        if df.is_empty():
            result['status'] = 'no_data'
            result['error'] = "数据文件为空"
            logger.warning("数据文件为空")
            return result
        
        # 执行检测
        test_result = test_primary_key_comprehensive(df, primary_key)
        result['details'] = test_result
        
        # 判断状态
        if test_result.get('error'):
            result['status'] = 'error'
        elif test_result['problematic_groups'] > 0:
            result['status'] = 'failed'
            logger.warning(f"  ❌ 发现 {test_result['problematic_groups']} 个问题组")
        elif test_result['duplicate_groups'] > 0:
            result['status'] = 'passed_with_duplicates'
            logger.info(f"  ⚠️ 发现 {test_result['duplicate_groups']} 个重复组，但无字段冲突（正常重复）")
        else:
            result['status'] = 'passed'
            logger.info("  ✅ 主键定义完整，无重复组")
            
    except Exception as e:
        result['status'] = 'error'
        result['error'] = f"分析数据失败: {e}"
        logger.error(f"分析数据失败: {e}")
        import traceback
        logger.debug(traceback.format_exc())
    
    return result

def generate_report(all_results: List[Dict[str, Any]]) -> str:
    """生成测试报告"""
    os.makedirs(REPORT_DIR, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = os.path.join(REPORT_DIR, f'primary_key_test_report_{timestamp}.json')
    
    # 汇总统计
    summary = {
        'total_interfaces': len(all_results),
        'passed': len([r for r in all_results if r['status'] == 'passed']),
        'passed_with_duplicates': len([r for r in all_results if r['status'] == 'passed_with_duplicates']),
        'failed': len([r for r in all_results if r['status'] == 'failed']),
        'error': len([r for r in all_results if r['status'] in ['error', 'no_data']]),
    }
    
    report = {
        'timestamp': timestamp,
        'summary': summary,
        'results': all_results
    }
    
    # 保存JSON报告
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n报告已保存: {report_file}")
    
    # 生成Markdown摘要
    md_file = os.path.join(REPORT_DIR, f'primary_key_test_report_{timestamp}.md')
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write("# Primary Key 有效性验证测试报告\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## 汇总\n\n")
        f.write(f"- 测试接口总数: {summary['total_interfaces']}\n")
        f.write(f"- ✅ 通过 (无重复): {summary['passed']}\n")
        f.write(f"- ⚠️ 通过 (有重复但无冲突): {summary['passed_with_duplicates']}\n")
        f.write(f"- ❌ 失败 (主键不完整): {summary['failed']}\n")
        f.write(f"- ⚠️ 错误/无数据: {summary['error']}\n\n")
        
        # 失败的接口详情
        failed_results = [r for r in all_results if r['status'] == 'failed']
        if failed_results:
            f.write("## 失败的接口详情\n\n")
            for result in failed_results:
                f.write(f"### {result['interface']}\n\n")
                f.write(f"- 当前主键: `{result.get('primary_key', [])}`\n")
                details = result.get('details', {})
                f.write(f"- 总记录数: {details.get('total_records', 0)}\n")
                f.write(f"- 重复组数: {details.get('duplicate_groups', 0)}\n")
                f.write(f"- 问题组数: {details.get('problematic_groups', 0)}\n\n")
                
                samples = details.get('samples', [])
                if samples:
                    f.write("**问题样本:**\n\n")
                    for i, sample in enumerate(samples[:3], 1):
                        f.write(f"样本 {i}:\n")
                        f.write(f"- Primary Key: `{sample['primary_key_value']}`\n")
                        f.write(f"- 记录数: {sample['record_count']}\n")
                        f.write("- 冲突字段:\n")
                        for conflict in sample['conflict_fields'][:5]:
                            f.write(f"  - `{conflict['field']}`: {conflict['values']}\n")
                        f.write("\n")
        
        # 所有接口结果表格
        f.write("## 所有接口结果\n\n")
        f.write("| 接口 | 状态 | 主键 | 总记录 | 重复组 | 问题组 |\n")
        f.write("|------|------|------|--------|--------|--------|\n")
        
        status_icons = {
            'passed': '✅ 通过',
            'passed_with_duplicates': '⚠️ 有重复',
            'failed': '❌ 失败',
            'error': '⚠️ 错误',
            'no_data': '⚠️ 无数据',
            'unknown': '❓ 未知'
        }
        
        for result in all_results:
            status = status_icons.get(result['status'], result['status'])
            pk = ', '.join(result.get('primary_key', []))
            details = result.get('details', {})
            total = details.get('total_records', 0)
            dups = details.get('duplicate_groups', 0)
            probs = details.get('problematic_groups', 0)
            f.write(f"| {result['interface']} | {status} | {pk} | {total} | {dups} | {probs} |\n")
        
        f.write("\n")
        
        # 修复建议
        if failed_results:
            f.write("## 修复建议\n\n")
            f.write("对于失败的接口，根据冲突字段分析，可能需要将以下字段添加到 primary_key 中:\n\n")
            
            for result in failed_results:
                interface = result['interface']
                details = result.get('details', {})
                samples = details.get('samples', [])
                
                # 收集所有冲突字段
                all_conflict_fields = set()
                for sample in samples:
                    for conflict in sample.get('conflict_fields', []):
                        all_conflict_fields.add(conflict['field'])
                
                if all_conflict_fields:
                    f.write(f"**{interface}**: 考虑添加 `{', '.join(sorted(all_conflict_fields))}`\n\n")
    
    logger.info(f"Markdown报告已保存: {md_file}")
    
    return report_file

def run_tests(interfaces: Optional[List[str]] = None):
    """运行所有测试"""
    if interfaces is None:
        # 默认16个测试接口
        interfaces = [
            "balancesheet_vip",
            "cashflow_vip", 
            "disclosure_date",
            "dividend",
            "express_vip",
            "fina_audit",
            "fina_indicator_vip",
            "fina_mainbz_vip",
            "forecast_vip",
            "income_vip",
            "pledge_detail",
            "pledge_stat",
            "stk_factor_pro",
            "stk_rewards",
            "top10_floatholders",
            "top10_holders"
        ]
    
    logger.info(f"开始测试 {len(interfaces)} 个接口的 primary key 有效性")
    logger.info(f"数据目录: {DATA_DIR}")
    
    all_results = []
    for interface_name in interfaces:
        result = analyze_interface(interface_name)
        all_results.append(result)
    
    # 生成报告
    report_file = generate_report(all_results)
    
    # 打印摘要
    logger.info("\n" + "="*60)
    logger.info("测试完成!")
    logger.info("="*60)
    
    summary = {
        'passed': len([r for r in all_results if r['status'] == 'passed']),
        'passed_with_duplicates': len([r for r in all_results if r['status'] == 'passed_with_duplicates']),
        'failed': len([r for r in all_results if r['status'] == 'failed']),
        'error': len([r for r in all_results if r['status'] in ['error', 'no_data']]),
    }
    
    logger.info(f"通过 (无重复): {summary['passed']}")
    logger.info(f"通过 (有重复但无冲突): {summary['passed_with_duplicates']}")
    logger.info(f"失败 (主键不完整): {summary['failed']}")
    logger.info(f"错误/无数据: {summary['error']}")
    
    if summary['failed'] > 0:
        logger.info("\n失败的接口:")
        for result in all_results:
            if result['status'] == 'failed':
                logger.info(f"  - {result['interface']}")
    
    return all_results

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Primary Key有效性验证测试')
    parser.add_argument('--interface', type=str, help='指定单个接口测试')
    parser.add_argument('--data_dir', type=str, help='指定数据目录')
    
    args = parser.parse_args()
    
    if args.data_dir:
        DATA_DIR = args.data_dir
    
    if args.interface:
        run_tests([args.interface])
    else:
        run_tests()
