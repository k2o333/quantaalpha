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
# Additional schemas for migrated business callers
# ---------------------------------------------------------------------------

CONSISTENCY_CHECK_TOOL = {
    "type": "function",
    "function": {
        "name": "check_consistency",
        "description": "Analyze consistency between factor expressions, descriptions, and underlying logic. Returns pass/fail with explanations.",
        "parameters": {
            "type": "object",
            "properties": {
                "is_consistent": {"type": "boolean", "description": "Whether the factor is internally consistent."},
                "issues": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of identified consistency issues.",
                },
                "suggestions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Suggestions to fix identified issues.",
                },
            },
            "required": ["is_consistent"],
        },
    },
}

FACTOR_EXTRACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_factors",
        "description": "Extract factor name, description, and formulation from report content.",
        "parameters": {
            "type": "object",
            "properties": {
                "factors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Factor name."},
                            "description": {"type": "string", "description": "Factor description."},
                            "formulation": {"type": "string", "description": "Factor formulation/expression."},
                        },
                        "required": ["name"],
                    },
                },
            },
            "required": ["factors"],
        },
    },
}

REPORT_CLASSIFICATION_TOOL = {
    "type": "function",
    "function": {
        "name": "classify_report",
        "description": "Classify a PDF report into a research category with confidence score.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Report category/classification."},
                "confidence": {"type": "number", "description": "Confidence score (0-1)."},
                "reasoning": {"type": "string", "description": "Brief reasoning for the classification."},
            },
            "required": ["category"],
        },
    },
}

EVALUATOR_FINAL_DECISION_TOOL = {
    "type": "function",
    "function": {
        "name": "final_decision",
        "description": "Make a final evaluation decision on factor quality and validity.",
        "parameters": {
            "type": "object",
            "properties": {
                "passed": {"type": "boolean", "description": "Whether the factor passed evaluation."},
                "score": {"type": "number", "description": "Evaluation score."},
                "feedback": {"type": "string", "description": "Detailed feedback/justification."},
                "action": {
                    "type": "string",
                    "enum": ["accept", "reject", "modify"],
                    "description": "Recommended action.",
                },
            },
            "required": ["passed"],
        },
    },
}

FACTOR_CORRECTION_TOOL = {
    "type": "function",
    "function": {
        "name": "correct_factor",
        "description": "Identify and correct errors in a factor expression or implementation.",
        "parameters": {
            "type": "object",
            "properties": {
                "has_error": {"type": "boolean", "description": "Whether an error was found."},
                "error_type": {"type": "string", "description": "Type of error found."},
                "original": {"type": "string", "description": "Original factor expression."},
                "corrected": {"type": "string", "description": "Corrected factor expression."},
                "explanation": {"type": "string", "description": "Explanation of the correction."},
            },
            "required": ["has_error"],
        },
    },
}

KNOWLEDGE_COMPONENT_TOOL = {
    "type": "function",
    "function": {
        "name": "select_knowledge_components",
        "description": "Select component indices that are relevant to a new task.",
        "parameters": {
            "type": "object",
            "properties": {
                "component_no_list": {
                    "type": "array",
                    "items": {"type": "integer"},
                },
            },
            "required": ["component_no_list"],
        },
    },
}

HYPOTHESIS_FROM_REPORT_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_report_hypothesis",
        "description": "Generate a structured factor-mining hypothesis from report content and extracted factor descriptions.",
        "parameters": {
            "type": "object",
            "properties": {
                "hypothesis": {"type": "string"},
                "reason": {"type": "string"},
                "concise_reason": {"type": "string"},
                "concise_observation": {"type": "string"},
                "concise_justification": {"type": "string"},
                "concise_knowledge": {"type": "string"},
            },
            "required": ["hypothesis"],
        },
    },
}

REPORT_FACTOR_EXTRACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_report_factors",
        "description": "Extract the summary, factors, and models from a research report.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "factors": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
                "models": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["factors"],
        },
    },
}

