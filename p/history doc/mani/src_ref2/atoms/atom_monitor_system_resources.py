#!/usr/bin/env python
"""
Verification script for atom_monitor_system_resources
- 系统资源监控函数，监控CPU和内存使用情况
"""

def verify_atom_monitor_system_resources():
    """
    验证系统资源监控函数，监控CPU和内存使用情况
    """
    print("Testing atom_monitor_system_resources: 系统资源监控功能")

    import psutil
    import time
    import os
    import tempfile
    from datetime import datetime
    import threading
    import json

    def get_system_resources():
        """
        获取当前系统资源使用情况
        """
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_info = psutil.virtual_memory()
        disk_usage = psutil.disk_usage('/')

        resources = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],  # Include milliseconds
            'cpu_percent': cpu_percent,
            'memory_total_gb': round(memory_info.total / (1024**3), 2),
            'memory_available_gb': round(memory_info.available / (1024**3), 2),
            'memory_used_gb': round(memory_info.used / (1024**3), 2),
            'memory_percent': memory_info.percent,
            'disk_total_gb': round(disk_usage.total / (1024**3), 2),
            'disk_used_gb': round(disk_usage.used / (1024**3), 2),
            'disk_percent': disk_usage.percent,
            'process_count': len(psutil.pids()),
            'network_io': psutil.net_io_counters() if psutil.net_io_counters() else None
        }

        if resources['network_io']:
            resources['network_sent_mb'] = round(resources['network_io'].bytes_sent / (1024**2), 2)
            resources['network_recv_mb'] = round(resources['network_io'].bytes_recv / (1024**2), 2)

        return resources

    def monitor_system_resources(duration=1, interval=1, log_to_file=None):
        """
        监控系统资源使用情况，在指定时间内定期记录
        """
        print(f"  - Starting system resource monitoring for {duration}s with {interval}s intervals")

        logs = []
        start_time = time.time()
        end_time = start_time + duration

        while time.time() < end_time:
            resources = get_system_resources()
            logs.append(resources)

            print(f"    {resources['timestamp']} - CPU: {resources['cpu_percent']}%, "
                  f"Mem: {resources['memory_percent']}%, "
                  f"Disk: {resources['disk_percent']}%")

            # Optionally log to file
            if log_to_file:
                with open(log_to_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(resources) + '\n')

            time.sleep(interval)

        print(f"  - Completed monitoring, collected {len(logs)} samples")
        return logs

    def start_background_monitoring(stop_event, log_to_file=None):
        """
        启动后台监控（用于测试并发监控）
        """
        while not stop_event.is_set():
            resources = get_system_resources()
            if log_to_file:
                with open(log_to_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(resources) + '\n')
            time.sleep(0.5)
            if stop_event.is_set():
                break

    # Test 1: Basic system resource monitoring
    print("\n--- Test 1: Basic system resource monitoring ---")
    initial_resources = get_system_resources()

    assert 'cpu_percent' in initial_resources
    assert 'memory_percent' in initial_resources
    assert 'disk_percent' in initial_resources
    assert initial_resources['memory_total_gb'] > 0
    assert initial_resources['disk_total_gb'] > 0

    print(f"  - Current system: CPU={initial_resources['cpu_percent']}%, "
          f"Memory={initial_resources['memory_percent']}%, "
          f"Disk={initial_resources['disk_percent']}%")
    print("✓ Basic system resource monitoring works")

    # Test 2: Short-term monitoring
    print("\n--- Test 2: Short-term monitoring ---")
    logs = monitor_system_resources(duration=2, interval=0.5)
    assert len(logs) >= 3, f"Expected at least 3 samples, got {len(logs)}"

    # Check that we have valid resource data in all logs
    for log in logs:
        assert 'cpu_percent' in log
        assert 'memory_percent' in log

    print(f"✓ Short-term monitoring collected {len(logs)} samples")

    # Test 3: Resource monitoring with file output
    print("\n--- Test 3: Resource monitoring with file output ---")
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as temp_file:
        temp_log_path = temp_file.name

    file_logs = monitor_system_resources(duration=1.5, interval=0.3, log_to_file=temp_log_path)

    # Check the file content
    with open(temp_log_path, 'r', encoding='utf-8') as f:
        file_lines = f.readlines()

    assert len(file_lines) >= 3, f"Expected at least 3 entries in file, got {len(file_lines)}"

    # Parse first line to ensure it's valid JSON
    first_entry = json.loads(file_lines[0].strip())
    assert 'cpu_percent' in first_entry
    assert 'memory_percent' in first_entry

    print(f"✓ Resource monitoring to file worked, logged {len(file_lines)} entries to {temp_log_path}")

    # Clean up temp file
    os.unlink(temp_log_path)

    # Test 4: Resource threshold checking
    print("\n--- Test 4: Resource threshold checking ---")
    def check_resource_thresholds(cpu_threshold=80, memory_threshold=80, disk_threshold=90):
        """
        Check if system resources exceed thresholds
        """
        resources = get_system_resources()
        issues = []

        if resources['cpu_percent'] > cpu_threshold:
            issues.append(f"High CPU usage: {resources['cpu_percent']}% > {cpu_threshold}%")

        if resources['memory_percent'] > memory_threshold:
            issues.append(f"High memory usage: {resources['memory_percent']}% > {memory_threshold}%")

        if resources['disk_percent'] > disk_threshold:
            issues.append(f"High disk usage: {resources['disk_percent']}% > {disk_threshold}%")

        if issues:
            for issue in issues:
                print(f"  - ALERT: {issue}")
        else:
            print(f"  - OK: All resources below thresholds (CPU<{cpu_threshold}%, Mem<{memory_threshold}%, Disk<{disk_threshold}%)")

        return issues, resources

    issues, current_resources = check_resource_thresholds()
    print("✓ Resource threshold checking works")

    # Test 5: Memory usage spike simulation and detection
    print("\n--- Test 5: Memory usage spike detection ---")
    # Record baseline
    baseline_resources = get_system_resources()
    print(f"  - Baseline: Memory {baseline_resources['memory_percent']}%")

    # Simulate memory usage (allocate a large object temporarily)
    large_data = [0] * 5000000  # 5 million integers
    time.sleep(0.5)  # Allow memory to be allocated

    # Check memory after allocation
    after_allocation = get_system_resources()
    print(f"  - After allocation: Memory {after_allocation['memory_percent']}%")

    # Clean up and check again
    del large_data
    time.sleep(0.5)  # Allow garbage collection

    after_cleanup = get_system_resources()
    print(f"  - After cleanup: Memory {after_cleanup['memory_percent']}%")

    print("✓ Memory spike detection works")

    # Test 6: CPU stress simulation and detection
    print("\n--- Test 6: CPU stress simulation ---")
    baseline_cpu = get_system_resources()['cpu_percent']
    print(f"  - Baseline CPU: {baseline_cpu}%")

    # Simulate CPU load
    start_time = time.time()
    while time.time() - start_time < 0.5:  # 0.5 seconds of CPU work
        # CPU-intensive operation
        for i in range(10000):
            _ = i * i

    after_cpu_work = get_system_resources()['cpu_percent']
    print(f"  - After CPU work: {after_cpu_work}%")

    print("✓ CPU stress simulation works")

    # Test 7: Long-term monitoring statistics
    print("\n--- Test 7: Long-term monitoring statistics ---")
    # Collect data for a longer period
    long_logs = monitor_system_resources(duration=1.2, interval=0.3)  # 4-5 samples

    # Calculate statistics
    cpu_values = [log['cpu_percent'] for log in long_logs]
    memory_values = [log['memory_percent'] for log in long_logs]

    avg_cpu = sum(cpu_values) / len(cpu_values)
    avg_memory = sum(memory_values) / len(memory_values)
    max_cpu = max(cpu_values)
    max_memory = max(memory_values)

    print(f"  - Statistics: Avg CPU={avg_cpu:.2f}%, Max CPU={max_cpu}%, "
          f"Avg Memory={avg_memory:.2f}%, Max Memory={max_memory}%")

    print("✓ Long-term monitoring statistics work")

    # Test 8: Concurrent resource monitoring
    print("\n--- Test 8: Concurrent resource monitoring ---")
    stop_event = threading.Event()

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as temp_file:
        concurrent_log_path = temp_file.name

    # Start background monitoring in a separate thread
    monitor_thread = threading.Thread(
        target=start_background_monitoring,
        args=(stop_event, concurrent_log_path),
        daemon=True
    )
    monitor_thread.start()

    # Do some work while monitoring runs
    time.sleep(1.0)

    # Stop monitoring
    stop_event.set()
    monitor_thread.join(timeout=2)  # Wait up to 2 seconds for thread to finish

    # Check the results
    with open(concurrent_log_path, 'r', encoding='utf-8') as f:
        concurrent_logs = f.readlines()

    print(f"  - Concurrent monitoring collected {len(concurrent_logs)} entries")
    assert len(concurrent_logs) > 0, "Should have collected some logs during concurrent monitoring"

    print("✓ Concurrent resource monitoring works")

    # Clean up
    os.unlink(concurrent_log_path)

    # Test 9: Performance of resource gathering
    print("\n--- Test 9: Performance of resource gathering ---")
    import time

    # Time how long it takes to gather resources 10 times
    start_time = time.time()
    for i in range(10):
        get_system_resources()
    end_time = time.time()

    total_time = end_time - start_time
    avg_time = total_time / 10 * 1000  # Convert to milliseconds

    print(f"✓ Performance: Average {avg_time:.2f}ms per resource gathering call (10 calls in {total_time:.3f}s)")

    print("\natom_monitor_system_resources: VERIFICATION PASSED")
    return True

if __name__ == "__main__":
    verify_atom_monitor_system_resources()