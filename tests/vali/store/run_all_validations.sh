#!/bin/bash

# 非日线数据下载优化验证脚本
# 运行所有验证脚本来测试优化效果

echo "========================================="
echo "开始非日线数据下载优化验证"
echo "========================================="

# 设置环境变量（请根据实际情况修改）
export TUSHARE_TOKEN="your_tushare_token_here"

echo "1. 验证财务数据批量下载优化..."
python /home/quan/testdata/aspipe_v4/vali/validate_financial_bulk_download.py

echo -e "\n========================================="
echo "2. 验证事件数据批量下载优化..."
python /home/quan/testdata/aspipe_v4/vali/validate_event_bulk_download.py

echo -e "\n========================================="
echo "3. 验证股东数据批量下载优化..."
python /home/quan/testdata/aspipe_v4/vali/validate_holder_bulk_download.py

echo -e "\n========================================="
echo "4. 验证研究数据批量下载优化..."
python /home/quan/testdata/aspipe_v4/vali/validate_research_bulk_download.py

echo -e "\n========================================="
echo "所有验证完成！"
echo "========================================="