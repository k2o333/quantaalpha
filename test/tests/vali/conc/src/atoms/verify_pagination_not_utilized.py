import os
import glob

# Test script to verify pagination not utilized assumption
def test_pagination_not_utilized():
    """
    This test verifies that multiple interfaces support pagination features
    but are not fully utilized, such as cyq_perf with max 5000 per call,
    cyq_chips with max 2000 per call, stk_factor with max 10000 per call, etc.
    """
    print("Testing pagination not utilized assumption...")

    # Look for patterns in the codebase that indicate pagination usage
    app_dir = "/home/quan/testdata/aspipe_v4/app"
    pagination_utilized_indicators = []
    pagination_not_utilized_indicators = []

    # Check interface files for pagination usage
    all_files = glob.glob(f"{app_dir}/**/*.py", recursive=True)

    for file_path in all_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # Look for specific interfaces mentioned in the assumption
                if 'cyq_perf' in content or 'cyq_chips' in content or 'stk_factor' in content:
                    # Check if pagination is used for these interfaces
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        # Check for cyq_perf usage
                        if 'cyq_perf' in line:
                            # Look for pagination parameters
                            has_limit_offset = any([
                                'limit=' in line or 'offset=' in line,
                                'limit=' in content[i-10:i+10] or 'offset=' in content[i-10:i+10]
                            ])

                            if has_limit_offset:
                                pagination_utilized_indicators.append({
                                    'file': file_path,
                                    'pattern': 'cyq_perf with pagination parameters',
                                    'code_snippet': line.strip()
                                })
                            else:
                                pagination_not_utilized_indicators.append({
                                    'file': file_path,
                                    'pattern': 'cyq_perf without pagination parameters',
                                    'code_snippet': line.strip()
                                })

                        # Check for cyq_chips usage
                        if 'cyq_chips' in line:
                            # Look for pagination parameters
                            has_limit_offset = any([
                                'limit=' in line or 'offset=' in line,
                                'limit=' in content[i-10:i+10] or 'offset=' in content[i-10:i+10]
                            ])

                            if has_limit_offset:
                                pagination_utilized_indicators.append({
                                    'file': file_path,
                                    'pattern': 'cyq_chips with pagination parameters',
                                    'code_snippet': line.strip()
                                })
                            else:
                                pagination_not_utilized_indicators.append({
                                    'file': file_path,
                                    'pattern': 'cyq_chips without pagination parameters',
                                    'code_snippet': line.strip()
                                })

                        # Check for stk_factor usage
                        if 'stk_factor' in line:
                            # Look for pagination parameters
                            has_limit_offset = any([
                                'limit=' in line or 'offset=' in line,
                                'limit=' in content[i-10:i+10] or 'offset=' in content[i-10:i+10]
                            ])

                            if has_limit_offset:
                                pagination_utilized_indicators.append({
                                    'file': file_path,
                                    'pattern': 'stk_factor with pagination parameters',
                                    'code_snippet': line.strip()
                                })
                            else:
                                pagination_not_utilized_indicators.append({
                                    'file': file_path,
                                    'pattern': 'stk_factor without pagination parameters',
                                    'code_snippet': line.strip()
                                })

                # Look for general pagination patterns
                if 'def ' in content and ('download' in content or 'get_' in content):
                    # Check for functions that could use pagination but don't
                    if 'limit=' not in content and 'offset=' not in content:
                        # Look for pagination-capable functions that don't use pagination
                        if any(interface in content for interface in ['daily', 'income', 'balancesheet', 'cashflow']):
                            pagination_not_utilized_indicators.append({
                                'file': file_path,
                                'pattern': f'Potential pagination-capable function without pagination: found interface-related function without limit/offset',
                                'code_snippet': content[:500]
                            })

                # Check for the pagination download function in tushare_api.py
                if 'download_with_pagination' in content:
                    # This is the pagination function, check how it's used
                    pagination_utilized_indicators.append({
                        'file': file_path,
                        'pattern': 'download_with_pagination function found',
                        'code_snippet': content[content.find('download_with_pagination'):content.find('download_with_pagination')+300]
                    })

                    # Check if it's actually used for the specified interfaces
                    if 'cyq_' in content or 'stk_factor' in content:
                        # Check if this function is called with these interfaces
                        pagination_lines = content.split('\n')
                        for j, pag_line in enumerate(pagination_lines):
                            if 'download_with_pagination' in pag_line and any(interface in pag_line for interface in ['cyq_', 'stk_factor']):
                                pagination_utilized_indicators.append({
                                    'file': file_path,
                                    'pattern': 'download_with_pagination used with cyq_/stk_factor interfaces',
                                    'code_snippet': pag_line.strip()
                                })

        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    # Check specifically for usage of download_with_pagination function
    tushare_api_path = f"{app_dir}/tushare_api.py"
    if os.path.exists(tushare_api_path):
        try:
            with open(tushare_api_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # Look for the download_with_pagination function
                if 'def download_with_pagination' in content:
                    start_idx = content.find('def download_with_pagination')
                    end_idx = content.find('\n\ndef ', start_idx + 10)
                    if end_idx == -1:
                        end_idx = len(content)

                    pagination_func_content = content[start_idx:end_idx]

                    # Check if this function exists and is well-implemented
                    pagination_utilized_indicators.append({
                        'file': tushare_api_path,
                        'pattern': 'download_with_pagination function exists and is well-implemented',
                        'code_snippet': pagination_func_content[:800]
                    })

                    # Check if this function is actually called for specific interfaces
                    for interface in ['cyq_perf', 'cyq_chips', 'stk_factor']:
                        if f'api_func' in content and interface in content:
                            # Check if there are calls that could use pagination but don't
                            lines = content.split('\n')
                            for i, line in enumerate(lines):
                                if interface in line and 'download_with_pagination' not in line:
                                    pagination_not_utilized_indicators.append({
                                        'file': tushare_api_path,
                                        'pattern': f'{interface} interface used without pagination',
                                        'code_snippet': line.strip()
                                    })

        except Exception as e:
            print(f"Error reading {tushare_api_path}: {e}")

    print(f"Found {len(pagination_utilized_indicators)} pagination utilized indicators")
    print(f"Found {len(pagination_not_utilized_indicators)} pagination not utilized indicators")

    # The assumption is validated if pagination is not properly utilized for specified interfaces
    has_pagination_not_utilized = len(pagination_not_utilized_indicators) > 0

    print(f"Pagination not utilized exists: {has_pagination_not_utilized}")
    print(f"Pagination utilized indicators: {len(pagination_utilized_indicators)}")
    print(f"Pagination not utilized indicators: {len(pagination_not_utilized_indicators)}")

    if has_pagination_not_utilized:
        print("CONFIRMED: The system does not fully utilize pagination features for supported interfaces")
        print("This validates the assumption that pagination is not fully utilized for interfaces like cyq_perf, cyq_chips, and stk_factor")

        # Show specific evidence
        for i, indicator in enumerate(pagination_not_utilized_indicators[:5]):
            print(f"\nPagination Not Utilized Evidence {i+1}: {indicator['pattern']} in {indicator['file']}")
            print(f"Code snippet: {indicator['code_snippet']}")

        return True
    else:
        print("NOT CONFIRMED: The system may fully utilize pagination features")
        if len(pagination_utilized_indicators) > 0:
            print("Found pagination utilization indicators:")
            for i, indicator in enumerate(pagination_utilized_indicators[:3]):
                print(f"Pagination Utilized Evidence {i+1}: {indicator['pattern']} in {indicator['file']}")
                print(f"Code snippet: {indicator['code_snippet'][:200]}...")
        return False

if __name__ == "__main__":
    result = test_pagination_not_utilized()
    print(f"Test result: {result}")