import os
import glob

# Test script to verify insufficient memory management assumption
def test_insufficient_memory_management():
    """
    This test verifies that when processing large data downloads,
    there is no effective memory control mechanism, which could lead to memory overflow.
    """
    print("Testing insufficient memory management assumption...")

    # Look for patterns in the codebase that indicate memory management behavior
    app_dir = "/home/quan/testdata/aspipe_v4/app"
    memory_management_indicators = []

    # Look for memory-related patterns in all files
    all_files = glob.glob(f"{app_dir}/**/*.py", recursive=True)

    for file_path in all_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # Look for memory management patterns
                lines = content.split('\n')

                # Look for pandas operations that could cause memory issues
                for i, line in enumerate(lines):
                    if 'pd.concat' in line or 'pandas.concat' in line:
                        # Check if there's memory management around concat operations
                        before_concat = '\n'.join(lines[max(0, i-5):i])
                        after_concat = '\n'.join(lines[i:i+5])

                        has_memory_mgmt = any([
                            'del ' in before_concat + after_concat,
                            'gc.collect()' in before_concat + after_concat,
                            'memory' in before_concat + after_concat,
                            'chunk' in before_concat + after_concat
                        ])

                        if not has_memory_mgmt:
                            memory_management_indicators.append({
                                'file': file_path,
                                'pattern': 'pd.concat without memory management',
                                'code_snippet': f"Line {i+1}: {line.strip()}\nContext:\n{before_concat}\n{line.strip()}\n{after_concat}"
                            })

                    # Look for large data operations without memory control
                    if 'DataFrame' in line and ('concat' in line or 'merge' in line or 'join' in line):
                        before_ops = '\n'.join(lines[max(0, i-5):i])
                        after_ops = '\n'.join(lines[i:i+5])

                        has_memory_mgmt = any([
                            'chunk' in before_ops + after_ops,
                            'batch' in before_ops + after_ops,
                            'memory_limit' in before_ops + after_ops,
                            'gc.collect()' in before_ops + after_ops,
                            'del ' in before_ops + after_ops
                        ])

                        if not has_memory_mgmt:
                            memory_management_indicators.append({
                                'file': file_path,
                                'pattern': 'Large data operation without memory management',
                                'code_snippet': f"Line {i+1}: {line.strip()}\nContext:\n{before_ops}\n{line.strip()}\n{after_ops}"
                            })

                # Check for memory management imports or usage
                if 'gc' in content or 'memory' in content.lower():
                    # Look for explicit memory management code
                    gc_lines = [line for line in lines if 'gc.' in line or 'collect' in line.lower()]
                    if gc_lines:
                        for gc_line in gc_lines:
                            memory_management_indicators.append({
                                'file': file_path,
                                'pattern': 'Explicit memory management (gc.collect)',
                                'code_snippet': gc_line
                            })

                # Look for chunking or batch processing patterns
                has_chunking = any([
                    'chunksize' in content.lower(),
                    'chunk_size' in content.lower(),
                    'batch' in content.lower(),
                    'partition' in content.lower()
                ])

                if not has_chunking:
                    # Look for large data accumulation patterns
                    if 'all_data = []' in content or 'all_data.append(' in content:
                        # Check if data is accumulated in memory without chunking
                        if 'pd.concat' in content and 'all_data' in content:
                            memory_management_indicators.append({
                                'file': file_path,
                                'pattern': 'Accumulating large data in memory without chunking',
                                'code_snippet': content[:500]
                            })

        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    # Check for explicit memory management in key files
    for file_path in all_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # Look for memory management patterns in download functions
                if 'def ' in content and ('download' in content or 'fetch' in content):
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if line.strip().startswith('def ') and ('download' in line or 'fetch' in line):
                            # Look for memory-related code
                            func_start = i
                            func_end = len(lines)
                            for j in range(i+1, len(lines)):
                                if lines[j].strip().startswith('def ') or lines[j].strip().startswith('class '):
                                    func_end = j
                                    break

                            function_content = '\n'.join(lines[func_start:func_end])

                            # Check if function handles memory for large datasets
                            has_memory_mgmt = any([
                                'chunk' in function_content.lower(),
                                'batch' in function_content.lower(),
                                'gc.collect' in function_content,
                                'del ' in function_content
                            ])

                            if not has_memory_mgmt and ('pd.concat' in function_content or 'DataFrame' in function_content):
                                memory_management_indicators.append({
                                    'file': file_path,
                                    'pattern': f'Download function without memory management: {line.strip()}',
                                    'code_snippet': function_content[:500]
                                })

        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    print(f"Found {len(memory_management_indicators)} memory management indicators")

    # Check if the indicators show insufficient memory management
    # Look for patterns of problematic memory usage without proper management
    problematic_indicators = [ind for ind in memory_management_indicators if 'without' in ind['pattern']]

    has_insufficient_memory_management = len(problematic_indicators) > 0

    print(f"Insufficient memory management exists: {has_insufficient_memory_management}")
    print(f"Problematic memory management indicators: {len(problematic_indicators)}")

    if has_insufficient_memory_management:
        print("CONFIRMED: The system has insufficient memory management for large data downloads")
        print("This validates the assumption that there's no effective memory control mechanism")

        # Show specific evidence
        for i, indicator in enumerate(problematic_indicators[:5]):
            print(f"\nMemory Management Issue {i+1}: {indicator['pattern']} in {indicator['file']}")
            print(f"Code snippet:\n{indicator['code_snippet'][:500]}...")

        return True
    else:
        print("NOT CONFIRMED: The system may have sufficient memory management")
        return False

if __name__ == "__main__":
    result = test_insufficient_memory_management()
    print(f"Test result: {result}")