#!/bin/bash
# 运行接口下载速度测试的便捷脚本

echo "选择要运行的测试:"
echo "1) 完整下载速度测试 (耗时较长)"
echo "2) 快速接口检查 (推荐日常使用)"
echo "3) 查看详细测试报告"
echo "4) 退出"

read -p "请输入选项 (1-4): " choice

case $choice in
    1)
        echo "开始完整下载速度测试..."
        python /home/quan/testdata/aspipe_v4/test/download_speed_test.py
        ;;
    2)
        echo "开始快速接口检查..."
        python /home/quan/testdata/aspipe_v4/test/quick_interface_check.py
        ;;
    3)
        echo "显示详细测试报告..."
        cat /home/quan/testdata/aspipe_v4/test/download_speed_test_report.md
        ;;
    4)
        echo "退出"
        exit 0
        ;;
    *)
        echo "无效选项，请重新运行脚本并输入有效选项 (1-4)"
        exit 1
        ;;
esac