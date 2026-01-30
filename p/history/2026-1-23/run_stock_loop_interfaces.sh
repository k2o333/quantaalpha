#!/bin/bash

# 定义接口列表
interfaces=(
    "top10_holders"
    "top10_floatholders"
    "stk_rewards"
    "disclosure_date"
    "cashflow_vip"
    "stk_factor"
    "balancesheet_vip"
    "income_vip"
    "fina_indicator_vip"
    "pledge_detail"
    "forecast_vip"
    "fina_audit"
    "stk_factor_pro"
    "fina_mainbz_vip"
    "express_vip"
    "pro_bar"
    "pledge_stat"
    "dividend"
)

# 创建输出目录
mkdir -p "/home/quan/testdata/aspipe_v4/p/2026-1-23/output"

# 循环执行每个接口
for interface in "${interfaces[@]}"; do
    echo "正在执行接口: $interface"
    
    # 执行Python命令并将输出保存到文件
    cd /home/quan/testdata/aspipe_v4 && python app4/main.py --interface "$interface" --ts_code 000002.SZ \
        > "/home/quan/testdata/aspipe_v4/p/2026-1-23/output/${interface}.txt" 2>&1
    
    echo "接口 $interface 执行完成，输出已保存到 ${interface}.txt"
done

echo "所有接口执行完成！"