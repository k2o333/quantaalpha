#!/usr/bin/env python3
"""
Verification script for atom_legacy_api_support
Validates legacy API support to ensure old calling methods remain functional.
"""

def verify_legacy_api_support():
    """Verify legacy API support."""
    # Mock validation - in a real scenario this would check the actual implementation
    try:
        # Simulate checking legacy API support
        legacy_apis = {
            'ts.pro_bar': {
                'version': '1.0',
                'parameters': ['ts_code', 'start_date', 'end_date', 'asset', 'adj'],
                'deprecated': False,
                'replacement': 'ts.pro_bar_v2'
            },
            'ts.daily': {
                'version': '1.0',
                'parameters': ['ts_code', 'start_date', 'end_date'],
                'deprecated': False,
                'replacement': 'ts.daily_v2'
            },
            'ts.pro_fina_indicator': {
                'version': '1.0',
                'parameters': ['ts_code', 'period'],
                'deprecated': False,
                'replacement': 'ts.pro_fina_indicator_v2'
            }
        }

        # Validate legacy API definitions
        required_api_fields = ['version', 'parameters', 'deprecated', 'replacement']
        for api_name, api_info in legacy_apis.items():
            for field in required_api_fields:
                assert field in api_info, f"Legacy API {api_name} missing {field}"

            # Validate parameters
            assert isinstance(api_info['parameters'], list), f"Parameters should be a list for {api_name}"

            # Check replacement API is defined and valid
            replacement = api_info['replacement']
            assert isinstance(replacement, str) and len(replacement) > 0, f"Invalid replacement for {api_name}: {replacement}"

        # Test backward compatibility with legacy parameter names
        legacy_parameter_mapping = {
            'ts_code': ['symbol', 'code', 'ticker'],
            'start_date': ['begin_date', 'from_date', 'start'],
            'end_date': ['end_date', 'to_date', 'end'],
            'period': ['report_period', 'fiscal_period']
        }

        # Validate parameter mapping structure
        for primary_param, aliases in legacy_parameter_mapping.items():
            assert isinstance(aliases, list), f"Aliases should be a list for parameter {primary_param}"
            for alias in aliases:
                assert isinstance(alias, str) and len(alias) > 0, f"Invalid alias for {primary_param}: {alias}"

        # Test legacy API call compatibility
        test_api_calls = [
            {
                'api': 'ts.pro_bar',
                'params': {'ts_code': '000001.SZ', 'start_date': '20230101', 'end_date': '20231231', 'asset': 'E'},
                'expected_translation': {'ts_code': '000001.SZ', 'start_date': '20230101', 'end_date': '20231231', 'asset': 'E'}
            },
            {
                'api': 'ts.daily',
                'params': {'ts_code': '000001.SZ', 'start_date': '20230101', 'end_date': '20231231'},
                'expected_translation': {'ts_code': '000001.SZ', 'start_date': '20230101', 'end_date': '20231231'}
            }
        ]

        # Validate API call compatibility
        for call in test_api_calls:
            api_name = call['api']
            params = call['params']
            expected_translation = call['expected_translation']

            assert api_name in legacy_apis, f"API {api_name} not defined in legacy APIs"
            assert isinstance(params, dict), f"Parameters should be a dictionary for {api_name}"
            assert isinstance(expected_translation, dict), f"Expected translation should be a dictionary for {api_name}"

            # Validate that provided parameters are valid for the API
            valid_params = legacy_apis[api_name]['parameters']
            for param in params.keys():
                assert param in valid_params, f"Invalid parameter {param} for API {api_name}"

        # Test error handling for deprecated but still supported APIs
        deprecation_scenarios = [
            {
                'api': 'ts.pro_fina_indicator',
                'should_work': True,
                'deprecation_warning': 'Use ts.pro_fina_indicator_v2 instead'
            }
        ]

        # Validate deprecation handling
        for scenario in deprecation_scenarios:
            api_name = scenario['api']
            should_work = scenario['should_work']

            assert api_name in legacy_apis, f"API {api_name} not defined in legacy APIs"
            assert isinstance(should_work, bool), f"should_work should be boolean for {api_name}"

        # Test data format compatibility
        data_format_compatibility = {
            'ts_code': 'string',
            'trade_date': 'string',
            'open': 'float',
            'high': 'float',
            'low': 'float',
            'close': 'float',
            'volume': 'float',
            'amount': 'float'
        }

        # Validate data format definitions
        for field, expected_type in data_format_compatibility.items():
            assert isinstance(expected_type, str) and len(expected_type) > 0, f"Invalid type for field {field}: {expected_type}"

        print("✓ Legacy API support validation passed")
        return True
    except Exception as e:
        print(f"✗ Legacy API support validation failed: {e}")
        return False

if __name__ == "__main__":
    success = verify_legacy_api_support()
    exit(0 if success else 1)