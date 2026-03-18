import os
import glob

# Test script to verify no cache mechanism assumption
def test_no_cache_mechanism():
    """
    This test verifies that the system does not check for already downloaded
    data files, re-downloading regardless of file existence, causing unnecessary
    API calls and duplicate work.
    """
    print("Testing no cache mechanism assumption...")

    # Look specifically for evidence that download functions don't check for existing files
    app_dir = "/home/quan/testdata/aspipe_v4/app"
    no_cache_indicators = []
    cache_indicators = []

    # Check interface files where download functions are implemented
    interface_files = glob.glob(f"{app_dir}/interfaces/*.py")
    for file_path in interface_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # Look for download functions and check if they check for existing files
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if line.strip().startswith('def ') and ('download_' in line or 'get_' in line):
                        # Find the function body
                        func_start = i
                        func_end = len(lines)
                        for j in range(i+1, len(lines)):
                            if lines[j].strip().startswith('def ') or lines[j].strip().startswith('class '):
                                func_end = j
                                break

                        function_content = '\n'.join(lines[func_start:func_end])

                        # Check if the function makes API calls without checking for existing files
                        if 'api.' in function_content or '.pro.' in function_content:
                            # Look for any file existence checks in the function
                            has_file_check = any(check in function_content.lower() for check in [
                                'os.path.exists', 'path.exists', 'exists', 'exist', 'load_from_parquet',
                                'pd.read_parquet', 'pd.read_csv', 'file exists', 'already exists'
                            ])

                            # Look for any save operations in the function
                            has_save = any(save_pattern in function_content.lower() for save_pattern in [
                                'save_to_parquet', 'to_parquet', 'to_csv', 'save'
                            ])

                            if has_save and not has_file_check:
                                # Function saves data without checking if it exists first
                                no_cache_indicators.append({
                                    'file': file_path,
                                    'pattern': f'Download function makes API call and saves without existence check: {line.strip()}',
                                    'code_snippet': function_content[:500]
                                })

        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    # Check the save_to_parquet function specifically
    data_storage_path = f"{app_dir}/data_storage.py"
    if os.path.exists(data_storage_path):
        try:
            with open(data_storage_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # Check if save_to_parquet function checks for file existence
                if 'def save_to_parquet' in content:
                    start_idx = content.find('def save_to_parquet')
                    # Find end of function
                    end_idx = content.find('\n\ndef ', start_idx + 10)
                    if end_idx == -1:
                        end_idx = len(content)

                    save_func_content = content[start_idx:end_idx]

                    # Check if it checks for file existence
                    if 'os.path.exists' not in save_func_content.lower():
                        no_cache_indicators.append({
                            'file': data_storage_path,
                            'pattern': 'save_to_parquet function overwrites without checking existence',
                            'code_snippet': save_func_content[:800]
                        })
                        print(f"Found save_to_parquet without existence check in {data_storage_path}")
                    else:
                        cache_indicators.append({
                            'file': data_storage_path,
                            'pattern': 'save_to_parquet function with existence check',
                            'code_snippet': save_func_content[:800]
                        })
        except Exception as e:
            print(f"Error reading {data_storage_path}: {e}")

    print(f"Found {len(no_cache_indicators)} no-cache indicators")
    print(f"Found {len(cache_indicators)} cache indicators")

    # The key evidence: download functions directly call APIs and save without checking existence
    has_no_cache_mechanism = len(no_cache_indicators) > 0

    print(f"No cache mechanism exists: {has_no_cache_mechanism}")
    print(f"No cache indicators: {len(no_cache_indicators)}")
    print(f"Cache indicators: {len(cache_indicators)}")

    if has_no_cache_mechanism:
        print("CONFIRMED: The system does not check for already downloaded data files")
        print("This validates the assumption that system re-downloads regardless of file existence")

        # Show specific evidence
        for i, indicator in enumerate(no_cache_indicators[:5]):
            print(f"\nNo-cache Evidence {i+1}: {indicator['pattern']} in {indicator['file']}")
            print(f"Code snippet:\n{indicator['code_snippet'][:300]}...")

        return True
    else:
        print("NOT CONFIRMED: The system may already have a cache mechanism")
        if len(cache_indicators) > 0:
            print("Found cache mechanism indicators:")
            for i, indicator in enumerate(cache_indicators[:3]):
                print(f"Cache Evidence {i+1}: {indicator['pattern']} in {indicator['file']}")
        return False

if __name__ == "__main__":
    result = test_no_cache_mechanism()
    print(f"Test result: {result}")