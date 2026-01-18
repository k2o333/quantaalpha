#!/usr/bin/env python
"""
Verification script for atom_psutil_availability
This script verifies that the psutil library can be imported and used to get system resource information.
"""

def verify_psutil_availability():
    try:
        import psutil

        print("psutil imported successfully")

        # Test basic functionality by getting system information
        cpu_count = psutil.cpu_count()
        print(f"CPU count: {cpu_count}")

        memory_info = psutil.virtual_memory()
        print(f"Total memory: {memory_info.total / (1024**3):.2f} GB")

        disk_usage = psutil.disk_usage('/')
        print(f"Disk total: {disk_usage.total / (1024**3):.2f} GB")

        boot_time = psutil.boot_time()
        print(f"System boot time: {boot_time}")

        # Get current process information
        current_process = psutil.Process()
        process_memory = current_process.memory_info().rss / (1024**2)
        print(f"Current process memory usage: {process_memory:.2f} MB")

        print("SUCCESS: psutil library is available and functional")
        return True

    except ImportError as e:
        print(f"FAILURE: Could not import psutil: {e}")
        return False
    except Exception as e:
        print(f"FAILURE: Error testing psutil functionality: {e}")
        return False

if __name__ == "__main__":
    success = verify_psutil_availability()
    if success:
        print("Verification completed successfully")
    else:
        print("Verification failed")
        exit(1)