REPORT_FACTOR_CONTINUATION_TOOL = {
    "type": "function",
    "function": {
        "name": "continue_report_factor_extraction",
        "description": "Continue extracting factor names and descriptions from a research report.",
        "parameters": {
            "type": "object",
            "properties": {
                "factors": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["factors"],
        },
    },
}

REPORT_FORMULATION_EXTRACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_report_factor_formulations",
        "description": "Extract factor formulations and variable explanations from a report.",
        "parameters": {
            "type": "object",
            "properties": {
                "factors": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "formulation": {"type": "string"},
                            "variables": {
                                "type": "object",
                                "additionalProperties": {"type": "string"},
                            },
                        },
                    },
                },
            },
            "required": ["factors"],
        },
    },
}

FACTOR_RELEVANCE_TOOL = {
    "type": "function",
    "function": {
        "name": "assess_factor_relevance",
        "description": "Assess whether candidate factors are relevant quantitative investment factors.",
        "parameters": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "relevance": {"type": "boolean"},
                            "reason": {"type": "string"},
                        },
                        "required": ["relevance"],
                    },
                },
            },
            "required": ["results"],
        },
    },
}

FACTOR_VIABILITY_TOOL = {
    "type": "function",
    "function": {
        "name": "assess_factor_viability",
        "description": "Assess whether candidate factors are viable given the available data and constraints.",
        "parameters": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "viability": {"type": "boolean"},
                            "reason": {"type": "string"},
                        },
                        "required": ["viability"],
                    },
                },
            },
            "required": ["results"],
        },
    },
}

FACTOR_DUPLICATION_TOOL = {
    "type": "function",
    "function": {
        "name": "detect_factor_duplication_groups",
        "description": "Detect duplicate groups of factors from a candidate factor table.",
        "parameters": {
            "type": "object",
            "properties": {
                "duplicate_groups": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            "required": ["duplicate_groups"],
        },
    },
}

FACTOR_OUTPUT_FORMAT_TOOL = {
    "type": "function",
    "function": {
        "name": "evaluate_factor_output_format",
        "description": "Evaluate whether the generated factor output format is correct.",
        "parameters": {
            "type": "object",
            "properties": {
                "output_format_decision": {"type": "boolean"},
                "output_format_feedback": {"type": "string"},
            },
            "required": ["output_format_decision", "output_format_feedback"],
        },
    },
}

FACTOR_FINAL_DECISION_TOOL = {
    "type": "function",
    "function": {
        "name": "evaluate_factor_final_decision",
        "description": "Make the final pass/fail decision for a factor implementation.",
        "parameters": {
            "type": "object",
            "properties": {
                "final_decision": {"type": "boolean"},
                "final_feedback": {"type": "string"},
            },
            "required": ["final_decision", "final_feedback"],
        },
    },
}

MODEL_FINAL_DECISION_TOOL = {
    "type": "function",
    "function": {
        "name": "evaluate_model_final_decision",
        "description": "Make the final pass/fail decision for a model implementation.",
        "parameters": {
            "type": "object",
            "properties": {
                "final_decision": {"type": "boolean"},
                "final_feedback": {"type": "string"},
            },
            "required": ["final_decision", "final_feedback"],
        },
    },
}

FACTOR_CODE_GENERATION_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_factor_code",
        "description": "Generate Python code for a factor implementation.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
            },
            "required": ["code"],
        },
    },
}

FACTOR_EXPR_CORRECTION_TOOL = {
    "type": "function",
    "function": {
        "name": "correct_factor_expression",
        "description": "Correct a factor expression and return the revised expression only.",
        "parameters": {
            "type": "object",
            "properties": {
                "expr": {"type": "string"},
            },
            "required": ["expr"],
        },
    },
}

MODEL_CODE_GENERATION_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_model_code",
        "description": "Generate Python code for a model implementation.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
            },
            "required": ["code"],
        },
    },
}

# ---------------------------------------------------------------------------
# Unified tool list — all active schemas
# ---------------------------------------------------------------------------

ALL_MINING_TOOLS = [
    PROPOSE_FACTORS_TOOL,
    CONSTRUCT_FACTORS_TOOL,
    FEEDBACK_TOOL,
    CONSISTENCY_CHECK_TOOL,
    FACTOR_EXTRACTION_TOOL,
    REPORT_CLASSIFICATION_TOOL,
    EVALUATOR_FINAL_DECISION_TOOL,
    FACTOR_CORRECTION_TOOL,
    KNOWLEDGE_COMPONENT_TOOL,
]
