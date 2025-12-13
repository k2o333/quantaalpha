import os
import glob

# Test script to verify no concurrent download assumption
def test_no_concurrent_download():
    """
    This test verifies that all different types of data download tasks
    are executed sequentially, not taking advantage of multi-core CPU
    for parallel downloading of multiple data types.
    """
    print("Testing no concurrent download assumption...")

    # Look for patterns in the codebase that indicate sequential vs concurrent execution
    app_dir = "/home/quan/testdata/aspipe_v4/app"
    sequential_indicators = []
    concurrent_indicators = []

    # Look for the specific pattern in date_range_downloader.py
    date_range_path = f"{app_dir}/date_range_downloader.py"
    if os.path.exists(date_range_path):
        try:
            with open(date_range_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # Look for the main download function that shows sequential execution
                if 'def download_all_available_data' in content:
                    start_idx = content.find('def download_all_available_data')
                    end_idx = content.find('def ', start_idx + 50)  # Find next function or end
                    if end_idx == -1:
                        end_idx = len(content)

                    func_content = content[start_idx:end_idx]

                    # This function clearly shows sequential execution with a while loop
                    if 'while len(completed_tasks) < original_task_count and download_tasks:' in func_content:
                        sequential_indicators.append({
                            'file': date_range_path,
                            'pattern': 'Sequential download loop in download_all_available_data',
                            'code_snippet': func_content[start_idx:start_idx+800]
                        })

                    # Look for the task processing loop
                    if 'download_tasks[0]' in func_content and 'pop(0)' in func_content:
                        # This shows FIFO queue processing, which is sequential
                        loop_start = func_content.find('task_name, download_func, max_retries = download_tasks[0]')
                        snippet = func_content[loop_start:loop_start+1000]  # Get the loop and surrounding code

                        sequential_indicators.append({
                            'file': date_range_path,
                            'pattern': 'FIFO sequential task processing (the exact bottleneck)',
                            'code_snippet': snippet
                        })

                print(f"Found sequential download patterns in date_range_downloader.py: {len(sequential_indicators)} instances")
        except Exception as e:
            print(f"Error reading {date_range_path}: {e}")

    # Look for concurrent/parallel processing indicators in all files
    all_files = glob.glob(f"{app_dir}/**/*.py", recursive=True)
    for file_path in all_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # Look for concurrent/parallel processing indicators
                if any(pattern in content.lower() for pattern in ['asyncio', 'multiprocessing', 'concurrent.futures', 'threadpoolexecutor', 'processpoolexecutor']):
                    concurrent_indicators.append({
                        'file': file_path,
                        'pattern': 'Concurrent processing library found',
                        'code_snippet': content[:500]
                    })

                # Look for async/await patterns
                if 'async ' in content and 'await ' in content:
                    concurrent_indicators.append({
                        'file': file_path,
                        'pattern': 'Async/await pattern found',
                        'code_snippet': content[:500]
                    })

        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    print(f"Found {len(sequential_indicators)} sequential processing indicators")
    print(f"Found {len(concurrent_indicators)} concurrent processing indicators")

    # Summary
    # The assumption is validated if we find clear sequential patterns and few/no concurrent patterns
    has_no_concurrent_download = len(sequential_indicators) > 0 and len(concurrent_indicators) == 0

    print(f"No concurrent download exists: {has_no_concurrent_download}")
    print(f"Sequential indicators: {len(sequential_indicators)}")
    print(f"Concurrent indicators: {len(concurrent_indicators)}")

    if has_no_concurrent_download:
        print("CONFIRMED: The system executes different data download tasks sequentially")
        print("This validates the assumption that multiple data types are not downloaded in parallel")

        # Show specific evidence
        for i, indicator in enumerate(sequential_indicators):
            print(f"\nSequential Evidence {i+1}: {indicator['pattern']} in {indicator['file']}")
            print(f"Code snippet:\n{indicator['code_snippet']}")

        return True
    else:
        print("NOT CONFIRMED: The system may already use concurrent downloads")
        if len(concurrent_indicators) > 0:
            print("Found concurrent processing indicators:")
            for i, indicator in enumerate(concurrent_indicators[:3]):
                print(f"Concurrent Evidence {i+1}: {indicator['pattern']} in {indicator['file']}")
        return False

if __name__ == "__main__":
    result = test_no_concurrent_download()
    print(f"Test result: {result}")