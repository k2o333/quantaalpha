#!/usr/bin/env python3
"""
测试脚本：验证 report_rc 接口的去重逻辑
对比：
1. 正常下载（带去重）
2. 下载全部数据（不去重）
3. 验证去重是否按照配置的4个主键进行

主键配置（来自 report_rc.yaml）：
- ts_code      # 股票代码
- report_date  # 报告日期
- org_name     # 机构名称
- report_title # 报告标题
"""

import polars as pl
import yaml
import logging
from datetime import datetime
from pathlib import Path
import sys
import os
import requests
import time

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 加载环境变量
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)

from core.processor import DataProcessor
from core.schema_manager import SchemaManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_interface_config(interface_name: str) -> dict:
    """加载接口配置"""
    config_path = Path(__file__).parent / "config" / "interfaces" / f"{interface_name}.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def call_tushare_api(api_name: str, params: dict) -> list:
    """直接调用TuShare API"""
    token = os.getenv('TUSHARE_TOKEN')
    if not token:
        raise RuntimeError("TUSHARE_TOKEN not found in environment")
    
    url = "http://api.tushare.pro"
    headers = {'Content-Type': 'application/json'}
    
    payload = {
        'api_name': api_name,
        'token': token,
        'params': params,
        'fields': ''
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data.get('code') != 0:
            logger.error(f"API error: {data.get('msg')}")
            return []
        
        fields = data['data'].get('fields', [])
        items = data['data'].get('items', [])
        
        # 转换为字典列表
        result = []
        for item in items:
            record = dict(zip(fields, item))
            result.append(record)
        
        return result
    except Exception as e:
        logger.error(f"API call failed: {e}")
        return []


def download_report_rc_data(start_date: str, end_date: str = None) -> list:
    """
    下载report_rc数据（分页模式）
    """
    all_data = []
    
    # 生成日期范围（按天分页）
    from datetime import datetime, timedelta
    
    start_dt = datetime.strptime(start_date, '%Y%m%d')
    if end_date:
        end_dt = datetime.strptime(end_date, '%Y%m%d')
    else:
        end_dt = datetime.now()
    
    current_dt = start_dt
    
    while current_dt <= end_dt:
        date_str = current_dt.strftime('%Y%m%d')
        params = {'report_date': date_str}
        
        data = call_tushare_api('report_rc', params)
        
        if data:
            all_data.extend(data)
            logger.info(f"  {date_str}: 下载 {len(data)} 条记录")
        
        current_dt += timedelta(days=1)
        
        # 检查是否需要停止（连续空数据阈值）
        # 这里简化处理，实际应该跟踪连续空天数
        
        # 限速
        time.sleep(0.5)
    
    return all_data


def process_with_dedup(data: list, interface_config: dict) -> pl.DataFrame:
    """使用完整处理流程（包含去重）"""
    processor = DataProcessor()
    return processor.process_data(data, interface_config)


def process_without_dedup(data: list, interface_name: str) -> pl.DataFrame:
    """仅创建DataFrame，不做去重处理"""
    df = SchemaManager.create_dataframe_safe(data, interface_name)
    
    if not df.is_empty():
        df.columns = [str(col) for col in df.columns]
        df = df.select([col for i, col in enumerate(df.columns) if col not in df.columns[:i]])
    
    return df


def manual_dedup_by_keys(df: pl.DataFrame, primary_keys: list) -> pl.DataFrame:
    """
    手动按照指定主键去重
    用于验证去重逻辑
    """
    if df.is_empty():
        return df

    # 检查主键是否都存在于DataFrame中
    existing_keys = [key for key in primary_keys if key in df.columns]
    missing_keys = [key for key in primary_keys if key not in df.columns]

    if missing_keys:
        logger.warning(f"缺少主键字段: {missing_keys}")

    if not existing_keys:
        logger.warning("没有有效的主键字段，无法进行去重")
        return df

    logger.info(f"使用主键去重: {existing_keys}")

    original_count = len(df)

    # 先过滤掉主键为空的记录
    conditions = []
    for key in existing_keys:
        conditions.append(pl.col(key).is_not_null())

    if conditions:
        df = df.filter(pl.all_horizontal(conditions))
        null_filtered = original_count - len(df)
        if null_filtered > 0:
            logger.info(f"  过滤主键空值: {null_filtered} 条")

    # 按主键去重，保留最后一条
    before_dedup = len(df)
    df = df.unique(subset=existing_keys, keep='last')
    after_dedup = len(df)

    logger.info(f"  按主键去重: {before_dedup - after_dedup} 条重复记录被移除")

    return df


def analyze_duplicates(df: pl.DataFrame, primary_keys: list) -> dict:
    """
    分析重复记录的详细情况
    """
    if df.is_empty():
        return {'total': 0, 'unique': 0, 'duplicates': 0, 'duplicate_groups': []}

    existing_keys = [key for key in primary_keys if key in df.columns]

    if not existing_keys:
        return {'total': len(df), 'unique': len(df), 'duplicates': 0, 'duplicate_groups': []}

    # 过滤掉主键为空的记录
    conditions = []
    for key in existing_keys:
        conditions.append(pl.col(key).is_not_null())

    df_valid = df.filter(pl.all_horizontal(conditions)) if conditions else df

    # 统计重复
    total = len(df_valid)
    unique_df = df_valid.unique(subset=existing_keys, keep='last')
    unique_count = len(unique_df)
    duplicate_count = total - unique_count

    # 找出重复组（显示前10个）
    duplicate_groups = (df_valid
        .group_by(existing_keys)
        .agg(pl.count().alias('count'))
        .filter(pl.col('count') > 1)
        .sort('count', descending=True)
        .head(10)
    )

    return {
        'total': total,
        'unique': unique_count,
        'duplicates': duplicate_count,
        'duplicate_groups': duplicate_groups
    }


def compare_results(df_with_dedup: pl.DataFrame, df_without_dedup: pl.DataFrame,
                    primary_keys: list, interface_name: str):
    """
    对比两种模式的结果
    """
    logger.info("=" * 60)
    logger.info("对比验证结果")
    logger.info("=" * 60)

    # 1. 基础统计
    logger.info("\n【基础统计】")
    logger.info(f"  带去重:   {len(df_with_dedup)} 条记录")
    logger.info(f"  不去重:   {len(df_without_dedup)} 条记录")
    logger.info(f"  差值:     {len(df_without_dedup) - len(df_with_dedup)} 条")

    # 2. 对不去重的数据进行手动去重
    logger.info("\n【手动去重验证】")
    df_manual_dedup = manual_dedup_by_keys(df_without_dedup, primary_keys)

    # 3. 对比手动去重结果和程序去重结果
    logger.info("\n【结果对比】")
    logger.info(f"  程序去重结果:   {len(df_with_dedup)} 条")
    logger.info(f"  手动去重结果:   {len(df_manual_dedup)} 条")

    if len(df_with_dedup) == len(df_manual_dedup):
        logger.info("  ✅ 数量一致！去重逻辑验证通过")
    else:
        logger.warning(f"  ⚠️ 数量不一致！差值: {len(df_manual_dedup) - len(df_with_dedup)} 条")

    # 4. 详细分析重复情况
    logger.info("\n【重复记录分析】")
    dup_analysis = analyze_duplicates(df_without_dedup, primary_keys)
    logger.info(f"  总记录数:       {dup_analysis['total']}")
    logger.info(f"  唯一记录数:     {dup_analysis['unique']}")
    logger.info(f"  重复记录数:     {dup_analysis['duplicates']}")
    if dup_analysis['total'] > 0:
        logger.info(f"  重复率:         {dup_analysis['duplicates'] / dup_analysis['total'] * 100:.2f}%")

    # 5. 显示重复组示例
    if not dup_analysis['duplicate_groups'].is_empty():
        logger.info("\n【重复组示例（前10个）】")
        print(dup_analysis['duplicate_groups'].to_pandas().to_string())

    # 6. 验证数据内容是否一致
    if not df_with_dedup.is_empty() and not df_manual_dedup.is_empty():
        logger.info("\n【数据内容验证】")

        # 选择共同列进行比较
        common_cols = [col for col in df_with_dedup.columns if col in df_manual_dedup.columns]
        compare_cols = [col for col in primary_keys if col in common_cols]

        if compare_cols:
            # 按主键排序后比较
            sorted_prog = df_with_dedup.select(compare_cols).sort(compare_cols)
            sorted_manual = df_manual_dedup.select(compare_cols).sort(compare_cols)

            if len(sorted_prog) == len(sorted_manual):
                # 比较主键值是否完全一致
                prog_keys = sorted_prog.to_dicts()
                manual_keys = sorted_manual.to_dicts()

                match_count = sum(1 for p, m in zip(prog_keys, manual_keys) if p == m)
                if match_count == len(prog_keys):
                    logger.info(f"  ✅ 主键值完全一致！({match_count}/{len(prog_keys)})")
                else:
                    logger.warning(f"  ⚠️ 主键值不一致: {match_count}/{len(prog_keys)} 匹配")
            else:
                logger.warning(f"  ⚠️ 记录数不同，无法比较内容")

    return {
        'program_dedup_count': len(df_with_dedup),
        'manual_dedup_count': len(df_manual_dedup),
        'raw_count': len(df_without_dedup),
        'duplicate_analysis': dup_analysis
    }


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='验证 report_rc 接口去重逻辑')
    parser.add_argument('--start_date', type=str, default='20260101',
                        help='开始日期 (YYYYMMDD)')
    parser.add_argument('--end_date', type=str, default=None,
                        help='结束日期 (YYYYMMDD)，默认为今天')
    parser.add_argument('--interface', type=str, default='report_rc',
                        help='接口名称')

    args = parser.parse_args()

    # 加载配置获取主键
    config = load_interface_config(args.interface)
    primary_keys = config.get('output', {}).get('primary_key', [])

    logger.info("=" * 60)
    logger.info("去重验证测试脚本")
    logger.info("=" * 60)
    logger.info(f"接口: {args.interface}")
    logger.info(f"主键: {primary_keys}")
    logger.info(f"日期范围: {args.start_date} ~ {args.end_date or '今天'}")
    logger.info("")

    if not primary_keys:
        logger.error("错误: 未配置主键，无法验证去重逻辑")
        return

    # 下载数据（一次下载，两种方式处理）
    logger.info("=" * 60)
    logger.info("步骤1: 下载原始数据")
    logger.info("=" * 60)
    
    raw_data = download_report_rc_data(args.start_date, args.end_date)
    logger.info(f"下载完成: 共 {len(raw_data)} 条原始记录")
    logger.info("")

    # 模式1: 正常处理（带去重）
    logger.info("=" * 60)
    logger.info("步骤2: 正常处理（带完整去重）")
    logger.info("=" * 60)
    df_with_dedup = process_with_dedup(raw_data, config)
    logger.info(f"处理后: {len(df_with_dedup)} 条记录")
    logger.info("")

    # 模式2: 仅创建DataFrame（不去重）
    logger.info("=" * 60)
    logger.info("步骤3: 仅创建DataFrame（不去重）")
    logger.info("=" * 60)
    df_without_dedup = process_without_dedup(raw_data, args.interface)
    logger.info(f"原始DataFrame: {len(df_without_dedup)} 条记录")
    logger.info("")

    # 对比结果
    result = compare_results(df_with_dedup, df_without_dedup, primary_keys, args.interface)

    # 最终结论
    logger.info("=" * 60)
    logger.info("【最终结论】")
    logger.info("=" * 60)

    prog_count = result['program_dedup_count']
    manual_count = result['manual_dedup_count']
    raw_count = result['raw_count']
    dup_count = result['duplicate_analysis']['duplicates']

    logger.info(f"原始下载记录数: {raw_count}")
    logger.info(f"程序去重后记录数: {prog_count}")
    logger.info(f"手动去重后记录数: {manual_count}")
    logger.info(f"检测到的重复记录数: {dup_count}")
    logger.info("")

    if prog_count == manual_count:
        logger.info("✅ 验证通过！程序去重逻辑正确，按照配置的4个主键进行去重：")
        for key in primary_keys:
            logger.info(f"   - {key}")
    else:
        logger.warning("⚠️ 验证失败！程序去重结果与手动去重不一致")
        logger.info(f"   差值: {manual_count - prog_count} 条")

    logger.info("")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
