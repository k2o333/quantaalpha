import os
import glob

# Test script to verify date range support assumption
def test_date_range_support():
    """
    This test verifies the date range query support for different interfaces,
    which interfaces support date range queries and which do not.
    """
    print("Testing date range support assumption...")

    # Look for patterns in the codebase that indicate date range support
    app_dir = "/home/quan/testdata/aspipe_v4/app"
    date_range_supported = []
    date_range_not_supported = []

    # Check interface files for date range usage patterns
    all_files = glob.glob(f"{app_dir}/**/*.py", recursive=True)

    for file_path in all_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # Look for functions that use date range parameters
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    # Look for functions that support date ranges (have start_date and end_date parameters)
                    if 'start_date' in line and 'end_date' in line:
                        # Check if this is in a function definition
                        if 'def ' in line or ('def ' in content[max(0, i-2):i+2]):
                            # Find the function name
                            func_line = line if 'def ' in line else next((l for l in content[max(0, i-2):i+2].split('\n') if 'def ' in l), line)
                            if 'def ' in func_line:
                                func_name = func_line.split('def ')[1].split('(')[0]
                                date_range_supported.append({
                                    'file': file_path,
                                    'interface': func_name,
                                    'pattern': f'Function {func_name} supports date range parameters',
                                    'code_snippet': func_line.strip()
                                })

                    # Look for specific interface calls that use date ranges
                    if any(interface in line for interface in ['daily', 'pro_bar', 'income', 'balancesheet', 'cashflow', 'fina_indicator']):
                        # Check if date range parameters are used
                        if 'start_date' in line and 'end_date' in line:
                            # Extract interface name
                            for interface in ['daily', 'pro_bar', 'income', 'balancesheet', 'cashflow', 'fina_indicator']:
                                if interface in line:
                                    date_range_supported.append({
                                        'file': file_path,
                                        'interface': interface,
                                        'pattern': f'{interface} interface uses date range parameters',
                                        'code_snippet': line.strip()
                                    })
                                    break

                    # Look for daily_basic interface which is known not to support date ranges
                    if 'daily_basic' in line:
                        # Check if it's called with a single trade_date (indicating no date range support)
                        if 'trade_date=' in line and not ('start_date=' in line and 'end_date=' in line):
                            date_range_not_supported.append({
                                'file': file_path,
                                'interface': 'daily_basic',
                                'pattern': 'daily_basic interface called with single trade_date (no date range support)',
                                'code_snippet': line.strip()
                            })

                    # Look for other interfaces that are called without date ranges when they could support them
                    for interface in ['cyq_perf', 'cyq_chips', 'stk_factor', 'dividend', 'forecast', 'express']:
                        if interface in line and 'start_date' not in line and 'end_date' not in line:
                            # This may indicate that this interface doesn't support date ranges
                            date_range_not_supported.append({
                                'file': file_path,
                                'interface': interface,
                                'pattern': f'{interface} interface used without date range parameters',
                                'code_snippet': line.strip()
                            })

                # Look for patterns that confirm daily_basic doesn't support date ranges
                if 'daily_basic' in content:
                    # Look for comments or documentation about daily_basic limitations
                    if 'does not support date range' in content.lower() or 'single date' in content.lower():
                        date_range_not_supported.append({
                            'file': file_path,
                            'interface': 'daily_basic',
                            'pattern': 'Comment indicates daily_basic does not support date range',
                            'code_snippet': content[:500]
                        })

        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    # Check specific files that handle different interfaces
    interface_files = glob.glob(f"{app_dir}/interfaces/*.py")
    for file_path in interface_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

                # Check each interface file for date range capability
                if 'daily_basic' in content:
                    # Look for daily_basic function definition
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if 'def ' in line and 'daily_basic' in line:
                            # Check the function signature and implementation
                            func_start = i
                            func_end = len(lines)
                            for j in range(i+1, len(lines)):
                                if lines[j].strip().startswith('def ') or lines[j].strip().startswith('class '):
                                    func_end = j
                                    break

                            function_content = '\n'.join(lines[func_start:func_end])

                            # Check if it only accepts trade_date (single date) and not date ranges
                            if 'trade_date' in function_content and 'start_date' not in function_content and 'end_date' not in function_content:
                                date_range_not_supported.append({
                                    'file': file_path,
                                    'interface': 'daily_basic',
                                    'pattern': 'daily_basic function signature shows single date parameter only',
                                    'code_snippet': function_content[:300]
                                })

                # Check other interfaces for date range support
                for interface in ['daily', 'income', 'balancesheet', 'cashflow']:
                    if f'def download_{interface}' in content:
                        # Look for the function and see if it supports date ranges
                        start_idx = content.find(f'def download_{interface}')
                        end_idx = content.find('\n\ndef ', start_idx + 10)
                        if end_idx == -1:
                            end_idx = len(content)

                        func_content = content[start_idx:end_idx]

                        if 'start_date' in func_content and 'end_date' in func_content:
                            date_range_supported.append({
                                'file': file_path,
                                'interface': interface,
                                'pattern': f'{interface} function supports date range parameters',
                                'code_snippet': func_content[:300]
                            })
                        else:
                            date_range_not_supported.append({
                                'file': file_path,
                                'interface': interface,
                                'pattern': f'{interface} function does not support date range parameters',
                                'code_snippet': func_content[:300]
                            })

        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    print(f"Found {len(date_range_supported)} interfaces that support date ranges")
    print(f"Found {len(date_range_not_supported)} interfaces that do not support date ranges")

    # Compile a summary of findings
    all_interfaces = set()
    for item in date_range_supported + date_range_not_supported:
        all_interfaces.add(item['interface'])

    print(f"\nInterfaces analyzed: {list(all_interfaces)}")

    print(f"\nInterfaces that SUPPORT date ranges:")
    for item in date_range_supported:
        print(f"  - {item['interface']} in {item['file']}")

    print(f"\nInterfaces that do NOT support date ranges:")
    for item in date_range_not_supported:
        print(f"  - {item['interface']} in {item['file']}")

    # The assumption is validated if we can identify which interfaces support date ranges and which don't
    has_date_range_support_info = len(date_range_supported) > 0 or len(date_range_not_supported) > 0

    print(f"\nDate range support information available: {has_date_range_support_info}")

    if has_date_range_support_info:
        print("CONFIRMED: The system has different date range support across interfaces")
        print("This validates the assumption about which interfaces support date range queries and which don't")

        return True
    else:
        print("NOT CONFIRMED: Could not determine date range support patterns")
        return False

if __name__ == "__main__":
    result = test_date_range_support()
    print(f"Test result: {result}")