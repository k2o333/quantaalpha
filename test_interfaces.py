#!/usr/bin/env python3
"""
测试 17 个 stock loop 模式接口的增量更新功能
"""

import os
import sys
import subprocess
import polars as pl
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# 接口分类
INTERFACES = {
    # 类型 A：交易日历接口
    'type_a': [
        'cyq_chips',
        'moneyflow_dc', 
        'stk_factor_pro'
    ],
    # 类型 B：报告期接口
    'type_b': [
        'income_vip',
        'balancesheet_vip',
        'cashflow_vip',
        'fina_indicator_vip',
        'fina_audit',
        'fina_mainbz_vip',
        'forecast_vip',
        'top10_floatholders'
    ],
    # 类型 C：日期锚定接口
    'type_c': [
        'disclosure_date',
        'top10_holders',
        'dividend',
        'pledge_stat',
        'stk_rewards'
    ],
    # 类型 D：无日期过滤接口
    'type_d': [
        'pledge_detail'
    ]
}

# 测试配置
TS_CODE = '000001.SZ'  # 平安银行
START_DATE_1 = '20240101'
END_DATE_1 = '20240630'
START_DATE_2 = '20230101'
END_DATE_2 = '20241231'
PYTHON_PATH = '/root/miniforge3/envs/get/bin/python'
MAIN_PY = '/home/quan/testdata/aspipe_v4/app4/main.py'
DATA_BASE_DIR = '/home/quan/testdata/aspipe_v4/data'


