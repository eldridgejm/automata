import datetime

from pytest import raises

from automata.hooks import DiscoverHookArgs, Hooks
from automata.materials import discover
from automata.materials.exceptions import DiscoveryError


def test_finds_collections(default_example_course):
    # when
    universe = discover(default_example_course.path)

    # then
    assert universe.collections.keys() == {"homeworks", "default"}


def test_finds_publications(default_example_course):
    # when
    universe = discover(default_example_course.path)

    # then
    assert universe.collections["homeworks"].publications.keys() == {
        "01-intro",
        "02-python",
        "03-not_ready",
        "04-normal_publication",
    }


def test_finds_singleton_publications_and_places_them_in_default_collection(
    temporary_course,
):
    # a "singleton" is a publication that does not exist in a collection
    # given
    temporary_course.create_publication(
        "",  # there's no collection
        "textbook",
        """
            metadata:
                name: Textbook

            artifacts:
                textbook.pdf:
                    recipe: touch textbook.pdf
        """,
    )

    # when
    universe = discover(temporary_course.path)

    # then
    assert universe.collections["default"].publications.keys() == {
        "textbook",
    }


def test_reads_publication_metadata(default_example_course):
    # when
    universe = discover(default_example_course.path)

    # then
    assert (
        universe.collections["homeworks"].publications["01-intro"].metadata["name"]
        == "Homework 01"
    )


def test_loads_artifacts(default_example_course):
    # when
    universe = discover(default_example_course.path)

    artifact = (
        universe.collections["homeworks"]
        .publications["01-intro"]
        .artifacts["solution.pdf"]
    )

    # then
    assert artifact.recipe == "touch solution.pdf"


def test_loads_dates_as_dates(default_example_course):
    # when
    universe = discover(default_example_course.path)

    # then
    assert isinstance(
        universe.collections["homeworks"].publications["01-intro"].metadata["due"],
        datetime.datetime,
    )

    assert isinstance(
        universe.collections["homeworks"].publications["01-intro"].metadata["released"],
        datetime.date,
    )


def test_reads_ready(default_example_course):
    # when
    universe = discover(default_example_course.path)

    artifact = (
        universe.collections["homeworks"]
        .publications["03-not_ready"]
        .artifacts["homework.pdf"]
    )

    # then
    assert not artifact.ready


def test_validates_collection_schema(temporary_course):
    # given a collection with a malformed collection.yaml
    temporary_course.create_collection(
        "homeworks",
        """
            foo: bar
            schema: 42
        """,
    )

    # when run on a malformed collection.yaml
    with raises(DiscoveryError):
        discover(temporary_course.path)


def test_validates_publication_schema(temporary_course):
    # given a publication with a malformed publication.yaml
    temporary_course.create_publication(
        "",
        "textbook",
        # missing metadata
        """
            name: hello
            artifacts:
                homework:
                    path: ./build/nothing.pdf
                    recipe: make
        """,
    )

    with raises(DiscoveryError):
        discover(temporary_course.path)


