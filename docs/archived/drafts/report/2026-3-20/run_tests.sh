#!/bin/bash
# Iterate 2 系列测试脚本
# 日期: 2026-03-20
# 环境: Linux, Python 3.12.13, pytest 9.0.2

set -e

PYTHON="/root/miniforge3/envs/mining/bin/python"
PROJECT_ROOT="/home/quan/testdata/aspipe_v4"
TESTS_DIR="$PROJECT_ROOT/third_party/quantaalpha/tests"

echo "=========================================="
echo "Iterate 2 系列测试验证"
echo "=========================================="

echo ""
echo "1. Iterate 2.1: revalidate 语义澄清与真实复验链路"
echo "------------------------------------------------"
$PYTHON -m pytest $TESTS_DIR/test_revalidate_cli.py -v
$PYTHON -m pytest $TESTS_DIR/test_revalidate_real_backtest.py -v

echo ""
echo "2. Iterate 2.2: 失败因子重试过滤"
echo "------------------------------------------------"
$PYTHON -m pytest $TESTS_DIR/test_debug_failure_filter.py -v

echo ""
echo "3. Iterate 2.3: 质量门控与状态流转回归测试"
echo "------------------------------------------------"
$PYTHON -m pytest $TESTS_DIR/test_status_transition.py $TESTS_DIR/test_planning_constraints.py $TESTS_DIR/test_quality_gate.py -v

echo ""
echo "4. Iterate 2.4: 外部调度脚本、运行摘要与状态审计"
echo "------------------------------------------------"
$PYTHON -m pytest $TESTS_DIR/test_scheduler_summary.py -v

echo ""
echo "5. Iterate 2.5: 因子库写入保护"
echo "------------------------------------------------"
$PYTHON -m pytest $TESTS_DIR/test_factor_library_locking.py -v

echo ""
echo "=========================================="
echo "全部测试执行完成"
echo "=========================================="
