from textwrap import dedent

from automata.util.yaml import parse_yaml


def test_parse_yaml_converts_tags_to_function_dicts() -> None:
    yaml_content = dedent(
        """
        value: !double 2
        items: !join [a, b]
        options: !wrap {x: 1}
        nested:
          - !foo bar
        """
    ).strip()

    parsed = parse_yaml(yaml_content)

    assert parsed == {
        "value": {"__double__": "2"},
        "items": {"__join__": ["a", "b"]},
        "options": {"__wrap__": {"x": 1}},
        "nested": [{"__foo__": "bar"}],
    }


# syntax errors ========================================================================


def test_syntax_error_names_the_source_file_and_position():
    from pathlib import Path

    import pytest

    from automata.exceptions import Error
    from automata.util.yaml import parse_yaml

    with pytest.raises(Error) as excinfo:
        parse_yaml("a: [1, 2\nb: 3\n", source=Path("schedule.yaml"))

    message = str(excinfo.value)
    assert message.startswith("Invalid YAML in schedule.yaml, line 2, column 2:")
    assert "expected ',' or ']'" in message
    assert "<unicode string>" not in message


def test_syntax_error_without_a_source_still_gives_the_position():
    import pytest

    from automata.exceptions import Error
    from automata.util.yaml import parse_yaml

    with pytest.raises(Error) as excinfo:
        parse_yaml("key: : value\n")

    assert str(excinfo.value).startswith("Invalid YAML, line 1, column")
