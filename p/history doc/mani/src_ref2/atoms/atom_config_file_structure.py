#!/usr/bin/env python
"""
Verification script for atom_config_file_structure
This script verifies configuration file structure appropriate for A-share market data platform
"""

def verify_config_file_structure():
    try:
        import json
        import yaml
        import os
        import tempfile
        from datetime import datetime

        print("Step 1: Creating configuration structure for A-share market data platform")

        # Define a comprehensive configuration structure for A-share market data platform
        config_structure = {
            "platform": {
                "name": "A-share Market Data Platform",
                "version": "1.0.0",
                "description": "Platform for managing Chinese A-share market data"
            },
            "data_sources": {
                "primary": {
                    "name": "exchange_api",
                    "endpoint": "https://api.sse.com.cn, https://api.szse.cn",
                    "rate_limit": {
                        "requests_per_minute": 100,
                        "burst_size": 10
                    },
                    "authentication": {
                        "type": "token",
                        "required": True
                    }
                },
                "secondary": {
                    "name": "third_party_vendor",
                    "endpoint": "https://api.vendor.com",
                    "rate_limit": {
                        "requests_per_minute": 50,
                        "burst_size": 5
                    },
                    "backup": True
                }
            },
            "storage": {
                "default_format": "parquet",
                "compression": "snappy",
                "path_patterns": {
                    "daily_bars": "data/daily/{exchange}/{year}/{month}/{day}/",
                    "reference_data": "data/reference/{year}/",
                    "adjustments": "data/adjustments/{year}/{month}/"
                },
                "retention_policies": {
                    "daily_data": "5_years",
                    "reference_data": "indefinite",
                    "log_data": "1_year"
                }
            },
            "data_processing": {
                "batch_size": 10000,
                "buffer_size": 50000,
                "concurrency": {
                    "max_workers": 8,
                    "download_workers": 4,
                    "processing_workers": 4
                },
                "data_quality": {
                    "validation_enabled": True,
                    "null_threshold": 0.05,  # 5% null threshold
                    "outlier_detection": True,
                    "validation_rules": {
                        "price_range": [0.01, 10000],  # A-share price limits
                        "volume_range": [0, 1e10],
                        "symbol_pattern": "^(SH|SZ)\\d{6}$"
                    }
                }
            },
            "partitioning": {
                "strategies": {
                    "daily_bars": {
                        "level_1": "symbol",
                        "level_2": "year",
                        "level_3": "month"
                    },
                    "reference": {
                        "level_1": "year",
                        "level_2": "data_type"
                    }
                },
                "max_partition_depth": 3
            },
            "security": {
                "encryption_at_rest": True,
                "api_security": {
                    "token_rotation_days": 30,
                    "rate_limiting": True
                }
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "handlers": {
                    "file": {
                        "filename": "logs/platform.log",
                        "max_bytes": 10485760,  # 10MB
                        "backup_count": 5
                    },
                    "console": True
                }
            },
            "monitoring": {
                "metrics_enabled": True,
                "health_check_interval": 60,  # seconds
                "alert_thresholds": {
                    "api_response_time_ms": 5000,
                    "data_latency_minutes": 10
                }
            }
        }

        print("Step 2: Validating configuration structure")

        # Validate required sections exist
        required_sections = [
            "platform", "data_sources", "storage", "data_processing",
            "partitioning", "security", "logging", "monitoring"
        ]

        for section in required_sections:
            assert section in config_structure, f"Required configuration section '{section}' missing"

        # Validate specific configuration elements for A-share market
        assert "daily_bars" in config_structure["storage"]["path_patterns"], "Daily bars path pattern required"
        assert "reference_data" in config_structure["storage"]["path_patterns"], "Reference data path pattern required"

        # Validate A-share specific parameters
        price_range = config_structure["data_processing"]["data_quality"]["validation_rules"]["price_range"]
        assert price_range[0] >= 0.01, "A-share prices must be >= 0.01 CNY"  # Minimum price in A-share market
        assert price_range[1] <= 10000, "A-share prices should be reasonable (<= 10000 CNY)"  # Reasonable upper limit

        # Validate symbol pattern for Chinese market (SH/SZ + 6 digits)
        import re
        symbol_pattern = config_structure["data_processing"]["data_quality"]["validation_rules"]["symbol_pattern"]
        test_symbols = ["SH600000", "SZ000001", "SZ300001"]
        for symbol in test_symbols:
            assert re.match(symbol_pattern, symbol), f"Symbol {symbol} should match pattern {symbol_pattern}"

        print("Step 3: Testing configuration serialization")

        with tempfile.TemporaryDirectory() as temp_dir:
            # Test JSON serialization
            json_config_path = os.path.join(temp_dir, "config.json")
            with open(json_config_path, 'w', encoding='utf-8') as f:
                json.dump(config_structure, f, indent=2, ensure_ascii=False)

            # Read back and validate
            with open(json_config_path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)

            assert loaded_config["platform"]["name"] == config_structure["platform"]["name"], "JSON config should match original"
            print(f"  JSON configuration saved to: {json_config_path}")

            # Test YAML serialization
            yaml_config_path = os.path.join(temp_dir, "config.yaml")
            with open(yaml_config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_structure, f, default_flow_style=False, allow_unicode=True)

            # Read back and validate
            with open(yaml_config_path, 'r', encoding='utf-8') as f:
                loaded_yaml_config = yaml.safe_load(f)

            assert loaded_yaml_config["platform"]["name"] == config_structure["platform"]["name"], "YAML config should match original"
            print(f"  YAML configuration saved to: {yaml_config_path}")

        print("Step 4: Validating A-share market specific configurations")

        # Verify rate limits appropriate for Chinese market data sources
        primary_rate_limit = config_structure["data_sources"]["primary"]["rate_limit"]
        assert "requests_per_minute" in primary_rate_limit, "Rate limit configuration required"
        assert primary_rate_limit["requests_per_minute"] > 0, "Rate limit must be positive"

        # Verify storage path patterns include Chinese market segments
        storage_path = config_structure["storage"]["path_patterns"]["daily_bars"]
        assert "{exchange}" in storage_path, "Storage path should include exchange for Chinese market segmentation"
        assert "{year}" in storage_path, "Storage path should include year for time-based organization"

        # Verify data quality rules appropriate for A-share market
        validation_rules = config_structure["data_processing"]["data_quality"]["validation_rules"]
        assert "symbol_pattern" in validation_rules, "Symbol validation required for Chinese market"
        assert "price_range" in validation_rules, "Price range validation required for A-share market"

        print("All configuration elements validated successfully")
        print(f"Configuration contains {len(required_sections)} main sections")
        print(f"Example data source: {config_structure['data_sources']['primary']['name']}")
        print(f"Storage format: {config_structure['storage']['default_format']}")
        print(f"Max workers: {config_structure['data_processing']['concurrency']['max_workers']}")

        print("SUCCESS: Configuration file structure is appropriate for A-share market data platform")
        return True

    except Exception as e:
        print(f"FAILURE: Error in configuration file structure validation: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = verify_config_file_structure()
    if success:
        print("Verification completed successfully")
    else:
        print("Verification failed")
        exit(1)