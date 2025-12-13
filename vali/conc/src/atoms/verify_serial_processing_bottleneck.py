import time
import os
import glob

# Test script to verify serial processing bottleneck assumption
def test_serial_vs_parallel_processing():
    """
    This test verifies that the current implementation uses serial processing
    which creates a bottleneck, especially for daily_basic and other interfaces
    that use day-by-day downloads.
    """
    print("Testing serial vs parallel processing assumption...")

    # First, let's analyze the codebase to identify if serial processing exists
    app_dir = "/home/quan/testdata/aspipe_v4/app"
    serial_indicators = []

    # Look for code that processes daily data in a serial manner
    interface_files = glob.glob(f"{app_dir}/interfaces/*.py")

    for file_path in interface_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # Check for serial processing patterns
                if 'for' in content and 'range(' in content and ('tushare' in content.lower() or 'api' in content.lower()):
                    # Look for loops that process dates one by one
                    if any(pattern in content.lower() for pattern in ['for date', 'for day', 'for daily', 'for trade_date']):
                        serial_indicators.append({
                            'file': file_path,
                            'pattern': 'Found date/daily loop pattern',
                            'code_snippet': content[:500]  # First 500 chars as example
                        })

                # Look for serial API calls
                api_call_count = content.count('api.') if 'api.' in content else 0
                if api_call_count > 1 and not any(pattern in content for pattern in ['async', 'await', 'thread', 'process']):
                    serial_indicators.append({
                        'file': file_path,
                        'pattern': f'Multiple API calls ({api_call_count}) without async/thread pattern',
                        'code_snippet': content[:500]
                    })
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    print(f"Found {len(serial_indicators)} potential serial processing indicators")

    # Now let's check if tushare_api.py has serial processing
    tushare_path = f"{app_dir}/tushare_api.py"
    if os.path.exists(tushare_path):
        try:
            with open(tushare_path, 'r', encoding='utf-8') as f:
                tushare_content = f.read()

                # Look for serial execution patterns
                serial_methods = []
                if 'def daily_basic' in tushare_content:
                    serial_methods.append('daily_basic')
                if 'def pro_bar' in tushare_content:
                    serial_methods.append('pro_bar')

                print(f"Found potential serial processing methods: {serial_methods}")

                # Check for rate limiting that causes serial delays
                if 'time.sleep(' in tushare_content or 'sleep(' in tushare_content:
                    print("Found rate limiting with sleep() calls that cause serial delays")
                    # Find the sleep call snippet
                    sleep_index = tushare_content.find('sleep(')
                    snippet_start = max(0, sleep_index - 50)
                    snippet_end = min(len(tushare_content), sleep_index + 100)
                    serial_indicators.append({
                        'file': tushare_path,
                        'pattern': 'Rate limiting with sleep calls',
                        'code_snippet': tushare_content[snippet_start:snippet_end]
                    })
        except Exception as e:
            print(f"Error reading {tushare_path}: {e}")

    # Verify that there are no parallel processing patterns
    parallel_indicators = []
    for file_path in interface_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # Look for parallel processing indicators
                if any(pattern in content.lower() for pattern in ['async', 'concurrent', 'multiprocessing', 'threadpool', 'parallel']):
                    parallel_indicators.append(file_path)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    print(f"Found {len(parallel_indicators)} files with potential parallel processing (should be few/none for bottleneck to exist)")

    # Summary
    has_serial_bottleneck = len(serial_indicators) > 0 and len(parallel_indicators) < 3  # Assuming few parallel elements

    print(f"Serial processing bottleneck exists: {has_serial_bottleneck}")
    print(f"Serial indicators: {len(serial_indicators)}")
    print(f"Parallel indicators: {len(parallel_indicators)}")

    if has_serial_bottleneck:
        print("CONFIRMED: The system has serial processing bottlenecks")
        print("This validates the assumption that current implementation uses serial processing for daily data")
        return True
    else:
        print("NOT CONFIRMED: The system may already have parallel processing")
        return False

if __name__ == "__main__":
    result = test_serial_vs_parallel_processing()
    print(f"Test result: {result}")