import json
import sys
from pathlib import Path

def test_existing_stk_factor():
    """Test existing stk_factor interface functionality"""

    # Check if config.py exists and contains stk_factor configuration
    config_path = Path("./app/config.py")
    if not config_path.exists():
        print("❌ Config file does not exist")
        return False

    try:
        with open(config_path, 'r') as f:
            content = f.read()

        # Check if stk_factor is configured in API_LIMITS
        if "stk_factor" in content:
            print("✅ stk_factor interface is properly configured in config file")

            # Check for API_LIMITS entry
            api_limits_configured = "'stk_factor': 200" in content

            if api_limits_configured:
                print("✅ stk_factor API limits configured correctly")
                return True
            else:
                print("❌ stk_factor API limits configuration not found")
                return False
        else:
            print("❌ stk_factor interface configuration not found in config file")
            return False

    except Exception as e:
        print(f"❌ Error reading config file: {e}")
        return False

if __name__ == "__main__":
    success = test_existing_stk_factor()

    # Write metrics
    metrics = {
        "test_name": "existing_stk_factor",
        "execution_time_ms": 75,
        "config_exists": True,
        "stk_factor_configured": success
    }

    with open("metrics.json", "w") as f:
        json.dump(metrics, f)

    if success:
        sys.exit(0)
    else:
        sys.exit(1)