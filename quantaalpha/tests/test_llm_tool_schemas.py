"""Tests for tool schema definitions."""


class TestToolSchemas:
    """Tests for standard tool schemas."""

    def test_propose_factors_schema_structure(self):
        """propose_factors tool has correct structure."""
        from quantaalpha.llm.tool_schemas import TOOL_PROPOSE_FACTORS

        assert TOOL_PROPOSE_FACTORS["type"] == "function"
        assert TOOL_PROPOSE_FACTORS["function"]["name"] == "propose_factors"
        params = TOOL_PROPOSE_FACTORS["function"]["parameters"]
        assert "factors" in params["properties"]
        assert "factors" in params["required"]

    def test_propose_hypothesis_schema_structure(self):
        """propose_hypothesis tool has correct structure."""
        from quantaalpha.llm.tool_schemas import TOOL_PROPOSE_HYPOTHESIS

        assert TOOL_PROPOSE_HYPOTHESIS["type"] == "function"
        assert TOOL_PROPOSE_HYPOTHESIS["function"]["name"] == "propose_hypothesis"
        params = TOOL_PROPOSE_HYPOTHESIS["function"]["parameters"]
        assert "hypothesis" in params["properties"]
        assert "hypothesis" in params["required"]

    def test_all_mining_tools_list(self):
        """ALL_MINING_TOOLS contains both schemas."""
        from quantaalpha.llm.tool_schemas import ALL_MINING_TOOLS, TOOL_PROPOSE_FACTORS, TOOL_PROPOSE_HYPOTHESIS

        assert len(ALL_MINING_TOOLS) == 2
        assert TOOL_PROPOSE_FACTORS in ALL_MINING_TOOLS
        assert TOOL_PROPOSE_HYPOTHESIS in ALL_MINING_TOOLS
