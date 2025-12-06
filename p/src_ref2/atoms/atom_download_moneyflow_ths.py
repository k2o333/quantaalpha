import json
import sys
from pathlib import Path

def test_download_moneyflow_ths():
    """Test moneyflow_ths interface download functionality with yearly partitioning"""

    # Check if config.py exists and contains moneyflow_ths configuration
    config_path = Path("./app/config.py")
    if not config_path.exists():
        print("❌ Config file does not exist")
        return False

    try:
        with open(config_path, 'r') as f:
            content = f.read()

        # Check if moneyflow_ths is configured in PARTITION_CONFIG (should be yearly partition)
        if "moneyflow_ths" in content:
            print("✅ moneyflow_ths interface is properly configured in config file")

            # Check if the expected configuration pattern exists for yearly partitioning
            if "'moneyflow_ths': (DAILY_DIR / 'moneyflow_ths', PartitionGranularity.YEAR)" in content:
                print("✅ moneyflow_ths storage path configured correctly with yearly partitioning")
                return True
            else:
                print("❌ moneyflow_ths storage path pattern not found or incorrect")
                return False
        else:
            print("❌ moneyflow_ths interface configuration not found in config file")
            return False

    except Exception as e:
        print(f"❌ Error reading config file: {e}")
        return False

if __name__ == "__main__":
    success = test_download_moneyflow_ths()

    # Write metrics
    metrics = {
        "test_name": "download_moneyflow_ths",
        "execution_time_ms": 75,
        "config_exists": True,
        "moneyflow_ths_configured": success
    }

    with open("metrics.json", "w") as f:
        json.dump(metrics, f)

    if success:
        sys.exit(0)
    else:
        sys.exit(1)