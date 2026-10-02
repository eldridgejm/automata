"""Unit tests for the automata.util.resolution module."""

import datetime

import pytest
import smartconfig
import smartconfig.exceptions

from automata import materials
from automata.materials import resolve_for_each_publication
from automata.util.resolution import (
    describe_config_error,
    resolve,
    resolve_for_each,
    unwrap_templates,
)

# unwrap_templates() tests
# ============================================================================


def test_unwrap_templates_converts_template():
    """Test that __template__ dicts are converted to regular strings."""
    config = {"__template__": "hello world"}
    result = unwrap_templates(config)

    assert isinstance(result, str)
    assert result == "hello world"


def test_unwrap_templates_handles_dict():
    """Test that __template__ dicts inside dicts are converted."""
    config = {
        "key1": {"__template__": "value1"},
        "key2": "regular_string",
        "key3": 123,
    }
    result = unwrap_templates(config)

    assert isinstance(result, dict)
    assert result["key1"] == "value1"
    assert isinstance(result["key1"], str)
    assert result["key2"] == "regular_string"
    assert result["key3"] == 123


def test_unwrap_templates_handles_nested_dict():
    """Test that __template__ dicts in nested dicts are converted."""
    config: smartconfig.types.Configuration = {
        "outer": {
            "inner": {"__template__": "nested_value"},
            "regular": "string",
        }
    }
    result = unwrap_templates(config)

    assert isinstance(result, dict)
    assert isinstance(result["outer"], dict)
    assert result["outer"]["inner"] == "nested_value"
    assert isinstance(result["outer"]["inner"], str)


def test_unwrap_templates_handles_list():
    """Test that __template__ dicts in lists are converted."""
    config = [
        {"__template__": "item1"},
        "item2",
        123,
        {"key": {"__template__": "value"}},
    ]
    result = unwrap_templates(config)

    assert isinstance(result, list)
    assert result[0] == "item1"
    assert isinstance(result[0], str)
    assert result[1] == "item2"
    assert result[2] == 123
    assert isinstance(result[3], dict)
    assert result[3]["key"] == "value"


def test_unwrap_templates_handles_primitives():
    """Test that primitive types are returned unchanged."""
    assert unwrap_templates("string") == "string"
    assert unwrap_templates(123) == 123
    assert unwrap_templates(45.67) == 45.67
    assert unwrap_templates(True) is True
    assert unwrap_templates(None) is None


def test_unwrap_templates_with_preserve_function():
    """Test that preserve function prevents unwrapping of specific nodes."""
    config: smartconfig.types.Configuration = {
        "convert_me": {"__template__": "will_convert"},
        "keep_me": {"__template__": "will_keep"},
    }

    def preserve(node):
        if isinstance(node, dict) and "__template__" in node:
            return node["__template__"] == "will_keep"
        return False

    result = unwrap_templates(config, preserve=preserve)

    assert isinstance(result, dict)
    assert result["convert_me"] == "will_convert"
    assert isinstance(result["convert_me"], str)

    assert isinstance(result["keep_me"], dict)
    assert result["keep_me"]["__template__"] == "will_keep"


def test_unwrap_templates_preserve_entire_dict():
    """Test that preserve function can preserve entire dict structures."""
    config: smartconfig.types.Configuration = {
        "preserve_this": {
            "foo": {"__template__": "keep foo"},
            "bar": {"__template__": "keep bar"},
        },
        "convert_this": {
            "inner": {"__template__": "change"},
        },
    }

    def preserve(node):
        # Preserve dicts that have both "foo" and "bar" keys
        if isinstance(node, dict) and "foo" in node and "bar" in node:
            return True
        return False

    result = unwrap_templates(config, preserve=preserve)

    assert isinstance(result, dict)
    assert isinstance(result["preserve_this"], dict)
    assert isinstance(result["preserve_this"]["foo"], dict)
    assert result["preserve_this"]["foo"]["__template__"] == "keep foo"
    assert isinstance(result["preserve_this"]["bar"], dict)
    assert result["preserve_this"]["bar"]["__template__"] == "keep bar"
    assert isinstance(result["convert_this"], dict)
    assert result["convert_this"]["inner"] == "change"
    assert isinstance(result["convert_this"]["inner"], str)


# resolve_for_each() tests
# ============================================================================


