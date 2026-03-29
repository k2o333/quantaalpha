"""
Tests for continuous pipeline configuration.

Verifies:
- YAML configuration parsing
- SchedulerConfig creation from PipelineConfig
- Configuration contract compliance
"""

import tempfile
from pathlib import Path

import pytest
import yaml


class TestPipelineConfig:
    """Tests for PipelineConfig YAML parsing."""

    @pytest.fixture
    def sample_yaml_content(self) -> str:
        """Sample pipeline.yaml content for testing."""
        return """
runtime:
  data_check_interval_seconds: 300
  revalidation_interval_hours: 24
  revalidation_days_threshold: 21
  mining_interval_hours: 12

app4_bridge:
  enabled: true
  interfaces:
    - daily
    - daily_basic
    - moneyflow
  data_roots:
    - /home/quan/testdata/aspipe_v4/data
  freshness_threshold_hours: 24
  update_timeout_seconds: 180
  max_update_interfaces_per_cycle: 3
  python_executable: /root/miniforge3/envs/get/bin/python

factor:
  library_path: third_party/quantaalpha/data/factorlib/all_factors_library.json
  monitoring_output_path: log/monitoring/
  backtest_config_path: config/backtest.yaml

validation:
  min_ic: 0.02
  min_rank_ic: 0.01
  max_revalidation_per_run: 10
  max_mining_per_run: 5

execution:
  train:
    start: "2020-01-01"
    end: "2022-12-31"
  valid:
    start: "2023-01-01"
    end: "2023-12-31"
  test:
    start: "2024-01-01"
    end: "2024-12-31"

features:
  enable_data_monitor: true
  enable_revalidation: true
  enable_mining: true
"""

    @pytest.fixture
    def temp_yaml_file(self, sample_yaml_content: str) -> Path:
        """Create a temporary YAML file for testing."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(sample_yaml_content)
            return Path(f.name)

    def test_load_pipeline_config(self, temp_yaml_file: Path):
        """Test loading pipeline configuration from YAML."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig.from_yaml(str(temp_yaml_file))

        # Runtime checks
        assert config.data_check_interval_seconds == 300
        assert config.revalidation_interval_hours == 24
        assert config.revalidation_days_threshold == 21
        assert config.mining_interval_hours == 12

        # App4 bridge checks
        assert config.app4_bridge.enabled is True
        assert "daily" in config.app4_bridge.interfaces
        assert "/home/quan/testdata/aspipe_v4/data" in config.app4_bridge.data_roots
        assert config.app4_bridge.freshness_threshold_hours == 24
        assert config.app4_bridge.update_timeout_seconds == 180
        assert config.app4_bridge.max_update_interfaces_per_cycle == 3
        assert config.app4_bridge.python_executable == "/root/miniforge3/envs/get/bin/python"

        # Factor checks
        assert config.factor.library_path == "third_party/quantaalpha/data/factorlib/all_factors_library.json"
        assert config.factor.monitoring_output_path == "log/monitoring/"
        assert config.factor.backtest_config_path == "config/backtest.yaml"

        # Validation checks
        assert config.validation.min_ic == 0.02
        assert config.validation.min_rank_ic == 0.01
        assert config.validation.max_revalidation_per_run == 10
        assert config.validation.max_mining_per_run == 5

        # Execution period checks
        assert config.execution.train.start == "2020-01-01"
        assert config.execution.train.end == "2022-12-31"
        assert config.execution.valid.start == "2023-01-01"
        assert config.execution.valid.end == "2023-12-31"
        assert config.execution.test.start == "2024-01-01"
        assert config.execution.test.end == "2024-12-31"

        # Feature flags checks
        assert config.enable_data_monitor is True
        assert config.enable_revalidation is True
        assert config.enable_mining is True

    def test_pipeline_config_to_dict(self, temp_yaml_file: Path):
        """Test conversion of PipelineConfig to dictionary."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        config = PipelineConfig.from_yaml(str(temp_yaml_file))
        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert "runtime" in config_dict
        assert "app4_bridge" in config_dict
        assert "factor" in config_dict
        assert "validation" in config_dict
        assert "execution" in config_dict
        assert "features" in config_dict

        # Verify nested structure
        assert config_dict["runtime"]["data_check_interval_seconds"] == 300
        assert config_dict["app4_bridge"]["interfaces"] == ["daily", "daily_basic", "moneyflow"]
        assert config_dict["app4_bridge"]["update_timeout_seconds"] == 180
        assert config_dict["app4_bridge"]["max_update_interfaces_per_cycle"] == 3
        assert config_dict["app4_bridge"]["python_executable"] == "/root/miniforge3/envs/get/bin/python"
        assert config_dict["validation"]["min_ic"] == 0.02

    def test_pipeline_config_defaults(self):
        """Test PipelineConfig with default values."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        # Create empty YAML file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            temp_path = Path(f.name)

        try:
            config = PipelineConfig.from_yaml(str(temp_path))

            # Check defaults
            assert config.data_check_interval_seconds == 300
            assert config.revalidation_interval_hours == 24
            assert config.app4_bridge.enabled is True
            assert config.validation.min_ic == 0.02
        finally:
            temp_path.unlink()


