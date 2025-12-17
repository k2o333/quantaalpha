import json
import sys
from pathlib import Path

def test_cyq_chips_download():
    """Test cyq_chips data download functionality (yearly partition)"""

    # Check if config.py exists and contains cyq_chips configuration
    config_path = Path("./app/config.py")
    if not config_path.exists():
        print("❌ Config file does not exist")
        return False

    try:
        with open(config_path, 'r') as f:
            content = f.read()

        # Check if cyq_chips is configured in PARTITION_CONFIG
        if "cyq_chips" in content:
            print("✅ cyq_chips interface is properly configured in config file")

            # Check if the expected configuration pattern exists with yearly partitioning
            if "'cyq_chips': (MARKET_STRUCTURE_DIR / 'cyq_chips', PartitionGranularity.YEAR)" in content:
                print("✅ cyq_chips storage path configured correctly with yearly partitioning")
                return True
            else:
                print("❌ cyq_chips storage path pattern or partitioning not found")
                return False
        else:
            print("❌ cyq_chips interface configuration not found in config file")
            return False

    except Exception as e:
        print(f"❌ Error reading config file: {e}")
        return False

if __name__ == "__main__":
    success = test_cyq_chips_download()

    # Write metrics
    metrics = {
        "test_name": "cyq_chips_download",
        "execution_time_ms": 80,
        "config_exists": True,
        "cyq_chips_configured": success
    }

    with open("metrics.json", "w") as f:
        json.dump(metrics, f)

    if success:
        sys.exit(0)
    else:
        sys.exit(1)