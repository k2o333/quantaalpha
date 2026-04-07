"""Standard tool schemas for factor mining."""

TOOL_PROPOSE_FACTORS = {
    "type": "function",
    "function": {
        "name": "propose_factors",
        "description": "Propose new alpha factors for quantitative research",
        "parameters": {
            "type": "object",
            "properties": {
                "factors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "factor_name": {"type": "string"},
                            "factor_expression": {"type": "string"},
                            "hypothesis": {"type": "string"},
                            "data_dependency": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["factor_name", "factor_expression"],
                    },
                }
            },
            "required": ["factors"],
        },
    },
}

TOOL_PROPOSE_HYPOTHESIS = {
    "type": "function",
    "function": {
        "name": "propose_hypothesis",
        "description": "Propose a research hypothesis for factor exploration",
        "parameters": {
            "type": "object",
            "properties": {
                "hypothesis": {"type": "string"},
                "reason": {"type": "string"},
                "observations": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["hypothesis"],
        },
    },
}

ALL_MINING_TOOLS = [TOOL_PROPOSE_FACTORS, TOOL_PROPOSE_HYPOTHESIS]
