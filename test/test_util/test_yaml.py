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
