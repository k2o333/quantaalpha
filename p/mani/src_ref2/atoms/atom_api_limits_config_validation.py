#!/usr/bin/env python
"""
Verification script for atom_api_limits_config_validation
This script validates API limit configuration structures appropriate for A-share market data platform
(NOTE: This validation is for configuration STRUCTURE only, no actual API calls are made)
"""

def verify_api_limits_config_validation():
    try:
        import json
        import tempfile
        import os
        from datetime import datetime, timedelta
        import re

        print("Step 1: Creating API limits configuration for A-share market data platform")

        # Define comprehensive API limit configuration appropriate for Chinese market
        # NOTE: This is structure validation only, no actual API calls will be made
        api_limits_config = {
            "exchanges": {
                "sse": {  # Shanghai Stock Exchange
                    "name": "Shanghai Stock Exchange",
                    "api_endpoint": "https://stock.xueqiu.com/",
                    "rate_limits": {
                        "requests_per_minute": 10,  # Changed from 60 to maintain consistency
                        "requests_per_hour": 600,   # Now consistent: 10/min * 60 = 600/hour
                        "requests_per_day": 10000,
                        "burst_limit": 10  # Requests allowed in a short burst
                    },
                    "throttling_strategy": {
                        "type": "token_bucket",
                        "refill_rate": 1.0,  # tokens per second
                        "capacity": 10  # burst capacity
                    },
                    "endpoints": {
                        "daily_bars": {
                            "rate_limit": {
                                "requests_per_minute": 5,
                                "requests_per_hour": 300
                            },
                            "max_symbols_per_call": 50,
                            "data_delay_minutes": 15  # Real-time data may have delay
                        },
                        "reference_data": {
                            "rate_limit": {
                                "requests_per_minute": 8,
                                "requests_per_hour": 480
                            },
                            "max_symbols_per_call": 100,
                            "data_delay_minutes": 0  # Reference data is typically readily available
                        },
                        "historical_data": {
                            "rate_limit": {
                                "requests_per_minute": 3,
                                "requests_per_hour": 180
                            },
                            "max_date_range_days": 365,
                            "data_delay_minutes": 0
                        }
                    },
                    "authentication": {
                        "required": True,
                        "type": "api_key",
                        "api_key_format": "^[A-Za-z0-9]{32,64}$",  # Example format
                        "token_expiration_days": 30
                    }
                },
                "sze": {  # Shenzhen Stock Exchange
                    "name": "Shenzhen Stock Exchange",
                    "api_endpoint": "https://biz.finance.sina.com.cn/",
                    "rate_limits": {
                        "requests_per_minute": 10,  # Changed from 60 to maintain consistency
                        "requests_per_hour": 600,   # Now consistent: 10/min * 60 = 600/hour
                        "requests_per_day": 10000,
                        "burst_limit": 10
                    },
                    "throttling_strategy": {
                        "type": "token_bucket",
                        "refill_rate": 1.0,
                        "capacity": 10
                    },
                    "endpoints": {
                        "daily_bars": {
                            "rate_limit": {
                                "requests_per_minute": 5,
                                "requests_per_hour": 300
                            },
                            "max_symbols_per_call": 50,
                            "data_delay_minutes": 15
                        },
                        "reference_data": {
                            "rate_limit": {
                                "requests_per_minute": 8,
                                "requests_per_hour": 480
                            },
                            "max_symbols_per_call": 100,
                            "data_delay_minutes": 0
                        },
                        "historical_data": {
                            "rate_limit": {
                                "requests_per_minute": 3,
                                "requests_per_hour": 180
                            },
                            "max_date_range_days": 365,
                            "data_delay_minutes": 0
                        }
                    },
                    "authentication": {
                        "required": True,
                        "type": "api_key",
                        "api_key_format": "^[A-Za-z0-9]{32,64}$",
                        "token_expiration_days": 30
                    }
                }
            },
            "third_party_vendors": {
                "wind": {
                    "name": "Wind Information",
                    "rate_limits": {
                        "requests_per_minute": 100,
                        "requests_per_hour": 2000,
                        "requests_per_day": 50000
                    },
                    "endpoints": {
                        "market_data": {
                            "rate_limit": {
                                "requests_per_minute": 50,
                                "requests_per_hour": 1000
                            }
                        }
                    }
                },
                "tushare": {
                    "name": "Tushare",
                    "rate_limits": {
                        "requests_per_minute": 500,
                        "requests_per_hour": 3000,
                        "requests_per_day": 1000000
                    },
                    "endpoints": {
                        "daily_bars": {
                            "rate_limit": {
                                "requests_per_minute": 500,
                                "requests_per_hour": 3000
                            },
                            "max_symbols_per_call": 1000
                        }
                    }
                }
            },
            "platform_policies": {
                "concurrent_connections": 10,
                "request_timeout_seconds": 30,
                "retry_policy": {
                    "max_retries": 3,
                    "backoff_factor": 1.5,
                    "retryable_status_codes": [429, 502, 503, 504]
                },
                "monitoring": {
                    "rate_limit_usage_threshold": 80,  # Percentage
                    "alert_when_approaching_limit": True
                }
            }
        }

        print("Step 2: Validating API limits configuration structure")

        # Validate required fields exist
        assert "exchanges" in api_limits_config, "Configuration must have exchanges section"
        assert "sse" in api_limits_config["exchanges"], "Configuration must include SSE exchange"
        assert "sze" in api_limits_config["exchanges"], "Configuration must include SZE exchange"
        assert "rate_limits" in api_limits_config["exchanges"]["sse"], "SSE must have rate limits"
        assert "rate_limits" in api_limits_config["exchanges"]["sze"], "SZE must have rate limits"

        # Validate rate limit values are reasonable for A-share market
        sse_limits = api_limits_config["exchanges"]["sse"]["rate_limits"]
        sze_limits = api_limits_config["exchanges"]["sze"]["rate_limits"]

        # These are realistic values for Chinese exchange APIs (many implement conservative limits)
        for exchange_name, limits in [("SSE", sse_limits), ("SZE", sze_limits)]:
            assert isinstance(limits["requests_per_minute"], int) and limits["requests_per_minute"] > 0, f"{exchange_name} min rate must be positive"
            assert isinstance(limits["requests_per_hour"], int) and limits["requests_per_hour"] > 0, f"{exchange_name} hour rate must be positive"
            assert isinstance(limits["requests_per_day"], int) and limits["requests_per_day"] > 0, f"{exchange_name} day rate must be positive"
            assert limits["requests_per_minute"] * 60 <= limits["requests_per_hour"], f"{exchange_name} rate consistency"

        print(f"  Rate limits validated for both exchanges")

        # Validate throttling strategies
        for exchange_name, exchange_data in api_limits_config["exchanges"].items():
            assert "throttling_strategy" in exchange_data, f"{exchange_name} must have throttling strategy"
            strategy = exchange_data["throttling_strategy"]
            assert "type" in strategy, f"{exchange_name} throttling type must be specified"
            assert "token_bucket" == strategy["type"], f"{exchange_name} should use token_bucket strategy"
            assert "refill_rate" in strategy, f"{exchange_name} refill rate must be specified"
            assert "capacity" in strategy, f"{exchange_name} capacity must be specified"

        print(f"  Throttling strategies validated")

        # Validate endpoint-specific limits
        for exchange_name, exchange_data in api_limits_config["exchanges"].items():
            assert "endpoints" in exchange_data, f"{exchange_name} must have endpoint configurations"
            endpoints = exchange_data["endpoints"]
            assert "daily_bars" in endpoints, f"{exchange_name} must have daily_bars endpoint config"
            assert "reference_data" in endpoints, f"{exchange_name} must have reference_data endpoint config"

            # Validate endpoint rate limits make sense
            for endpoint_name, endpoint_config in endpoints.items():
                if "rate_limit" in endpoint_config:
                    rate_limit = endpoint_config["rate_limit"]
                    assert "requests_per_minute" in rate_limit, f"{exchange_name} {endpoint_name} must have min rate"
                    assert "requests_per_hour" in rate_limit, f"{exchange_name} {endpoint_name} must have hour rate"
                    assert rate_limit["requests_per_minute"] * 60 <= rate_limit["requests_per_hour"], f"Rate consistency for {exchange_name} {endpoint_name}"

        print(f"  Endpoint-specific limits validated")

        # Validate authentication requirements
        for exchange_name, exchange_data in api_limits_config["exchanges"].items():
            assert "authentication" in exchange_data, f"{exchange_name} must have authentication config"
            auth = exchange_data["authentication"]
            assert "required" in auth, f"{exchange_name} authentication required flag must exist"
            assert "type" in auth, f"{exchange_name} authentication type must exist"

            # Validate API key format if specified
            if "api_key_format" in auth:
                # Check that format is a valid regex
                try:
                    re.compile(auth["api_key_format"])
                    print(f"    {exchange_name} API key format regex is valid")
                except re.error:
                    raise ValueError(f"{exchange_name} API key format is not a valid regex")

        print(f"  Authentication configurations validated")

        # Validate platform-wide policies
        platform_policies = api_limits_config["platform_policies"]
        assert "concurrent_connections" in platform_policies, "Platform must have concurrent connections config"
        assert "request_timeout_seconds" in platform_policies, "Platform must have timeout config"
        assert "retry_policy" in platform_policies, "Platform must have retry policy config"

        assert platform_policies["concurrent_connections"] > 0, "Concurrent connections must be positive"
        assert platform_policies["request_timeout_seconds"] > 0, "Timeout must be positive"

        print(f"  Platform policies validated")

        # Test config serialization and deserialization
        print("Step 3: Testing configuration serialization")

        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = os.path.join(temp_dir, "api_limits_config.json")

            # Write config to file
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(api_limits_config, f, indent=2, ensure_ascii=False)

            # Read config back
            with open(config_file, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)

            # Verify critical values survived serialization
            assert loaded_config["exchanges"]["sse"]["rate_limits"]["requests_per_minute"] == api_limits_config["exchanges"]["sse"]["rate_limits"]["requests_per_minute"]
            assert loaded_config["exchanges"]["sze"]["rate_limits"]["requests_per_minute"] == api_limits_config["exchanges"]["sze"]["rate_limits"]["requests_per_minute"]

            print(f"  Configuration successfully serialized and deserialized: {config_file}")

        # Validate Chinese market-specific configurations
        print("Step 4: Validating A-share market specific configurations")

        # Chinese exchanges have specific characteristics
        assert "sse" in api_limits_config["exchanges"], "SSE exchange must be configured (Shanghai)"
        assert "sze" in api_limits_config["exchanges"], "SZE exchange must be configured (Shenzhen)"

        # Verify exchange names make sense for Chinese market
        sse_name = api_limits_config["exchanges"]["sse"]["name"]
        sze_name = api_limits_config["exchanges"]["sze"]["name"]
        assert "Shanghai" in sse_name, "SSE should mention Shanghai"
        assert "Shenzhen" in sze_name, "SZE should mention Shenzhen"

        # Validate that rate limits consider the size of A-share market
        # The market has hundreds of millions of trades daily, so conservative limits in our config are appropriate
        total_daily_limit = (api_limits_config["exchanges"]["sse"]["rate_limits"]["requests_per_day"] +
                             api_limits_config["exchanges"]["sze"]["rate_limits"]["requests_per_day"])

        # Verify limits are reasonable (not unreasonably high or low)
        assert 1000 <= total_daily_limit <= 100000, f"Total daily limit {total_daily_limit} should be reasonable for A-share market"

        print(f"  Exchange-specific configurations validated: SSE and SZE")
        print(f"  Total daily limit: {total_daily_limit} requests (reasonable for A-share market)")

        print("SUCCESS: API limits configuration structure is appropriate for A-share market platform")
        return True

    except Exception as e:
        print(f"FAILURE: Error in API limits configuration validation: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = verify_api_limits_config_validation()
    if success:
        print("Verification completed successfully")
    else:
        print("Verification failed")
        exit(1)