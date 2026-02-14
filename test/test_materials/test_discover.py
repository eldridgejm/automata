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
    universe = discover(default_example_course.path, skip_directories={"01-intro"})

    # then
    assert "01-intro" not in universe.collections["homeworks"].publications


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
    skipped_paths = []
    hooks = Hooks()

    @hooks.on_discover_skip.register()
    def track_skipped(args: DiscoverHookArgs) -> None:
        skipped_paths.append(args.path)

    # when
    discover(
        default_example_course.path,
        skip_directories={"01-intro"},
        hooks=hooks,
    )

    # then
    assert len(skipped_paths) == 1
    assert skipped_paths[0].name == "01-intro"


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
    publication_paths = []
    hooks = Hooks()

    @hooks.on_discover_publication.register()
    def track_publications(args: DiscoverHookArgs) -> None:
        publication_paths.append(args.path)

    # when
    discover(default_example_course.path, hooks=hooks)

    # then
    assert len(publication_paths) > 0
    assert all(p.name == "publication.yaml" for p in publication_paths)


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

    lines = output_file.read_text().strip().split("\n")
    assert len(lines) > 0
    for line in lines:
        content = json.loads(line)
        assert "path" in content
        assert content["path"].endswith("publication.yaml")


def test_on_discover_skip_shell_script_receives_json(default_example_course, tmp_path):
    """Test that shell script on on_discover_skip receives JSON payload."""
    # given
    output_file = tmp_path / "output.json"
    hooks = Hooks()
    hooks.on_discover_skip.register_shell_script(f"cat > {output_file}")

    # when
    discover(
        default_example_course.path,
        skip_directories={"01-intro"},
        hooks=hooks,
    )

    # then
    import json

    content = json.loads(output_file.read_text())
    assert "path" in content
    assert "01-intro" in content["path"]


# inline publications tests ============================================================


def test_inline_publications_in_collection(temporary_course):
    """Test that publications can be defined inline in collection.yaml."""
    # given
    (temporary_course.path / "homeworks").mkdir(parents=True, exist_ok=True)
    (temporary_course.path / "homeworks" / "collection.yaml").write_text(
        """
publication_schema:
    required_artifacts:
        - homework.pdf
    is_ordered: true

publications:
    01-intro:
        metadata:
            name: Homework 01
        artifacts:
            homework.pdf:
                recipe: touch homework.pdf
    02-python:
        metadata:
            name: Homework 02
        artifacts:
            homework.pdf:
                recipe: touch homework.pdf
"""
    )

    # when
    universe = discover(temporary_course.path)

    # then
    assert universe.collections.keys() == {"homeworks", "default"}
    assert universe.collections["homeworks"].publications.keys() == {
        "01-intro",
        "02-python",
    }
    assert (
        universe.collections["homeworks"].publications["01-intro"].metadata["name"]
        == "Homework 01"
    )
    assert (
        universe.collections["homeworks"].publications["02-python"].metadata["name"]
        == "Homework 02"
    )


def test_inline_publications_with_this_reference(temporary_course):
    """Test that ${this} self-references work in inline publications."""
    # given
    (temporary_course.path / "homeworks").mkdir(parents=True, exist_ok=True)
    (temporary_course.path / "homeworks" / "collection.yaml").write_text(
        """
publication_schema:
    required_artifacts:
        - homework.pdf
    optional_artifacts:
        - solution.pdf
    metadata_schema:
        required_keys:
            name:
                type: string
            due:
                type: datetime

publications:
    01-intro:
        metadata:
            name: Homework 01
            due: 2024-09-20 23:59:00
        artifacts:
            homework.pdf:
                recipe: touch homework.pdf
            solution.pdf:
                release_time: ${this.metadata.due}
"""
    )

    # when
    universe = discover(temporary_course.path)

    # then
    pub = universe.collections["homeworks"].publications["01-intro"]
    assert pub.metadata["name"] == "Homework 01"
    assert pub.artifacts["solution.pdf"].release_time == pub.metadata["due"]


def test_inline_publications_with_previous_reference(temporary_course):
    """Test that ${previous} references work in ordered inline collections."""
    # given
    (temporary_course.path / "lectures").mkdir(parents=True, exist_ok=True)
    (temporary_course.path / "lectures" / "collection.yaml").write_text(
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
            date: 2024-01-05 14:00:00
        artifacts: {}
    02-basics:
        metadata:
            name: Lecture 02
            date:
                __datetime.parse__: 7 days after ${previous.metadata.date}
        artifacts: {}
    03-advanced:
        metadata:
            name: Lecture 03
            date:
                __datetime.parse__: 7 days after ${previous.metadata.date}
        artifacts: {}
"""
    )

    # when
    universe = discover(temporary_course.path)

    # then
    lectures = universe.collections["lectures"].publications
    assert lectures["01-intro"].metadata["date"] == datetime.datetime(2024, 1, 5, 14, 0)
    assert lectures["02-basics"].metadata["date"] == datetime.datetime(
        2024, 1, 12, 14, 0
    )
    assert lectures["03-advanced"].metadata["date"] == datetime.datetime(
        2024, 1, 19, 14, 0
    )


def test_inline_publications_with_vars(temporary_course):
    """Test that ${vars} work in inline publications."""
    # given
    (temporary_course.path / "homeworks").mkdir(parents=True, exist_ok=True)
    (temporary_course.path / "homeworks" / "collection.yaml").write_text(
        """
publication_schema:
    required_artifacts:
        - ${vars.primary_artifact}
    allow_unspecified_artifacts: true

publications:
    01-intro:
        metadata:
            course: ${vars.course_name}
        artifacts:
            homework.pdf:
                recipe: touch homework.pdf
"""
    )

    vars = {"course_name": "CS101", "primary_artifact": "homework.pdf"}

    # when
    universe = discover(temporary_course.path, vars=vars)

    # then
    assert (
        universe.collections["homeworks"].publications["01-intro"].metadata["course"]
        == "CS101"
    )
    assert universe.collections["homeworks"].publication_schema.required_artifacts == [
        "homework.pdf"
    ]


def test_error_when_both_inline_and_separate_publications(temporary_course):
    """Test that an error is raised when both inline and separate publications exist."""
    # given - create collection with inline publications
    (temporary_course.path / "homeworks").mkdir(parents=True, exist_ok=True)
    (temporary_course.path / "homeworks" / "collection.yaml").write_text(
        """
publication_schema:
    required_artifacts:
        - homework.pdf

publications:
    01-inline:
        metadata: {}
        artifacts:
            homework.pdf:
                recipe: touch homework.pdf
"""
    )

    # also create a separate publication.yaml
    temporary_course.create_publication(
        "homeworks",
        "02-separate",
        """
            metadata: {}
            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
        """,
    )

    # when/then
    with raises(DiscoveryError) as exc_info:
        discover(temporary_course.path)

    assert "inline" in str(exc_info.value).lower()
    assert (
        "separate" in str(exc_info.value).lower()
        or "publication.yaml" in str(exc_info.value).lower()
    )
