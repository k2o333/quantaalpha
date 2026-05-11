"""Focused tests for migrated business callers.

Proves that:
1. feedback.py uses call_structured with FEEDBACK_TOOL
2. consistency_checker.py uses call_structured with CONSISTENCY_CHECK_TOOL
3. Remaining JSON business callers bind real tool schemas instead of plain text JSON
4. The unified structured gateway is used, not direct build_messages_and_create_chat_completion_json
"""

import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestFeedbackMigration:
    """Tests proving feedback.py migrated to call_structured."""

    def test_feedback_imports_call_structured(self):
        """feedback.py must import call_structured."""
        from quantaalpha.factors import feedback

        assert hasattr(feedback, "call_structured"), "feedback.py must import call_structured"

    def test_feedback_imports_feedback_tool(self):
        """feedback.py must import FEEDBACK_TOOL."""
        from quantaalpha.factors import feedback

        assert hasattr(feedback, "FEEDBACK_TOOL"), "feedback.py must import FEEDBACK_TOOL"

    def test_qlib_feedback_uses_call_structured(self):
        """QlibFactorHypothesisExperiment2Feedback.generate_feedback must use call_structured."""
        from quantaalpha.factors.feedback import QlibFactorHypothesisExperiment2Feedback

        source = inspect.getsource(QlibFactorHypothesisExperiment2Feedback.generate_feedback)
        assert "call_structured" in source, "Must use call_structured, not direct build_messages_and_create_chat_completion_json"
        assert "FEEDBACK_TOOL" in source, "Must pass FEEDBACK_TOOL schema"

    def test_alphaagent_feedback_uses_call_structured(self):
        """AlphaAgentQlibFactorHypothesisExperiment2Feedback.generate_feedback must use call_structured."""
        from quantaalpha.factors.feedback import AlphaAgentQlibFactorHypothesisExperiment2Feedback

        source = inspect.getsource(AlphaAgentQlibFactorHypothesisExperiment2Feedback.generate_feedback)
        assert "call_structured" in source, "Must use call_structured"
        assert "FEEDBACK_TOOL" in source, "Must pass FEEDBACK_TOOL schema"

    def test_model_feedback_uses_call_structured(self):
        """QlibModelHypothesisExperiment2Feedback.generate_feedback must use call_structured."""
        from quantaalpha.factors.feedback import QlibModelHypothesisExperiment2Feedback

        source = inspect.getsource(QlibModelHypothesisExperiment2Feedback.generate_feedback)
        assert "call_structured" in source, "Must use call_structured"
        assert "FEEDBACK_TOOL" in source, "Must pass FEEDBACK_TOOL schema"

    def test_feedback_calls_use_bounded_backend_retries(self):
        """Feedback calls must not spend a full global timeout on a slow first provider."""
        from quantaalpha.factors import feedback

        source = Path(feedback.__file__).read_text()
        assert "FEEDBACK_REQUEST_TIMEOUT_SECONDS" in source
        assert "FEEDBACK_MAX_RETRY" in source
        assert "request_timeout_seconds=FEEDBACK_REQUEST_TIMEOUT_SECONDS" in source
        assert "max_retry_override=FEEDBACK_MAX_RETRY" in source

    def test_all_feedback_paths_use_feedback_task_type(self):
        """Every feedback structured call should be observable and routeable as feedback."""
        from quantaalpha.factors.feedback import (
            AlphaAgentQlibFactorHypothesisExperiment2Feedback,
            QlibFactorHypothesisExperiment2Feedback,
            QlibModelHypothesisExperiment2Feedback,
        )

        for cls in (
            QlibFactorHypothesisExperiment2Feedback,
            AlphaAgentQlibFactorHypothesisExperiment2Feedback,
            QlibModelHypothesisExperiment2Feedback,
        ):
            source = inspect.getsource(cls.generate_feedback)
            assert 'task_type="feedback_summarization"' in source

    def test_alphaagent_feedback_timeout_returns_nonblocking_feedback(self):
        """Feedback LLM exhaustion should not fail the mining task."""
        from quantaalpha.factors.feedback import AlphaAgentQlibFactorHypothesisExperiment2Feedback

        feedbacker = object.__new__(AlphaAgentQlibFactorHypothesisExperiment2Feedback)
        feedbacker.scen = MagicMock()
        feedbacker.scen.get_scenario_all_desc.return_value = "scenario"

        exp = MagicMock()
        exp.result = {"IC": [0.0]}
        exp.sub_tasks = []
        exp.based_experiments = []

        hypothesis = MagicMock()
        hypothesis.hypothesis = "test hypothesis"

        with patch("quantaalpha.factors.feedback.APIBackend") as MockAPI:
            mock_api = MagicMock()
            mock_api.build_messages.return_value = [{"role": "user", "content": "test"}]
            MockAPI.return_value = mock_api

            with patch("quantaalpha.factors.feedback.call_structured", side_effect=RuntimeError("timeout")):
                result = feedbacker.generate_feedback(exp, hypothesis, MagicMock())

        assert result.decision is False
        assert "failed" in result.observations.lower()
        assert "timeout" in result.reason


