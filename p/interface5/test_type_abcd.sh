#!/bin/bash

# 测试 stock_loop 模式的接口功能
# 将输出保存到指定目录的 txt 文件中

# 设置变量
PYTHON_PATH="/root/miniforge3/envs/get/bin/python"
MAIN_PY="/home/quan/testdata/aspipe_v4/app4/main.py"
OUTPUT_DIR="/home/quan/testdata/aspipe_v4/p/interface5/output"
TS_CODE="000001.SZ"

# Type A: stock_loop 模式 - 交易日历类
TYPE_A_INTERFACES=(
    "stk_factor_pro"
    "cyq_chips"
    "moneyflow_dc"
)

# Type B: stock_loop 模式 - 定期报告类
TYPE_B_INTERFACES=(
    "fina_audit"
    "top10_floatholders"
)

# Type C: stock_loop 模式 - 股东权益类
TYPE_C_INTERFACES=(
    "disclosure_date"
    "top10_holders"
    "dividend"
    "pledge_stat"
    "stk_rewards"
)

# Type D: stock_loop 模式 - 基础信息类
TYPE_D_INTERFACES=(
    "pledge_detail"
)

# 创建输出目录
mkdir -p "$OUTPUT_DIR"


# 函数：执行下载命令并将输出保存到文件
run_download() {
    local interface_name=$1
    local ts_code=$2
    local start_date=$3
    local end_date=$4
    local test_name=$5
    local extra_args=$6
    local output_file="$OUTPUT_DIR/${interface_name}_${test_name}_output.txt"

    echo "正在下载接口: ${interface_name}"
    echo "命令: ${PYTHON_PATH} ${MAIN_PY} --interface ${interface_name} --ts_code ${ts_code} --start_date ${start_date} --end_date ${end_date} ${extra_args}"

    # 使用 timeout 命令限制执行时间，并将输出保存到文件
    timeout 60 ${PYTHON_PATH} ${MAIN_PY} --interface ${interface_name} --ts_code ${ts_code} --start_date ${start_date} --end_date ${end_date} ${extra_args} > "$output_file" 2>&1

    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
        echo "✓ ${interface_name} 下载成功"
        echo "输出已保存到: $output_file"
    elif [ $exit_code -eq 124 ]; then
        echo "✗ ${interface_name} 下载超时（超过60秒）"
        echo "输出已保存到: $output_file"
    else
        echo "✗ ${interface_name} 下载失败，退出码: $exit_code"
        echo "输出已保存到: $output_file"
    fi

    return $exit_code
}

# 函数：测试 Type A 接口
test_type_a() {
    echo ""
    echo "=========================================="
    echo "测试 Type A: stock_loop 模式 - 交易日历类"
    echo "=========================================="

    for interface in "${TYPE_A_INTERFACES[@]}"; do
        echo ""
        echo "----------------------------------------"
        echo "测试接口: $interface"
        echo "----------------------------------------"


        # 测试1: 全量下载（小范围）
        echo "[测试1] 全量下载（小范围: 20240101 ~ 20240630）"
        run_download "$interface" "$TS_CODE" "20240101" "20240630" "full_small" ""

        # 测试2: 增量下载（扩展范围）
        echo "[测试2] 增量下载（扩展范围: 20230101 ~ 20241231）"
        run_download "$interface" "$TS_CODE" "20230101" "20241231" "inc_large" ""


        echo "完成测试: $interface"
    done
}

# 函数：测试 Type B 接口
test_type_b() {
    echo ""
    echo "=========================================="
    echo "测试 Type B: stock_loop 模式 - 定期报告类"
    echo "=========================================="

    for interface in "${TYPE_B_INTERFACES[@]}"; do
        echo ""
        echo "----------------------------------------"
        echo "测试接口: $interface"
        echo "----------------------------------------"


        # 测试1: 全量下载（小范围）
        echo "[测试1] 全量下载（小范围: 20230101 ~ 20240630）"
        run_download "$interface" "$TS_CODE" "20230101" "20240630" "full_small" ""

        # 测试2: 增量下载（扩展范围）
        echo "[测试2] 增量下载（扩展范围: 20200101 ~ 20241231）"
        run_download "$interface" "$TS_CODE" "20200101" "20241231" "inc_large" ""


        echo "完成测试: $interface"
    done
}

# 函数：测试 Type C 接口
test_type_c() {
    echo ""
    echo "=========================================="
    echo "测试 Type C: stock_loop 模式 - 股东权益类"
    echo "=========================================="

    for interface in "${TYPE_C_INTERFACES[@]}"; do
        echo ""
        echo "----------------------------------------"
        echo "测试接口: $interface"
        echo "----------------------------------------"


        # 测试1: 全量下载（小范围）
        echo "[测试1] 全量下载（小范围: 20240101 ~ 20240630）"
        run_download "$interface" "$TS_CODE" "20240101" "20240630" "full_small" ""

        # 测试2: 增量下载（扩展范围）
        echo "[测试2] 增量下载（扩展范围: 20230101 ~ 20241231）"
        run_download "$interface" "$TS_CODE" "20230101" "20241231" "inc_large" ""


        echo "完成测试: $interface"
    done
}

# 函数：测试 Type D 接口
test_type_d() {
    echo ""
    echo "=========================================="
    echo "测试 Type D: stock_loop 模式 - 基础信息类"
    echo "=========================================="

    for interface in "${TYPE_D_INTERFACES[@]}"; do
        echo ""
        echo "----------------------------------------"
        echo "测试接口: $interface"
        echo "----------------------------------------"


        # 测试1: 无日期参数下载
        echo "[测试1] 全量下载（小范围：20240101 ~ 20240630）"
        run_download "$interface" "$TS_CODE" "20240101" "20240630" "full_small" ""

        # 测试2: 增量下载（扩展范围：20230101 ~ 20241231）
        echo "[测试2] 增量下载（扩展范围：20230101 ~ 20241231）"
        run_download "$interface" "$TS_CODE" "20230101" "20241231" "inc_large" ""


        echo "完成测试: $interface"
    done
}

# 主函数
main() {
    echo "=========================================="
    echo "开始测试 stock_loop 模式接口功能"
    echo "=========================================="
    echo "股票代码: $TS_CODE"
    echo "输出目录: $OUTPUT_DIR"
    echo "=========================================="

    # 测试 Type A
    test_type_a

    # 测试 Type B
    test_type_b

    # 测试 Type C
    test_type_c

    # 测试 Type D
    test_type_d

    echo ""
    echo "=========================================="
    echo "所有测试完成"
    echo "输出保存到: $OUTPUT_DIR"
    echo "=========================================="
}

# 执行主函数
main "$@"
