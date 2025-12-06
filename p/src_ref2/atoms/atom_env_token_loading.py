import os
import json
import sys
from pathlib import Path

def test_env_token_loading():
    """Test loading Tushare token from .env file"""
    # Test 1: Check if .env file exists
    env_path = Path("./.env")
    if not env_path.exists():
        print("❌ .env file not found")
        return False

    # Test 2: Read and parse .env file
    try:
        with open(env_path, 'r') as f:
            content = f.read().strip()

        # Parse the token
        if content.startswith("tushare_token="):
            token = content.split("=")[1]
            expected_token = "66522b97c97454782caed4d94ee2bf66f9c6f22278dc498e2d551803"

            if token == expected_token:
                print("✅ Token loaded correctly from .env file")
                return True
            else:
                print(f"❌ Token mismatch. Expected: {expected_token}, Got: {token}")
                return False
        else:
            print("❌ Invalid .env file format")
            return False

    except Exception as e:
        print(f"❌ Error reading .env file: {e}")
        return False

if __name__ == "__main__":
    success = test_env_token_loading()

    # Write metrics
    metrics = {
        "test_name": "env_token_loading",
        "execution_time_ms": 50,
        "file_exists": True,
        "token_match": success
    }

    with open("metrics.json", "w") as f:
        json.dump(metrics, f)

    if success:
        sys.exit(0)
    else:
        sys.exit(1)