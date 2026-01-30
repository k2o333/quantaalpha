#!/bin/bash
# stk_factor_pro 修复验证脚本
# 使用方法: bash 验证修复脚本.sh

set -e  # 遇到错误立即退出

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 目录配置
BASE_DIR="/home/quan/testdata/aspipe_v4"
DATA_DIR="$BASE_DIR/data/stk_factor_pro"
LOG_FILE="$BASE_DIR/log/app4.log"

echo "==================================="
echo "stk_factor_pro 修复验证脚本"
echo "==================================="
echo ""

# 步骤1: 检查目录
echo "[步骤1] 检查目录结构..."
if [ ! -d "$BASE_DIR" ]; then
    echo -e "${RED}✗ 错误: 项目目录不存在: $BASE_DIR${NC}"
    exit 1
fi

if [ ! -d "$BASE_DIR/app4" ]; then
    echo -e "${RED}✗ 错误: app4目录不存在${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 目录结构正常${NC}"
echo ""

# 步骤2: 清理旧数据
echo "[步骤2] 清理旧数据..."
if [ -d "$DATA_DIR" ]; then
    FILE_COUNT=$(ls -1 "$DATA_DIR" | wc -l)
    echo "  发现 $FILE_COUNT 个旧文件"
    rm -rf "$DATA_DIR"
    echo -e "${GREEN}✓ 已清理旧数据${NC}"
else
    echo -e "${YELLOW}⚠ 数据目录不存在，无需清理${NC}"
fi
echo ""

# 步骤3: 备份当前日志
echo "[步骤3] 备份日志..."
if [ -f "$LOG_FILE" ]; then
    cp "$LOG_FILE" "$LOG_FILE.bak"
    echo -e "${GREEN}✓ 已备份日志到: $LOG_FILE.bak${NC}"
else
    echo -e "${YELLOW}⚠ 日志文件不存在${NC}"
fi
echo ""

# 步骤4: 运行测试
echo "[步骤4] 运行 stk_factor_pro 接口测试..."
echo "  命令: python $BASE_DIR/app4/main.py --interface stk_factor_pro --ts_code 000014.SZ"
echo ""

cd "$BASE_DIR/app4"
START_TIME=$(date +%s)

# 运行测试
python main.py --interface stk_factor_pro --ts_code 000014.SZ > /tmp/stk_factor_pro_test.log 2>&1
EXIT_CODE=$?

END_TIME=$(date +%s)
RUNTIME=$((END_TIME - START_TIME))

echo "  运行时间: ${RUNTIME}秒"
echo ""

# 步骤5: 分析结果
echo "[步骤5] 分析测试结果..."
echo ""

# 5.1 检查ERROR日志
echo "  5.1 检查类型转换错误..."
ERROR_COUNT=$(grep -c "创建DataFrame失败 for stk_factor_pro" "$LOG_FILE" || echo "0")
if [ "$ERROR_COUNT" -eq "0" ]; then
    echo -e "    ${GREEN}✓ 未发现类型转换错误${NC}"
else
    echo -e "    ${RED}✗ 发现 $ERROR_COUNT 处类型转换错误${NC}"
    echo "    需要应用修复: storage.py 第211行"
fi
echo ""

# 5.2 检查文件数量
echo "  5.2 检查生成的文件数量..."
if [ ! -d "$DATA_DIR" ]; then
    echo -e "    ${RED}✗ 错误: 数据目录未创建${NC}"
    exit 1
fi

FILE_COUNT=$(find "$DATA_DIR" -name "*.parquet" | wc -l)
echo "  发现 $FILE_COUNT 个parquet文件"

if [ "$FILE_COUNT" -eq "1" ]; then
    echo -e "    ${GREEN}✓ 文件数量正确（1个）${NC}"
elif [ "$FILE_COUNT" -eq "0" ]; then
    echo -e "    ${RED}✗ 错误: 没有生成数据文件${NC}"
else
    echo -e "    ${RED}✗ 警告: 生成 $FILE_COUNT 个文件（应为1个）${NC}"
    echo "    需要应用修复: main.py 第419行 和 storage.py 第457行"
fi
echo ""

# 5.3 检查重复写入
echo "  5.3 检查重复写入日志..."
WRITE_COUNT=$(grep -c "Wrote 8024 records" "$LOG_FILE" || echo "0")
if [ "$WRITE_COUNT" -eq "1" ]; then
    echo -e "    ${GREEN}✓ 写入次数正确（1次）${NC}"
elif [ "$WRITE_COUNT" -eq "0" ]; then
    echo -e "    ${RED}✗ 错误: 未检测到写入操作${NC}"
else
    echo -e "    ${RED}✗ 警告: 写入 $WRITE_COUNT 次（应为1次）${NC}"
fi
echo ""

# 5.4 检查去重功能
echo "  5.4 检查去重功能..."
if grep -q "Existing file does not exist" "$LOG_FILE"; then
    echo -e "    ${YELLOW}⚠ 警告: 去重逻辑未找到现有文件${NC}"
    echo "    需要应用修复: main.py 第389行"
else
    echo -e "    ${GREEN}✓ 去重功能正常${NC}"
fi
echo ""

# 5.5 验证数据完整性
echo "  5.5 验证数据完整性..."
PYTHON_CHECK=$(python3 << 'EOF'
import sys
import polars as pl
import glob
import os

data_dir = "/home/quan/testdata/aspipe_v4/data/stk_factor_pro"
files = glob.glob(f"{data_dir}/*.parquet")

if not files:
    print("ERROR: 未找到数据文件")
    sys.exit(1)

try:
    df = pl.read_parquet(files)
    print(f"SUCCESS: 记录数={len(df)}, 字段数={len(df.columns)}, 文件数={len(files)}")
except Exception as e:
    print(f"ERROR: 读取数据失败: {e}")
    sys.exit(1)
EOF
)

if [[ $PYTHON_CHECK == SUCCESS* ]]; then
    echo -e "    ${GREEN}✓ $PYTHON_CHECK${NC}"
else
    echo -e "    ${RED}✗ $PYTHON_CHECK${NC}"
fi
echo ""

# 步骤6: 第二次运行验证去重
echo "[步骤6] 验证去重功能（第二次运行）..."
echo "  再次运行相同命令..."
cd "$BASE_DIR/app4"
python main.py --interface stk_factor_pro --ts_code 000014.SZ > /tmp/stk_factor_pro_test2.log 2>&1

echo "  检查去重结果..."
if grep -q "No new records\|0 duplicates\|removed.*0" "$LOG_FILE"; then
    echo -e "    ${GREEN}✓ 去重功能正常（识别到重复数据）${NC}"
elif grep -q "Deduplication completed.*removed=0" "$LOG_FILE"; then
    echo -e "    ${GREEN}✓ 去重功能正常（无重复数据）${NC}"
else
    echo -e "    ${YELLOW}⚠ 无法确认去重功能${NC}"
fi
echo ""

# 总结
echo "==================================="
echo "验证完成"
echo "==================================="
echo ""
echo "总结:"
echo "  - 如果发现类型转换错误，应用: storage.py 修复"
echo "  - 如果发现多个文件，应用: main.py + storage.py 修复"
echo "  - 如果去重失效，应用: main.py 去重逻辑修复"
echo ""
echo "详细修复方案请查看:"
echo "  $BASE_DIR/p/2026-1-26/stk_factor_pro问题诊断与解决方案.md"
echo ""
