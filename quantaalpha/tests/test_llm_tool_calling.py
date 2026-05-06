"""Pytest collection facade for split large-file tests."""

from .llm_tool_calling_core import TestToolCallingSupport, TestToolCallResponseParsing, TestBuildMessagesToolRole, TestAutoContinueToolCalls, TestJsonModeToolCallPriority
from .llm_tool_calling_degradation import TestUseToolCallingGatewaySwitch, TestModelDegradationContract, TestCompatibilityWrapperDegradation, TestFinishReasonStopNotCapabilityFailure

__all__ = [
    "TestToolCallingSupport",
    "TestToolCallResponseParsing",
    "TestBuildMessagesToolRole",
    "TestAutoContinueToolCalls",
    "TestJsonModeToolCallPriority",
    "TestUseToolCallingGatewaySwitch",
    "TestModelDegradationContract",
    "TestCompatibilityWrapperDegradation",
    "TestFinishReasonStopNotCapabilityFailure",
]