class TestSchedulerConfigFromPipeline:
    """Tests for creating SchedulerConfig from PipelineConfig."""

    def test_scheduler_config_from_pipeline(self):
        """Test SchedulerConfig creation from PipelineConfig."""
        from quantaalpha.continuous.scheduler import PipelineConfig, SchedulerConfig, ValidationConfig

        # Create a PipelineConfig with proper nested validation
        pipeline = PipelineConfig(
            data_check_interval_seconds=600,
            revalidation_interval_hours=48,
            revalidation_days_threshold=30,
            mining_interval_hours=24,
            validation=ValidationConfig(
                max_revalidation_per_run=5,
                max_mining_per_run=3,
            ),
        )

        # Create SchedulerConfig from PipelineConfig
        scheduler_config = SchedulerConfig.from_pipeline_config(pipeline)

        assert scheduler_config.data_check_interval_seconds == 600
        assert scheduler_config.revalidation_interval_hours == 48
        assert scheduler_config.revalidation_days_threshold == 30
        assert scheduler_config.mining_interval_hours == 24
        assert scheduler_config.max_revalidation_per_run == 5
        assert scheduler_config.max_mining_per_run == 3

    def test_scheduler_config_with_app4_bridge(self):
        """Test SchedulerConfig properly maps app4_bridge data_roots."""
        from quantaalpha.continuous.scheduler import (
            App4BridgeConfig,
            PipelineConfig,
            SchedulerConfig,
        )

        pipeline = PipelineConfig(
            app4_bridge=App4BridgeConfig(
                enabled=True,
                data_roots=["/home/quan/testdata/aspipe_v4/data", "/home/quan/testdata/aspipe_v4/data2"],
                interfaces=["daily", "moneyflow"],
            )
        )

        scheduler_config = SchedulerConfig.from_pipeline_config(pipeline)

        assert scheduler_config.data_dirs == ["/home/quan/testdata/aspipe_v4/data", "/home/quan/testdata/aspipe_v4/data2"]


class TestApp4BridgeConfig:
    """Tests for App4BridgeConfig dataclass."""

    def test_app4_bridge_default_values(self):
        """Test App4BridgeConfig default values."""
        from quantaalpha.continuous.scheduler import App4BridgeConfig

        config = App4BridgeConfig()

        assert config.enabled is True
        assert config.interfaces == []
        assert config.freshness_threshold_hours == 24
        assert config.update_timeout_seconds == 120
        assert config.max_update_interfaces_per_cycle == 5
        assert config.python_executable == ""
        assert config.data_roots == []
        assert config.freshness_threshold_hours == 24

    def test_app4_bridge_has_update_timeout_seconds(self):
        """Test App4BridgeConfig has update_timeout_seconds field."""
        from quantaalpha.continuous.scheduler import App4BridgeConfig

        config = App4BridgeConfig()
        assert hasattr(config, "update_timeout_seconds")
        assert config.update_timeout_seconds == 120

    def test_app4_bridge_has_max_update_interfaces_per_cycle(self):
        """Test App4BridgeConfig has max_update_interfaces_per_cycle field."""
        from quantaalpha.continuous.scheduler import App4BridgeConfig

        config = App4BridgeConfig()
        assert hasattr(config, "max_update_interfaces_per_cycle")
        assert config.max_update_interfaces_per_cycle == 5

    def test_pipeline_config_reads_bridge_update_timeout_from_yaml(self, tmp_path: Path):
        """Test PipelineConfig reads update_timeout_seconds from YAML."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        yaml_content = """
