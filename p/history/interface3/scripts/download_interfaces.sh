#!/bin/bash

# Stock Loop 接口批量下载脚本
# 包含17个接口，每种接口使用4种不同的参数组合进行下载
# 每个命令都有60秒超时限制

# 设置输出目录
OUTPUT_DIR="/home/quan/testdata/aspipe_v4/p/interface3/output"
APP_PATH="/home/quan/testdata/aspipe_v4/app4"
TS_CODE="000001.SZ"

# 创建输出目录（如果不存在）
mkdir -p "$OUTPUT_DIR"

# 定义接口列表（共17个接口）
INTERFACES=(
    "disclosure_date"
    "stk_factor_pro"       
    "top10_holders"        
    "top10_floatholders"   
    "income_vip"           
    "fina_indicator_vip"   
    "cyq_chips"            
    "cashflow_vip"         
    "forecast_vip"         
    "moneyflow_dc"         
    "fina_audit"           
    "pledge_stat"          
    "dividend"             
    "pledge_detail"        
    "stk_rewards"          
    "fina_mainbz_vip"      
    "balancesheet_vip"     
)

# 遍历接口并执行下载
echo "开始下载 stock loop 接口数据..."
echo "输出目录: $OUTPUT_DIR"
echo "测试股票代码: $TS_CODE"
echo "每个命令有60秒超时限制"
echo "=========================================="

for interface in "${INTERFACES[@]}"; do
    echo ""
    echo "[$interface] 开始下载..."
    
    # 对每个接口执行4种不同的参数模式
    # 参数模式1
    output_file="$OUTPUT_DIR/${interface}_param0.txt"
    echo "  参数模式 1: --interface $interface --ts_code $TS_CODE --start_date 20250701 --end_date 20251231 -> 输出到: ${interface}_param0.txt"
    timeout 60 /root/miniforge3/envs/get/bin/python "$APP_PATH/main.py" --interface "$interface" --ts_code "$TS_CODE" --start_date 20250701 --end_date 20251231 > "$output_file" 2>&1
    if [ $? -eq 0 ]; then
        echo "  [$interface param0] 下载完成 ✓"
    else
        echo "  [$interface param0] 下载失败或超时 ✗ (查看 $output_file 了解详情)"
    fi
    
    # 参数模式2
    output_file="$OUTPUT_DIR/${interface}_param1.txt"
    echo "  参数模式 2: --interface $interface --ts_code $TS_CODE --start_date 20250101 --end_date 20251231 -> 输出到: ${interface}_param1.txt"
    timeout 60 /root/miniforge3/envs/get/bin/python "$APP_PATH/main.py" --interface "$interface" --ts_code "$TS_CODE" --start_date 20250101 --end_date 20251231 > "$output_file" 2>&1
    if [ $? -eq 0 ]; then
        echo "  [$interface param1] 下载完成 ✓"
    else
        echo "  [$interface param1] 下载失败或超时 ✗ (查看 $output_file 了解详情)"
    fi
    
    # 参数模式3
    output_file="$OUTPUT_DIR/${interface}_param2.txt"
    echo "  参数模式 3: --interface $interface --ts_code $TS_CODE -> 输出到: ${interface}_param2.txt"
    timeout 60 /root/miniforge3/envs/get/bin/python "$APP_PATH/main.py" --interface "$interface" --ts_code "$TS_CODE" > "$output_file" 2>&1
    if [ $? -eq 0 ]; then
        echo "  [$interface param2] 下载完成 ✓"
    else
        echo "  [$interface param2] 下载失败或超时 ✗ (查看 $output_file 了解详情)"
    fi
    
    # 参数模式4
    output_file="$OUTPUT_DIR/${interface}_param3.txt"
    echo "  参数模式 4: --update --interface $interface -> 输出到: ${interface}_param3.txt"
    timeout 60 /root/miniforge3/envs/get/bin/python "$APP_PATH/main.py" --update --interface "$interface" > "$output_file" 2>&1
    if [ $? -eq 0 ]; then
        echo "  [$interface param3] 下载完成 ✓"
    else
        echo "  [$interface param3] 下载失败或超时 ✗ (查看 $output_file 了解详情)"
    fi
done

echo ""
echo "=========================================="
echo "所有接口下载任务执行完毕！"
echo "输出文件列表:"
ls -la "$OUTPUT_DIR"
