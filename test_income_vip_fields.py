#!/usr/bin/env python3
"""
测试income_vip接口的字段返回情况
"""
import sys
import os

# 确保从正确的目录运行
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

sys.path.insert(0, os.path.join(script_dir, 'app4'))

# 修改ConfigLoader的默认配置目录
from core import config_loader
original_config_dir = config_loader.__file__

# 手动设置配置目录路径
config_dir = os.path.join(script_dir, 'app4/config')
print(f"Config directory: {config_dir}")
print(f"Config dir exists: {os.path.exists(config_dir)}")

from core.config_loader import ConfigLoader
from core.downloader import GenericDownloader

# 手动设置配置目录路径
config_dir = os.path.join(script_dir, 'app4/config')
print(f"Config directory: {config_dir}")
print(f"Config dir exists: {os.path.exists(config_dir)}")

# 加载配置
config_loader_instance = ConfigLoader(config_dir=config_dir)
downloader = GenericDownloader(config_loader_instance)

# 获取income_vip接口配置
interface_config = config_loader_instance.get_interface_config('income_vip')

# 读取配置文件中的所有字段
import yaml
config_file_path = os.path.join(script_dir, 'app4/config/interfaces/income_vip.yaml')
with open(config_file_path, 'r') as f:
    config = yaml.safe_load(f)

columns = config['output']['columns']
fields_list = [col for col in columns.keys() if not col.startswith('_')]

print("=" * 80)
print("测试方案1：请求所有字段")
print("=" * 80)
print(f"请求字段数: {len(fields_list)}")
all_fields_str = ','.join(fields_list)
print(f"fields参数长度: {len(all_fields_str)} 字符")

params = {'period': '20241231'}
test1_params = params.copy()
test1_params['fields'] = all_fields_str

# 发送请求
result1 = downloader._make_request(interface_config, test1_params)
if result1:
    print(f"✓ 请求成功，返回 {len(result1)} 条记录")
    if result1:
        print(f"✓ 实际返回字段数: {len(result1[0].keys())}")
        print(f"✓ 返回的字段: {list(result1[0].keys())}")
else:
    print("✗ 请求失败")

print("\n" + "=" * 80)
print("测试方案2：只请求前10个字段")
print("=" * 80)
test2_fields = fields_list[:10]
test2_fields_str = ','.join(test2_fields)
print(f"请求字段: {test2_fields}")
print(f"fields参数长度: {len(test2_fields_str)} 字符")

test2_params = params.copy()
test2_params['fields'] = test2_fields_str

result2 = downloader._make_request(interface_config, test2_params)
if result2:
    print(f"✓ 请求成功，返回 {len(result2)} 条记录")
    if result2:
        print(f"✓ 实际返回字段数: {len(result2[0].keys())}")
        print(f"✓ 返回的字段: {list(result2[0].keys())}")
else:
    print("✗ 请求失败")

print("\n" + "=" * 80)
print("测试方案3：请求特定关键字段")
print("=" * 80)
test3_fields = ['ts_code', 'ann_date', 'end_date', 'update_flag', 'ebit', 'ebitda', 'n_commis_income']
test3_fields_str = ','.join(test3_fields)
print(f"请求字段: {test3_fields}")
print(f"fields参数长度: {len(test3_fields_str)} 字符")

test3_params = params.copy()
test3_params['fields'] = test3_fields_str

result3 = downloader._make_request(interface_config, test3_params)
if result3:
    print(f"✓ 请求成功，返回 {len(result3)} 条记录")
    if result3:
        print(f"✓ 实际返回字段数: {len(result3[0].keys())}")
        print(f"✓ 返回的字段: {list(result3[0].keys())}")
else:
    print("✗ 请求失败")

print("\n" + "=" * 80)
print("测试方案4：不指定fields参数")
print("=" * 80)
test4_params = params.copy()
# 不传递fields参数

result4 = downloader._make_request(interface_config, test4_params)
if result4:
    print(f"✓ 请求成功，返回 {len(result4)} 条记录")
    if result4:
        print(f"✓ 实际返回字段数: {len(result4[0].keys())}")
        print(f"✓ 返回的字段: {list(result4[0].keys())}")
else:
    print("✗ 请求失败")

print("\n" + "=" * 80)
print("结论")
print("=" * 80)
print("如果所有测试都返回相同的40个字段，说明API有固定返回限制")
print("如果测试2/3/4成功返回请求的字段，说明fields参数有效")
print("如果测试1失败但测试2/3成功，说明fields参数有长度限制")