app4_bridge:
  enabled: true
  interfaces:
    - daily
  data_roots:
    - /home/quan/testdata/aspipe_v4/data
  freshness_threshold_hours: 24
  update_timeout_seconds: 180
"""
        yaml_path = tmp_path / "test_timeout.yaml"
        yaml_path.write_text(yaml_content)

        config = PipelineConfig.from_yaml(str(yaml_path))

        assert config.app4_bridge.update_timeout_seconds == 180

    def test_pipeline_config_reads_max_update_interfaces_from_yaml(self, tmp_path: Path):
        """Test PipelineConfig reads max_update_interfaces_per_cycle from YAML."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        yaml_content = """
app4_bridge:
  enabled: true
  interfaces:
    - daily
  data_roots:
    - /home/quan/testdata/aspipe_v4/data
  freshness_threshold_hours: 24
  max_update_interfaces_per_cycle: 3
"""
        yaml_path = tmp_path / "test_max_interfaces.yaml"
        yaml_path.write_text(yaml_content)

        config = PipelineConfig.from_yaml(str(yaml_path))

        assert config.app4_bridge.max_update_interfaces_per_cycle == 3


class TestFactorConfig:
    """Tests for FactorConfig dataclass."""

    def test_factor_config_default_values(self):
        """Test FactorConfig default values."""
        from quantaalpha.continuous.scheduler import FactorConfig

        config = FactorConfig()

        assert config.library_path == "third_party/quantaalpha/data/factorlib/all_factors_library.json"
        assert config.monitoring_output_path == "log/monitoring/"
        assert config.backtest_config_path == "config/backtest.yaml"

    def test_pipeline_config_uses_existing_factorlib_path_by_default(self, tmp_path: Path):
        """Test PipelineConfig uses existing factor library path by default."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        yaml_content = """
app4_bridge:
  enabled: true
  interfaces:
    - daily
  data_roots:
    - /home/quan/testdata/aspipe_v4/data
"""
        yaml_path = tmp_path / "test_lib_path.yaml"
        yaml_path.write_text(yaml_content)

        config = PipelineConfig.from_yaml(str(yaml_path))

        assert config.factor.library_path.endswith("third_party/quantaalpha/data/factorlib/all_factors_library.json")


class TestRuntimeConfig:
    """Tests for runtime configuration fields."""

    def test_runtime_config_has_cycle_budget_seconds(self):
        """Test RuntimeConfig/SchedulerConfig has cycle_budget_seconds field."""
        from quantaalpha.continuous.scheduler import SchedulerConfig

        config = SchedulerConfig()
        assert hasattr(config, "cycle_budget_seconds")
        assert config.cycle_budget_seconds == 3600  # default 1 hour

    def test_runtime_config_has_per_factor_timeout_seconds(self):
        """Test RuntimeConfig/SchedulerConfig has per_factor_timeout_seconds field."""
        from quantaalpha.continuous.scheduler import SchedulerConfig

        config = SchedulerConfig()
        assert hasattr(config, "per_factor_timeout_seconds")
        assert config.per_factor_timeout_seconds == 300  # default 5 minutes

    def test_pipeline_config_parses_cycle_budget_seconds_from_yaml(self, tmp_path: Path):
        """Test PipelineConfig parses cycle_budget_seconds from YAML."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        yaml_content = """
runtime:
  cycle_budget_seconds: 7200
"""
        yaml_path = tmp_path / "test_cycle_budget.yaml"
        yaml_path.write_text(yaml_content)

        config = PipelineConfig.from_yaml(str(yaml_path))

        assert config.cycle_budget_seconds == 7200

    def test_pipeline_config_parses_per_factor_timeout_seconds_from_yaml(self, tmp_path: Path):
        """Test PipelineConfig parses per_factor_timeout_seconds from YAML."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        yaml_content = """
runtime:
  per_factor_timeout_seconds: 600
