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
        """ALL_MINING_TOOLS contains the three active schemas."""
        from quantaalpha.llm.tool_schemas import ALL_MINING_TOOLS, PROPOSE_FACTORS_TOOL, CONSTRUCT_FACTORS_TOOL, FEEDBACK_TOOL

        assert len(ALL_MINING_TOOLS) == 3
        assert PROPOSE_FACTORS_TOOL in ALL_MINING_TOOLS
        assert CONSTRUCT_FACTORS_TOOL in ALL_MINING_TOOLS
        assert FEEDBACK_TOOL in ALL_MINING_TOOLS


class TestSchemaSingleSource:
    """Tests proving tool_schemas.py is the single source of truth for active schemas.

    These tests verify that:
    - proposal.py imports schemas from tool_schemas.py, not defining them locally.
    - PROPOSE_FACTORS_TOOL, CONSTRUCT_FACTORS_TOOL, FEEDBACK_TOOL exist in tool_schemas.py.
    """

    def test_propose_factors_tool_in_tool_schemas(self):
        """PROPOSE_FACTORS_TOOL must exist in tool_schemas.py."""
        from quantaalpha.llm.tool_schemas import PROPOSE_FACTORS_TOOL

        assert PROPOSE_FACTORS_TOOL["type"] == "function"
        assert PROPOSE_FACTORS_TOOL["function"]["name"] == "propose_hypothesis"
        params = PROPOSE_FACTORS_TOOL["function"]["parameters"]
        assert "hypothesis" in params["properties"]
        assert "concise_observation" in params["properties"]
        assert "concise_knowledge" in params["properties"]
        assert "concise_justification" in params["properties"]
        assert "concise_specification" in params["properties"]

    def test_construct_factors_tool_in_tool_schemas(self):
        """CONSTRUCT_FACTORS_TOOL must exist in tool_schemas.py."""
        from quantaalpha.llm.tool_schemas import CONSTRUCT_FACTORS_TOOL

        assert CONSTRUCT_FACTORS_TOOL["type"] == "function"
        assert CONSTRUCT_FACTORS_TOOL["function"]["name"] == "construct_factors"
        params = CONSTRUCT_FACTORS_TOOL["function"]["parameters"]
        assert "factors" in params["properties"]
        assert params["properties"]["factors"]["type"] == "object"

    def test_feedback_tool_in_tool_schemas(self):
        """FEEDBACK_TOOL must exist in tool_schemas.py."""
        from quantaalpha.llm.tool_schemas import FEEDBACK_TOOL

        assert FEEDBACK_TOOL["type"] == "function"
        assert FEEDBACK_TOOL["function"]["name"] == "provide_feedback"
        params = FEEDBACK_TOOL["function"]["parameters"]
        assert "Observations" in params["properties"]

    def test_proposal_imports_schemas_from_tool_schemas(self):
        """proposal.py must import schemas from tool_schemas.py, not define them locally."""
        from quantaalpha.factors import proposal
        from quantaalpha.llm import tool_schemas

        # PROPOSE_FACTORS_TOOL in proposal.py must be the SAME object as in tool_schemas.py
        assert proposal.PROPOSE_FACTORS_TOOL is tool_schemas.PROPOSE_FACTORS_TOOL, (
            "proposal.py must import PROPOSE_FACTORS_TOOL from tool_schemas.py, not define locally"
        )
        assert proposal.CONSTRUCT_FACTORS_TOOL is tool_schemas.CONSTRUCT_FACTORS_TOOL, (
            "proposal.py must import CONSTRUCT_FACTORS_TOOL from tool_schemas.py, not define locally"
        )
        assert proposal.FEEDBACK_TOOL is tool_schemas.FEEDBACK_TOOL, (
            "proposal.py must import FEEDBACK_TOOL from tool_schemas.py, not define locally"
        )

    def test_all_mining_tools_includes_active_schemas(self):
        """ALL_MINING_TOOLS must include the actively used schemas."""
        from quantaalpha.llm.tool_schemas import ALL_MINING_TOOLS, PROPOSE_FACTORS_TOOL, CONSTRUCT_FACTORS_TOOL, FEEDBACK_TOOL

        assert PROPOSE_FACTORS_TOOL in ALL_MINING_TOOLS
        assert CONSTRUCT_FACTORS_TOOL in ALL_MINING_TOOLS
        assert FEEDBACK_TOOL in ALL_MINING_TOOLS
