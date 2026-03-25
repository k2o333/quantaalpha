from quantaalpha.llm.client import robust_json_parse


def test_robust_json_parse_repairs_latex_style_underscore_escape() -> None:
    result = robust_json_parse(r'{"text": "\_"}')

    assert result == {"text": r"\_"}


def test_robust_json_parse_repairs_brace_escape_sequences() -> None:
    result = robust_json_parse(r'{"text": "\{\}"}')

    assert result == {"text": r"\{\}"}
