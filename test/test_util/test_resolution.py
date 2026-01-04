"""Unit tests for the automata.util.resolution module."""

import smartconfig

from automata import materials
from automata.util.resolution import (
    resolve_for_each,
    resolve_for_each_publication,
    unwrap_raw_strings,
)

# unwrap_raw_strings() tests
# ============================================================================


def test_unwrap_raw_strings_converts_raw_string():
    """Test that RawString instances are converted to regular strings."""
    config = smartconfig.types.RawString("hello world")
    result = unwrap_raw_strings(config)

    assert isinstance(result, str)
    assert result == "hello world"


def test_unwrap_raw_strings_handles_dict():
    """Test that RawString instances in dicts are converted."""
    config = {
        "key1": smartconfig.types.RawString("value1"),
        "key2": "regular_string",
        "key3": 123,
    }
    result = unwrap_raw_strings(config)

    assert isinstance(result, dict)
    assert result["key1"] == "value1"
    assert isinstance(result["key1"], str)
    assert result["key2"] == "regular_string"
    assert result["key3"] == 123


def test_unwrap_raw_strings_handles_nested_dict():
    """Test that RawString instances in nested dicts are converted."""
    config: smartconfig.types.Configuration = {
        "outer": {
            "inner": smartconfig.types.RawString("nested_value"),
            "regular": "string",
        }
    }
    result = unwrap_raw_strings(config)

    assert isinstance(result, dict)
    assert isinstance(result["outer"], dict)
    assert result["outer"]["inner"] == "nested_value"
    assert isinstance(result["outer"]["inner"], str)


def test_unwrap_raw_strings_handles_list():
    """Test that RawString instances in lists are converted."""
    config = [
        smartconfig.types.RawString("item1"),
        "item2",
        123,
        {"key": smartconfig.types.RawString("value")},
    ]
    result = unwrap_raw_strings(config)

    assert isinstance(result, list)
    assert result[0] == "item1"
    assert isinstance(result[0], str)
    assert result[1] == "item2"
    assert result[2] == 123
    assert isinstance(result[3], dict)
    assert result[3]["key"] == "value"


def test_unwrap_raw_strings_handles_primitives():
    """Test that primitive types are returned unchanged."""
    assert unwrap_raw_strings("string") == "string"
    assert unwrap_raw_strings(123) == 123
    assert unwrap_raw_strings(45.67) == 45.67
    assert unwrap_raw_strings(True) is True
    assert unwrap_raw_strings(None) is None


def test_unwrap_raw_strings_with_preserve_function():
    """Test that preserve function prevents conversion of specific nodes."""
    config: smartconfig.types.Configuration = {
        "convert_me": smartconfig.types.RawString("will_convert"),
        "keep_me": smartconfig.types.RawString("will_keep"),
    }

    def preserve(node):
        # Preserve nodes that are RawStrings with "will_keep"
        if isinstance(node, smartconfig.types.RawString):
            return str(node) == "will_keep"
        return False

    result = unwrap_raw_strings(config, preserve=preserve)

    # The "convert_me" RawString should be converted
    assert isinstance(result, dict)
    assert result["convert_me"] == "will_convert"
    assert isinstance(result["convert_me"], str)

    # The "keep_me" RawString should be preserved
    assert isinstance(result["keep_me"], smartconfig.types.RawString)
    assert str(result["keep_me"]) == "will_keep"


def test_unwrap_raw_strings_preserve_entire_dict():
    """Test that preserve function can preserve entire dict structures."""
    config: smartconfig.types.Configuration = {
        "preserve_this": {
            "foo": smartconfig.types.RawString("keep foo"),
            "bar": smartconfig.types.RawString("keep bar"),
        },
        "convert_this": {
            "inner": smartconfig.types.RawString("change"),
        },
    }

    def preserve(node):
        # Preserve dicts that have "preserve_this" key
        if isinstance(node, dict) and "preserve_this" in node:
            return True
        return False

    result = unwrap_raw_strings(config, preserve=preserve)

    assert isinstance(result, dict)
    assert isinstance(result["preserve_this"], dict)
    assert isinstance(result["preserve_this"]["foo"], smartconfig.types.RawString)
    assert isinstance(result["preserve_this"]["bar"], smartconfig.types.RawString)
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
