from textwrap import dedent

from pytest import raises

from automata.materials import read_collection_file
from automata.materials.exceptions import DiscoveryError


def test_on_valid_file(write_file):
    # given
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            publication_schema:
                required_artifacts:
                    - homework
                    - solution

                optional_artifacts:
                    - template

                metadata_schema:
                    required_keys:
                        name:
                            type: string
                        due:
                            type: date
            """
        ),
    )

    # when
    collection = read_collection_file(path)

    # then
    assert collection.publication_schema.required_artifacts == ["homework", "solution"]
    assert collection.publication_schema.optional_artifacts == ["template"]
    assert isinstance(collection.publication_schema.metadata_schema, dict)
    assert (
        collection.publication_schema.metadata_schema["required_keys"]["name"]["type"]
        == "string"
    )


def test_resolves(write_file):
    # given
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            publication_schema:
                required_artifacts:
                    - homework
                    - solution
                    - ${this.publication_schema.optional_artifacts.0}

                optional_artifacts:
                    - ${vars.external.optional}

                metadata_schema:
                    required_keys:
                        name:
                            type: string
                        due:
                            type: date
            """
        ),
    )

    # when
    collection = read_collection_file(path, vars={"external": {"optional": "template"}})

    # then
    assert collection.publication_schema.required_artifacts == [
        "homework",
        "solution",
        "template",
    ]
    assert collection.publication_schema.optional_artifacts == ["template"]
    assert isinstance(collection.publication_schema.metadata_schema, dict)
    assert (
        collection.publication_schema.metadata_schema["required_keys"]["name"]["type"]
        == "string"
    )


def test_validates_fields(write_file):
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            publication_schema:
                # this ain't right..., should be a list of str
                required_artifacts: 42

                optional_artifacts:
                    - template

                metadata_schema:
                    required_keys:
                        name:
                            type: string
                        due:
                            type: date
            """
        ),
    )

    # then
    with raises(DiscoveryError):
        read_collection_file(path)


def test_requires_required_artifacts(write_file):
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            publication_schema:
                # this ain't right..., should have required_artifacts...

                optional_artifacts:
                    - template

                metadata_schema:
                    required_keys:
                        name:
                            type: string
                        due:
                            type: date
            """
        ),
    )

    # then
    with raises(DiscoveryError):
        read_collection_file(path)


def test_doesnt_require_optional_artifacts(write_file):
    # given
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            publication_schema:
                required_artifacts:
                    - foo
                    - bar

                metadata_schema:
                    required_keys:
                        name:
                            type: string
                        due:
                            type: date
            """
        ),
    )

    # when
    collection = read_collection_file(path)

    # then
    assert collection.publication_schema.optional_artifacts == []


def test_doesnt_require_metadata_schema(write_file):
    # given
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            publication_schema:
                required_artifacts:
                    - foo
                    - bar
            """
        ),
    )

    # when
    collection = read_collection_file(path)

    # then
    assert collection.publication_schema.metadata_schema is None


def test_raises_on_invalid_metadata_schema(write_file):
    # given
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            publication_schema:
                required_artifacts:
                    - foo
                    - bar

                metadata_schema:
                    foo: 1
                    bar: 2
            """
        ),
    )

    # when then
    with raises(DiscoveryError):
        read_collection_file(path)


# external variables
# --------------------------------------------------------------------------------------


def test_external_vars_simple_substitution(write_file):
    """Test that external vars can be substituted into collection file."""
    # given
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            publication_schema:
                required_artifacts:
                    - ${vars.artifact_name}
            """
        ),
    )

    # when
    collection = read_collection_file(path, vars={"artifact_name": "homework.pdf"})

    # then
    assert collection.publication_schema.required_artifacts == ["homework.pdf"]


def test_external_vars_nested_substitution(write_file):
    """Test that nested external vars can be substituted."""
    # given
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            publication_schema:
                required_artifacts:
                    - ${vars.course.primary_artifact}
                    - ${vars.course.secondary_artifact}
            """
        ),
    )

    # when
    collection = read_collection_file(
        path,
        vars={
            "course": {
                "primary_artifact": "homework.pdf",
                "secondary_artifact": "solution.pdf",
            }
        },
    )

    # then
    assert collection.publication_schema.required_artifacts == [
        "homework.pdf",
        "solution.pdf",
    ]


def test_external_vars_combined_with_this_reference(write_file):
    """Test that external vars work alongside this references."""
    # given
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            publication_schema:
                required_artifacts:
                    - ${vars.primary}
                    - ${this.publication_schema.optional_artifacts.0}

                optional_artifacts:
                    - ${vars.secondary}
            """
        ),
    )

    # when
    collection = read_collection_file(
        path,
        vars={"primary": "homework.pdf", "secondary": "solution.pdf"},
    )

    # then
    assert collection.publication_schema.required_artifacts == [
        "homework.pdf",
        "solution.pdf",
    ]
    assert collection.publication_schema.optional_artifacts == ["solution.pdf"]


def test_external_vars_missing_raises_error(write_file):
    """Test that referencing missing external vars raises an error."""
    # given
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            publication_schema:
                required_artifacts:
                    - ${vars.nonexistent}
            """
        ),
    )

    # when/then
    with raises(DiscoveryError):
        read_collection_file(path, vars={})


# error message quality tests
# --------------------------------------------------------------------------------------


def test_error_message_includes_file_path(write_file):
    """Test that discovery errors include the path to the problematic file."""
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            publication_schema:
                required_artifacts:
                    - ${vars.undefined}
            """
        ),
    )

    with raises(DiscoveryError) as exc_info:
        read_collection_file(path, vars={})

    error_message = str(exc_info.value)
    assert "collection.yaml" in error_message


def test_error_message_includes_keypath_for_resolution_error(write_file):
    """Test that resolution errors indicate which key failed."""
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            publication_schema:
                required_artifacts:
                    - homework.pdf
                metadata_schema:
                    required_keys:
                        name:
                            type: ${vars.missing_type}
            """
        ),
    )

    with raises(DiscoveryError) as exc_info:
        read_collection_file(path, vars={})

    error_message = str(exc_info.value)
    # Should indicate the keypath where the error occurred
    assert (
        "metadata_schema" in error_message
        or "required_keys" in error_message
        or "type" in error_message
    )


def test_error_message_for_schema_violation(write_file):
    """Test that schema violations indicate what went wrong."""
    path = write_file(
        "collection.yaml",
        contents=dedent(
            """
            publication_schema:
                required_artifacts: "not a list"
            """
        ),
    )

    with raises(DiscoveryError) as exc_info:
        read_collection_file(path)

    error_message = str(exc_info.value)
    assert "collection.yaml" in error_message
    assert "required_artifacts" in error_message or "list" in error_message
