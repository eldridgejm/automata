from pathlib import Path
from textwrap import dedent

from automata.util.yaml import parse_yaml, parse_yaml_with_source_map


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


# source maps ==========================================================================

_CONFIG = dedent(
    """\
    website:
      theme:
        use: default
        config:
          navigation:
            - text: Home
              url: /
            - text: Syllabus
          tags: [a, b]
    date: !template "${ vars.start }"
    """
)


def test_source_map_gives_the_line_of_each_key() -> None:
    _, source_map = parse_yaml_with_source_map(_CONFIG)

    assert source_map.line_of(("website",)) == 1
    assert source_map.line_of(("website", "theme", "use")) == 3
    assert source_map.line_of(("website", "theme", "config", "navigation")) == 5
    assert source_map.line_of(("date",)) == 10


def test_source_map_gives_the_line_of_each_list_item() -> None:
    _, source_map = parse_yaml_with_source_map(_CONFIG)
    navigation = ("website", "theme", "config", "navigation")

    assert source_map.line_of((*navigation, "0")) == 6
    assert source_map.line_of((*navigation, "0", "url")) == 7
    assert source_map.line_of((*navigation, "1", "text")) == 8
    assert source_map.line_of(("website", "theme", "config", "tags", "1")) == 9


def test_source_map_accepts_integer_list_indices() -> None:
    _, source_map = parse_yaml_with_source_map(_CONFIG)

    assert source_map.line_of(("website", "theme", "config", "navigation", 0)) == 6


def test_source_map_falls_back_to_the_closest_enclosing_key() -> None:
    # e.g. a missing required key, whose keypath ends at the key itself
    _, source_map = parse_yaml_with_source_map(_CONFIG)
    navigation = ("website", "theme", "config", "navigation")

    assert source_map.line_of((*navigation, "1", "url")) == 8
    assert source_map.line_of(("website", "theme", "nope", "deeper")) == 2


def test_source_map_has_no_line_for_a_missing_top_level_key() -> None:
    _, source_map = parse_yaml_with_source_map(_CONFIG)

    assert source_map.line_of(("nope",)) is None
    assert source_map.line_of(()) is None


def test_source_map_counts_lines_before_the_content() -> None:
    # e.g. page frontmatter, which starts on line 2
    _, source_map = parse_yaml_with_source_map("vars:\n  a: 1\n", first_line=2)

    assert source_map.line_of(("vars", "a")) == 3


def test_source_map_records_the_file() -> None:
    _, source_map = parse_yaml_with_source_map("a: 1\n", source=Path("x.yaml"))

    assert source_map.file == Path("x.yaml")


def test_parse_yaml_with_source_map_parses_like_parse_yaml() -> None:
    data, _ = parse_yaml_with_source_map(_CONFIG)

    assert data == parse_yaml(_CONFIG)


def _outer_and_included():
    _, outer = parse_yaml_with_source_map(
        "a:\n  b:\n    __include__: x.yaml\nq: 1\n", source=Path("outer.yaml")
    )
    _, included = parse_yaml_with_source_map(
        "c: 1\nd:\n  e: 2\n", source=Path("x.yaml")
    )
    outer.add_include(("a", "b"), included)
    return outer


def test_locate_finds_keys_of_included_files_in_those_files() -> None:
    outer = _outer_and_included()

    assert outer.locate(("a", "b", "d", "e")) == (Path("x.yaml"), 3)


def test_locate_falls_back_to_the_line_that_includes_the_file() -> None:
    outer = _outer_and_included()

    assert outer.locate(("a", "b", "nope")) == (Path("outer.yaml"), 2)
    assert outer.locate(("a", "b")) == (Path("outer.yaml"), 2)


def test_locate_finds_keys_outside_includes_in_the_file_itself() -> None:
    outer = _outer_and_included()

    assert outer.locate(("q",)) == (Path("outer.yaml"), 4)
    assert outer.locate(("nope",)) == (Path("outer.yaml"), None)


def test_source_map_keys_are_the_parsed_keys() -> None:
    # YAML reads 01 as the integer 1, so errors give the keypath ("1", ...)
    _, source_map = parse_yaml_with_source_map("01:\n  a: 1\nfalse: 2\n")

    assert source_map.line_of(("1", "a")) == 2
    assert source_map.line_of(("False",)) == 3
