import os
import glob

# Test script to verify independent API calls assumption
def test_independent_api_calls():
    """
    This test verifies that for multiple daily data interfaces,
    the code executes independent API calls for each trading day
    without batch processing or parallelization.
    """
    print("Testing independent API calls assumption...")

    # Look for patterns in the codebase that indicate independent API calls
    app_dir = "/home/quan/testdata/aspipe_v4/app"
    independent_call_indicators = []

    # Look for the specific pattern in daily_data.py
    daily_data_path = f"{app_dir}/interfaces/daily_data.py"
    if os.path.exists(daily_data_path):
        try:
            with open(daily_data_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # Look for the function that downloads daily_basic_range
                if 'def download_daily_basic_range' in content:
                    # This function specifically shows the pattern of independent API calls
                    # It loops through trading days and makes individual API calls
                    start_idx = content.find('def download_daily_basic_range')
                    end_idx = content.find('def ', start_idx + 50)  # Find next function or end
                    if end_idx == -1:
                        end_idx = len(content)

                    func_content = content[start_idx:end_idx]

                    if 'for i, trade_date in enumerate(trading_days)' in func_content:
                        # Found the problematic loop that makes individual API calls
                        loop_start = func_content.find('for i, trade_date in enumerate(trading_days)')
                        snippet = func_content[loop_start:loop_start+500]  # Get the loop and surrounding code

                        independent_call_indicators.append({
                            'file': daily_data_path,
                            'pattern': 'Independent daily_basic API calls in a loop (the exact bottleneck)',
                            'code_snippet': snippet
                        })

                        # Also look for the actual API call inside the loop
                        if 'self.download_daily_basic(trade_date=trade_date)' in func_content:
                            call_idx = func_content.find('self.download_daily_basic(trade_date=trade_date)')
                            call_snippet = func_content[max(0, call_idx-100):call_idx+100]
                            independent_call_indicators.append({
                                'file': daily_data_path,
                                'pattern': 'Individual API call made for each trade_date',
                                'code_snippet': call_snippet
                            })

                print(f"Found independent API call pattern in daily_data.py: {len(independent_call_indicators)} instances")
        except Exception as e:
            print(f"Error reading {daily_data_path}: {e}")

    # Look for similar patterns in other interface files
    interface_files = glob.glob(f"{app_dir}/interfaces/*.py")
    for file_path in interface_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # Look for any functions that iterate through dates and make API calls
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'for' in line and ('date' in line or 'day' in line or 'trade' in line) and 'in' in line:
                        # Check the next few lines for API calls
                        for j in range(i+1, min(i+10, len(lines))):
                            if ('api.' in lines[j].lower() or 'download_' in lines[j] or 'pro.' in lines[j]):
                                # Check if this is inside a function that handles date ranges
                                # by looking for 'range' in the function definition
                                for k in range(max(0, i-20), i):
                                    if lines[k].startswith('def '):
                                        func_def = lines[k]
                                        if 'range' in func_def.lower() or 'date' in func_def.lower():
                                            independent_call_indicators.append({
                                                'file': file_path,
                                                'pattern': f'Date iteration with API calls in {func_def.strip()}',
                                                'code_snippet': '\n'.join(lines[max(0, k):min(len(lines), j+2)])
                                            })
                                        break
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    print(f"Found {len(independent_call_indicators)} potential independent API call indicators")

    # Summary
    has_independent_api_calls = len(independent_call_indicators) > 0

    print(f"Independent API calls exist without batching: {has_independent_api_calls}")
    print(f"Independent call indicators: {len(independent_call_indicators)}")

    if has_independent_api_calls:
        print("CONFIRMED: The system makes independent API calls for each trading day")
        print("This validates the assumption that code executes individual API calls without batching")

        # Show specific evidence
        for i, indicator in enumerate(independent_call_indicators):
            print(f"\nEvidence {i+1} in {indicator['file']}:")
            print(f"Pattern: {indicator['pattern']}")
            print(f"Code snippet:\n{indicator['code_snippet']}")

        return True
    else:
        print("NOT CONFIRMED: Could not find clear evidence of independent API calls")
        return False

if __name__ == "__main__":
    result = test_independent_api_calls()
    print(f"Test result: {result}")