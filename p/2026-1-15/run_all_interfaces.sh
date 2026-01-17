#!/bin/bash

# 批量测试所有接口并保存输出

CONFIG_DIR="/home/quan/testdata/aspipe_v4/app4/config/interfaces"
OUTPUT_DIR="/home/quan/testdata/aspipe_v4/p/2026-1-15/interfaceterout"

# 遍历所有yaml配置文件
for config_file in "$CONFIG_DIR"/*.yaml; do
    # 提取接口名称（去掉.yaml后缀）
    interface_name=$(basename "$config_file" .yaml)

    # 跳过备份文件
    if [[ $interface_name == bak_* ]]; then
        echo "跳过备份文件: $interface_name"
        continue
    fi

    echo "正在测试接口: $interface_name"

    # 执行测试命令并保存输出
    /root/miniforge3/bin/python /home/quan/testdata/aspipe_v4/app4/main.py \
        --interface "$interface_name" \
        --ts_code 000003.SZ \
        --start_date 20240401 \
        --end_date 20240705 \
        > "$OUTPUT_DIR/${interface_name}.txt" 2>&1

    if [ $? -eq 0 ]; then
        echo "✓ $interface_name 测试完成"
    else
        echo "✗ $interface_name 测试失败"
    fi
done

echo "所有接口测试完成！"