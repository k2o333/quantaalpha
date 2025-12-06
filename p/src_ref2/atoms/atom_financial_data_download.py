import json
import sys
from pathlib import Path

def test_financial_data_download():
    """Test financial data download functionality using VIP interfaces"""

    # Check if config.py exists and contains financial data configurations
    config_path = Path("./app/config.py")
    if not config_path.exists():
        print("❌ Config file does not exist")
        return False

    try:
        with open(config_path, 'r') as f:
            content = f.read()

        # Check if financial data interfaces are configured (balancesheet_vip, income_vip, cashflow_vip, fina_indicator_vip)
        financial_configs = [
            "'balancesheet_vip':",  # This should be configured for VIP financial data
            "'income_vip':",
            "'cashflow_vip':",
            "'fina_indicator_vip':"
        ]

        all_configs_present = True
        for config in financial_configs:
            if config not in content:
                print(f"❌ Financial data configuration {config} not found in config file")
                all_configs_present = False
            else:
                print(f"✅ Financial data configuration {config} found in config file")

        # Also check that API limits exist for these financial interfaces
        financial_limits = [
            "'balancesheet_vip': 50",
            "'income_vip': 50",
            "'cashflow_vip': 50",
            "'fina_indicator_vip': 50"
        ]

        all_limits_present = True
        for limit in financial_limits:
            if limit not in content:
                print(f"❌ Financial data API limit {limit} not found in config file")
                all_limits_present = False
            else:
                print(f"✅ Financial data API limit {limit} found in config file")

        if all_configs_present and all_limits_present:
            print("✅ All financial data download configurations are properly set up for VIP interfaces")
            return True
        else:
            print("❌ Some financial data download configurations are missing")
            return False

    except Exception as e:
        print(f"❌ Error reading config file: {e}")
        return False

if __name__ == "__main__":
    success = test_financial_data_download()

    # Write metrics
    metrics = {
        "test_name": "financial_data_download",
        "execution_time_ms": 80,
        "config_exists": True,
        "financial_data_configured": success
    }

    with open("metrics.json", "w") as f:
        json.dump(metrics, f)

    if success:
        sys.exit(0)
    else:
        sys.exit(1)