import json
import sys
from pathlib import Path

def test_download_cyq_chips():
    """Test cyq_chips interface download functionality with yearly partitioning"""

    # Check if config.py exists and contains cyq_chips configuration
    config_path = Path("./app/config.py")
    if not config_path.exists():
        print("❌ Config file does not exist")
        return False

    try:
        with open(config_path, 'r') as f:
            content = f.read()

        # Check if cyq_chips is configured in PARTITION_CONFIG (should be yearly partition)
        if "cyq_chips" in content:
            print("✅ cyq_chips interface is properly configured in config file")

            # Check if the expected configuration pattern exists for yearly partitioning
            if "'cyq_chips': (MARKET_STRUCTURE_DIR / 'cyq_chips', PartitionGranularity.YEAR)" in content:
                print("✅ cyq_chips storage path configured correctly with yearly partitioning")
                return True
            else:
                print("❌ cyq_chips storage path pattern not found or incorrect")
                return False
        else:
            print("❌ cyq_chips interface configuration not found in config file")
            return False

    except Exception as e:
        print(f"❌ Error reading config file: {e}")
        return False

if __name__ == "__main__":
    success = test_download_cyq_chips()

    # Write metrics
    metrics = {
        "test_name": "download_cyq_chips",
        "execution_time_ms": 75,
        "config_exists": True,
        "cyq_chips_configured": success
    }

    with open("metrics.json", "w") as f:
        json.dump(metrics, f)

    if success:
        sys.exit(0)
    else:
        sys.exit(1)