def test_validates_publication_metadata_schema(temporary_course):
    # given a publication with metadata that doesn't match the schema in the
    # collection.yaml
    temporary_course.create_collection(
        "homeworks",
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
        """,
    )

    temporary_course.create_publication(
        "homeworks",
        "01-intro",
        """
            metadata:
                what: ok

            artifacts:
                homework:
                    path: ./build/nothing.pdf
                    recipe: make
        """,
    )

    with raises(DiscoveryError):
        discover(temporary_course.path)


def test_raises_when_nested_collections_discovered(temporary_course):
    # given a collection "bar" nested in a collection "foo"
    BASIC_COLLECTION_YAML = """
        publication_schema:
            required_artifacts: []

            metadata_schema:
                name:
                    type: string
                author:
                    type: string
    """

    temporary_course.create_collection("foo", BASIC_COLLECTION_YAML)
    temporary_course.create_collection("foo/bar", BASIC_COLLECTION_YAML)

    with raises(DiscoveryError):
        discover(temporary_course.path)


def test_uses_relative_paths_as_keys(temporary_course):
    # given a collection with publications/collections more than one level deep in the
    # directory hierarchy
    temporary_course.create_collection(
        "foo/bar",
        """
            publication_schema:
                required_artifacts: ["foo"]
        """,
    )

    temporary_course.create_publication(
        "foo/bar",
        "baz/bazinga",
        """
            artifacts:
                foo:
                    path: filename
                    recipe: ok
        """,
    )

    # when
    universe = discover(temporary_course.path)

    # then
    assert "foo/bar" in universe.collections
    assert "baz/bazinga" in universe.collections["foo/bar"].publications


def test_skip_directories(default_example_course):
    # when we don't skip anything
    universe = discover(default_example_course.path)

    # then
    assert "01-intro" in universe.collections["homeworks"].publications

    # when we do skip a directory
    universe = discover(
        default_example_course.path, skip=lambda p: p.name == "01-intro"
    )

    # then
    assert "01-intro" not in universe.collections["homeworks"].publications


def test_skip_with_glob_pattern(default_example_course):
    import fnmatch

    # when we skip publications matching a glob pattern
    universe = discover(
        default_example_course.path,
        skip=lambda p: fnmatch.fnmatch(p.name, "0[12]-*"),
    )

    # then
    pubs = universe.collections["homeworks"].publications
    assert "01-intro" not in pubs
    assert "02-python" not in pubs
    assert "03-not_ready" in pubs
    assert "04-normal_publication" in pubs


def test_key_used_for_path_if_path_not_provided(default_example_course):
    # when
    universe = discover(default_example_course.path)

    artifact = (
        universe.collections["homeworks"]
        .publications["01-intro"]
        .artifacts["homework.pdf"]
    )

    # then
    assert artifact.path == "homework.pdf"


def test_sorts_publications_lexicographically_if_collection_is_ordered(
    default_example_course,
):
    # given the default example, with a few more publications with a gap in their
    # numbering
    BASIC_PUBLICATION_YAML = """
        metadata:
            name: "Late Homework"
            due: 2020-09-10 23:59:00
            released: 2020-09-01
        artifacts:
            homework.pdf:
                recipe: touch homework.pdf
            solution.pdf:
                recipe: touch solution.pdf
    """
    publication_names = ["10-late_homework", "11-later_homework"]
    for publication_name in publication_names:
        default_example_course.create_publication(
            "homeworks",
            publication_name,
            BASIC_PUBLICATION_YAML,
        )

    # when
    universe = discover(default_example_course.path)

    # then
    assert list(universe.collections["homeworks"].publications) == [
        "01-intro",
        "02-python",
        "03-not_ready",
        "04-normal_publication",
        "10-late_homework",
        "11-later_homework",
    ]


def test_with_dates_relating_to_previous(temporary_course):
    # given a collection with dates that are relative to the previous publication
    temporary_course.create_collection(
        "lectures",
        """
            publication_schema:
                required_artifacts: []

                optional_artifacts:
                    - template.zip

                metadata_schema:
                    required_keys:
                      name:
                          type: string
                      date:
                          type: datetime

                is_ordered: true
        """,
    )

    temporary_course.create_publication(
        "lectures",
        "01-intro",
        """
            metadata:
                name: Lecture 01
                date: 2021-01-05 23:00:00

            artifacts:
                template.zip:
                    recipe: touch template.zip
                    release_time: ${this.metadata.date}
        """,
    )

    temporary_course.create_publication(
        "lectures",
        "02-foo",
        """
            metadata:
                name: Lecture 01
                date:
                    __datetime.parse__: >-
                        first tuesday or thursday after
                        ${previous.metadata.date}

            artifacts:
                template.zip:
                    recipe: touch template.zip
                    release_time: ${this.metadata.date}
        """,
    )

    temporary_course.create_publication(
        "lectures",
        "03-bar",
        """
            metadata:
                name: Lecture 01
                date:
                    __datetime.parse__: >-
                        first tuesday or thursday after
                        ${previous.metadata.date}

            artifacts:
                template.zip:
                    recipe: touch template.zip
                    release_time: ${this.metadata.date}
        """,
    )

    temporary_course.create_publication(
        "lectures",
        "04-baz",
        """
            metadata:
                name: Lecture 01
                date: 2021-01-19 23:00:00

            artifacts:
                template.zip:
                    recipe: touch template.zip
                    release_time: ${this.metadata.date}
        """,
    )

    temporary_course.create_publication(
        "lectures",
        "05-conclusion",
        """
            metadata:
                name: Lecture 01
                date:
                    __datetime.parse__: >-
                        first tuesday or thursday after
                        ${previous.metadata.date}

            artifacts:
                template.zip:
                    recipe: touch template.zip
                    release_time: ${this.metadata.date}
        """,
    )

    # when
    universe = discover(temporary_course.path)

    # then
    publications = universe.collections["lectures"].publications

    assert publications["01-intro"].metadata["date"] == datetime.datetime(
        2021, 1, 5, 23, 0
    )
    assert publications["02-foo"].metadata["date"] == datetime.datetime(
        2021, 1, 7, 23, 0
    )
    assert publications["03-bar"].metadata["date"] == datetime.datetime(
        2021, 1, 12, 23, 0
    )
    # suppose lecture 4 had to be moved; it is manually set in the file
    assert publications["04-baz"].metadata["date"] == datetime.datetime(
        2021, 1, 19, 23, 0
    )
    assert publications["05-conclusion"].metadata["date"] == datetime.datetime(
        2021, 1, 21, 23, 0
    )


def test_interpolates_vars_in_publication_file(temporary_course):
    # given
    vars = {
        "course": {
            "name": "my favorite homework",
            "start_date": datetime.date(2020, 1, 1),
        }
    }

    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - homework.pdf
                    - solution.pdf

                optional_artifacts:
                    - template.zip

                metadata_schema:
                    required_keys:
                        name:
                            type: string
                        due:
                            type: date
                        released:
                            type: date

                is_ordered: true
        """,
    )

    temporary_course.create_publication(
        "homeworks",
        "01-intro",
        """
            metadata:
                name: ${ vars.course.name }
                due: ${ vars.course.start_date }
                released: 2020-09-01

            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
                solution.pdf:
                    recipe: touch solution.pdf
        """,
    )

    # when
    universe = discover(temporary_course.path, vars=vars)

    # then
    assert (
        universe.collections["homeworks"].publications["01-intro"].metadata["name"]
        == "my favorite homework"
    )
    assert universe.collections["homeworks"].publications["01-intro"].metadata[
        "due"
    ] == datetime.date(2020, 1, 1)


