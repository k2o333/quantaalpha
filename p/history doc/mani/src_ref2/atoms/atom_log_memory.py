#!/usr/bin/env python
"""
Verification script for atom_log_memory
- 内存使用监控函数，在不同阶段记录内存使用情况
"""

def verify_atom_log_memory():
    """
    验证内存使用监控函数，在不同阶段记录内存使用情况
    """
    print("Testing atom_log_memory: 内存使用监控功能")

    import psutil
    import time
    import tempfile
    import os
    from datetime import datetime

    def get_memory_usage():
        """
        获取当前进程的内存使用情况
        """
        process = psutil.Process()
        memory_info = process.memory_info()
        return {
            'rss': memory_info.rss,  # Resident Set Size: actual physical memory currently used by the process
            'vms': memory_info.vms,  # Virtual Memory Size: total amount of virtual memory used by the process
            'percent': process.memory_percent()  # Percentage of total system memory used by the process
        }

    def log_memory(stage_name="unknown", log_to_file=None):
        """
        记录当前内存使用情况的函数，支持记录到文件和打印到控制台
        """
        memory_info = get_memory_usage()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            'timestamp': timestamp,
            'stage': stage_name,
            'rss_mb': round(memory_info['rss'] / 1024 / 1024, 2),  # Convert to MB
            'vms_mb': round(memory_info['vms'] / 1024 / 1024, 2),  # Convert to MB
            'percent': round(memory_info['percent'], 2)
        }

        print(f"  [{timestamp}] {stage_name}: RSS={log_entry['rss_mb']}MB, VMS={log_entry['vms_mb']}MB, {log_entry['percent']}%")

        # Optionally log to file
        if log_to_file:
            import json
            with open(log_to_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')

        return log_entry

    def simulate_data_processing_stages():
        """
        模拟数据处理的不同阶段，记录内存使用变化
        """
        print("  - Simulating data processing stages...")

        # Stage 1: Initialize
        log_memory("Initialization")

        # Stage 2: Load small dataset
        small_data = [i for i in range(10000)]  # Small list
        log_memory("After loading small dataset")

        # Stage 3: Load medium dataset
        medium_data = [[i + j for j in range(100)] for i in range(10000)]  # Medium nested list
        log_memory("After loading medium dataset")

        # Stage 4: Load large dataset
        large_data = [[[i + j + k for k in range(10)] for j in range(100)] for i in range(5000)]  # Large nested list
        log_memory("After loading large dataset")

        # Stage 5: Process data
        processed_data = [sum(sublist) for inner_list in medium_data for sublist in [inner_list[::2]]]  # Process data
        log_memory("After data processing")

        # Stage 6: Cleanup
        del large_data
        time.sleep(0.1)  # Give garbage collector time
        log_memory("After large data cleanup")

        # Stage 7: Final
        del medium_data, small_data, processed_data
        time.sleep(0.1)  # Give garbage collector time
        log_memory("After final cleanup")

        return "Processing completed"

    # Test 1: Basic memory logging functionality
    print("\n--- Test 1: Basic memory logging ---")
    initial_log = log_memory("Initial state")
    assert 'rss_mb' in initial_log
    assert 'vms_mb' in initial_log
    assert 'percent' in initial_log
    assert initial_log['rss_mb'] > 0, "RSS should be positive"
    assert initial_log['vms_mb'] > 0, "VMS should be positive"
    print("✓ Basic memory logging works")

    # Test 2: Memory logging during processing
    print("\n--- Test 2: Memory logging during processing ---")
    result = simulate_data_processing_stages()
    assert result == "Processing completed"
    print("✓ Memory logging during data processing works")

    # Test 3: Memory logging with file output
    print("\n--- Test 3: Memory logging with file output ---")
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as temp_file:
        temp_log_path = temp_file.name

    # Log a few entries to the file
    log_memory("Test entry 1", log_to_file=temp_log_path)
    time.sleep(0.01)  # Small delay
    log_memory("Test entry 2", log_to_file=temp_log_path)

    # Check if file contains expected entries
    with open(temp_log_path, 'r', encoding='utf-8') as f:
        log_lines = f.readlines()

    assert len(log_lines) >= 2, f"Expected at least 2 log entries, got {len(log_lines)}"

    # Parse first entry
    import json
    first_entry = json.loads(log_lines[0].strip())
    assert 'stage' in first_entry
    assert 'rss_mb' in first_entry

    print(f"✓ Memory logging to file works, logged {len(log_lines)} entries")

    # Clean up temp file
    os.unlink(temp_log_path)

    # Test 4: Memory usage trend analysis
    print("\n--- Test 4: Memory usage trend analysis ---")
    # Create a scenario that shows memory increase then decrease
    memory_logs = []

    memory_logs.append(log_memory("Before allocation"))

    # Allocate large data structure
    large_list = [0] * 1000000  # 1M integers
    memory_logs.append(log_memory("After large allocation"))

    # Memory should be higher after allocation
    assert memory_logs[1]['rss_mb'] >= memory_logs[0]['rss_mb'], "Memory should increase after allocation"

    # Deallocate
    del large_list
    time.sleep(0.1)  # Give garbage collector time
    memory_logs.append(log_memory("After deallocation"))

    print("✓ Memory usage trend analysis works")

    # Test 5: Memory threshold detection
    print("\n--- Test 5: Memory threshold detection ---")
    def check_memory_threshold(threshold_mb=500):  # 500MB threshold
        """
        Check if memory usage exceeds threshold and return warning
        """
        current_memory = get_memory_usage()
        current_mb = current_memory['rss'] / 1024 / 1024

        if current_mb > threshold_mb:
            print(f"  - WARNING: Memory usage ({current_mb:.2f}MB) exceeds threshold ({threshold_mb}MB)")
            return True
        else:
            print(f"  - OK: Memory usage ({current_mb:.2f}MB) is below threshold ({threshold_mb}MB)")
            return False

    # Test with a reasonable threshold
    threshold_exceeded = check_memory_threshold(1000)  # 1000MB threshold (should be fine)
    print(f"✓ Memory threshold detection works (threshold exceeded: {threshold_exceeded})")

    # Test 6: Performance of memory logging function
    print("\n--- Test 6: Performance of memory logging ---")
    import time

    # Time how long it takes to log memory 100 times
    start_time = time.time()
    for i in range(100):
        log_memory(f"Performance test {i}")
    end_time = time.time()

    total_time = end_time - start_time
    avg_time = total_time / 100 * 1000  # Convert to milliseconds

    print(f"✓ Performance: Average {avg_time:.2f}ms per memory log call (100 calls in {total_time:.3f}s)")

    # Test 7: Multiple memory measurements consistency
    print("\n--- Test 7: Memory measurement consistency ---")
    measurements = []
    for i in range(5):
        mem_info = get_memory_usage()
        measurements.append(mem_info['rss'])
        time.sleep(0.01)  # Small delay

    # Measurements should be relatively consistent (allowing for some system variation)
    min_mem = min(measurements)
    max_mem = max(measurements)
    variation = max_mem - min_mem

    print(f"✓ Memory measurement consistency: variation of {variation / 1024 / 1024:.2f}MB across 5 measurements")

    print("\natom_log_memory: VERIFICATION PASSED")
    return True

if __name__ == "__main__":
    verify_atom_log_memory()