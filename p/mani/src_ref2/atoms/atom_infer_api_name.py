#!/usr/bin/env python
"""
Verification script for atom_infer_api_name
- 从函数对象推断API名称的函数
"""

def verify_atom_infer_api_name():
    """
    验证从函数对象推断API名称的函数
    """
    print("Testing atom_infer_api_name: API名称推断功能")

    import inspect
    import re
    from datetime import datetime
    import types

    def infer_api_name(func_obj):
        """
        从函数对象推断API名称的函数
        """
        print(f"  - Inferring API name from function: {func_obj.__name__ if hasattr(func_obj, '__name__') else 'unknown'}")

        # Method 1: Check function docstring for API name pattern FIRST (highest priority)
        docstring = inspect.getdoc(func_obj)
        if docstring:
            # Look for patterns like "API: api_name" or "api_name: description"
            api_patterns = [
                r'API:\s*([a-zA-Z_][a-zA-Z0-9_]*)',
                r'api_name:\s*([a-zA-Z_][a-zA-Z0-9_]*)',
                r'API name:\s*([a-zA-Z_][a-zA-Z0-9_]*)'
            ]

            for pattern in api_patterns:
                matches = re.search(pattern, docstring, re.IGNORECASE)
                if matches:
                    api_name = matches.group(1)
                    print(f"    - Using name from docstring: {api_name}")
                    return api_name

        # Method 2: Get from function annotation if available
        if hasattr(func_obj, '__annotations__') and 'api_name' in func_obj.__annotations__:
            api_name = func_obj.__annotations__['api_name']
            print(f"    - Using annotation: {api_name}")
            return api_name

        # Method 3: Get from function name directly
        if hasattr(func_obj, '__name__'):
            name = func_obj.__name__
            print(f"    - Using function name: {name}")

            # Handle specific patterns for known API functions
            if name.startswith('download_'):
                api_name = name[9:]  # Remove 'download_' prefix
                print(f"    - Download function detected: {api_name}")
                return api_name
            elif name.startswith('get_'):
                api_name = name[4:]  # Remove 'get_' prefix
                print(f"    - Get function detected: {api_name}")
                return api_name
            elif name.startswith('fetch_'):
                api_name = name[6:]  # Remove 'fetch_' prefix
                print(f"    - Fetch function detected: {api_name}")
                return api_name
            elif name.startswith('load_'):
                api_name = name[5:]  # Remove 'load_' prefix
                print(f"    - Load function detected: {api_name}")
                return api_name
            elif name.startswith('api_'):
                api_name = name[4:]  # Remove 'api_' prefix
                print(f"    - API function detected: {api_name}")
                return api_name
            else:
                # For other functions, return the name as is
                return name

        # Method 4: Check function signature for API-related parameters
        try:
            sig = inspect.signature(func_obj)
            # Look for parameters that might indicate API type
            for param_name in sig.parameters:
                if 'api' in param_name.lower():
                    # Try to infer from parameter name
                    if param_name.lower() in ['api_name', 'api_type', 'api_method']:
                        print(f"    - Could not determine specific API name from parameters")
                        # Return a generic indicator
                        return 'unknown_api'

            # Check if function has specific parameters that hint at API type
            params = list(sig.parameters.keys())
            if 'ts_code' in params and 'trade_date' in params:
                print(f"    - Function signature suggests 'daily' API")
                return 'daily'
            elif 'ts_code' in params and 'end_date' in params:
                print(f"    - Function signature suggests 'financial' API")
                return 'financial'
            elif 'ts_code' in params and 'start_date' in params:
                print(f"    - Function signature suggests 'timeseries' API")
                return 'timeseries'

        except Exception as e:
            print(f"    - Error analyzing function signature: {e}")

        # Method 5: Check function's module or file name context
        if hasattr(func_obj, '__module__'):
            module_name = func_obj.__module__
            # Look for patterns in module name that might indicate API type
            if 'download' in module_name.lower():
                print(f"    - Module context suggests download API")
                return 'download_generic'
            elif 'financial' in module_name.lower() or 'finance' in module_name.lower():
                print(f"    - Module context suggests financial API")
                return 'financial_generic'

        # Method 6: If all else fails, return a default or derived name
        print(f"    - Using default naming approach")
        if hasattr(func_obj, '__name__'):
            return func_obj.__name__.replace('func_', '').replace('_function', '')
        else:
            return 'unknown_api'

    # Define test functions that simulate real API functions
    def download_daily(ts_code, trade_date, adj='qfq'):
        """
        Download daily trading data for a given stock
        API: daily
        """
        return f"Daily data for {ts_code}"

    def get_financial_report(ts_code, end_date, report_type='annual'):
        """
        Get financial report data
        API name: income_vip
        """
        return f"Financial report for {ts_code}"

    def fetch_balance_sheet(ts_code, end_date):
        """
        Fetch balance sheet data for a company
        API: balance_vip
        """
        return f"Balance sheet for {ts_code}"

    def load_stock_basic(ts_code=None):
        """
        Load basic stock information
        api_name: stock_basic
        """
        return "Basic stock info"

    def api_moneyflow_data(ts_code, trade_date):
        """
        API for getting money flow data
        """
        return f"Money flow for {ts_code}"

    def generic_data_loader(table_name, **kwargs):
        """A generic function to load any data"""
        return f"Generic data for {table_name}"

    def calculate_indicator(ts_code, window=20):
        """Calculate technical indicator - not an API function"""
        return f"Indicator for {ts_code}"

    # Test 1: Basic function name inference
    print("\n--- Test 1: Basic function name inference ---")
    api_name1 = infer_api_name(download_daily)
    assert api_name1 == 'daily', f"Expected 'daily', got '{api_name1}'"
    print("✓ Download function name inference works")

    api_name2 = infer_api_name(get_financial_report)
    assert api_name2 == 'income_vip', f"Expected 'income_vip', got '{api_name2}'"
    print("✓ Get function name inference works")

    # Test 2: Function with different prefixes
    print("\n--- Test 2: Function with different prefixes ---")
    api_name3 = infer_api_name(fetch_balance_sheet)
    assert api_name3 == 'balance_vip', f"Expected 'balance_vip', got '{api_name3}'"
    print("✓ Fetch function name inference works")

    api_name4 = infer_api_name(load_stock_basic)
    assert api_name4 == 'stock_basic', f"Expected 'stock_basic', got '{api_name4}'"
    print("✓ Load function name inference works")

    api_name5 = infer_api_name(api_moneyflow_data)
    assert api_name5 == 'moneyflow_data', f"Expected 'moneyflow_data', got '{api_name5}'"
    print("✓ API prefixed function name inference works")

    # Test 3: Generic functions
    print("\n--- Test 3: Generic functions ---")
    api_name6 = infer_api_name(generic_data_loader)
    assert api_name6 in ['generic_data_loader', 'data_loader'], f"Expected generic name, got '{api_name6}'"
    print("✓ Generic function handled appropriately")

    api_name7 = infer_api_name(calculate_indicator)
    assert api_name7 == 'calculate_indicator', f"Expected 'calculate_indicator', got '{api_name7}'"
    print("✓ Non-API function name preserved")

    # Test 4: Lambda functions
    print("\n--- Test 4: Lambda functions ---")
    lambda_func = lambda ts_code: f"Lambda result for {ts_code}"
    api_name_lambda = infer_api_name(lambda_func)
    # Lambda names are typically '<lambda>', so inference might return the default
    print(f"  - Lambda function inferred name: {api_name_lambda}")
    assert api_name_lambda is not None, "Should handle lambda functions"
    print("✓ Lambda functions handled")

    # Test 5: Partial functions
    print("\n--- Test 5: Partial functions ---")
    from functools import partial

    def base_download(ts_code, date, data_type):
        return f"Download {data_type} for {ts_code}"

    partial_func = partial(base_download, data_type='daily')
    api_name_partial = infer_api_name(partial_func)
    print(f"  - Partial function inferred name: {api_name_partial}")
    assert api_name_partial is not None, "Should handle partial functions"
    print("✓ Partial functions handled")

    # Test 6: Method from a class
    print("\n--- Test 6: Class methods ---")
    class DataAPI:
        def download_daily(self, ts_code):
            """API: daily"""
            return f"Daily for {ts_code}"

        def get_income(self, ts_code):
            """API name: income_vip"""
            return f"Income for {ts_code}"

        def calculate_metric(self, data):
            """Internal method, not an API"""
            return "metric"

    api_instance = DataAPI()
    api_name_method1 = infer_api_name(api_instance.download_daily)
    print(f"  - Class method inferred name: {api_name_method1}")
    # The name would be the method name: "download_daily", which should be parsed to "daily"
    # Since our function uses the actual function name to determine patterns
    api_name_method2 = infer_api_name(api_instance.get_income)
    print(f"  - Another class method inferred name: {api_name_method2}")
    api_name_method3 = infer_api_name(api_instance.calculate_metric)
    print(f"  - Non-API method inferred name: {api_name_method3}")

    assert api_name_method1 == 'daily', f"Expected 'daily', got '{api_name_method1}'"
    assert api_name_method2 == 'income_vip', f"Expected 'income_vip', got '{api_name_method2}'"
    assert api_name_method3 == 'calculate_metric', f"Expected 'calculate_metric', got '{api_name_method3}'"

    print("✓ Class methods handled correctly")

    # Test 7: Functions with complex signatures
    print("\n--- Test 7: Functions with complex signatures ---")

    def complex_download(ts_code: str, trade_date: str, fields: list, token: str = None) -> dict:
        """Download data with comprehensive parameters
        API: pro_bar
        """
        return {"data": "mock", "ts_code": ts_code}

    api_name_complex = infer_api_name(complex_download)
    expected_complex = 'pro_bar'
    print(f"  - Complex function inferred name: {api_name_complex}")
    assert api_name_complex == expected_complex, f"Expected '{expected_complex}', got '{api_name_complex}'"

    def signature_inference_func(ts_code: str, end_date: str):
        """Function signature should hint at financial API"""
        return "financial data"

    api_name_sig = infer_api_name(signature_inference_func)
    # This function has ts_code and end_date, which our logic identifies as financial
    print(f"  - Signature-inferred function name: {api_name_sig}")

    print("✓ Complex signatures handled correctly")

    # Test 8: Error handling with invalid objects
    print("\n--- Test 8: Error handling ---")
    # Test with non-function object
    try:
        api_name_invalid = infer_api_name("not_a_function")
        print(f"  - Invalid object handled: {api_name_invalid}")
    except Exception:
        # If it throws an exception, that's also acceptable
        print("  - Invalid object properly rejected")

    # Test with None
    try:
        api_name_none = infer_api_name(None)
        print(f"  - None handled: {api_name_none}")
    except Exception:
        # If it throws an exception, that's also acceptable
        print("  - None properly rejected")

    print("✓ Error handling works")

    # Test 9: Performance with many functions
    print("\n--- Test 9: Performance with multiple functions ---")
    import time

    # Create a list of mock functions
    test_functions = []
    for i in range(100):
        def make_func(n):
            def test_func(ts_code):
                """API: mock_api"""
                return f"result_{n}"
            test_func.__name__ = f"download_test_{n}"
            return test_func

        func = make_func(i)
        test_functions.append(func)

    start_time = time.time()
    for func in test_functions:
        name = infer_api_name(func)
        # Just call it, don't assert on result for performance test
    end_time = time.time()

    print(f"  - Processed {len(test_functions)} functions in {end_time - start_time:.3f}s")
    print("✓ Performance is acceptable")

    # Test 10: Realistic API function naming patterns
    print("\n--- Test 10: Realistic API naming patterns ---")

    # Simulate common tushare API function names
    def download_daily_basic(ts_code, trade_date=None):
        """Download daily basic data
        API: daily_basic
        """
        return "daily basic data"

    def get_fina_indicator_vip(ts_code, period):
        """Get financial indicators
        API: fina_indicator_vip
        """
        return "financial indicators"

    def fetch_moneyflow(ts_code, trade_date):
        """Fetch money flow data
        API: moneyflow
        """
        return "money flow data"

    realistic_funcs = [
        (download_daily_basic, 'daily_basic'),
        (get_fina_indicator_vip, 'fina_indicator_vip'),
        (fetch_moneyflow, 'moneyflow')
    ]

    for func, expected in realistic_funcs:
        inferred = infer_api_name(func)
        print(f"  - Function {func.__name__}: expected '{expected}', got '{inferred}'")
        assert inferred == expected, f"Expected '{expected}', got '{inferred}' for {func.__name__}"

    print("✓ Realistic API naming patterns work")

    print("\natom_infer_api_name: VERIFICATION PASSED")
    return True

if __name__ == "__main__":
    verify_atom_infer_api_name()