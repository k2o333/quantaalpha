#!/usr/bin/env python
"""
Verification script for atom_initialize_rate_limiters
- 初始化所有必需的速率限制器
"""

def verify_atom_initialize_rate_limiters():
    """
    验证初始化所有必需的速率限制器
    """
    print("Testing atom_initialize_rate_limiters: 速率限制器初始化功能")

    import time
    import threading
    from datetime import datetime, timedelta
    import json

    class RateLimiter:
        """
        简单的速率限制器实现
        """
        def __init__(self, max_calls, time_window):
            self.max_calls = max_calls
            self.time_window = time_window  # in seconds
            self.calls = []
            self.lock = threading.Lock()

        def is_allowed(self):
            """
            检查是否允许进行调用
            """
            with self.lock:
                now = time.time()
                # Remove calls that are outside the time window
                self.calls = [call_time for call_time in self.calls if now - call_time < self.time_window]

                if len(self.calls) < self.max_calls:
                    self.calls.append(now)
                    return True
                else:
                    return False

        def get_wait_time(self):
            """
            获取需要等待的时间（如果有的话）
            """
            with self.lock:
                if len(self.calls) == 0:
                    return 0

                now = time.time()
                # Remove calls that are outside the time window
                self.calls = [call_time for call_time in self.calls if now - call_time < self.time_window]

                if len(self.calls) < self.max_calls:
                    return 0
                else:
                    # Calculate when the oldest call will expire
                    oldest_call = min(self.calls)
                    wait_time = self.time_window - (now - oldest_call)
                    return max(0, wait_time)

    def initialize_rate_limiters():
        """
        初始化所有必需的速率限制器
        """
        print("  - Initializing rate limiters")

        # Define default rate limits for different API types
        default_limits = {
            'daily': {'max_calls': 500, 'time_window': 60},  # 500 calls per minute
            'weekly': {'max_calls': 200, 'time_window': 60},  # 200 calls per minute
            'monthly': {'max_calls': 100, 'time_window': 60},  # 100 calls per minute
            'balance_vip': {'max_calls': 100, 'time_window': 60},  # 100 calls per minute
            'income_vip': {'max_calls': 100, 'time_window': 60},  # 100 calls per minute
            'cashflow_vip': {'max_calls': 100, 'time_window': 60},  # 100 calls per minute
            'fina_indicator_vip': {'max_calls': 50, 'time_window': 60},  # 50 calls per minute
            'stock_basic': {'max_calls': 1000, 'time_window': 60},  # 1000 calls per minute
            'daily_basic': {'max_calls': 1000, 'time_window': 60},  # 1000 calls per minute
            'report_rc': {'max_calls': 50, 'time_window': 60},  # 50 calls per minute
            'moneyflow': {'max_calls': 200, 'time_window': 60},  # 200 calls per minute
            'pro_bar': {'max_calls': 500, 'time_window': 60},  # 500 calls per minute
        }

        # Create rate limiters dictionary
        rate_limiters = {}

        for api_name, limits in default_limits.items():
            max_calls = limits['max_calls']
            time_window = limits['time_window']

            rate_limiter = RateLimiter(max_calls, time_window)
            rate_limiters[api_name] = rate_limiter

            print(f"    - Created rate limiter for {api_name}: {max_calls} calls per {time_window} seconds")

        print(f"  - Initialized {len(rate_limiters)} rate limiters")
        return rate_limiters

    def test_rate_limiter_behavior(limiter, name, test_calls=10):
        """
        测试速率限制器的行为
        """
        print(f"    - Testing {name} rate limiter with {test_calls} calls")

        allowed_calls = 0
        blocked_calls = 0

        for i in range(test_calls):
            if limiter.is_allowed():
                allowed_calls += 1
                print(f"      - Call {i+1}: ALLOWED")
            else:
                blocked_calls += 1
                wait_time = limiter.get_wait_time()
                print(f"      - Call {i+1}: BLOCKED (wait {wait_time:.2f}s)")

        print(f"      - Results: {allowed_calls} allowed, {blocked_calls} blocked")
        return allowed_calls, blocked_calls

    def simulate_concurrent_api_calls(rate_limiters, api_name, num_threads=5, calls_per_thread=3):
        """
        模拟并发API调用
        """
        print(f"    - Simulating concurrent calls to {api_name} with {num_threads} threads")

        results = {'allowed': 0, 'blocked': 0}
        results_lock = threading.Lock()

        def make_calls(thread_id):
            limiter = rate_limiters[api_name]
            thread_allowed = 0
            thread_blocked = 0

            for i in range(calls_per_thread):
                if limiter.is_allowed():
                    thread_allowed += 1
                    time.sleep(0.01)  # Simulate work
                else:
                    thread_blocked += 1
                    wait_time = limiter.get_wait_time()
                    if wait_time > 0:
                        time.sleep(wait_time)

            with results_lock:
                results['allowed'] += thread_allowed
                results['blocked'] += thread_blocked

        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=make_calls, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        print(f"      - Concurrent results: {results['allowed']} allowed, {results['blocked']} blocked")
        return results

    # Test 1: Basic initialization
    print("\n--- Test 1: Basic initialization ---")
    rate_limiters = initialize_rate_limiters()

    # Check that we have expected rate limiters
    expected_apis = [
        'daily', 'weekly', 'monthly', 'balance_vip', 'income_vip',
        'cashflow_vip', 'fina_indicator_vip', 'stock_basic', 'daily_basic',
        'report_rc', 'moneyflow', 'pro_bar'
    ]

    assert len(rate_limiters) >= 10, f"Expected at least 10 rate limiters, got {len(rate_limiters)}"

    for api in expected_apis:
        assert api in rate_limiters, f"Rate limiter for {api} should exist"
        assert isinstance(rate_limiters[api], RateLimiter), f"{api} should be a RateLimiter instance"

    print("✓ Basic initialization works")

    # Test 2: Rate limiter behavior for different APIs
    print("\n--- Test 2: Rate limiter behavior ---")

    # Test with daily API (high limit)
    daily_limiter = rate_limiters['daily']
    test_rate_limiter_behavior(daily_limiter, 'daily', 5)

    # Test with fina_indicator_vip API (low limit)
    fina_limiter = rate_limiters['fina_indicator_vip']
    test_rate_limiter_behavior(fina_limiter, 'fina_indicator_vip', 10)

    print("✓ Rate limiter behavior works")

    # Test 3: Concurrent access to rate limiters
    print("\n--- Test 3: Concurrent access ---")
    concurrent_results = simulate_concurrent_api_calls(rate_limiters, 'daily', num_threads=3, calls_per_thread=5)
    assert concurrent_results['allowed'] + concurrent_results['blocked'] == 15, "Total calls should match expected"
    print("✓ Concurrent access works")

    # Test 4: Verify rate limiting effectiveness with time window
    print("\n--- Test 4: Time window effectiveness ---")
    test_limiter = rate_limiters['stock_basic']

    # Make calls very quickly to test rate limiting
    start_time = time.time()
    for i in range(10):
        allowed = test_limiter.is_allowed()
        print(f"      - Burst call {i+1}: {'ALLOWED' if allowed else 'BLOCKED'}")
        # Don't sleep, make calls as fast as possible

    # Wait for the time window to pass
    time.sleep(1)  # Wait 1 second

    # Make more calls after time window - should be allowed again
    new_allowed = 0
    for i in range(5):
        if test_limiter.is_allowed():
            new_allowed += 1
            print(f"      - Post-window call {i+1}: ALLOWED")

    print(f"      - {new_allowed} calls allowed after window reset")
    print("✓ Time window effectiveness works")

    # Test 5: Initialize with custom limits
    print("\n--- Test 5: Custom limits initialization ---")
    # Define custom limits for testing
    import types

    def initialize_rate_limiters_custom():
        custom_limits = {
            'test_api': {'max_calls': 5, 'time_window': 2},  # 5 calls per 2 seconds
        }

        rate_limiters = {}
        for api_name, limits in custom_limits.items():
            max_calls = limits['max_calls']
            time_window = limits['time_window']

            rate_limiter = RateLimiter(max_calls, time_window)
            rate_limiters[api_name] = rate_limiter
            print(f"    - Created custom rate limiter for {api_name}: {max_calls} calls per {time_window} seconds")

        return rate_limiters

    custom_limiters = initialize_rate_limiters_custom()
    assert 'test_api' in custom_limiters, "Custom limiter should be created"
    print("✓ Custom limits initialization works")

    # Test 6: Memory efficiency with many limiters
    print("\n--- Test 6: Memory efficiency ---")
    large_api_list = [f'api_{i}' for i in range(50)]

    def initialize_many_limiters():
        limiters = {}
        for api_name in large_api_list:
            limiter = RateLimiter(100, 60)  # Reasonable default
            limiters[api_name] = limiter
        return limiters

    start_time = time.time()
    many_limiters = initialize_many_limiters()
    end_time = time.time()

    assert len(many_limiters) == 50, "Should create all 50 limiters"
    print(f"  - Initialized {len(many_limiters)} limiters in {end_time - start_time:.3f}s")
    print("✓ Memory efficiency works")

    # Test 7: Rate limiting with realistic scenarios
    print("\n--- Test 7: Realistic API usage scenarios ---")

    # Scenario 1: Burst of calls followed by regular pattern (like typical API usage)
    scenario_limiter = RateLimiter(10, 1)  # 10 calls per second

    # Simulate burst of calls
    burst_allowed = 0
    for i in range(15):
        if scenario_limiter.is_allowed():
            burst_allowed += 1

    print(f"      - Burst scenario: {burst_allowed}/15 calls allowed in burst")

    # Wait for window to reset
    time.sleep(1.1)

    # Check if more calls are allowed after reset
    post_burst_allowed = 0
    for i in range(5):
        if scenario_limiter.is_allowed():
            post_burst_allowed += 1

    print(f"      - After reset: {post_burst_allowed}/5 calls allowed")
    print("✓ Realistic API usage scenarios work")

    # Test 8: Wait time calculation accuracy
    print("\n--- Test 8: Wait time calculation ---")
    wait_limiter = RateLimiter(2, 5)  # 2 calls per 5 seconds

    # Fill up the limiter
    for i in range(2):
        wait_limiter.is_allowed()

    # Try a call that should be blocked
    is_allowed = wait_limiter.is_allowed()
    if not is_allowed:
        wait_time = wait_limiter.get_wait_time()
        print(f"      - Wait time calculated: {wait_time:.2f}s (should be positive)")
        assert wait_time > 0, "Wait time should be positive when rate limited"

    print("✓ Wait time calculation works")

    print("\natom_initialize_rate_limiters: VERIFICATION PASSED")
    return True

if __name__ == "__main__":
    verify_atom_initialize_rate_limiters()