def test_resolve_for_each_with_static_config():
    """Test basic iteration over items with simple static config."""
    items = [1, 2, 3]
    # Use a config that doesn't need interpolation
    config: smartconfig.types.Configuration = {"static_value": "test"}
    schema = {"type": "dict", "required_keys": {"static_value": {"type": "string"}}}

    result = resolve_for_each(items, config, schema)

    # Should get one result per item
    assert len(result) == 3
    # Each result should have the static value
    assert all(r["static_value"] == "test" for r in result)  # type: ignore


def test_resolve_for_each_with_iterpolation():
    """Test iteration with config that uses the loop variable for interpolation."""
    items = ["apple", "banana", "cherry"]
    config: smartconfig.types.Configuration = {
        "fruit": "${item}",
        "length": "${ item | length }",
    }
    schema = {
        "type": "dict",
        "required_keys": {
            "fruit": {"type": "string"},
            "length": {"type": "integer"},
        },
    }

    result = resolve_for_each(items, config, schema)

    assert len(result) == 3
    assert isinstance(result, list)
    assert isinstance(result[0], dict)
    assert result[0]["fruit"] == "apple"
    assert result[0]["length"] == 5
    assert isinstance(result[1], dict)
    assert result[1]["fruit"] == "banana"
    assert result[1]["length"] == 6
    assert isinstance(result[2], dict)
    assert result[2]["fruit"] == "cherry"
    assert result[2]["length"] == 6


def test_resolve_for_each_with_custom_loop_variable():
    """Test that a custom loop variable name can be used."""
    items = [10, 20, 30]
    config: smartconfig.types.Configuration = {
        "value": "${num}",
        "double": "${ num * 2 }",
    }
    schema = {
        "type": "dict",
        "required_keys": {
            "value": {"type": "integer"},
            "double": {"type": "integer"},
        },
    }

    result = resolve_for_each(
        items,
        config,
        schema,
        loop_variable="num",
    )

    assert len(result) == 3
    assert isinstance(result, list)
    assert isinstance(result[0], dict)
    assert result[0]["value"] == 10
    assert result[0]["double"] == 20
    assert isinstance(result[1], dict)
    assert result[1]["value"] == 20
    assert result[1]["double"] == 40
    assert isinstance(result[2], dict)
    assert result[2]["value"] == 30
    assert result[2]["double"] == 60


def test_resolve_for_each_with_additional_vars():
    """Test that additional variables can be provided for resolution."""
    items = ["x", "y"]
    config: smartconfig.types.Configuration = {
        "item_plus_suffix": "${ item + suffix }",
    }
    schema = {
        "type": "dict",
        "required_keys": {
            "item_plus_suffix": {"type": "string"},
        },
    }

    result = resolve_for_each(
        items,
        config,
        schema,
        vars={"suffix": "_bar"},
    )

    assert len(result) == 2
    assert isinstance(result, list)
    assert isinstance(result[0], dict)
    assert result[0]["item_plus_suffix"] == "x_bar"
    assert isinstance(result[1], dict)
    assert result[1]["item_plus_suffix"] == "y_bar"


def test_resolve_for_each_with_fixup():
    """Test that the fixup function modifies each resolved config."""
    items = [3, 2]
    config: smartconfig.types.Configuration = {
        "number": "${ item }",
    }
    schema = {
        "type": "dict",
        "required_keys": {
            "number": {"type": "integer"},
        },
    }

    def fixup(resolved_config, item):
        resolved_config["number"] = resolved_config["number"] ** 2
        return resolved_config

    result = resolve_for_each(
        items,
        config,
        schema,
        fixup=fixup,
    )

    assert len(result) == 2
    assert isinstance(result, list)
    assert isinstance(result[0], dict)
    assert result[0]["number"] == 9
    assert isinstance(result[1], dict)
    assert result[1]["number"] == 4


def test_resolve_for_each_fixup_receives_item():
    """Test that the fixup function receives the item as the second argument."""
    items = ["apple", "banana", "cherry"]
    config: smartconfig.types.Configuration = {
        "fruit": "${item}",
    }
    schema = {
        "type": "dict",
        "required_keys": {
            "fruit": {"type": "string"},
        },
    }

    def fixup(resolved_config, item):
        # Use the item parameter to add computed information
        resolved_config["item_length"] = len(item)
        return resolved_config

    result = resolve_for_each(
        items,
        config,
        schema,
        fixup=fixup,
    )

    assert len(result) == 3
    assert result[0]["fruit"] == "apple"
    assert result[0]["item_length"] == 5
    assert result[1]["fruit"] == "banana"
    assert result[1]["item_length"] == 6
    assert result[2]["fruit"] == "cherry"
    assert result[2]["item_length"] == 6