class TestConsistencyCheckerMigration:
    """Tests proving consistency_checker.py migrated to call_structured."""

    def test_consistency_checker_imports_call_structured(self):
        """consistency_checker.py must import call_structured."""
        import ast
        from pathlib import Path

        source_file = Path(__file__).parent.parent / "factors" / "regulator" / "consistency_checker.py"
        source = source_file.read_text()
        tree = ast.parse(source)

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "llm.client" in node.module:
                    for alias in node.names:
                        imports.append(alias.name)

        assert "call_structured" in imports, "Must import call_structured from llm.client"

    def test_consistency_checker_imports_schema(self):
        """consistency_checker.py must import CONSISTENCY_CHECK_TOOL."""
        import ast
        from pathlib import Path

        source_file = Path(__file__).parent.parent / "factors" / "regulator" / "consistency_checker.py"
        source = source_file.read_text()
        tree = ast.parse(source)

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "llm.tool_schemas" in node.module:
                    for alias in node.names:
                        imports.append(alias.name)

        assert "CONSISTENCY_CHECK_TOOL" in imports, "Must import CONSISTENCY_CHECK_TOOL from llm.tool_schemas"

    def test_consistency_check_uses_call_structured(self):
        """FactorConsistencyChecker.check_consistency must use call_structured."""
        from pathlib import Path

        source_file = Path(__file__).parent.parent / "factors" / "regulator" / "consistency_checker.py"
        source = source_file.read_text()

        assert "call_structured(" in source, "Must call call_structured"
        assert "CONSISTENCY_CHECK_TOOL" in source, "Must reference CONSISTENCY_CHECK_TOOL schema"


class TestRemainingStructuredCallers:
    def test_factor_from_report_uses_hypothesis_tool(self):
        source = Path(__file__).parent.parent.joinpath("pipeline", "factor_from_report.py").read_text()
        assert "HYPOTHESIS_FROM_REPORT_TOOL" in source, "factor_from_report must pass a real tool schema"
        assert "tools=[" in source, "factor_from_report must bind tool schema at call site"

    def test_factor_coder_eva_utils_uses_structured_tools(self):
        from quantaalpha.factors.coder import eva_utils

        output_source = inspect.getsource(eva_utils.FactorOutputFormatEvaluator.evaluate)
        assert "FACTOR_OUTPUT_FORMAT_TOOL" in output_source, "output-format evaluator must bind a tool schema"
        assert "tools=[" in output_source, "output-format evaluator must pass tools"

        final_source = inspect.getsource(eva_utils.FactorFinalDecisionEvaluator.evaluate)
        assert "FACTOR_FINAL_DECISION_TOOL" in final_source, "final-decision evaluator must bind a tool schema"
        assert "tools=[" in final_source, "final-decision evaluator must pass tools"

    def test_model_coder_eva_utils_uses_structured_tool(self):
        from quantaalpha.contrib.model.coder import eva_utils

        source = inspect.getsource(eva_utils.ModelFinalEvaluator.evaluate)
        assert "MODEL_FINAL_DECISION_TOOL" in source, "model final evaluator must bind a tool schema"
        assert "tools=[" in source, "model final evaluator must pass tools"

    def test_coder_generation_paths_bind_code_and_expr_tools(self):
        from quantaalpha.contrib.model.coder import evolving_strategy as model_evolving_strategy
        from quantaalpha.factors.coder import evolving_strategy as factor_evolving_strategy

        factor_code_source = inspect.getsource(factor_evolving_strategy.FactorMultiProcessEvolvingStrategy.implement_one_task)
        assert "FACTOR_CODE_GENERATION_TOOL" in factor_code_source, "factor code generation must bind a tool schema"
        assert "tools=[" in factor_code_source, "factor code generation must pass tools"

        factor_expr_source = inspect.getsource(factor_evolving_strategy.FactorParsingStrategy.implement_one_task)
        assert "FACTOR_EXPR_CORRECTION_TOOL" in factor_expr_source, "factor expr correction must bind a tool schema"
        assert "tools=[" in factor_expr_source, "factor expr correction must pass tools"

        model_code_source = inspect.getsource(model_evolving_strategy.ModelMultiProcessEvolvingStrategy.implement_one_task)
        assert "MODEL_CODE_GENERATION_TOOL" in model_code_source, "model code generation must bind a tool schema"
        assert "tools=[" in model_code_source, "model code generation must pass tools"

    def test_pdf_loader_binds_tools_for_json_calls(self):
        source = Path(__file__).parent.parent.joinpath("factors", "loader", "pdf_loader.py").read_text()
        for schema_name in (
            "REPORT_CLASSIFICATION_TOOL",
            "REPORT_FACTOR_EXTRACTION_TOOL",
            "REPORT_FACTOR_CONTINUATION_TOOL",
            "REPORT_FORMULATION_EXTRACTION_TOOL",
            "FACTOR_RELEVANCE_TOOL",
            "FACTOR_VIABILITY_TOOL",
            "FACTOR_DUPLICATION_TOOL",
        ):
            assert schema_name in source, f"pdf_loader must import and use {schema_name}"

    def test_knowledge_management_uses_component_tool(self):
        from quantaalpha.coder.costeer import knowledge_management

        source = inspect.getsource(knowledge_management.CoSTEERRAGStrategyV2.analyze_component)
        assert "KNOWLEDGE_COMPONENT_TOOL" in source, "knowledge management must bind a tool schema"
        assert "tools=[" in source, "knowledge management must pass tools"


class TestStructuredSessionAndFallbackContracts:
    def test_chat_session_json_uses_structured_gateway(self):
        from quantaalpha.llm import client

        source = inspect.getsource(client.ChatSession.build_chat_completion_json)
        assert "call_structured(" in source, "ChatSession JSON path must delegate to call_structured"

    def test_client_does_not_force_json_prompt_on_primary_path(self):
        source = Path(__file__).parent.parent.joinpath("llm", "client.py").read_text()
        assert "Please respond in json format." not in source, "client.py should not inject text JSON instructions on the primary path"