def test_interpolates_vars_in_collection_file(temporary_course):
    """Test that vars are interpolated in collection.yaml files during discovery."""
    # given
    vars = {
        "artifacts": {
            "primary": "homework.pdf",
            "secondary": "solution.pdf",
        }
    }

    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - ${vars.artifacts.primary}
                    - ${vars.artifacts.secondary}
        """,
    )

    temporary_course.create_publication(
        "homeworks",
        "01-intro",
        """
            metadata: {}
            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
                solution.pdf:
                    recipe: touch solution.pdf
        """,
    )

    # when
    universe = discover(temporary_course.path, vars=vars)

    # then
    assert universe.collections["homeworks"].publication_schema.required_artifacts == [
        "homework.pdf",
        "solution.pdf",
    ]


def test_interpolates_vars_in_collection_metadata_schema(temporary_course):
    """Test that vars can be used in collection metadata_schema."""
    # given
    vars = {"field_type": "string"}

    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - homework.pdf

                metadata_schema:
                    required_keys:
                        name:
                            type: ${vars.field_type}
        """,
    )

    temporary_course.create_publication(
        "homeworks",
        "01-intro",
        """
            metadata:
                name: Homework 01
            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
        """,
    )

    # when
    universe = discover(temporary_course.path, vars=vars)

    # then
    schema = universe.collections["homeworks"].publication_schema.metadata_schema
    assert schema["required_keys"]["name"]["type"] == "string"


def test_skip_directories_invokes_hook(default_example_course):
    """Test that the on_discover_skip hook is invoked when directories are skipped."""
    # given
    skipped_args = []
    hooks = Hooks()

    @hooks.on_discover_skip.register()
    def track_skipped(args: DiscoverHookArgs) -> None:
        skipped_args.append(args)

    # when
    discover(
        default_example_course.path,
        skip=lambda p: p.name == "01-intro",
        hooks=hooks,
    )

    # then
    assert len(skipped_args) == 1
    assert skipped_args[0].path.name == "01-intro"
    assert skipped_args[0].key is None


def test_discover_invokes_on_discover_collection_hook(default_example_course):
    """Test that on_discover_collection hook is invoked for each collection."""
    # given
    collection_paths = []
    hooks = Hooks()

    @hooks.on_discover_collection.register()
    def track_collections(args: DiscoverHookArgs) -> None:
        collection_paths.append(args.path)

    # when
    discover(default_example_course.path, hooks=hooks)

    # then
    assert len(collection_paths) == 1
    assert collection_paths[0].name == "collection.yaml"


def test_discover_invokes_on_discover_publication_hook(default_example_course):
    """Test that on_discover_publication hook is invoked for each publication."""
    # given
    publication_args = []
    hooks = Hooks()

    @hooks.on_discover_publication.register()
    def track_publications(args: DiscoverHookArgs) -> None:
        publication_args.append(args)

    # when
    discover(default_example_course.path, hooks=hooks)

    # then
    expected_keys = {"01-intro", "02-python", "03-not_ready", "04-normal_publication"}
    assert {a.key for a in publication_args} == expected_keys
    assert all(a.path.name == "publication.yaml" for a in publication_args)


