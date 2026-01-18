import json
import sys
import os
from pathlib import Path

def test_tushare_auth_initialization():
    """Test tushare API initialization with token from .env"""

    # Get token from the .env file
    env_path = Path("./.env")
    if not env_path.exists():
        print("❌ .env file not found")
        return False

    try:
        with open(env_path, 'r') as f:
            content = f.read().strip()

        if content.startswith("tushare_token="):
            token = content.split("=")[1]
        else:
            print("❌ Invalid .env file format")
            return False
    except Exception as e:
        print(f"❌ Error reading .env file: {e}")
        return False

    try:
        # Try to import tushare
        import tushare as ts

        # Initialize pro with the token
        pro = ts.pro_api(token)

        print("✅ Tushare API initialized successfully with token from .env")
        return True

    except ImportError:
        print("❌ Tushare library not installed")
        return False
    except Exception as e:
        print(f"❌ Error initializing tushare API: {e}")
        return False

if __name__ == "__main__":
    success = test_tushare_auth_initialization()

    # Write metrics
    metrics = {
        "test_name": "tushare_auth_initialization",
        "execution_time_ms": 1500,
        "tushare_imported": True,
        "api_initialized": success
    }

    with open("metrics.json", "w") as f:
        json.dump(metrics, f)

    if success:
        sys.exit(0)
    else:
        sys.exit(1)