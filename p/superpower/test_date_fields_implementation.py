#!/usr/bin/env python3
"""
接口日期字段功能验证脚本
验证当前系统中日期字段转换功能是否正常工作
"""
import os
import sys
sys.path.append('/home/quan/testdata/aspipe_v4')

def test_derived_fields_config():
    """测试派生字段配置是否正确"""
    import yaml

    # 测试几个关键接口
    interfaces_to_test = [
        'daily',
        'stock_basic',
        'income',
        'top10_holders',
        'dividend'
    ]

    print("Testing derived fields configuration...")

    for interface in interfaces_to_test:
        config_path = f'/home/quan/testdata/aspipe_v4/app4/config/interfaces/{interface}.yaml'
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            if 'derived_fields' in config:
                print(f"✓ {interface}: Found derived_fields configuration with {len(config['derived_fields'])} fields")
                for field_name, field_config in config['derived_fields'].items():
                    print(f"  - {field_name}: {field_config.get('source')} -> {field_config.get('type')}")
            else:
                print(f"✗ {interface}: No derived_fields configuration found")
        else:
            print(f"✗ {interface}: Config file not found")

def test_date_converter():
    """测试日期转换器功能"""
    print("\nTesting date converter functionality...")

    try:
        from app4.core.date_converter import DateConverter

        converter = DateConverter()
        result = converter.convert("20240101")
        if result:
            print(f"✓ Date conversion working: 20240101 -> {result}")
        else:
            print("✗ Date conversion failed")

    except Exception as e:
        print(f"✗ Date converter test failed: {e}")

def test_processing_order():
    """测试处理顺序功能"""
    print("\nTesting data processing order...")

    # 创建测试数据
    from datetime import date
    test_data = [
        {'ts_code': '000001.SZ', 'trade_date': '20240101'},
        {'ts_code': None, 'trade_date': '20240102'},  # 主键为空
        {'ts_code': '000002.SZ', 'trade_date': '20240103'}
    ]

    # 创建接口配置
    interface_config = {
        'api_name': 'test_interface',
        'output': {
            'primary_key': ['ts_code', 'trade_date']
        },
        'derived_fields': {
            'trade_date_dt': {
                'description': 'Date type trade_date',
                'format': '%Y%m%d',
                'source': 'trade_date',
                'type': 'date'
            }
        }
    }

    try:
        from app4.core.processor import DataProcessor
        processor = DataProcessor()

        result_df = processor.process_data(test_data, interface_config)

        print(f"✓ Processing completed: {len(test_data)} input records -> {len(result_df)} output records")

        # 检查是否包含日期格式字段
        if result_df is not None and not result_df.is_empty():
            columns = result_df.columns
            if 'trade_date_dt' in columns:
                print(f"✓ Date field derivation working: 'trade_date_dt' field exists")

                # Check the type of the derived field
                if hasattr(result_df['trade_date_dt'], 'dtype'):
                    print(f"  Date field type: {result_df['trade_date_dt'].dtype}")
            else:
                print("✗ Date field derivation not working: 'trade_date_dt' field missing")

    except Exception as e:
        print(f"✗ Processing order test failed: {e}")
        import traceback
        traceback.print_exc()

def test_schema_manager():
    """测试SchemaManager是否正确处理派生字段"""
    print("\nTesting schema manager...")

    test_data = [
        {'trade_date': '20240101'},
        {'trade_date': '20240102'}
    ]

    # Create a temporary test interface config
    import tempfile
    import os
    import yaml

    temp_config = {
        'api_name': 'test_date_interface',
        'derived_fields': {
            'trade_date_dt': {
                'description': 'Date type trade_date',
                'format': '%Y%m%d',
                'source': 'trade_date',
                'type': 'date'
            }
        },
        'output': {
            'primary_key': ['trade_date']
        }
    }

    # Write temporary config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(temp_config, f)
        temp_config_path = f.name

    try:
        from app4.core.schema_manager import SchemaManager
        import polars as pl

        # Create a mock interface config location
        import shutil
        original_path = '/home/quan/testdata/aspipe_v4/app4/config/interfaces/test_date_interface.yaml'
        shutil.copy(temp_config_path, original_path)

        # Test the schema manager
        df = SchemaManager.create_dataframe(test_data, 'test_date_interface')

        if df is not None and not df.is_empty():
            print(f"✓ SchemaManager working: Created DataFrame with {len(df)} rows")
            if 'trade_date_dt' in df.columns:
                print("✓ Derived field properly added")
                print(f"  trade_date_dt values: {df['trade_date_dt'].to_list()}")
            else:
                print("✗ Derived field not added")
        else:
            print("✗ SchemaManager failed to create DataFrame")

    except Exception as e:
        print(f"✗ SchemaManager test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        try:
            os.unlink(temp_config_path)
            config_path = '/home/quan/testdata/aspipe_v4/app4/config/interfaces/test_date_interface.yaml'
            if os.path.exists(config_path):
                os.unlink(config_path)
        except:
            pass

def main():
    """主函数"""
    print("接口日期字段功能验证")
    print("="*50)

    test_derived_fields_config()
    test_date_converter()
    test_processing_order()
    test_schema_manager()

    print("\n验证完成！")

if __name__ == "__main__":
    main()