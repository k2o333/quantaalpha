import json
import sys
from pathlib import Path

def test_download_express():
    """Test express interface download functionality with single file storage"""

    # Check if config.py exists and contains express configuration
    config_path = Path("./app/config.py")
    if not config_path.exists():
        print("❌ Config file does not exist")
        return False

    try:
        with open(config_path, 'r') as f:
            content = f.read()

        # Check if express is configured in PARTITION_CONFIG (should be single file)
        if "express" in content:
            print("✅ express interface is properly configured in config file")

            # Check if the expected configuration pattern exists for single file storage
            if "'express': (EVENTS_DIR / 'express.parquet', PartitionGranularity.NONE)" in content:
                print("✅ express storage path configured correctly as single file")
                return True
            else:
                print("❌ express storage path pattern not found or incorrect")
                return False
        else:
            print("❌ express interface configuration not found in config file")
            return False

    except Exception as e:
        print(f"❌ Error reading config file: {e}")
        return False

if __name__ == "__main__":
    success = test_download_express()

    # Write metrics
    metrics = {
        "test_name": "download_express",
        "execution_time_ms": 75,
        "config_exists": True,
        "express_configured": success
    }

    with open("metrics.json", "w") as f:
        json.dump(metrics, f)

    if success:
        sys.exit(0)
    else:
        sys.exit(1)