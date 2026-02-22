#!/bin/bash

# 测试 reverse_date_range 模式的接口功能
# 将输出保存到指定目录的 txt 文件中

# 设置变量
PYTHON_PATH="/root/miniforge3/envs/get/bin/python"
MAIN_PY="/home/quan/testdata/aspipe_v4/app4/main.py"
OUTPUT_DIR="/home/quan/testdata/aspipe_v4/p/interface5/outputreverse"

# reverse_date_range 模式接口列表
REVERSE_DATE_RANGE_INTERFACES=(
    "daily_basic"
    "moneyflow"
    "moneyflow_ind_dc"
    "moneyflow_ind_ths"
    "moneyflow_mkt_dc"
    "moneyflow_ths"
    "moneyflow_cnt_ths"
    "new_share"
    "repurchase"
    "stock_st"
    "stk_holdertrade"
    "stk_managers"
    "block_trade"
    "suspend_d"
    "report_rc"
    "share_float"
    "cyq_perf"
)

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 函数：执行更新命令并将输出保存到文件
run_update() {
    local interface_name=$1
    local start_date=$2
    local end_date=$3
    local test_name=$4
    local output_file="$OUTPUT_DIR/${interface_name}_${test_name}_output.txt"

    echo "正在更新接口: ${interface_name}"
    echo "命令: ${PYTHON_PATH} ${MAIN_PY} --interface ${interface_name} --start_date ${start_date} --end_date ${end_date}"

    # 使用 timeout 命令限制执行时间，并将输出保存到文件
    timeout 300 ${PYTHON_PATH} ${MAIN_PY} --interface ${interface_name} --start_date ${start_date} --end_date ${end_date} > "$output_file" 2>&1

    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
        echo "✓ ${interface_name} 更新成功"
        echo "输出已保存到: $output_file"
    elif [ $exit_code -eq 124 ]; then
        echo "✗ ${interface_name} 更新超时（超过300秒）"
        echo "输出已保存到: $output_file"
    else
        echo "✗ ${interface_name} 更新失败，退出码: $exit_code"
        echo "输出已保存到: $output_file"
    fi

    return $exit_code
}

# 主函数
main() {
    echo "=========================================="
    echo "开始测试 reverse_date_range 模式接口功能"
    echo "=========================================="
    echo "输出目录: $OUTPUT_DIR"
    echo "=========================================="

    # 使用20260210开始的日期范围
    START_DATE="20260210"
    END_DATE="20260222"

    for interface in "${REVERSE_DATE_RANGE_INTERFACES[@]}"; do
        echo ""
        echo "----------------------------------------"
        echo "测试接口: $interface"
        echo "----------------------------------------"

        # 测试: 使用指定的日期范围
        echo "[测试] 更新接口（起始日期: $START_DATE, 结束日期: $END_DATE）"
        run_update "$interface" "$START_DATE" "$END_DATE" "reverse_date_range"

        echo "完成测试: $interface"
    done

    echo ""
    echo "=========================================="
    echo "所有测试完成"
    echo "输出保存到: $OUTPUT_DIR"
    echo "=========================================="
}

# 执行主函数
main "$@"