"""
        yaml_path = tmp_path / "test_factor_timeout.yaml"
        yaml_path.write_text(yaml_content)

        config = PipelineConfig.from_yaml(str(yaml_path))

        assert config.per_factor_timeout_seconds == 600

    def test_pipeline_config_runtime_defaults(self):
        """Test PipelineConfig has reasonable defaults for runtime fields."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        # Create empty YAML file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            temp_path = Path(f.name)

        try:
            config = PipelineConfig.from_yaml(str(temp_path))

            # Check runtime defaults
            assert config.cycle_budget_seconds == 3600
            assert config.per_factor_timeout_seconds == 300
        finally:
            temp_path.unlink()

    def test_scheduler_config_from_pipeline_preserves_cycle_budget(self):
        """Test SchedulerConfig.from_pipeline_config preserves cycle_budget_seconds."""
        from quantaalpha.continuous.scheduler import PipelineConfig, SchedulerConfig

        pipeline = PipelineConfig(cycle_budget_seconds=7200)
        scheduler = SchedulerConfig.from_pipeline_config(pipeline)

        assert scheduler.cycle_budget_seconds == 7200

    def test_scheduler_config_from_pipeline_preserves_per_factor_timeout(self):
        """Test SchedulerConfig.from_pipeline_config preserves per_factor_timeout_seconds."""
        from quantaalpha.continuous.scheduler import PipelineConfig, SchedulerConfig

        pipeline = PipelineConfig(per_factor_timeout_seconds=600)
        scheduler = SchedulerConfig.from_pipeline_config(pipeline)

        assert scheduler.per_factor_timeout_seconds == 600


class TestApp4BridgeInterfaceTiers:
    """Tests for app4_bridge interface_tiers field."""

    def test_app4_bridge_has_interface_tiers(self):
        """Test App4BridgeConfig has interface_tiers field."""
        from quantaalpha.continuous.scheduler import App4BridgeConfig

        config = App4BridgeConfig()
        assert hasattr(config, "interface_tiers")
        assert config.interface_tiers == {}

    def test_app4_bridge_interface_tiers_default_empty_dict(self):
        """Test App4BridgeConfig interface_tiers defaults to empty dict."""
        from quantaalpha.continuous.scheduler import App4BridgeConfig

        config = App4BridgeConfig()
        assert config.interface_tiers == {}

    def test_pipeline_config_parses_interface_tiers_from_yaml(self, tmp_path: Path):
        """Test PipelineConfig parses interface_tiers from YAML."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        yaml_content = """
app4_bridge:
  enabled: true
  interfaces:
    - daily
    - moneyflow
  interface_tiers:
    critical:
      - daily
    normal:
      - moneyflow
"""
        yaml_path = tmp_path / "test_interface_tiers.yaml"
        yaml_path.write_text(yaml_content)

        config = PipelineConfig.from_yaml(str(yaml_path))

        assert config.app4_bridge.interface_tiers == {"critical": ["daily"], "normal": ["moneyflow"]}

    def test_pipeline_config_to_dict_includes_interface_tiers(self, tmp_path: Path):
        """Test PipelineConfig.to_dict includes interface_tiers."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        yaml_content = """
app4_bridge:
  enabled: true
  interface_tiers:
    critical:
      - daily
