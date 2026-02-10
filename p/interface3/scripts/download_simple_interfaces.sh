#!/bin/bash

# Stock Loop 接口批量下载脚本
# 使用单一命令模式：main.py --interface <接口名>
# 遍历与download_interfaces.sh相同的接口列表

# 设置输出目录
OUTPUT_DIR="/home/quan/testdata/aspipe_v4/p/interface3/output"
APP_PATH="/home/quan/testdata/aspipe_v4/app4"
TS_CODE="000001.SZ"

# 创建输出目录（如果不存在）
mkdir -p "$OUTPUT_DIR"

# 定义接口列表（共17个接口，与download_interfaces.sh相同）
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
echo "使用单一命令模式: main.py --interface <接口名>"
echo "每个命令有60秒超时限制"
echo "=========================================="

for interface in "${INTERFACES[@]}"; do
    echo ""
    echo "[$interface] 开始下载..."
    
    # 单一命令模式
    output_file="$OUTPUT_DIR/${interface}_simple.txt"
    echo "  命令: --interface $interface -> 输出到: ${interface}_simple.txt"
    
    timeout 60 /root/miniforge3/envs/get/bin/python "$APP_PATH/main.py" --interface "$interface" > "$output_file" 2>&1
    
    if [ $? -eq 0 ]; then
        echo "  [$interface] 下载完成 ✓"
    else
        echo "  [$interface] 下载失败或超时 ✗ (查看 $output_file 了解详情)"
    fi
done

echo ""
echo "=========================================="
echo "所有接口下载任务执行完毕！"
echo "输出文件列表:"
ls -la "$OUTPUT_DIR"
