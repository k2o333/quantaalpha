#!/usr/bin/env python3
"""
测试17个接口的增量下载功能
每次下载前清空数据，第一次下载较小范围，第二次下载较大范围，验证去重增量下载功能
将34次下载的输出保存到指定目录的txt文件中
"""

import os
import sys
import subprocess
import time
from typing import List, Tuple
import signal

# 设置变量
PYTHON_PATH = "/root/miniforge3/envs/get/bin/python"
MAIN_PY = "/home/quan/testdata/aspipe_v4/app4/main.py"
DATA_BASE_DIR = "/home/quan/testdata/aspipe_v4/data"
OUTPUT_DIR = "/home/quan/testdata/aspipe_v4/p/interface4/output"
TS_CODE = "000001.SZ"
START_DATE_1 = "20240101"
END_DATE_1 = "20240630"
START_DATE_2 = "20230101"
END_DATE_2 = "20241231"

# 创建输出目录
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 定义17个接口
INTERFACES = [
    "cyq_chips",
    "moneyflow_dc",
    "stk_factor_pro",
    "income_vip",
    "balancesheet_vip",
    "cashflow_vip",
    "fina_indicator_vip",
    "fina_audit",
    "fina_mainbz_vip",
    "forecast_vip",
    "top10_floatholders",
    "disclosure_date",
    "top10_holders",
    "dividend",
    "pledge_stat",
    "stk_rewards",
    "pledge_detail"
]


def clear_interface_data(interface_name: str):
    """清空接口数据目录"""
    data_dir = os.path.join(DATA_BASE_DIR, interface_name)
    
    if os.path.exists(data_dir):
        import shutil
        print(f"清空 {interface_name} 的数据...")
        shutil.rmtree(data_dir)
        print(f"{interface_name} 数据已清空")
    else:
        print(f"{interface_name} 数据目录不存在，无需清空")


def run_download_with_timeout(interface_name: str, ts_code: str, start_date: str, end_date: str, download_number: str, timeout: int = 60) -> Tuple[bool, str]:
    """执行下载命令并设置超时，将输出保存到文件"""
    cmd = [
        PYTHON_PATH, MAIN_PY,
        '--update',
        '--interface', interface_name,
        '--ts_code', ts_code,
        '--start_date', start_date,
        '--end_date', end_date
    ]
    
    output_file = os.path.join(OUTPUT_DIR, f"{interface_name}_{download_number}_output.txt")
    
    print(f"正在下载接口: {interface_name}")
    print(f"命令: {' '.join(cmd)}")
    
    try:
        # 使用subprocess.run并设置超时，将输出保存到文件
        with open(output_file, 'w') as f:
            result = subprocess.run(
                cmd,
                timeout=timeout,
                stdout=f,
                stderr=subprocess.STDOUT  # 将stderr也重定向到stdout
            )
        
        if result.returncode == 0:
            print(f"✓ {interface_name} 下载成功")
            print(f"输出已保存到: {output_file}")
            return True, ""
        else:
            print(f"✗ {interface_name} 下载失败，退出码: {result.returncode}")
            print(f"输出已保存到: {output_file}")
            return False, f"Exit code: {result.returncode}"
            
    except subprocess.TimeoutExpired:
        # 即使超时也要确保输出已被保存
        print(f"✗ {interface_name} 下载超时（超过{timeout}秒）")
        print(f"输出已保存到: {output_file}")
        return False, "Timeout"


def main():
    print("开始测试17个接口的增量下载功能")
    print("=" * 50)
    print(f"股票代码: {TS_CODE}")
    print(f"第一次下载范围: {START_DATE_1} ~ {END_DATE_1}")
    print(f"第二次下载范围: {START_DATE_2} ~ {END_DATE_2}")
    print(f"输出将保存到: {OUTPUT_DIR}")
    print("=" * 50)
    
    total = len(INTERFACES)
    completed = 0
    failed = 0
    
    for interface in INTERFACES:
        print("")
        print("=" * 50)
        print(f"开始测试接口: {interface}")
        print("=" * 50)
        
        # 第一次下载（小范围）
        print("[步骤1] 第一次下载（小范围）")
        clear_interface_data(interface)
        success, error = run_download_with_timeout(interface, TS_CODE, START_DATE_1, END_DATE_1, "1")
        
        if not success:
            print("第一次下载失败，跳过此接口")
            failed += 1
            continue
        
        print("第一次下载完成")
        
        # 第二次下载（大范围）
        print("[步骤2] 第二次下载（大范围）")
        success, error = run_download_with_timeout(interface, TS_CODE, START_DATE_2, END_DATE_2, "2")
        
        if success:
            print("第二次下载完成")
            print(f"✓ 接口 {interface} 测试通过")
            completed += 1
        else:
            print(f"✗ 接口 {interface} 测试失败")
            failed += 1
        
        print("-" * 50)
    
    print("")
    print("=" * 50)
    print("测试完成总结")
    print("=" * 50)
    print(f"总接口数: {total}")
    print(f"成功: {completed}")
    print(f"失败: {failed}")
    print(f"所有输出已保存到: {OUTPUT_DIR}")
    print("=" * 50)


if __name__ == "__main__":
    main()