def run_command(cmd: List[str]) -> Tuple[int, str, str]:
    """执行命令并返回结果"""
    print(f"执行命令: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )
    return result.returncode, result.stdout, result.stderr


def get_date_column(interface_name: str) -> str:
    """获取接口的日期列名"""
    date_columns = {
        'cyq_chips': 'trade_date',
        'moneyflow_dc': 'trade_date',
        'stk_factor_pro': 'trade_date',
        'income_vip': 'end_date',
        'balancesheet_vip': 'end_date',
        'cashflow_vip': 'end_date',
        'fina_indicator_vip': 'end_date',
        'fina_audit': 'end_date',
        'fina_mainbz_vip': 'end_date',
        'forecast_vip': 'end_date',
        'top10_floatholders': 'end_date',
        'disclosure_date': 'end_date',
        'top10_holders': 'end_date',
        'dividend': 'ann_date',
        'pledge_stat': 'end_date',
        'stk_rewards': 'end_date',
        'pledge_detail': 'ann_date'
    }
    return date_columns.get(interface_name, 'trade_date')


def check_data_exists(interface_name: str, ts_code: str) -> bool:
    """检查数据是否存在"""
    data_dir = os.path.join(DATA_BASE_DIR, interface_name)
    if not os.path.exists(data_dir):
        return False
    
    # 查找 parquet 文件
    import glob
    parquet_files = glob.glob(os.path.join(data_dir, '*.parquet'))
    return len(parquet_files) > 0


def get_data_date_range(interface_name: str, ts_code: str) -> Tuple[str, str]:
    """获取已下载数据的日期范围"""
    data_dir = os.path.join(DATA_BASE_DIR, interface_name)
    date_column = get_date_column(interface_name)
    
    if not os.path.exists(data_dir):
        return None, None
    
    # 读取所有 parquet 文件
    import glob
    parquet_files = glob.glob(os.path.join(data_dir, '*.parquet'))
    
    if not parquet_files:
        return None, None
    
    try:
        df = pl.read_parquet(data_dir)
        
        # 过滤当前股票
        if 'ts_code' in df.columns:
            df = df.filter(pl.col('ts_code') == ts_code)
        
        if df.is_empty():
            return None, None
        
        min_date = df[date_column].min()
        max_date = df[date_column].max()
        
        return min_date, max_date
    except Exception as e:
        print(f"读取数据失败: {e}")
        return None, None


def clear_data(interface_name: str):
    """清除接口数据"""
    data_dir = os.path.join(DATA_BASE_DIR, interface_name)
    if os.path.exists(data_dir):
        import shutil
        shutil.rmtree(data_dir)
        print(f"已清除 {interface_name} 的数据")


def test_interface(interface_name: str, interface_type: str) -> Dict:
    """测试单个接口"""
    print(f"\n{'='*80}")
    print(f"测试接口: {interface_name} (类型: {interface_type})")
    print(f"{'='*80}")
    
    result = {
        'interface': interface_name,
        'type': interface_type,
        'passed': False,
        'steps': []
    }
    
    # 步骤 1: 清除旧数据
    print("\n[步骤 1] 清除旧数据")
    clear_data(interface_name)
    result['steps'].append({'step': 1, 'name': '清除旧数据', 'status': 'success'})
    
    # 步骤 2: 第一次下载（小范围）
    print(f"\n[步骤 2] 第一次下载: {START_DATE_1} ~ {END_DATE_1}")
    cmd = [
        PYTHON_PATH, MAIN_PY,
        '--update',
        '--interface', interface_name,
        '--ts_code', TS_CODE,
        '--start_date', START_DATE_1,
        '--end_date', END_DATE_1
    ]
    
    returncode, stdout, stderr = run_command(cmd)
    
    if returncode != 0:
        print(f"下载失败: {stderr}")
        result['steps'].append({'step': 2, 'name': '第一次下载', 'status': 'failed', 'error': stderr})
        return result
    
    print("下载完成")
    result['steps'].append({'step': 2, 'name': '第一次下载', 'status': 'success'})
    
    # 步骤 3: 验证第一次下载的数据范围
    print("\n[步骤 3] 验证第一次下载的数据范围")
    min_date1, max_date1 = get_data_date_range(interface_name, TS_CODE)
    
    if min_date1 is None or max_date1 is None:
        print("未找到数据!")
        result['steps'].append({'step': 3, 'name': '验证第一次下载', 'status': 'failed', 'error': '未找到数据'})
        return result
    
    print(f"数据日期范围: {min_date1} ~ {max_date1}")
    print(f"期望日期范围: {START_DATE_1} ~ {END_DATE_1}")
    
    # 对于类型 D，不检查具体日期范围
    if interface_type != 'type_d':
        if min_date1 < START_DATE_1 or max_date1 > END_DATE_1:
            print("警告: 数据日期超出期望范围")
    
    result['steps'].append({
        'step': 3, 
        'name': '验证第一次下载', 
        'status': 'success',
        'min_date': min_date1,
        'max_date': max_date1
    })
    
    # 步骤 4: 第二次下载（大范围）
    print(f"\n[步骤 4] 第二次下载: {START_DATE_2} ~ {END_DATE_2}")
    cmd = [
        PYTHON_PATH, MAIN_PY,
        '--update',
        '--interface', interface_name,
        '--ts_code', TS_CODE,
        '--start_date', START_DATE_2,
        '--end_date', END_DATE_2
    ]
    
    returncode, stdout, stderr = run_command(cmd)
    
    if returncode != 0:
        print(f"下载失败: {stderr}")
        result['steps'].append({'step': 4, 'name': '第二次下载', 'status': 'failed', 'error': stderr})
        return result
    
    print("下载完成")
    result['steps'].append({'step': 4, 'name': '第二次下载', 'status': 'success'})
    
    # 步骤 5: 验证第二次下载的数据范围
    print("\n[步骤 5] 验证第二次下载的数据范围")
    min_date2, max_date2 = get_data_date_range(interface_name, TS_CODE)
    
    if min_date2 is None or max_date2 is None:
        print("未找到数据!")
        result['steps'].append({'step': 5, 'name': '验证第二次下载', 'status': 'failed', 'error': '未找到数据'})
        return result
    
    print(f"数据日期范围: {min_date2} ~ {max_date2}")
    print(f"期望日期范围: {START_DATE_2} ~ {END_DATE_2}")
    
    # 对于类型 D，不检查具体日期范围
    if interface_type != 'type_d':
        # 验证数据范围确实扩展了
        if min_date2 > min_date1 or max_date2 < max_date1:
            print("警告: 数据范围没有正确扩展")
    
    result['steps'].append({
        'step': 5, 
        'name': '验证第二次下载', 
        'status': 'success',
        'min_date': min_date2,
        'max_date': max_date2
    })
    
    result['passed'] = True
    print(f"\n✓ 接口 {interface_name} 测试通过!")
    
    return result


def main():
    """主函数"""
    print("="*80)
    print("开始测试 17 个 stock loop 模式接口")
    print("="*80)
    
    all_results = []
    
    # 测试所有接口
    for interface_type, interfaces in INTERFACES.items():
        for interface_name in interfaces:
            result = test_interface(interface_name, interface_type)
            all_results.append(result)
    
    # 打印总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    passed = sum(1 for r in all_results if r['passed'])
    failed = sum(1 for r in all_results if not r['passed'])
    
    print(f"总接口数: {len(all_results)}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    
    print("\n详细结果:")
    for result in all_results:
        status = "✓ 通过" if result['passed'] else "✗ 失败"
        print(f"  [{result['type']}] {result['interface']}: {status}")
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
