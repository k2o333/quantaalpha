#!/bin/bash

# 测试 period_range 模式的接口功能
# 将输出保存到指定目录的 txt 文件中

# 设置变量
PYTHON_PATH="/root/miniforge3/envs/get/bin/python"
MAIN_PY="/home/quan/testdata/aspipe_v4/app4/main.py"
OUTPUT_DIR="/home/quan/testdata/aspipe_v4/p/interface5/outputperiod"

# period_range 模式接口列表
PERIOD_RANGE_INTERFACES=(
    "income_vip"
    "balancesheet_vip"
    "cashflow_vip"
    "fina_indicator_vip"
    "forecast_vip"
    "express_vip"
    "fina_mainbz_vip"
)

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 函数：执行更新命令并将输出保存到文件
run_update() {
    local interface_name=$1
    local start_date=$2
    local test_name=$3
    local output_file="$OUTPUT_DIR/${interface_name}_${test_name}_output.txt"

    echo "正在更新接口: ${interface_name}"
    echo "命令: ${PYTHON_PATH} ${MAIN_PY} --update --interface ${interface_name} --start_date ${start_date}"

    # 使用 timeout 命令限制执行时间，并将输出保存到文件
    timeout 300 ${PYTHON_PATH} ${MAIN_PY} --update --interface ${interface_name} --start_date ${start_date} > "$output_file" 2>&1

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
    echo "开始测试 period_range 模式接口功能"
    echo "=========================================="
    echo "输出目录: $OUTPUT_DIR"
    echo "=========================================="

    for interface in "${PERIOD_RANGE_INTERFACES[@]}"; do
        echo ""
        echo "----------------------------------------"
        echo "测试接口: $interface"
        echo "----------------------------------------"

        # 测试: 使用 --update 模式，从 20241001 开始
        echo "[测试] 更新接口（起始日期: 20241001）"
        run_update "$interface" "20241001" "update"

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
