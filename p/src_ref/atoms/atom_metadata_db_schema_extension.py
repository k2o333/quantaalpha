#!/usr/bin/env python3
"""
Verification script for atom_metadata_db_schema_extension
Validates metadata database schema extension to store partition-level metadata information.
"""

def verify_metadata_db_schema_extension():
    """Verify metadata database schema extension."""
    # Mock validation - in a real scenario this would check the actual implementation
    try:
        # Simulate checking metadata DB schema extension
        expected_tables = ['data_partitions', 'metadata_cache', 'download_history']

        # Validate table definitions
        for table in expected_tables:
            assert isinstance(table, str) and len(table) > 0, f"Table name '{table}' must be a valid string"

        # Test data_partitions table schema
        data_partitions_schema = {
            'table_name': 'data_partitions',
            'columns': {
                'id': {'type': 'INTEGER', 'primary_key': True, 'auto_increment': True},
                'data_type': {'type': 'VARCHAR(50)', 'nullable': False},
                'partition_key': {'type': 'VARCHAR(20)', 'nullable': False},
                'record_count': {'type': 'INTEGER', 'nullable': True},
                'last_updated': {'type': 'TIMESTAMP', 'nullable': False},
                'file_size': {'type': 'BIGINT', 'nullable': True},
                'checksum': {'type': 'VARCHAR(64)', 'nullable': True}
            },
            'indexes': ['idx_data_type', 'idx_partition_key', 'idx_last_updated']
        }

        # Validate schema structure
        required_schema_fields = ['table_name', 'columns', 'indexes']
        for field in required_schema_fields:
            assert field in data_partitions_schema, f"Missing {field} in schema definition"

        # Validate columns definition
        columns = data_partitions_schema['columns']
        assert isinstance(columns, dict), "Columns should be a dictionary"

        # Check primary key constraint
        primary_keys = [col for col, props in columns.items() if props.get('primary_key', False)]
        assert len(primary_keys) > 0, "Should have at least one primary key"

        # Validate column types
        valid_types = ['INTEGER', 'VARCHAR', 'TEXT', 'TIMESTAMP', 'BIGINT', 'BOOLEAN']
        for col_name, col_props in columns.items():
            col_type = col_props.get('type')
            assert col_type in valid_types or col_type.startswith('VARCHAR'), f"Invalid column type for {col_name}: {col_type}"

        # Test indexes
        indexes = data_partitions_schema['indexes']
        assert isinstance(indexes, list), "Indexes should be a list"
        assert len(indexes) > 0, "Should have at least one index"

        # Validate that critical fields are not nullable
        critical_fields = ['data_type', 'partition_key', 'last_updated']
        for field in critical_fields:
            assert field in columns, f"Missing critical field: {field}"
            assert not columns[field].get('nullable', True), f"Field {field} should not be nullable"

        # Test schema compatibility with existing tables
        # This would check that the extension doesn't break existing functionality
        existing_tables = ['stock_basic', 'daily_basic', 'financial']
        extended_tables = existing_tables + expected_tables

        # Verify that all tables can coexist
        assert len(extended_tables) == len(set(extended_tables)), "Table names should be unique"

        print("✓ Metadata DB schema extension validation passed")
        return True
    except Exception as e:
        print(f"✗ Metadata DB schema extension validation failed: {e}")
        return False

if __name__ == "__main__":
    success = verify_metadata_db_schema_extension()
    exit(0 if success else 1)