"""
        yaml_path = tmp_path / "test_tiers_dict.yaml"
        yaml_path.write_text(yaml_content)

        config = PipelineConfig.from_yaml(str(yaml_path))
        config_dict = config.to_dict()

        assert "interface_tiers" in config_dict["app4_bridge"]
        assert config_dict["app4_bridge"]["interface_tiers"] == {"critical": ["daily"]}


class TestValidationConfig:
    """Tests for ValidationConfig dataclass."""

    def test_validation_config_default_values(self):
        """Test ValidationConfig default values."""
        from quantaalpha.continuous.scheduler import ValidationConfig

        config = ValidationConfig()

        assert config.min_ic == 0.02
        assert config.min_rank_ic == 0.01
        assert config.max_revalidation_per_run == 10
        assert config.max_mining_per_run == 5


class TestExecutionConfig:
    """Tests for ExecutionConfig dataclass."""

    def test_execution_config_default_values(self):
        """Test ExecutionConfig default values."""
        from quantaalpha.continuous.scheduler import ExecutionConfig, ExecutionPeriod

        config = ExecutionConfig()

        assert isinstance(config.train, ExecutionPeriod)
        assert isinstance(config.valid, ExecutionPeriod)
        assert isinstance(config.test, ExecutionPeriod)
        assert config.train.start == ""
        assert config.train.end == ""

    def test_execution_period_custom_values(self):
        """Test ExecutionPeriod with custom values."""
        from quantaalpha.continuous.scheduler import ExecutionPeriod

        period = ExecutionPeriod(start="2020-01-01", end="2022-12-31")

        assert period.start == "2020-01-01"
        assert period.end == "2022-12-31"


class TestConfigContract:
    """Tests for configuration contract compliance."""

    def test_required_config_items_present(self, tmp_path: Path):
        """Verify all required configuration items are present in the contract."""
        from quantaalpha.continuous.scheduler import PipelineConfig

        # Check that we can parse a minimal valid config
        minimal_config = {
            "runtime": {
                "data_check_interval_seconds": 300,
                "revalidation_interval_hours": 24,
                "mining_interval_hours": 12,
            },
            "app4_bridge": {
                "enabled": True,
                "interfaces": ["daily"],
                "data_roots": ["/home/quan/testdata/aspipe_v4/data"],
                "freshness_threshold_hours": 24,
            },
            "factor": {
                "library_path": "third_party/quantaalpha/data/factorlib/all_factors_library.json",
                "monitoring_output_path": "log/monitoring/",
                "backtest_config_path": "config/backtest.yaml",
            },
            "validation": {
                "min_ic": 0.02,
                "min_rank_ic": 0.01,
                "max_revalidation_per_run": 10,
                "max_mining_per_run": 5,
            },
            "execution": {
                "train": {"start": "2020-01-01", "end": "2022-12-31"},
                "valid": {"start": "2023-01-01", "end": "2023-12-31"},
                "test": {"start": "2024-01-01", "end": "2024-12-31"},
            },
            "features": {
                "enable_data_monitor": True,
                "enable_revalidation": True,
                "enable_mining": True,
            },
        }

        yaml_path = tmp_path / "test_config.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(minimal_config, f)

        config = PipelineConfig.from_yaml(str(yaml_path))

        # Verify all sections are present (runtime values are at top level)
        assert config.data_check_interval_seconds == 300
        assert len(config.app4_bridge.interfaces) == 1
        assert config.validation.min_ic == 0.02
        assert config.execution.train.start == "2020-01-01"

    def test_downstream_assumptions_data_roots(self):
        """Test downstream assumption: data_roots maps to data_dirs in SchedulerConfig."""
        from quantaalpha.continuous.scheduler import App4BridgeConfig, PipelineConfig, SchedulerConfig

        pipeline = PipelineConfig(
            app4_bridge=App4BridgeConfig(
                data_roots=["/path/to/data1", "/path/to/data2"]
            )
        )

        scheduler = SchedulerConfig.from_pipeline_config(pipeline)

        assert scheduler.data_dirs == ["/path/to/data1", "/path/to/data2"]

    def test_downstream_assumptions_validation_thresholds(self):
        """Test downstream assumption: validation thresholds map into SchedulerConfig fields."""
        from quantaalpha.continuous.scheduler import PipelineConfig, SchedulerConfig, ValidationConfig

        pipeline = PipelineConfig(
            validation=ValidationConfig(
                min_ic=0.05,
                min_rank_ic=0.03,
                max_revalidation_per_run=10,
                max_mining_per_run=5,
            )
        )

        scheduler = SchedulerConfig.from_pipeline_config(pipeline)

        assert scheduler.min_ic == 0.05
        assert scheduler.min_rank_ic == 0.03

    def test_downstream_assumptions_execution_periods(self):
        """Test downstream assumption: execution periods are accessible."""
        from quantaalpha.continuous.scheduler import ExecutionConfig, ExecutionPeriod, PipelineConfig

        config = PipelineConfig(
            execution=ExecutionConfig(
                train=ExecutionPeriod(start="2020-01-01", end="2022-12-31"),
                valid=ExecutionPeriod(start="2023-01-01", end="2023-12-31"),
                test=ExecutionPeriod(start="2024-01-01", end="2024-12-31"),
            )
        )

        assert config.execution.train.start == "2020-01-01"
        assert config.execution.train.end == "2022-12-31"
        assert config.execution.valid.start == "2023-01-01"
        assert config.execution.test.start == "2024-01-01"
