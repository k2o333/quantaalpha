#!/bin/bash

# Primary Key 有效性验证测试脚本
# 复用 /home/quan/testdata/aspipe_v4/p/interface2/scripts/download_interfaces.sh 的风格

# 设置目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_PATH="/home/quan/testdata/aspipe_v4/app4"
DATA_DIR="$SCRIPT_DIR/data"
OUTPUT_DIR="$SCRIPT_DIR/reports"

# 创建目录
mkdir -p "$DATA_DIR"
mkdir -p "$OUTPUT_DIR"

# 定义接口列表（与 download_interfaces.sh 一致）
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

# 默认股票代码（用于stock_loop模式的接口）
TS_CODE="000002.SZ"
MAX_STOCKS=1  # 只下载1只股票

# 解析命令行参数
RUN_DOWNLOAD=true
RUN_TEST=true
SPECIFIC_INTERFACE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-download)
            RUN_DOWNLOAD=false
            shift
            ;;
        --no-test)
            RUN_TEST=false
            shift
            ;;
        --interface)
            SPECIFIC_INTERFACE="$2"
            shift 2
            ;;
        --ts_code)
            TS_CODE="$2"
            shift 2
            ;;
        --max_stocks)
            MAX_STOCKS="$2"
            shift 2
            ;;
        --help)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --no-download      跳过下载步骤，只运行测试"
            echo "  --no-test          跳过测试步骤，只下载数据"
            echo "  --interface NAME   只处理指定接口"
            echo "  --ts_code CODE     指定股票代码 (默认: $TS_CODE)"
            echo "  --max_stocks N     最大下载股票数量 (默认: $MAX_STOCKS)"
            echo "  --help             显示帮助信息"
            exit 0
            ;;
        *)
            echo "未知选项: $1"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "Primary Key 有效性验证测试"
echo "=========================================="
echo "数据目录: $DATA_DIR"
echo "报告目录: $OUTPUT_DIR"
echo ""

# 步骤1: 下载数据
if [ "$RUN_DOWNLOAD" = true ]; then
    echo "步骤1: 下载接口数据"
    echo "=========================================="
    
    cd "$APP_PATH" || exit 1
    
    if [ -n "$SPECIFIC_INTERFACE" ]; then
        # 只下载指定接口
        echo "下载单个接口: $SPECIFIC_INTERFACE"
        python "$SCRIPT_DIR/download_data.py" --interface "$SPECIFIC_INTERFACE" --ts_code "$TS_CODE" --max_stocks "$MAX_STOCKS"
    else
        # 下载所有接口
        echo "下载所有接口数据..."
        python "$SCRIPT_DIR/download_data.py" --ts_code "$TS_CODE" --max_stocks "$MAX_STOCKS"
    fi
    
    echo ""
    echo "下载步骤完成"
    echo ""
fi

# 步骤2: 运行测试
if [ "$RUN_TEST" = true ]; then
    echo "步骤2: 运行 Primary Key 测试"
    echo "=========================================="
    
    if [ -n "$SPECIFIC_INTERFACE" ]; then
        # 只测试指定接口
        echo "测试单个接口: $SPECIFIC_INTERFACE"
        python "$SCRIPT_DIR/test_primary_key.py" --interface "$SPECIFIC_INTERFACE"
    else
        # 测试所有接口
        echo "测试所有接口..."
        python "$SCRIPT_DIR/test_primary_key.py"
    fi
    
    echo ""
    echo "测试步骤完成"
    echo ""
fi

echo "=========================================="
echo "全部任务执行完毕!"
echo "=========================================="
echo ""
echo "数据文件位置: $DATA_DIR"
echo "测试报告位置: $OUTPUT_DIR"
echo ""

# 列出报告文件
if [ -d "$OUTPUT_DIR" ]; then
    latest_report=$(ls -t "$OUTPUT_DIR"/*.md 2>/dev/null | head -1)
    if [ -n "$latest_report" ]; then
        echo "最新测试报告: $latest_report"
    fi
fi