def test_on_discover_collection_shell_script_receives_json(
    default_example_course, tmp_path
):
    """Test that shell script on on_discover_collection receives JSON payload."""
    # given
    output_file = tmp_path / "output.json"
    hooks = Hooks()
    hooks.on_discover_collection.register_shell_script(f"cat > {output_file}")

    # when
    discover(default_example_course.path, hooks=hooks)

    # then
    import json

    content = json.loads(output_file.read_text())
    assert "path" in content
    assert content["path"].endswith("collection.yaml")


def test_on_discover_publication_shell_script_receives_json(
    default_example_course, tmp_path
):
    """Test that shell script on on_discover_publication receives JSON payload."""
    # given
    output_file = tmp_path / "output.jsonl"
    hooks = Hooks()
    hooks.on_discover_publication.register_shell_script(
        f"cat >> {output_file} && echo >> {output_file}"
    )

    # when
    discover(default_example_course.path, hooks=hooks)

    # then
    import json

    expected_keys = {"01-intro", "02-python", "03-not_ready", "04-normal_publication"}
    lines = output_file.read_text().strip().split("\n")
    assert len(lines) == len(expected_keys)
    keys = set()
    for line in lines:
        content = json.loads(line)
        assert content["path"].endswith("publication.yaml")
        keys.add(content["key"])
    assert keys == expected_keys


def test_on_discover_skip_shell_script_receives_json(default_example_course, tmp_path):
    """Test that shell script on on_discover_skip receives JSON payload."""
    # given
    output_file = tmp_path / "output.json"
    hooks = Hooks()
    hooks.on_discover_skip.register_shell_script(f"cat > {output_file}")

    # when
    discover(
        default_example_course.path,
        skip=lambda p: p.name == "01-intro",
        hooks=hooks,
    )

    # then
    import json

    content = json.loads(output_file.read_text())
    assert "path" in content
    assert "01-intro" in content["path"]


# inline publications
# --------------------------------------------------------------------------------------


def test_inline_publications(temporary_course):
    """Test that publications defined inline in collection.yaml are discovered."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - homework.pdf

            publications:
                01-intro:
                    metadata: {}
                    artifacts:
                        homework.pdf:
                            recipe: touch homework.pdf
                02-python:
                    metadata: {}
                    artifacts:
                        homework.pdf:
                            recipe: touch homework.pdf
        """,
    )

    universe = discover(temporary_course.path)

    assert universe.collections["homeworks"].publications.keys() == {
        "01-intro",
        "02-python",
    }


def test_inline_publications_with_metadata(temporary_course):
    """Test that inline publications have correct metadata."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - homework.pdf

            publications:
                01-intro:
                    metadata:
                        name: Homework 01
                    artifacts:
                        homework.pdf:
                            recipe: touch homework.pdf
        """,
    )

    universe = discover(temporary_course.path)

    pub = universe.collections["homeworks"].publications["01-intro"]
    assert pub.metadata["name"] == "Homework 01"


def test_inline_publications_conflict_with_filesystem(temporary_course):
    """Test that inline + filesystem publications raise an error."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - homework.pdf

            publications:
                01-intro:
                    metadata: {}
                    artifacts:
                        homework.pdf:
                            recipe: touch homework.pdf
        """,
    )

    # also create a filesystem publication under the same collection
    temporary_course.create_publication(
        "homeworks",
        "02-python",
        """
            metadata: {}
            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
        """,
    )

    with raises(DiscoveryError):
        discover(temporary_course.path)


def test_inline_publications_validates_metadata_schema(temporary_course):
    """Test that inline publications are validated against the metadata schema."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - homework

                metadata_schema:
                    required_keys:
                        name:
                            type: string

            publications:
                01-intro:
                    metadata:
                        what: ok
                    artifacts:
                        homework:
                            recipe: make
        """,
    )

    with raises(DiscoveryError):
        discover(temporary_course.path)


