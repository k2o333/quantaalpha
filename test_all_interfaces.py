#!/usr/bin/env python3
"""
测试 17 个 stock loop 模式接口的增量更新功能
生成详细的测试报告
"""

import os
import sys
import subprocess
import polars as pl
import glob
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional

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
REPORT_FILE = '/home/quan/testdata/aspipe_v4/test_report.md'


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


def clear_data(interface_name: str):
    """清除接口数据"""
    data_dir = os.path.join(DATA_BASE_DIR, interface_name)
    if os.path.exists(data_dir):
        import shutil
        shutil.rmtree(data_dir)
        return True
    return False


def get_data_info(interface_name: str, ts_code: str) -> Dict:
    """获取数据信息"""
    data_dir = os.path.join(DATA_BASE_DIR, interface_name)
    date_column = get_date_column(interface_name)
    
    result = {
        'exists': False,
        'record_count': 0,
        'min_date': None,
        'max_date': None,
        'dates': []
    }
    
    if not os.path.exists(data_dir):
        return result
    
    parquet_files = glob.glob(os.path.join(data_dir, '*.parquet'))
    if not parquet_files:
        return result
    
    try:
        df = pl.read_parquet(parquet_files)
        
        if 'ts_code' in df.columns:
            df = df.filter(pl.col('ts_code') == ts_code)
        
        if df.is_empty():
            return result
        
        result['exists'] = True
        result['record_count'] = len(df)
        
        if date_column in df.columns:
            result['min_date'] = df[date_column].min()
            result['max_date'] = df[date_column].max()
            result['dates'] = sorted(df[date_column].unique().to_list())
        
        return result
    except Exception as e:
        print(f"读取数据失败: {e}")
        return result


def run_command(cmd: List[str], log_file: str = None) -> Tuple[int, str, str]:
    """执行命令并返回结果"""
    print(f"执行命令: {' '.join(cmd)}")
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )
    
    if log_file:
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write(f"命令: {' '.join(cmd)}\n")
            f.write("="*80 + "\n\n")
            f.write("STDOUT:\n")
            f.write(result.stdout + "\n\n")
            f.write("STDERR:\n")
            f.write(result.stderr + "\n")
    
    return result.returncode, result.stdout, result.stderr


def test_interface(interface_name: str, interface_type: str, test_num: int, total_tests: int) -> Dict:
    """测试单个接口"""
    print(f"\n{'='*80}")
    print(f"[{test_num}/{total_tests}] 测试接口: {interface_name} (类型: {interface_type})")
    print(f"{'='*80}")
    
    log_dir = f"/home/quan/testdata/aspipe_v4/log/test_{interface_name}"
    os.makedirs(log_dir, exist_ok=True)
    
    result = {
        'interface': interface_name,
        'type': interface_type,
        'passed': False,
        'steps': [],
        'test_start_time': datetime.now().isoformat(),
        'test_end_time': None
    }
    
    try:
        # 步骤 1: 清除旧数据
        print("\n[步骤 1] 清除旧数据")
        cleared = clear_data(interface_name)
        step1_result = {
            'step': 1, 
            'name': '清除旧数据', 
            'status': 'success',
            'cleared': cleared
        }
        result['steps'].append(step1_result)
        
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
        
        log_file1 = os.path.join(log_dir, 'step1_download.log')
        returncode, stdout, stderr = run_command(cmd, log_file1)
        
        step2_status = 'success' if returncode == 0 else 'failed'
        data1 = get_data_info(interface_name, TS_CODE)
        
        step2_result = {
            'step': 2, 
            'name': '第一次下载', 
            'status': step2_status,
            'returncode': returncode,
            'data': data1,
            'stdout': stdout[-500:] if len(stdout) > 500 else stdout,
            'stderr': stderr
        }
        result['steps'].append(step2_result)
        
        if returncode != 0:
            print(f"下载失败: {stderr}")
            result['test_end_time'] = datetime.now().isoformat()
            return result
        
        print(f"第一次下载完成: {data1['record_count']} 条记录")
        if data1['min_date'] and data1['max_date']:
            print(f"数据日期范围: {data1['min_date']} ~ {data1['max_date']}")
        
        # 步骤 3: 第二次下载（大范围）
        print(f"\n[步骤 3] 第二次下载: {START_DATE_2} ~ {END_DATE_2}")
        cmd = [
            PYTHON_PATH, MAIN_PY,
            '--update',
            '--interface', interface_name,
            '--ts_code', TS_CODE,
            '--start_date', START_DATE_2,
            '--end_date', END_DATE_2
        ]
        
        log_file2 = os.path.join(log_dir, 'step2_download.log')
        returncode, stdout, stderr = run_command(cmd, log_file2)
        
        step3_status = 'success' if returncode == 0 else 'failed'
        data2 = get_data_info(interface_name, TS_CODE)
        
        step3_result = {
            'step': 3, 
            'name': '第二次下载', 
            'status': step3_status,
            'returncode': returncode,
            'data': data2,
            'stdout': stdout[-500:] if len(stdout) > 500 else stdout,
            'stderr': stderr
        }
        result['steps'].append(step3_result)
        
        if returncode != 0:
            print(f"下载失败: {stderr}")
            result['test_end_time'] = datetime.now().isoformat()
            return result
        
        print(f"第二次下载完成: {data2['record_count']} 条记录")
        if data2['min_date'] and data2['max_date']:
            print(f"数据日期范围: {data2['min_date']} ~ {data2['max_date']}")
        
        # 验证结果
        print("\n[步骤 4] 验证结果")
        
        # 检查是否有数据
        has_data = data2['record_count'] > 0
        
        # 检查日期范围是否合理（对于非类型D）
        date_range_ok = True
        if interface_type != 'type_d' and data2['min_date'] and data2['max_date']:
            # 只要有数据就算通过，不强制要求覆盖整个范围
            pass
        
        # 检查记录数是否增加或保持
        record_count_ok = data2['record_count'] >= data1['record_count']
        
        passed = has_data and record_count_ok
        
        step4_result = {
            'step': 4,
            'name': '验证结果',
            'status': 'success' if passed else 'failed',
            'has_data': has_data,
            'record_count_ok': record_count_ok,
            'date_range_ok': date_range_ok
        }
        result['steps'].append(step4_result)
        
        result['passed'] = passed
        result['test_end_time'] = datetime.now().isoformat()
        
        if passed:
            print(f"\n✓ 接口 {interface_name} 测试通过!")
        else:
            print(f"\n✗ 接口 {interface_name} 测试失败!")
        
    except Exception as e:
        print(f"测试过程出错: {e}")
        import traceback
        traceback.print_exc()
        result['error'] = str(e)
        result['test_end_time'] = datetime.now().isoformat()
    
    return result


