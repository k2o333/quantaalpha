"""Standard tool schemas for factor mining.

This module is the **single source of truth** for all tool schemas used by
QuantaAlpha's structured-output (tool-calling) pipeline.  Business code
(e.g. ``factors/proposal.py``) must import from here rather than defining
duplicate inline dicts.
"""

# ---------------------------------------------------------------------------
# Legacy schemas (kept for backward compatibility; may be deprecated later)
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Active schemas used by the current once-mining pipeline
# ---------------------------------------------------------------------------

PROPOSE_FACTORS_TOOL = {
    "type": "function",
    "function": {
        "name": "propose_hypothesis",
        "description": "Propose a new factor hypothesis with observation, knowledge, justification, and specification.",
        "parameters": {
            "type": "object",
            "properties": {
                "hypothesis": {"type": "string"},
                "concise_observation": {"type": "string"},
                "concise_knowledge": {"type": "string"},
                "concise_justification": {"type": "string"},
                "concise_specification": {"type": "string"},
            },
            "required": ["hypothesis"],
        },
    },
}

CONSTRUCT_FACTORS_TOOL = {
    "type": "function",
    "function": {
        "name": "construct_factors",
        "description": "Construct factor experiments from a hypothesis. Keys are factor names.",
        "parameters": {
            "type": "object",
            "properties": {
                "factors": {
                    "type": "object",
                    "description": "Dynamic keys: each key is a factor name, value has description, formulation, expression, variables.",
                },
            },
            "required": ["factors"],
        },
    },
}

FEEDBACK_TOOL = {
    "type": "function",
    "function": {
        "name": "provide_feedback",
        "description": "Provide feedback on hypothesis and experiment results.",
        "parameters": {
            "type": "object",
            "properties": {
                "Observations": {"type": "string"},
                "Feedback for Hypothesis": {"type": "string"},
                "New Hypothesis": {"type": "string"},
                "Reasoning": {"type": "string"},
                "Replace Best Result": {"type": "string"},
            },
            "required": ["Observations"],
        },
    },
}

# ---------------------------------------------------------------------------
# Unified tool list — all active schemas
# ---------------------------------------------------------------------------

ALL_MINING_TOOLS = [PROPOSE_FACTORS_TOOL, CONSTRUCT_FACTORS_TOOL, FEEDBACK_TOOL]