def test_inline_publications_with_previous(temporary_course):
    """Test that ${previous} works for inline publications in ordered collections."""
    temporary_course.create_collection(
        "lectures",
        """
            publication_schema:
                required_artifacts: []
                metadata_schema:
                    required_keys:
                        name:
                            type: string
                        date:
                            type: datetime
                is_ordered: true

            publications:
                01-intro:
                    metadata:
                        name: Lecture 01
                        date: 2021-01-05 23:00:00
                    artifacts: {}
                02-foo:
                    metadata:
                        name: Lecture 02
                        date:
                            !datetime.parse >-
                                first tuesday or thursday after
                                ${previous.metadata.date}
                    artifacts: {}
        """,
    )

    universe = discover(temporary_course.path)

    pubs = universe.collections["lectures"].publications
    assert pubs["01-intro"].metadata["date"] == datetime.datetime(2021, 1, 5, 23, 0)
    assert pubs["02-foo"].metadata["date"] == datetime.datetime(2021, 1, 7, 23, 0)


def test_inline_publications_with_vars(temporary_course):
    """Test that ${vars} interpolation works for inline publications."""
    vars = {"recipe": "make homework"}

    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - homework.pdf

            publications:
                01-intro:
                    metadata: {}
                    artifacts:
                        homework.pdf:
                            recipe: ${vars.recipe}
        """,
    )

    universe = discover(temporary_course.path, vars=vars)

    artifact = (
        universe.collections["homeworks"]
        .publications["01-intro"]
        .artifacts["homework.pdf"]
    )
    assert artifact.recipe == "make homework"


def test_inline_publications_with_this_reference(temporary_course):
    """Test that ${this} self-references work in inline publications."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts: []
                allow_unspecified_artifacts: true

            publications:
                01-intro:
                    metadata:
                        due: 2020-09-10 23:59:00
                    artifacts:
                        solution:
                            path: ./solution.pdf
                            release_time: ${this.metadata.due}
        """,
    )

    universe = discover(temporary_course.path)
    pub = universe.collections["homeworks"].publications["01-intro"]

    assert pub.artifacts["solution"].release_time == pub.metadata["due"]


def test_inline_publications_hook_fires(temporary_course):
    """Test that on_discover_publication hook fires for inline publications."""
    publication_args = []
    hooks = Hooks()

    @hooks.on_discover_publication.register()
    def track_publications(args: DiscoverHookArgs) -> None:
        publication_args.append(args)

    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts: []

            publications:
                01-intro:
                    metadata: {}
                    artifacts: {}
                02-python:
                    metadata: {}
                    artifacts: {}
        """,
    )

    discover(temporary_course.path, hooks=hooks)

    assert len(publication_args) == 2
    assert all(a.path.name == "collection.yaml" for a in publication_args)
    keys = {a.key for a in publication_args}
    assert keys == {"01-intro", "02-python"}


def test_inline_publications_workdir(temporary_course):
    """Test that inline publication artifacts use the collection dir as workdir."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - homework.pdf

            publications:
                01-intro:
                    metadata: {}
                    artifacts:
                        homework.pdf:
                            recipe: make homework
        """,
    )

    universe = discover(temporary_course.path)

    artifact = (
        universe.collections["homeworks"]
        .publications["01-intro"]
        .artifacts["homework.pdf"]
    )
    assert artifact.workdir == (temporary_course.path / "homeworks").resolve()


# collection schema parsing
# --------------------------------------------------------------------------------------

PERMISSIVE_COLLECTION = """
    publication_schema:
        required_artifacts: []
        allow_unspecified_artifacts: true
"""


