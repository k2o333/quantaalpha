#!/bin/bash

# 测试17个接口的增量下载功能
# 每次下载前清空数据，第一次下载较小范围，第二次下载较大范围，验证去重增量下载功能
# 将34次下载的输出保存到指定目录的txt文件中

# 设置变量
PYTHON_PATH="/root/miniforge3/envs/get/bin/python"
MAIN_PY="/home/quan/testdata/aspipe_v4/app4/main.py"
DATA_BASE_DIR="/home/quan/testdata/aspipe_v4/data"
OUTPUT_DIR="/home/quan/testdata/aspipe_v4/p/interface4/output"
TS_CODE="000001.SZ"
START_DATE_1="20240101"
END_DATE_1="20240630"
START_DATE_2="20230101"
END_DATE_2="20241231"

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 定义17个接口
INTERFACES=(
    "cyq_chips"
    "moneyflow_dc"
    "stk_factor_pro"
    "income_vip"
    "balancesheet_vip"
    "cashflow_vip"
    "fina_indicator_vip"
    "fina_audit"
    "fina_mainbz_vip"
    "forecast_vip"
    "top10_floatholders"
    "disclosure_date"
    "top10_holders"
    "dividend"
    "pledge_stat"
    "stk_rewards"
    "pledge_detail"
)

# 函数：清空接口数据目录
clear_interface_data() {
    local interface_name=$1
    local data_dir="${DATA_BASE_DIR}/${interface_name}"

    if [ -d "$data_dir" ]; then
        echo "清空 ${interface_name} 的数据..."
        rm -rf "$data_dir"
        echo "${interface_name} 数据已清空"
    else
        echo "${interface_name} 数据目录不存在，无需清空"
    fi
}

# 函数：执行下载命令并将输出保存到文件
run_download() {
    local interface_name=$1
    local ts_code=$2
    local start_date=$3
    local end_date=$4
    local download_number=$5
    local output_file="$OUTPUT_DIR/${interface_name}_${download_number}_output.txt"

    echo "正在下载接口: ${interface_name}"
    echo "命令: ${PYTHON_PATH} ${MAIN_PY} --update --interface ${interface_name} --ts_code ${ts_code} --start_date ${start_date} --end_date ${end_date}"

    # 使用timeout命令限制执行时间为60秒，并将输出保存到文件
    timeout 60 ${PYTHON_PATH} ${MAIN_PY} --update --interface ${interface_name} --ts_code ${ts_code} --start_date ${start_date} --end_date ${end_date} > "$output_file" 2>&1

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

# 主函数
main() {
    echo "开始测试17个接口的增量下载功能"
    echo "=================================="
    echo "股票代码: $TS_CODE"
    echo "第一次下载范围: $START_DATE_1 ~ $END_DATE_1"
    echo "第二次下载范围: $START_DATE_2 ~ $END_DATE_2"
    echo "输出将保存到: $OUTPUT_DIR"
    echo "=================================="

    local total=${#INTERFACES[@]}
    local completed=0
    local failed=0

    for interface in "${INTERFACES[@]}"; do
        echo ""
        echo "=================================="
        echo "开始测试接口: $interface"
        echo "=================================="

        # 第一次下载（小范围）
        echo "[步骤1] 第一次下载（小范围）"
        clear_interface_data "$interface"
        if run_download "$interface" "$TS_CODE" "$START_DATE_1" "$END_DATE_1" "1"; then
            echo "第一次下载完成"
        else
            echo "第一次下载失败，跳过此接口"
            ((failed++))
            continue
        fi

        # 第二次下载（大范围）
        echo "[步骤2] 第二次下载（大范围）"
        if run_download "$interface" "$TS_CODE" "$START_DATE_2" "$END_DATE_2" "2"; then
            echo "第二次下载完成"
            echo "✓ 接口 $interface 测试通过"
            ((completed++))
        else
            echo "✗ 接口 $interface 测试失败"
            ((failed++))
        fi

        echo "----------------------------------"
    done

    echo ""
    echo "=================================="
    echo "测试完成总结"
    echo "=================================="
    echo "总接口数: $total"
    echo "成功: $completed"
    echo "失败: $failed"
    echo "所有输出已保存到: $OUTPUT_DIR"
    echo "=================================="
}

# 执行主函数
main "$@"