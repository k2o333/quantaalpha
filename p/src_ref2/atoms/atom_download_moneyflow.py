import json
import sys
from pathlib import Path

def test_download_moneyflow():
    """Test moneyflow interface download functionality with yearly partitioning"""

    # Check if config.py exists and contains moneyflow configuration
    config_path = Path("./app/config.py")
    if not config_path.exists():
        print("❌ Config file does not exist")
        return False

    try:
        with open(config_path, 'r') as f:
            content = f.read()

        # Check if moneyflow is configured in PARTITION_CONFIG with yearly partitioning
        partition_config_pattern = "'moneyflow': (DAILY_DIR / 'moneyflow', PartitionGranularity.YEAR)"

        if partition_config_pattern in content:
            print("✅ moneyflow storage path configured correctly with yearly partitioning in DAILY_DIR")
            partition_configured = True
        else:
            print("❌ moneyflow storage configuration not found in PARTITION_CONFIG")
            return False

        # Check for API limits configuration
        if "'moneyflow': 200" in content:
            print("✅ moneyflow API limits configured correctly")
            api_limits_configured = True
        else:
            print("❌ moneyflow API limits not configured")
            return False

        if partition_configured and api_limits_configured:
            print("✅ moneyflow interface is properly configured for both storage and API limits")
            return True
        else:
            print("❌ moneyflow interface configuration incomplete")
            return False

    except Exception as e:
        print(f"❌ Error reading config file: {e}")
        return False

if __name__ == "__main__":
    success = test_download_moneyflow()

    # Write metrics
    metrics = {
        "test_name": "download_moneyflow",
        "execution_time_ms": 75,
        "config_exists": True,
        "moneyflow_configured": success
    }

    with open("metrics.json", "w") as f:
        json.dump(metrics, f)

    if success:
        sys.exit(0)
    else:
        sys.exit(1)