def test_collection_schema_parsed_correctly(temporary_course):
    """Test that a valid collection.yaml is parsed with all schema fields."""
    temporary_course.create_collection(
        "homeworks",
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
        """,
    )

    universe = discover(temporary_course.path)
    schema = universe.collections["homeworks"].publication_schema

    assert schema.required_artifacts == ["homework", "solution"]
    assert schema.optional_artifacts == ["template"]
    assert isinstance(schema.metadata_schema, dict)
    assert schema.metadata_schema["required_keys"]["name"]["type"] == "string"


def test_collection_requires_required_artifacts_key(temporary_course):
    """Test that omitting required_artifacts from schema raises an error."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                optional_artifacts:
                    - template
        """,
    )

    with raises(DiscoveryError):
        discover(temporary_course.path)


def test_collection_optional_artifacts_defaults_to_empty(temporary_course):
    """Test that omitting optional_artifacts defaults to an empty list."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - foo
        """,
    )

    universe = discover(temporary_course.path)
    schema = universe.collections["homeworks"].publication_schema

    assert schema.optional_artifacts == []


def test_collection_metadata_schema_defaults_to_none(temporary_course):
    """Test that omitting metadata_schema defaults to None."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - foo
        """,
    )

    universe = discover(temporary_course.path)
    schema = universe.collections["homeworks"].publication_schema

    assert schema.metadata_schema is None


def test_collection_raises_on_invalid_metadata_schema(temporary_course):
    """Test that an invalid metadata_schema structure raises an error."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - foo

                metadata_schema:
                    foo: 1
                    bar: 2
        """,
    )

    with raises(DiscoveryError):
        discover(temporary_course.path)


def test_collection_vars_in_multiple_fields(temporary_course):
    """Test that ${vars} can be used across multiple collection fields."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - ${vars.primary}

                optional_artifacts:
                    - ${vars.secondary}
        """,
    )

    universe = discover(
        temporary_course.path,
        vars={"primary": "homework.pdf", "secondary": "solution.pdf"},
    )
    schema = universe.collections["homeworks"].publication_schema

    assert schema.required_artifacts == ["homework.pdf"]
    assert schema.optional_artifacts == ["solution.pdf"]


def test_collection_missing_vars_raises_error(temporary_course):
    """Test that referencing missing vars in a collection raises an error."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - ${vars.nonexistent}
        """,
    )

    with raises(DiscoveryError):
        discover(temporary_course.path, vars={})


def test_collection_this_is_not_defined(temporary_course):
    """Test that ${this} is not available at the collection level."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - ${this.publication_schema.optional_artifacts.0}
                optional_artifacts:
                    - homework
        """,
    )

    with raises(DiscoveryError, match="this"):
        discover(temporary_course.path)


# publication schema enforcement
# --------------------------------------------------------------------------------------


def test_raises_if_required_artifact_missing(temporary_course):
    """Test that a publication missing a required artifact raises an error."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - homework
                    - solution
        """,
    )

    temporary_course.create_publication(
        "homeworks",
        "01",
        """
            metadata: {}
            artifacts:
                homework:
                    path: ./homework.pdf
        """,
    )

    with raises(DiscoveryError):
        discover(temporary_course.path)


def test_raises_if_extra_artifact_without_allow_unspecified(temporary_course):
    """Test that an unspecified artifact raises when allow_unspecified is false."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - homework
        """,
    )

    temporary_course.create_publication(
        "homeworks",
        "01",
        """
            metadata: {}
            artifacts:
                homework:
                    path: ./homework.pdf
                extra:
                    path: ./extra.pdf
        """,
    )

    with raises(DiscoveryError):
        discover(temporary_course.path)


def test_allows_extra_artifact_with_allow_unspecified(temporary_course):
    """Test that allow_unspecified_artifacts permits unlisted artifacts."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - homework
                allow_unspecified_artifacts: true
        """,
    )

    temporary_course.create_publication(
        "homeworks",
        "01",
        """
            metadata: {}
            artifacts:
                homework:
                    path: ./homework.pdf
                extra:
                    path: ./extra.pdf
        """,
    )

    universe = discover(temporary_course.path)
    pub = universe.collections["homeworks"].publications["01"]

    assert "extra" in pub.artifacts


# release time handling
# --------------------------------------------------------------------------------------


def test_release_time_via_this_reference(temporary_course):
    """Test release_time: ${this.metadata.due} resolves correctly."""
    temporary_course.create_collection("hw", PERMISSIVE_COLLECTION)

    temporary_course.create_publication(
        "hw",
        "01",
        """
            metadata:
                due: 2020-09-04 23:59:00

            artifacts:
                homework:
                    path: ./homework.pdf
                solution:
                    path: ./solution.pdf
                    release_time: ${this.metadata.due}
        """,
    )

    universe = discover(temporary_course.path)
    pub = universe.collections["hw"].publications["01"]

    assert pub.artifacts["solution"].release_time == pub.metadata["due"]


def test_release_time_relative_after(temporary_course):
    """Test __datetime.parse__ with 'N days after' for release_time."""
    temporary_course.create_collection("hw", PERMISSIVE_COLLECTION)

    temporary_course.create_publication(
        "hw",
        "01",
        """
            metadata:
                due: 2020-09-04 23:59:00

            artifacts:
                solution:
                    path: ./solution.pdf
                    release_time:
                        __datetime.parse__: "1 day after ${this.metadata.due}"
        """,
    )

    universe = discover(temporary_course.path)
    pub = universe.collections["hw"].publications["01"]
    expected = pub.metadata["due"] + datetime.timedelta(days=1)

    assert pub.artifacts["solution"].release_time == expected


def test_release_time_relative_before(temporary_course):
    """Test __datetime.parse__ with 'N days before' for release_time."""
    temporary_course.create_collection("hw", PERMISSIVE_COLLECTION)

    temporary_course.create_publication(
        "hw",
        "01",
        """
            metadata:
                due: 2020-09-04 23:59:00

            artifacts:
                homework:
                    path: ./homework.pdf
                    release_time:
                        __datetime.parse__: "3 days before ${this.metadata.due}"
        """,
    )

    universe = discover(temporary_course.path)
    pub = universe.collections["hw"].publications["01"]
    expected = pub.metadata["due"] - datetime.timedelta(days=3)

    assert pub.artifacts["homework"].release_time == expected


def test_release_time_absolute(temporary_course):
    """Test a literal datetime for release_time."""
    temporary_course.create_collection("hw", PERMISSIVE_COLLECTION)

    temporary_course.create_publication(
        "hw",
        "01",
        """
            metadata: {}

            artifacts:
                solution:
                    path: ./solution.pdf
                    release_time: 2020-01-02 23:59:00
        """,
    )

    universe = discover(temporary_course.path)
    pub = universe.collections["hw"].publications["01"]

    assert pub.artifacts["solution"].release_time == datetime.datetime(
        2020, 1, 2, 23, 59, 0
    )


# relative metadata dates
# --------------------------------------------------------------------------------------


def test_relative_dates_in_metadata(temporary_course):
    """Test __datetime.parse__ used in publication metadata fields."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - homework
                metadata_schema:
                    required_keys:
                        name:
                            type: string
                        due:
                            type: datetime
                        released:
                            type: datetime
        """,
    )

    temporary_course.create_publication(
        "homeworks",
        "01",
        """
            metadata:
                name: Homework 01
                due: 2020-09-10 23:59:00
                released:
                    __datetime.parse__: "7 days before ${this.metadata.due}"

            artifacts:
                homework:
                    path: ./homework.pdf
        """,
    )

    universe = discover(temporary_course.path)
    pub = universe.collections["homeworks"].publications["01"]

    assert pub.metadata["released"] == datetime.datetime(2020, 9, 3, 23, 59, 0)


def test_relative_dates_in_metadata_without_offset(temporary_course):
    """Test ${this.metadata.field} reference in metadata (no offset)."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - homework
                metadata_schema:
                    required_keys:
                        name:
                            type: string
                        due:
                            type: date
                        released:
                            type: date
        """,
    )

    temporary_course.create_publication(
        "homeworks",
        "01",
        """
            metadata:
                name: Homework 01
                due: 2020-09-10
                released: ${ this.metadata.due }

            artifacts:
                homework:
                    path: ./homework.pdf
        """,
    )

    universe = discover(temporary_course.path)
    pub = universe.collections["homeworks"].publications["01"]

    assert pub.metadata["released"] == datetime.date(2020, 9, 10)


def test_invalid_relative_date_string_raises(temporary_course):
    """Test that a bare invalid date string fails schema validation."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - homework
                metadata_schema:
                    required_keys:
                        name:
                            type: string
                        due:
                            type: date
                        released:
                            type: date
        """,
    )

    temporary_course.create_publication(
        "homeworks",
        "01",
        """
            metadata:
                name: Homework 01
                due: 2020-12-01
                released: 7 days before duedate

            artifacts:
                homework:
                    path: ./homework.pdf
        """,
    )

    with raises(DiscoveryError):
        discover(temporary_course.path)


# publication vars edge cases
# --------------------------------------------------------------------------------------


def test_publication_vars_combined_with_this(temporary_course):
    """Test that ${vars} and ${this} work together in a publication."""
    temporary_course.create_collection("hw", PERMISSIVE_COLLECTION)

    temporary_course.create_publication(
        "hw",
        "01",
        """
            metadata:
                name: ${vars.prefix} Assignment
                full_name: ${this.metadata.name} - Advanced

            artifacts:
                homework:
                    path: ./homework.pdf
        """,
    )

    universe = discover(temporary_course.path, vars={"prefix": "CS101"})
    pub = universe.collections["hw"].publications["01"]

    assert pub.metadata["name"] == "CS101 Assignment"
    assert pub.metadata["full_name"] == "CS101 Assignment - Advanced"


def test_publication_missing_vars_raises_error(temporary_course):
    """Test that referencing missing vars in a publication raises an error."""
    temporary_course.create_collection("hw", PERMISSIVE_COLLECTION)

    temporary_course.create_publication(
        "hw",
        "01",
        """
            metadata:
                name: ${vars.nonexistent}

            artifacts:
                homework:
                    path: ./homework.pdf
        """,
    )

    with raises(DiscoveryError):
        discover(temporary_course.path, vars={})


def test_previous_publication_combined_with_vars(temporary_course):
    """Test that ${vars} and ${previous} can be used together."""
    temporary_course.create_collection(
        "hw",
        """
            publication_schema:
                required_artifacts: []
                allow_unspecified_artifacts: true
                is_ordered: true
        """,
    )

    temporary_course.create_publication(
        "hw",
        "01",
        """
            metadata:
                name: CS101 - Homework 01

            artifacts:
                homework:
                    path: ./homework.pdf
        """,
    )

    temporary_course.create_publication(
        "hw",
        "02",
        """
            metadata:
                name: ${vars.course_code} - Homework 02
                follows: ${previous.metadata.name}

            artifacts:
                homework:
                    path: ./homework.pdf
        """,
    )

    universe = discover(temporary_course.path, vars={"course_code": "CS101"})
    pub = universe.collections["hw"].publications["02"]

    assert pub.metadata["name"] == "CS101 - Homework 02"
    assert pub.metadata["follows"] == "CS101 - Homework 01"


# error message quality
# --------------------------------------------------------------------------------------


def test_collection_error_includes_file_path(temporary_course):
    """Test that collection errors include the file path."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - ${vars.undefined}
        """,
    )

    with raises(DiscoveryError) as exc_info:
        discover(temporary_course.path, vars={})

    assert "collection.yaml" in str(exc_info.value)


def test_collection_error_includes_keypath(temporary_course):
    """Test that collection resolution errors indicate which key failed."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - homework.pdf
                metadata_schema:
                    required_keys:
                        name:
                            type: ${vars.missing_type}
        """,
    )

    with raises(DiscoveryError) as exc_info:
        discover(temporary_course.path, vars={})

    error_message = str(exc_info.value)
    assert (
        "metadata_schema" in error_message
        or "required_keys" in error_message
        or "type" in error_message
    )


def test_collection_error_for_schema_violation(temporary_course):
    """Test that collection schema violations describe the problem."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts: "not a list"
        """,
    )

    with raises(DiscoveryError) as exc_info:
        discover(temporary_course.path)

    error_message = str(exc_info.value)
    assert "collection.yaml" in error_message
    assert "required_artifacts" in error_message or "list" in error_message


def test_publication_error_includes_file_path(temporary_course):
    """Test that publication errors include the file path."""
    temporary_course.create_collection("hw", PERMISSIVE_COLLECTION)

    temporary_course.create_publication(
        "hw",
        "01",
        """
            metadata:
                name: ${vars.undefined_variable}
            artifacts:
                homework:
                    path: ./homework.pdf
        """,
    )

    with raises(DiscoveryError) as exc_info:
        discover(temporary_course.path, vars={})

    assert "publication.yaml" in str(exc_info.value)


def test_publication_error_includes_keypath(temporary_course):
    """Test that publication resolution errors indicate which key failed."""
    temporary_course.create_collection("hw", PERMISSIVE_COLLECTION)

    temporary_course.create_publication(
        "hw",
        "01",
        """
            metadata:
                name: Test
                nested:
                    deep:
                        value: ${vars.missing}
            artifacts:
                homework:
                    path: ./homework.pdf
        """,
    )

    with raises(DiscoveryError) as exc_info:
        discover(temporary_course.path, vars={})

    error_message = str(exc_info.value)
    assert (
        "metadata" in error_message
        or "nested" in error_message
        or "deep" in error_message
    )


def test_publication_error_for_missing_artifacts_key(temporary_course):
    """Test that a missing artifacts key produces a clear error."""
    temporary_course.create_collection("hw", PERMISSIVE_COLLECTION)

    temporary_course.create_publication(
        "hw",
        "01",
        """
            metadata:
                name: Test
        """,
    )

    with raises(DiscoveryError) as exc_info:
        discover(temporary_course.path)

    error_message = str(exc_info.value)
    assert "publication.yaml" in error_message
    assert "artifacts" in error_message


def test_inline_publication_error_points_to_collection_file(temporary_course):
    """Test that errors from inline publications reference collection.yaml."""
    temporary_course.create_collection(
        "homeworks",
        """
            publication_schema:
                required_artifacts:
                    - homework

            publications:
                01-intro:
                    metadata:
                        name: ${vars.undefined}
                    artifacts:
                        homework:
                            recipe: make
        """,
    )

    with raises(DiscoveryError) as exc_info:
        discover(temporary_course.path, vars={})

    assert exc_info.value.path.name == "collection.yaml"
