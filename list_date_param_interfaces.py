#!/usr/bin/env python3
"""
列出在main.py中使用日期参数下载的接口
"""

import os
import sys
from pathlib import Path
import yaml

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

def get_available_interfaces(config_dir):
    """获取所有可用接口名称"""
    interfaces = []
    config_path = Path(config_dir) / "interfaces"
    
    for yaml_file in config_path.glob("*.yaml"):
        with open(yaml_file, 'r', encoding='utf-8') as f:
            try:
                config = yaml.safe_load(f)
                interface_name = config.get('name', yaml_file.stem)
                interfaces.append(interface_name)
            except Exception as e:
                print(f"Error processing {yaml_file}: {e}")
    
    return interfaces

def get_interfaces_without_ts_code_dependency(config_dir):
    """获取不依赖ts_code参数的接口"""
    interfaces = []
    config_path = Path(config_dir) / "interfaces"
    
    for yaml_file in config_path.glob("*.yaml"):
        with open(yaml_file, 'r', encoding='utf-8') as f:
            try:
                config = yaml.safe_load(f)
                interface_name = config.get('name', yaml_file.stem)
                
                # 检查参数中是否包含ts_code
                parameters = config.get('parameters', {})
                param_names = list(parameters.keys())
                
                # 如果参数中不包含ts_code，则认为是仅使用日期参数的接口
                if 'ts_code' not in param_names:
                    interfaces.append(interface_name)
            except Exception as e:
                print(f"Error processing {yaml_file}: {e}")
    
    return interfaces

def main():
    config_dir = "/home/quan/testdata/aspipe_v4/app4/config"
    
    # 获取所有接口
    all_interfaces = get_available_interfaces(config_dir)
    print(f"Total available interfaces: {len(all_interfaces)}")
    
    # 获取不依赖ts_code的接口（这些接口可以仅使用日期参数运行）
    date_param_interfaces = get_interfaces_without_ts_code_dependency(config_dir)
    print(f"Interfaces that can run with only date parameters: {len(date_param_interfaces)}")
    
    # 从main.py逻辑中排除特定接口
    # 根据main.py，以下接口需要特殊处理或依赖其他参数
    excluded_interfaces = {
        'stk_rewards',      # 需要ts_code，属于tscode-historical模式
        'top10_holders',    # 需要ts_code，属于tscode-historical模式
        'pledge_detail',    # 需要ts_code，属于tscode-historical模式
        'fina_audit',       # 需要ts_code，属于tscode-historical模式
        'pro_bar'           # 特殊处理，但可以使用日期参数
    }
    
    # 过滤掉需要特殊处理的接口
    final_interfaces = [iface for iface in date_param_interfaces if iface not in excluded_interfaces]
    
    print("\nInterfaces that will be downloaded with date parameters (when no specific interface is specified):")
    print("="*80)
    for interface in sorted(final_interfaces):
        print(interface)
    
    # 将结果写入文件
    output_dir = Path('/home/quan/testdata/aspipe_v4/p/2026-1-2')
    output_file = output_dir / 'date_param_download_interfaces.txt'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("Interfaces that will be downloaded with date parameters:\n")
        f.write("=====================================================\n")
        for interface in sorted(final_interfaces):
            f.write(f"{interface}\n")
    
    print(f"\nResults saved to: {output_file}")
    print(f"Number of interfaces: {len(final_interfaces)}")

if __name__ == "__main__":
    main()