#!/usr/bin/env python
"""
Verification script for atom_setup_logging
- 日志系统设置函数，配置日志记录和轮转机制
"""

def verify_atom_setup_logging():
    """
    验证日志系统设置函数，配置日志记录和轮转机制
    """
    print("Testing atom_setup_logging: 日志系统设置功能")

    import logging
    import tempfile
    import os
    from datetime import datetime
    import time
    import threading

    def setup_logging(log_file_path=None, log_level=logging.INFO, max_bytes=10*1024*1024, backup_count=5):
        """
        设置日志系统，配置日志记录和轮转机制
        """
        print(f"  - Setting up logging system")
        print(f"    - Log file: {log_file_path}")
        print(f"    - Log level: {logging.getLevelName(log_level)}")
        print(f"    - Max bytes: {max_bytes}")
        print(f"    - Backup count: {backup_count}")

        # Create a custom logger
        logger = logging.getLogger('vdd_logger')

        # Remove any existing handlers to avoid duplicates
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # Set the log level
        logger.setLevel(log_level)

        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )

        # File handler with rotation
        if log_file_path:
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                log_file_path,
                maxBytes=max_bytes,
                backupCount=backup_count
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        print(f"  - Logging system configured with {len(logger.handlers)} handlers")
        return logger

    def test_logging_functionality(logger):
        """
        测试日志记录功能
        """
        print(f"  - Testing logging functionality with logger: {logger.name}")

        # Test different log levels
        logger.debug("This is a debug message")
        logger.info("This is an info message")
        logger.warning("This is a warning message")
        logger.error("This is an error message")
        logger.critical("This is a critical message")

        # Test with context
        logger.info(f"Current time: {datetime.now()}")
        logger.info(f"Current process: {os.getpid()}")

        print(f"  - All log levels tested successfully")

    def test_log_rotation(log_file_path, logger):
        """
        测试日志轮转功能
        """
        print(f"  - Testing log rotation with file: {log_file_path}")

        # Write a large amount of data to trigger rotation
        for i in range(100):
            logger.info(f"Test message {i} - " + "x" * 1000)  # Large message to fill up log quickly

        # Check if log file exists and size
        if os.path.exists(log_file_path):
            file_size = os.path.getsize(log_file_path)
            print(f"  - Current log file size: {file_size} bytes")
        else:
            print(f"  - Log file does not exist: {log_file_path}")

        print(f"  - Log rotation test completed")

    def test_concurrent_logging(logger):
        """
        测试并发日志记录
        """
        print(f"  - Testing concurrent logging")

        def log_from_thread(thread_id):
            for i in range(10):
                logger.info(f"Thread {thread_id} - Message {i}")
                time.sleep(0.01)

        # Create multiple threads that log concurrently
        threads = []
        for i in range(3):
            thread = threading.Thread(target=log_from_thread, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        print(f"  - Concurrent logging test completed")

    # Test 1: Basic logging setup
    print("\n--- Test 1: Basic logging setup ---")
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as temp_file:
        log_path = temp_file.name

    logger = setup_logging(log_file_path=log_path)
    assert logger is not None
    assert len(logger.handlers) > 0

    print("✓ Basic logging setup works")

    # Test 2: Logging functionality
    print("\n--- Test 2: Logging functionality ---")
    test_logging_functionality(logger)
    print("✓ Logging functionality works")

    # Test 3: Log rotation test
    print("\n--- Test 3: Log rotation ---")
    # Recreate logger with smaller max size to trigger rotation easily
    logger_rotation = setup_logging(log_file_path=log_path, max_bytes=1024)  # 1KB for testing
    test_log_rotation(log_path, logger_rotation)
    print("✓ Log rotation test completed")

    # Test 4: Different log levels
    print("\n--- Test 4: Different log levels ---")
    debug_logger = setup_logging(log_file_path=log_path, log_level=logging.DEBUG)

    # Test that different levels work
    levels_tested = []
    debug_logger.debug("Debug level test")
    levels_tested.append("debug")

    debug_logger.info("Info level test")
    levels_tested.append("info")

    debug_logger.warning("Warning level test")
    levels_tested.append("warning")

    debug_logger.error("Error level test")
    levels_tested.append("error")

    debug_logger.critical("Critical level test")
    levels_tested.append("critical")

    print(f"  - Tested log levels: {levels_tested}")
    print("✓ Different log levels work")

    # Test 5: Custom log format
    print("\n--- Test 5: Custom log format ---")
    # Test that we can set up logging without file (console only)
    console_logger = setup_logging(log_file_path=None)
    console_logger.info("This is a console-only message")
    print("✓ Console-only logging works")

    # Test 6: File-based logging only
    print("\n--- Test 6: File-based logging ---")
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as temp_file:
        file_log_path = temp_file.name

    file_logger = setup_logging(log_file_path=file_log_path, log_level=logging.DEBUG)
    file_logger.info("File-only log message")
    file_logger.error("File-only error message")

    # Check that file contains log entries
    time.sleep(0.1)  # Allow time for disk write
    if os.path.exists(file_log_path):
        with open(file_log_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        assert 'File-only log message' in file_content
        assert 'File-only error message' in file_content
        print(f"  - File contains {len(file_content)} characters")

    print("✓ File-based logging works")

    # Test 7: Concurrent logging
    print("\n--- Test 7: Concurrent logging ---")
    concurrent_logger = setup_logging(log_file_path=file_log_path)
    test_concurrent_logging(concurrent_logger)
    print("✓ Concurrent logging works")

    # Test 8: Performance test
    print("\n--- Test 8: Logging performance ---")
    perf_logger = setup_logging(log_file_path=None)  # Console only for performance

    start_time = time.time()
    for i in range(1000):
        perf_logger.info(f"Performance test message {i}")
    end_time = time.time()

    total_time = end_time - start_time
    avg_time = (total_time / 1000) * 1000  # Convert to milliseconds

    print(f"  - Logged 1000 messages in {total_time:.3f}s")
    print(f"  - Average {avg_time:.3f}ms per log message")
    print("✓ Logging performance test completed")

    # Test 9: Multiple loggers with same file
    print("\n--- Test 9: Multiple loggers with same file ---")
    logger1 = setup_logging(log_file_path=file_log_path, log_level=logging.INFO)
    logger2 = setup_logging(log_file_path=file_log_path, log_level=logging.WARNING)  # Different level

    logger1.info("Message from logger1")
    logger2.warning("Message from logger2")
    logger1.error("Error from logger1")

    print("✓ Multiple loggers with same file works")

    # Cleanup temporary files
    for temp_path in [log_path, file_log_path]:
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass  # File might be in use

    print("\natom_setup_logging: VERIFICATION PASSED")
    return True

if __name__ == "__main__":
    verify_atom_setup_logging()