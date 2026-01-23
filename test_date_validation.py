#!/usr/bin/env python3
"""
测试日期验证函数
"""
import sys
import os
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app4'))

def test_date_validation_enhancement():
    """Test date validation with invalid formats"""
    from app4.main import validate_and_adjust_date

    print("开始测试日期验证函数...")

    # Test invalid format
    try:
        validate_and_adjust_date("2023-01-01", "20231231")
        print("❌ 错误：应该抛出 ValueError 但没有")
    except ValueError as e:
        if "Invalid start_date format" in str(e):
            print("✅ 正确捕获了无效的开始日期格式")
        else:
            print(f"❌ 错误：捕获了错误的异常: {e}")

    # Test invalid format for end date
    try:
        validate_and_adjust_date("20230101", "2023-12-31")
        print("❌ 错误：应该抛出 ValueError 但没有")
    except ValueError as e:
        if "Invalid end_date format" in str(e):
            print("✅ 正确捕获了无效的结束日期格式")
        else:
            print(f"❌ 错误：捕获了错误的异常: {e}")

    # Test invalid date
    try:
        validate_and_adjust_date("20230230", "20230231")  # Invalid Feb 30
        print("❌ 错误：应该抛出 ValueError 但没有")
    except ValueError as e:
        print(f"✅ 正确捕获了无效日期: {e}")

    # Test start_date > end_date
    try:
        validate_and_adjust_date("20231231", "20230101")
        print("❌ 错误：应该抛出 ValueError 但没有")
    except ValueError as e:
        if "must be <= end_date" in str(e):
            print("✅ 正确捕获了开始日期大于结束日期的情况")
        else:
            print(f"❌ 错误：捕获了错误的异常: {e}")

    # Test valid date ranges should pass
    try:
        result = validate_and_adjust_date("20230101", "20231231")
        if result == ("20230101", "20231231"):
            print("✅ 正确处理了有效的日期范围")
        else:
            print(f"❌ 错误：返回了不正确的结果: {result}")
    except Exception as e:
        print(f"❌ 错误：有效日期范围抛出了异常: {e}")

    # Test future date adjustment
    try:
        future_date = (datetime.now().replace(year=datetime.now().year + 1)).strftime('%Y%m%d')
        adjusted_start, adjusted_end = validate_and_adjust_date("20230101", future_date)
        current_date = datetime.now().strftime('%Y%m%d')
        if adjusted_end <= current_date:
            print("✅ 正确调整了未来日期")
        else:
            print(f"❌ 错误：未来日期未正确调整: {adjusted_end} > {current_date}")
    except Exception as e:
        print(f"❌ 错误：未来日期调整抛出了异常: {e}")

    # Test None end_date
    try:
        result = validate_and_adjust_date("20230101", None)
        if result[0] == "20230101" and len(result[1]) == 8:
            print("✅ 正确处理了 end_date 为 None 的情况")
        else:
            print(f"❌ 错误：处理 None 值时返回了不正确的结果: {result}")
    except Exception as e:
        print(f"❌ 错误：处理 None 值时抛出了异常: {e}")

    print("日期验证函数测试完成！")

if __name__ == "__main__":
    test_date_validation_enhancement()