from textwrap import dedent
from pytest import raises

from automata.lib.materials import read_collection_file, DiscoveryError


def test_example(write_file):
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
        collection = read_collection_file(path)


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
        collection = read_collection_file(path)


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
        collection = read_collection_file(path)