# resolve_for_each_publication() tests
# ============================================================================


def test_resolve_for_each_publication_basic():
    """Test basic iteration over publications with simple config."""
    publications = [
        materials.Publication(metadata={"title": "Pub1"}, artifacts={}),
        materials.Publication(metadata={"title": "Pub2"}, artifacts={}),
    ]
    config: smartconfig.types.Configuration = {
        "publication_title": "${ publication.metadata.title }"
    }
    schema = {
        "type": "dict",
        "required_keys": {
            "publication_title": {"type": "string"},
        },
    }

    result = resolve_for_each_publication(publications, config, schema)

    assert len(result) == 2
    assert isinstance(result, list)
    assert isinstance(result[0], dict)
    assert result[0]["publication_title"] == "Pub1"
    assert isinstance(result[1], dict)
    assert result[1]["publication_title"] == "Pub2"


def test_resolve_for_each_publication_with_use_metadata():
    """Test that the use_metadata function works in resolution."""
    publications = [
        materials.Publication(
            metadata={"name": "TestPub", "due": "2024-12-31"}, artifacts={}
        )
    ]
    config: smartconfig.types.Configuration = {
        "publication_name": {"__use_metadata__": "name"},
        "publication_due": {"__use_metadata__": "due"},
    }
    schema = {
        "type": "dict",
        "required_keys": {
            "publication_name": {"type": "string"},
            "publication_due": {"type": "string"},
        },
    }

    result = resolve_for_each_publication(publications, config, schema)

    assert len(result) == 1
    assert isinstance(result, list)
    assert isinstance(result[0], dict)
    assert result[0]["publication_name"] == "TestPub"
    assert result[0]["publication_due"] == "2024-12-31"


def test_resolve_for_each_publication_fixup_receives_publication():
    """Test that the fixup function receives the publication as the second argument."""
    publications = [
        materials.Publication(
            metadata={"title": "Pub1", "number": 1}, artifacts={"hw.pdf": None}
        ),
        materials.Publication(
            metadata={"title": "Pub2", "number": 2},
            artifacts={"hw.pdf": None, "sol.pdf": None},
        ),
    ]
    config: smartconfig.types.Configuration = {
        "title": "${ publication.metadata.title }",
    }
    schema = {
        "type": "dict",
        "required_keys": {
            "title": {"type": "string"},
        },
    }

    def fixup(resolved_config, publication):
        # Use the publication parameter to add computed information
        resolved_config["artifact_count"] = len(publication.artifacts)
        return resolved_config

    result = resolve_for_each_publication(publications, config, schema, fixup=fixup)

    assert len(result) == 2
    assert result[0]["title"] == "Pub1"
    assert result[0]["artifact_count"] == 1
    assert result[1]["title"] == "Pub2"
    assert result[1]["artifact_count"] == 2


# date phrases in date and datetime fields
# ============================================================================


def _resolve_field(value, type_, **kwargs):
    from automata.util.resolution import resolve

    schema = {"type": "dict", "required_keys": {"when": {"type": type_}}}
    return resolve({"when": value}, schema, **kwargs)["when"]


def test_date_field_accepts_an_offset_phrase():
    import datetime

    assert _resolve_field("7 days after 2026-01-01", "date") == datetime.date(
        2026, 1, 8
    )


def test_datetime_field_accepts_a_date_with_an_at_time():
    import datetime

    assert _resolve_field("2026-10-06 at 23:59:00", "datetime") == datetime.datetime(
        2026, 10, 6, 23, 59
    )


def test_datetime_field_accepts_an_offset_phrase_with_an_at_time():
    import datetime

    result = _resolve_field("7 days before 2026-10-06 at 00:00:00", "datetime")

    assert result == datetime.datetime(2026, 9, 29, 0, 0)


def test_date_field_accepts_first_weekday_phrases():
    import datetime

    # 2026-09-24 is a Thursday; the next Tuesday or Thursday is 2026-09-29
    for phrase in [
        "first tuesday, thursday after 2026-09-24",
        "first tuesday or thursday after 2026-09-24",
    ]:
        assert _resolve_field(phrase, "date") == datetime.date(2026, 9, 29)


def test_date_phrases_can_use_interpolated_values():
    import datetime

    result = _resolve_field(
        "${ due } at 23:59:00", "datetime", global_variables={"due": "2026-10-06"}
    )

    assert result == datetime.datetime(2026, 10, 6, 23, 59)