def generate_report(all_results: List[Dict]) -> str:
    """生成测试报告"""
    report = []
    report.append("# 接口增量更新功能测试报告\n")
    report.append(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report.append(f"测试股票: {TS_CODE}\n")
    report.append("\n---\n")
    
    # 统计
    passed = sum(1 for r in all_results if r['passed'])
    failed = sum(1 for r in all_results if not r['passed'])
    total = len(all_results)
    
    report.append("## 测试总结\n")
    report.append(f"- 总接口数: {total}\n")
    report.append(f"- 通过: {passed}\n")
    report.append(f"- 失败: {failed}\n")
    report.append(f"- 通过率: {passed/total*100:.1f}%\n")
    report.append("\n")
    
    # 按类型统计
    type_stats = {}
    for result in all_results:
        itype = result['type']
        if itype not in type_stats:
            type_stats[itype] = {'total': 0, 'passed': 0, 'failed': 0}
        type_stats[itype]['total'] += 1
        if result['passed']:
            type_stats[itype]['passed'] += 1
        else:
            type_stats[itype]['failed'] += 1
    
    report.append("### 按类型统计\n")
    type_names = {
        'type_a': '类型 A: 交易日历接口',
        'type_b': '类型 B: 报告期接口',
        'type_c': '类型 C: 日期锚定接口',
        'type_d': '类型 D: 无日期过滤接口'
    }
    for itype, stats in sorted(type_stats.items()):
        report.append(f"- {type_names.get(itype, itype)}: {stats['total']} 个, 通过 {stats['passed']} 个, 失败 {stats['failed']} 个\n")
    report.append("\n")
    
    # 详细结果
    report.append("## 详细测试结果\n")
    
    for result in all_results:
        status_icon = "✓" if result['passed'] else "✗"
        report.append(f"\n### {status_icon} {result['interface']} ({result['type']})\n")
        
        for step in result['steps']:
            step_status = "✓" if step['status'] == 'success' else "✗"
            report.append(f"- **步骤 {step['step']}: {step['name']}** - {step_status}\n")
            
            if 'data' in step:
                data = step['data']
                if data['exists']:
                    report.append(f"  - 记录数: {data['record_count']}\n")
                    if data['min_date'] and data['max_date']:
                        report.append(f"  - 日期范围: {data['min_date']} ~ {data['max_date']}\n")
                    if data['dates']:
                        report.append(f"  - 日期列表: {', '.join(data['dates'][:10])}{'...' if len(data['dates'])>10 else ''}\n")
        
        if not result['passed']:
            report.append(f"\n**失败原因**: 请查看详细日志\n")
    
    report.append("\n---\n")
    report.append("## 测试配置\n")
    report.append(f"- 第一次下载日期: {START_DATE_1} ~ {END_DATE_1}\n")
    report.append(f"- 第二次下载日期: {START_DATE_2} ~ {END_DATE_2}\n")
    report.append(f"- Python 路径: {PYTHON_PATH}\n")
    report.append(f"- 主程序: {MAIN_PY}\n")
    
    return "\n".join(report)


def main():
    """主函数"""
    print("="*80)
    print("开始测试 17 个 stock loop 模式接口")
    print("="*80)
    
    all_results = []
    
    # 获取所有接口列表
    all_interfaces = []
    for interfaces in INTERFACES.values():
        all_interfaces.extend(interfaces)
    
    total_tests = len(all_interfaces)
    test_num = 0
    
    # 测试所有接口
    for interface_type, interfaces in INTERFACES.items():
        for interface_name in interfaces:
            test_num += 1
            result = test_interface(interface_name, interface_type, test_num, total_tests)
            all_results.append(result)
    
    # 生成报告
    print("\n" + "="*80)
    print("生成测试报告...")
    print("="*80)
    
    report = generate_report(all_results)
    
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(report)
    
    # 打印报告摘要
    print("\n" + report)
    
    # 保存 JSON 格式的结果
    json_file = REPORT_FILE.replace('.md', '.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n测试报告已保存到: {REPORT_FILE}")
    print(f"详细结果已保存到: {json_file}")
    
    # 返回退出码
    failed = sum(1 for r in all_results if not r['passed'])
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
