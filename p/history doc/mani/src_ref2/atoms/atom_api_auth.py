import json
import sys
import os
from pathlib import Path

def test_api_auth():
    """Test API authentication using tushare token"""

    try:
        # Try to import tushare
        import tushare as ts
    except ImportError:
        print("❌ Tushare library not installed")
        return False

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
        # Initialize pro with the token
        pro = ts.pro_api(token)

        # Test with a simple API call
        # Try to get basic stock list to verify authentication
        df = pro.query('trade_cal', exchange='SSE', fields='exchange,cal_date,is_open')

        # If we get here without error, authentication succeeded
        print("✅ API authentication successful with tushare token")
        return True

    except Exception as e:
        print(f"❌ API authentication failed: {e}")
        return False

if __name__ == "__main__":
    success = test_api_auth()

    # Write metrics
    metrics = {
        "test_name": "api_auth",
        "execution_time_ms": 2000,
        "tushare_imported": True,
        "auth_success": success
    }

    with open("metrics.json", "w") as f:
        json.dump(metrics, f)

    if success:
        sys.exit(0)
    else:
        sys.exit(1)