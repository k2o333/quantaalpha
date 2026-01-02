#!/usr/bin/env python3
"""
分析app4接口配置，按积分要求分类列出所有接口
"""
import os
import yaml
from collections import defaultdict

# 配置目录路径
config_dir = "/home/quan/testdata/aspipe_v4/app4/config"
interfaces_dir = os.path.join(config_dir, "interfaces")

# 收集接口信息
interfaces_by_points = defaultdict(list)
total_interfaces = 0

print("正在分析接口配置...")

# 遍历所有接口配置文件
for filename in os.listdir(interfaces_dir):
    if filename.endswith('.yaml') or filename.endswith('.yml'):
        interface_name = filename.replace('.yaml', '').replace('.yml', '')
        interface_path = os.path.join(interfaces_dir, filename)

        try:
            with open(interface_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            # 获取积分要求
            min_points = config.get('permissions', {}).get('min_points', 0)

            # 获取接口描述
            description = config.get('description', '无描述')

            # 获取分页模式
            pagination = config.get('pagination', {})
            pagination_mode = pagination.get('mode', 'none') if pagination.get('enabled', False) else 'none'

            # 获取速率限制
            rate_limit = config.get('permissions', {}).get('rate_limit', '未配置')

            # 检查是否需要ts_code
            parameters = config.get('parameters', {})
            needs_tscode = 'ts_code' in parameters

            # 添加到对应积分组
            interfaces_by_points[min_points].append({
                'name': interface_name,
                'description': description,
                'pagination_mode': pagination_mode,
                'rate_limit': rate_limit,
                'needs_tscode': needs_tscode
            })

            total_interfaces += 1

        except Exception as e:
            print(f"读取配置文件 {filename} 时出错: {e}")

# 创建输出内容
output_lines = []
output_lines.append("=" * 80)
output_lines.append("App4 接口配置分析报告")
output_lines.append("=" * 80)
output_lines.append(f"总计接口数量: {total_interfaces}")
output_lines.append("")

# 按积分要求排序输出
for points in sorted(interfaces_by_points.keys()):
    output_lines.append(f"\n【{points} 积分可访问的接口】")
    output_lines.append("-" * 50)

    for interface in sorted(interfaces_by_points[points], key=lambda x: x['name']):
        name = interface['name']
        desc = interface['description']
        pagination = interface['pagination_mode']
        rate_limit = interface['rate_limit']
        needs_tscode = "是" if interface['needs_tscode'] else "否"

        output_lines.append(f"接口名: {name}")
        output_lines.append(f"  描述: {desc}")
        output_lines.append(f"  分页模式: {pagination}")
        output_lines.append(f"  速率限制: {rate_limit} 次/分钟")
        output_lines.append(f"  需要ts_code: {needs_tscode}")
        output_lines.append("")

# 添加默认下载行为说明
output_lines.append("\n" + "=" * 80)
output_lines.append("默认下载行为说明（仅提供日期参数时）")
output_lines.append("=" * 80)
output_lines.append("""
当只提供日期参数（--start_date 和 --end_date）时：

1. 系统会下载所有积分足够的接口（排除需要ts_code的4个接口和pro_bar）
2. 具体下载哪些接口取决于你的积分等级：
   - 120积分：只能下载0积分接口
   - 2000积分：可以下载0积分和2000积分接口
   - 更高积分：可以下载所有接口

3. 被排除的接口（需要ts_code）：
   - stk_rewards（股票激励）
   - top10_holders（前10大股东）
   - pledge_detail（股权质押详情）
   - fina_audit（财务审计）
   - pro_bar（复权行情）

4. 分页下载：
   - date_range模式：按日期窗口分页（如365天）
   - offset模式：按偏移量分页
   - stock_loop模式：按股票循环下载
""")

# 按积分等级列出默认可下载接口
output_lines.append("\n【按积分等级列出的默认可下载接口】")
output_lines.append("-" * 50)

# 获取默认排除的接口
excluded_interfaces = {'stk_rewards', 'top10_holders', 'pledge_detail', 'fina_audit', 'pro_bar'}

for points in sorted(interfaces_by_points.keys()):
    available_interfaces = [iface for iface in interfaces_by_points[points]
                           if iface['name'] not in excluded_interfaces]

    if available_interfaces:
        output_lines.append(f"\n{points} 积分等级 ({len(available_interfaces)} 个接口):")
        for interface in sorted(available_interfaces, key=lambda x: x['name']):
            output_lines.append(f"  - {interface['name']}: {interface['description']}")

# 写入文件
output_path = "/home/quan/testdata/aspipe_v4/p/2026-1-2/app4_interfaces_analysis.txt"
with open(output_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(output_lines))

print(f"\n分析完成！结果已保存到: {output_path}")
print(f"总计分析了 {total_interfaces} 个接口")