import sys
import os

# 添加项目路径到sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import polars as pl
from app4.core.schema_manager import SchemaManager


def test_backward_compatibility():
    """测试向后兼容性 - 确保不提供config_dir时使用默认行为"""
    # 测试数据
    test_data = [
        {'ts_code': '000001.SZ', 'trade_date': '20230101', 'close': '10.5', 'volume': '1000'},
        {'ts_code': '000002.SZ', 'trade_date': '20230102', 'close': '12.3', 'volume': '2000'},
    ]

    # 测试不带config_dir的调用（应使用默认的项目配置）
    try:
        df = SchemaManager.create_dataframe(test_data, 'daily')  # 应该不会出错

        # 如果正常运行，则说明向后兼容
        print(f"DataFrame created successfully with {len(df)} rows and columns: {list(df.columns)}")
        print("Backwards compatibility test passed!")
    except Exception as e:
        print(f"Backwards compatibility test failed: {e}")
        raise


if __name__ == '__main__':
    test_backward_compatibility()