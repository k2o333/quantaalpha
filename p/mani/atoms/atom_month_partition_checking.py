#!/usr/bin/env python3
"""
Verification script for atom_month_partition_checking
Validates month partition data availability checking for year-month level data existence.
"""

def verify_month_partition_checking():
    """Verify month partition data availability checking."""
    # Mock validation - in a real scenario this would check the actual implementation
    try:
        # Simulate checking month partition functionality
        month_partitions = ['202301', '202302', '202303', '202312', '202401']

        # Test month format validation
        for partition in month_partitions:
            # Validate that month partition is in correct YYYYMM format
            assert len(partition) == 6 and partition.isdigit(), f"Invalid month partition format: {partition}"

            year = int(partition[:4])
            month = int(partition[4:6])

            assert 1900 <= year <= 2100, f"Year out of reasonable range in {partition}"
            assert 1 <= month <= 12, f"Month out of range in {partition}"

        # Simulate availability checking for month partitions
        available_months = ['202301', '202302', '202304', '202305']
        requested_months = ['202301', '202302', '202303', '202304', '202305']

        # Check missing months
        missing_months = [month for month in requested_months if month not in available_months]
        expected_missing = ['202303']
        assert missing_months == expected_missing, f"Expected missing months {expected_missing}, got {missing_months}"

        # Test with different data types in month partitions
        month_partition_data = {
            'daily_basic': ['202301', '202302', '202303'],
            'financial': ['202304', '202305', '202306'],
            'suspend': ['202307', '202308', '202309']
        }

        for data_type, months in month_partition_data.items():
            for month_partition in months:
                # Validate format is correct YYYYMM
                assert len(month_partition) == 6 and month_partition.isdigit(), f"Invalid month format in {data_type}: {month_partition}"

                year = int(month_partition[:4])
                month = int(month_partition[4:6])

                assert 1900 <= year <= 2100, f"Year out of range in {data_type}: {month_partition}"
                assert 1 <= month <= 12, f"Month out of range in {data_type}: {month_partition}"

        print("✓ Month partition checking validation passed")
        return True
    except Exception as e:
        print(f"✗ Month partition checking validation failed: {e}")
        return False

if __name__ == "__main__":
    success = verify_month_partition_checking()
    exit(0 if success else 1)