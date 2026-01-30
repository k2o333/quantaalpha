#!/bin/bash

# Stock Loop 接口批量下载脚本
# 删除 stk_factor 和 pro_bar 后剩余的16个接口

# 设置输出目录
OUTPUT_DIR="/home/quan/testdata/aspipe_v4/p/interface2/output"
APP_PATH="/home/quan/testdata/aspipe_v4/app4"
TS_CODE="000014.SZ"

# 创建输出目录（如果不存在）
mkdir -p "$OUTPUT_DIR"

# 定义接口列表（stock loop 形式，排除已删除的 stk_factor 和 pro_bar）
INTERFACES=(
    "balancesheet_vip"
    "cashflow_vip"
    "disclosure_date"
    "dividend"
    "express_vip"
    "fina_audit"
    "fina_indicator_vip"
    "fina_mainbz_vip"
    "forecast_vip"
    "income_vip"
    "pledge_detail"
    "pledge_stat"
    "stk_factor_pro"
    "stk_rewards"
    "top10_floatholders"
    "top10_holders"
)

# 遍历接口并执行下载
echo "开始下载 stock loop 接口数据..."
echo "输出目录: $OUTPUT_DIR"
echo "测试股票代码: $TS_CODE"
echo "=========================================="

for interface in "${INTERFACES[@]}"; do
    output_file="$OUTPUT_DIR/${interface}.txt"
    echo ""
    echo "[$interface] 开始下载..."
    
    # 执行下载命令并保存输出
    cd "$APP_PATH" && python main.py --interface "$interface" --ts_code "$TS_CODE" > "$output_file" 2>&1
    
    # 检查执行结果
    if [ $? -eq 0 ]; then
        echo "[$interface] 下载完成 ✓"
    else
        echo "[$interface] 下载失败 ✗ (查看 $output_file 了解详情)"
    fi
done

echo ""
echo "=========================================="
echo "所有接口下载任务执行完毕！"
echo "输出文件列表:"
ls -la "$OUTPUT_DIR"