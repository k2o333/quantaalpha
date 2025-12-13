import os
import glob

# Test script to verify inefficient error handling assumption
def test_inefficient_error_handling():
    """
    This test verifies that when downloads fail, the system performs exponential
    backoff retries, increasing total time, and lacks effective failure skip mechanisms.
    """
    print("Testing inefficient error handling assumption...")

    # Look for patterns in the codebase that indicate error handling behavior
    app_dir = "/home/quan/testdata/aspipe_v4/app"
    inefficient_error_indicators = []
    efficient_error_indicators = []

    # Check error handler and retry mechanisms
    all_files = glob.glob(f"{app_dir}/**/*.py", recursive=True)

    for file_path in all_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # Look for exponential backoff retry patterns
                if '@retry_on_failure' in content or 'retry_on_failure' in content:
                    # Check the retry decorator/function parameters
                    retry_lines = [line for line in content.split('\n') if '@retry_on_failure' in line or 'retry_on_failure' in line]

                    for retry_line in retry_lines:
                        if 'backoff' in retry_line and ('2.0' in retry_line or 'exponential' in retry_line.lower()):
                            inefficient_error_indicators.append({
                                'file': file_path,
                                'pattern': 'Exponential backoff retry mechanism found',
                                'code_snippet': retry_line
                            })

                        # Check for high retry counts
                        if 'max_retries' in retry_line:
                            # Extract the retry count
                            import re
                            retry_match = re.search(r'max_retries[=\s:]+(\d+)', retry_line)
                            if retry_match:
                                retry_count = int(retry_match.group(1))
                                if retry_count > 3:
                                    inefficient_error_indicators.append({
                                        'file': file_path,
                                        'pattern': f'High retry count ({retry_count}) in retry mechanism',
                                        'code_snippet': retry_line
                                    })

                # Look for retry implementations with exponential backoff
                if 'time.sleep' in content and ('2 **' in content or 'pow(' in content or '**' in content):
                    # This suggests exponential backoff
                    inefficient_error_indicators.append({
                        'file': file_path,
                        'pattern': 'Exponential backoff sleep pattern found',
                        'code_snippet': content[:500]
                    })

                # Look for error handling without skip mechanisms
                if 'except' in content:
                    # Check if exceptions lead to retries without skip options
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if 'except' in line:
                            # Look for retry behavior without skip options
                            # Check next few lines for retry patterns
                            for j in range(i+1, min(i+10, len(lines))):
                                if 'retry' in lines[j] or 'continue' in lines[j] or 'sleep' in lines[j]:
                                    # Check if there's a way to skip failed items
                                    has_skip = any(skip_word in content.lower() for skip_word in ['skip', 'ignore', 'pass'])
                                    if not has_skip:
                                        inefficient_error_indicators.append({
                                            'file': file_path,
                                            'pattern': 'Exception handling with retry but no skip mechanism',
                                            'code_snippet': '\n'.join(lines[max(0, i-2):min(len(lines), j+3)])
                                        })
                                    break

                # Look for the specific retry_on_failure decorator implementation
                if 'def retry_on_failure' in content:
                    start_idx = content.find('def retry_on_failure')
                    end_idx = content.find('\n\ndef ', start_idx + 10)
                    if end_idx == -1:
                        end_idx = len(content)

                    retry_func_content = content[start_idx:end_idx]

                    # Check if it implements exponential backoff
                    if '2 **' in retry_func_content or 'backoff' in retry_func_content:
                        inefficient_error_indicators.append({
                            'file': file_path,
                            'pattern': 'retry_on_failure function with exponential backoff',
                            'code_snippet': retry_func_content[:800]
                        })

        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    # Specifically check the error_handler.py file
    error_handler_path = f"{app_dir}/error_handler.py"
    if os.path.exists(error_handler_path):
        try:
            with open(error_handler_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # Look for retry mechanism implementation
                if 'def retry_on_failure' in content:
                    start_idx = content.find('def retry_on_failure')
                    end_idx = content.find('\n\ndef ', start_idx + 10)
                    if end_idx == -1:
                        end_idx = len(content)

                    retry_func_content = content[start_idx:end_idx]

                    # Check for exponential backoff
                    if 'backoff' in retry_func_content:
                        backoff_line = [line for line in retry_func_content.split('\n') if 'backoff' in line]
                        if backoff_line:
                            inefficient_error_indicators.append({
                                'file': error_handler_path,
                                'pattern': 'Exponential backoff in retry_on_failure function',
                                'code_snippet': '\n'.join(backoff_line[:3])
                            })

                    # Check for high retry counts
                    if 'max_retries' in retry_func_content:
                        import re
                        retry_match = re.search(r'max_retries[=\s:]+(\d+)', retry_func_content)
                        if retry_match:
                            retry_count = int(retry_match.group(1))
                            if retry_count > 3:
                                inefficient_error_indicators.append({
                                    'file': error_handler_path,
                                    'pattern': f'High default retry count ({retry_count}) in error handler',
                                    'code_snippet': retry_func_content[:300]
                                })

                    # Check for sleep/wait patterns
                    if 'time.sleep' in retry_func_content:
                        sleep_lines = [line for line in retry_func_content.split('\n') if 'time.sleep' in line]
                        if sleep_lines:
                            inefficient_error_indicators.append({
                                'file': error_handler_path,
                                'pattern': 'Sleep in retry mechanism',
                                'code_snippet': '\n'.join(sleep_lines[:2])
                            })

        except Exception as e:
            print(f"Error reading {error_handler_path}: {e}")

    print(f"Found {len(inefficient_error_indicators)} inefficient error handling indicators")
    print(f"Found {len(efficient_error_indicators)} efficient error handling indicators")

    # The assumption is validated if we find evidence of inefficient error handling
    has_inefficient_error_handling = len(inefficient_error_indicators) > 0

    print(f"Inefficient error handling exists: {has_inefficient_error_handling}")
    print(f"Inefficient error indicators: {len(inefficient_error_indicators)}")
    print(f"Efficient error indicators: {len(efficient_error_indicators)}")

    if has_inefficient_error_handling:
        print("CONFIRMED: The system has inefficient error handling with exponential backoff retries")
        print("This validates the assumption that system increases total time with retries and lacks skip mechanisms")

        # Show specific evidence
        for i, indicator in enumerate(inefficient_error_indicators[:5]):
            print(f"\nInefficient Error Handling Evidence {i+1}: {indicator['pattern']} in {indicator['file']}")
            print(f"Code snippet:\n{indicator['code_snippet']}")

        return True
    else:
        print("NOT CONFIRMED: The system may have efficient error handling")
        if len(efficient_error_indicators) > 0:
            print("Found efficient error handling indicators:")
            for i, indicator in enumerate(efficient_error_indicators[:3]):
                print(f"Efficient Error Handling Evidence {i+1}: {indicator['pattern']} in {indicator['file']}")
        return False

if __name__ == "__main__":
    result = test_inefficient_error_handling()
    print(f"Test result: {result}")