def test_iso_strings_and_date_objects_convert_as_before():
    import datetime

    assert _resolve_field("2026-10-06", "date") == datetime.date(2026, 10, 6)
    assert _resolve_field("2026-10-06 23:59:00", "datetime") == datetime.datetime(
        2026, 10, 6, 23, 59
    )
    assert _resolve_field(datetime.date(2026, 10, 6), "date") == datetime.date(
        2026, 10, 6
    )


def test_explicit_datetime_parse_still_works():
    import datetime

    result = _resolve_field({"__datetime.parse__": "3 days after 2026-01-01"}, "date")

    assert result == datetime.date(2026, 1, 4)


def test_unreadable_date_phrase_gives_a_clear_error():
    import pytest

    with pytest.raises(smartconfig.exceptions.ResolutionError) as excinfo:
        _resolve_field("7 dyas before 2026-10-06", "datetime")

    message = str(excinfo.value)
    assert "7 dyas before 2026-10-06" in message
    assert "date phrase" in message
    assert '"when"' in message  # names the field


def test_phrases_in_untyped_fields_stay_strings():
    assert _resolve_field("7 days after 2026-01-01", "any") == "7 days after 2026-01-01"


# describe_config_error ================================================================


def test_config_errors_give_file_line_keypath_and_reason(tmp_path):
    message = describe_config_error(
        "Expected a dict.", ("website", "theme"), file=tmp_path / "a.yaml", line=2
    )

    assert message == f"{tmp_path / 'a.yaml'}:2: website.theme: Expected a dict."


def test_config_errors_without_a_line_give_file_keypath_and_reason(tmp_path):
    message = describe_config_error(
        "Expected a dict.", ("website",), file=tmp_path / "a.yaml"
    )

    assert message == f"{tmp_path / 'a.yaml'}: website: Expected a dict."


# datetimes need a time ================================================================

_DATETIME = {"type": "dict", "required_keys": {"due": {"type": "datetime"}}}
_DATE = {"type": "dict", "required_keys": {"due": {"type": "date"}}}


def _datetime_error(value) -> str:
    with pytest.raises(smartconfig.exceptions.ResolutionError) as excinfo:
        resolve({"due": value}, _DATETIME)
    return excinfo.value.reason


def test_a_bare_date_is_not_a_datetime():
    # YAML reads an unquoted 2025-01-10 as a date
    assert _datetime_error(datetime.date(2025, 1, 10)) == (
        'Expected a date and time, like "2025-01-10 23:59:00", but got the date '
        "2025-01-10 with no time."
    )


def test_a_quoted_date_is_not_a_datetime():
    assert _datetime_error("2025-01-10") == (
        'Expected a date and time, like "2025-01-10 23:59:00", but got the date '
        "2025-01-10 with no time."
    )


def test_a_date_phrase_without_a_time_is_not_a_datetime():
    assert _datetime_error("3 days after 2025-01-10") == (
        'Expected a date and time, but "3 days after 2025-01-10" gives only a '
        'date. Add a time, like "3 days after 2025-01-10 at 23:59:00".'
    )


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2025-01-10 12:00:00", datetime.datetime(2025, 1, 10, 12)),
        (datetime.datetime(2025, 1, 10, 12), datetime.datetime(2025, 1, 10, 12)),
        ("3 days after 2025-01-10 at 23:59:00", datetime.datetime(2025, 1, 13, 23, 59)),
    ],
)
def test_datetimes_with_a_time_are_accepted(value, expected):
    assert resolve({"due": value}, _DATETIME) == {"due": expected}


def test_a_phrase_relative_to_a_datetime_takes_its_time():
    # e.g. release_time: 3 days after ${ this.metadata.midterm }, with no "at"
    midterm = datetime.datetime(2025, 6, 10, 13, 0)

    result = resolve(
        {"due": "3 days after ${ midterm }"},
        _DATETIME,
        global_variables={"midterm": midterm},
    )

    assert result == {"due": datetime.datetime(2025, 6, 13, 13, 0)}


@pytest.mark.parametrize(
    "value", [datetime.date(2025, 1, 10), "2025-01-10", "7 days before 2025-01-17"]
)
def test_date_fields_still_accept_dates(value):
    assert resolve({"due": value}, _DATE) == {"due": datetime.date(2025, 1, 10)}
