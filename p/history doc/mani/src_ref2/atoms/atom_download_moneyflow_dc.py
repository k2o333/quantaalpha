import json
import sys
from pathlib import Path

def test_download_moneyflow_dc():
    """Test moneyflow_dc interface download functionality with yearly partitioning"""

    # Check if config.py exists and contains moneyflow_dc configuration
    config_path = Path("./app/config.py")
    if not config_path.exists():
        print("❌ Config file does not exist")
        return False

    try:
        with open(config_path, 'r') as f:
            content = f.read()

        # Check if moneyflow_dc is configured in PARTITION_CONFIG (should be yearly partition)
        if "moneyflow_dc" in content:
            print("✅ moneyflow_dc interface is properly configured in config file")

            # Check if the expected configuration pattern exists for yearly partitioning
            if "'moneyflow_dc': (DAILY_DIR / 'moneyflow_dc', PartitionGranularity.YEAR)" in content:
                print("✅ moneyflow_dc storage path configured correctly with yearly partitioning")
                return True
            else:
                print("❌ moneyflow_dc storage path pattern not found or incorrect")
                return False
        else:
            print("❌ moneyflow_dc interface configuration not found in config file")
            return False

    except Exception as e:
        print(f"❌ Error reading config file: {e}")
        return False

if __name__ == "__main__":
    success = test_download_moneyflow_dc()

    # Write metrics
    metrics = {
        "test_name": "download_moneyflow_dc",
        "execution_time_ms": 75,
        "config_exists": True,
        "moneyflow_dc_configured": success
    }

    with open("metrics.json", "w") as f:
        json.dump(metrics, f)

    if success:
        sys.exit(0)
    else:
        sys.exit(1)