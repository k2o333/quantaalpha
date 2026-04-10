"""Regression tests for logging color compatibility."""


def test_log_colors_exposes_end_alias_for_client_logging():
    """Fallback LogColors must provide the END alias used by llm.client."""
    from quantaalpha.log import LogColors

    assert hasattr(LogColors, "END")
    assert LogColors.END.value == LogColors.RESET.value


def test_fallback_logger_accepts_tag_keyword():
    """Fallback logger wrapper must accept the `tag` kwarg used across llm.client."""
    from quantaalpha.log import logger

    logger.info("compatibility test", tag="llm_messages")


def test_log_colors_string_formatting_uses_escape_value():
    """Formatted LogColors values must render as ANSI escape strings, not enum names."""
    from quantaalpha.log import LogColors

    assert f"{LogColors.CYAN}" == LogColors.CYAN.value
    assert f"{LogColors.BOLD}" == LogColors.BOLD.value
