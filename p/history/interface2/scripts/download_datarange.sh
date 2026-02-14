#!/bin/bash

# Data Range 接口批量下载脚本
# 测试24个data range接口，每个接口下载今天一天的数据

# 设置输出目录
OUTPUT_DIR="/home/quan/testdata/aspipe_v4/p/interface2/output_datarange"
APP_PATH="/home/quan/testdata/aspipe_v4/app4"

# 获取今天的日期
TODAY=$(date +%Y%m%d)

# 创建输出目录（如果不存在）
mkdir -p "$OUTPUT_DIR"

# 定义data range接口列表
INTERFACES=(
    "cyq_perf"
    "report_rc"
    "new_share"
    "stk_surv"
    "daily_basic"
    "moneyflow_cnt_ths"
    "cyq_chips"
    "moneyflow_mkt_dc"
    "stk_holdertrade"
    "stk_premarket"
    "daily"
    "suspend_d"
    "block_trade"
    "moneyflow_ind_dc"
    "moneyflow"
    "repurchase"
    "share_float"
    "moneyflow_dc"
    "stk_managers"
    "stock_hsgt"
    "moneyflow_ind_ths"
    "moneyflow_ths"
    "stock_st"
    "trade_cal"
)

# 遍历接口并执行下载
echo "开始下载 data range 接口数据..."
echo "输出目录: $OUTPUT_DIR"
echo "查询日期: $TODAY"
echo "=========================================="

for interface in "${INTERFACES[@]}"; do
    output_file="$OUTPUT_DIR/${interface}.txt"
    echo ""
    echo "[$interface] 开始下载 (日期: $TODAY)..."
    
    # 执行下载命令并保存输出
    cd "$APP_PATH" && python main.py --interface "$interface" --start_date "$TODAY" --end_date "$TODAY" > "$output_file" 2>&1
    
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
