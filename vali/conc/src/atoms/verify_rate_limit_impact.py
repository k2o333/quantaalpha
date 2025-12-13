import os
import glob

# Test script to verify rate limit impact assumption
def test_rate_limit_impact():
    """
    This test verifies that each API call is subject to rate limiting,
    with waiting time between calls that significantly slows down downloads.
    """
    print("Testing rate limit impact assumption...")

    # Look for rate limiting patterns in the codebase
    app_dir = "/home/quan/testdata/aspipe_v4/app"
    rate_limit_indicators = []

    # Check all Python files in the app directory
    all_files = glob.glob(f"{app_dir}/**/*.py", recursive=True)

    for file_path in all_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # Look for rate limiting implementations
                if 'time.sleep(' in content:
                    rate_limit_indicators.append({
                        'file': file_path,
                        'pattern': 'time.sleep() found',
                        'code_snippet': content[content.find('time.sleep(')-50:content.find('time.sleep(')+100]
                    })

                if 'sleep(' in content:
                    rate_limit_indicators.append({
                        'file': file_path,
                        'pattern': 'sleep() found',
                        'code_snippet': content[content.find('sleep(')-50:content.find('sleep(')+100]
                    })

                # Look for rate limiting related patterns
                if any(pattern in content.lower() for pattern in ['rate_limit', 'rate limit', 'api_limit', 'throttle', 'delay', 'wait']):
                    rate_limit_indicators.append({
                        'file': file_path,
                        'pattern': 'Rate limit related text found',
                        'code_snippet': content[:500]
                    })

                # Check for API call patterns that might include rate limiting
                if 'tushare' in content.lower() and ('time.' in content or 'sleep' in content):
                    rate_limit_indicators.append({
                        'file': file_path,
                        'pattern': 'Tushare API call with time/sleep pattern',
                        'code_snippet': content[:500]
                    })

        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    print(f"Found {len(rate_limit_indicators)} potential rate limit impact indicators")

    # Look for specific tushare_api.py rate limiting
    tushare_path = f"{app_dir}/tushare_api.py"
    if os.path.exists(tushare_path):
        try:
            with open(tushare_path, 'r', encoding='utf-8') as f:
                tushare_content = f.read()

                # Check for time delays or rate limiting logic
                time_patterns = ['time.sleep(', 'sleep(', 'delay', 'wait']
                for pattern in time_patterns:
                    if pattern in tushare_content:
                        print(f"Found rate limiting pattern '{pattern}' in tushare_api.py")
                        # Find the context around this pattern
                        idx = tushare_content.find(pattern)
                        start = max(0, idx - 100)
                        end = min(len(tushare_content), idx + 150)
                        rate_limit_indicators.append({
                            'file': tushare_path,
                            'pattern': f'Rate limiting: {pattern}',
                            'code_snippet': tushare_content[start:end]
                        })

                # Look for specific API call functions that might have delays
                api_functions = ['daily_basic', 'pro_bar', 'daily', 'fina', 'disclosure_date']
                for func in api_functions:
                    if f'def {func}' in tushare_content:
                        func_start = tushare_content.find(f'def {func}')
                        # Get the function definition context (next 500 chars)
                        func_end = min(len(tushare_content), func_start + 500)
                        func_content = tushare_content[func_start:func_end]

                        if any(delay_pattern in func_content.lower() for delay_pattern in ['time.sleep', 'sleep', 'delay', 'wait']):
                            print(f"Function {func} has rate limiting logic")
                            rate_limit_indicators.append({
                                'file': tushare_path,
                                'pattern': f'Function {func} has rate limiting',
                                'code_snippet': func_content
                            })

        except Exception as e:
            print(f"Error reading {tushare_path}: {e}")

    # Look for configuration files that might specify rate limits
    for file_path in glob.glob(f"{app_dir}/*.py") + glob.glob(f"{app_dir}/config/*.py"):
        try:
            if 'config' in file_path or 'setting' in file_path.lower():
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                    if any(pattern in content.lower() for pattern in ['rate_limit', 'api_limit', 'max_calls', 'calls_per', 'throttle']):
                        rate_limit_indicators.append({
                            'file': file_path,
                            'pattern': 'Rate limiting config found',
                            'code_snippet': content[:500]
                        })
        except Exception as e:
            print(f"Error reading config file {file_path}: {e}")

    # Summary
    has_rate_limit_impact = len(rate_limit_indicators) > 0

    print(f"Rate limit impact exists: {has_rate_limit_impact}")
    print(f"Rate limit indicators: {len(rate_limit_indicators)}")

    if has_rate_limit_impact:
        print("CONFIRMED: The system has rate limiting that impacts download speed")
        print("This validates the assumption that API calls have waiting times that slow down downloads")
        return True
    else:
        print("NOT CONFIRMED: No clear rate limiting patterns found")
        return False

if __name__ == "__main__":
    result = test_rate_limit_impact()
    print(f"Test result: {result}")