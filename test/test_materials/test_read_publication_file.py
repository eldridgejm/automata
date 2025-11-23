import datetime
from textwrap import dedent

from pytest import raises

from automata.lib import (
    PublicationSchema,
    UnbuiltArtifact,
    read_publication_file,
)
from automata.lib.exceptions import DiscoveryError


def test_on_valid_file(write_file):
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    path: ./homework.pdf
                    recipe: make homework
                solution:
                    path: ./solution.pdf
                    recipe: make solution
            """
        ),
    )

    # when
    publication = read_publication_file(path)

    # then
    assert publication.metadata["name"] == "Homework 01"
    assert isinstance(publication.metadata["due"], datetime.datetime)
    assert isinstance(publication.metadata["released"], datetime.date)
    assert isinstance(publication.artifacts["homework"], UnbuiltArtifact)
    assert publication.artifacts["homework"].recipe == "make homework"


def test_raises_if_required_artifact_is_not_provided(write_file):
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-10
                released: ${ this.metadata.due }

            artifacts:
                homework:
                    path: ./homework.pdf
                    recipe: make homework
            """
        ),
    )

    schema = PublicationSchema(
        required_artifacts=["homework", "solution"],
        metadata_schema={
            "required_keys": {
                "name": {"type": "string"},
                "due": {"type": "date"},
                "released": {"type": "date"},
            }
        },
    )

    # when
    with raises(DiscoveryError):
        read_publication_file(path, publication_schema=schema)


def test_raises_if_extra_artifact_provided_without_allow_unspecified(
    write_file,
):
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-10
                released: ${ this.metadata.due }

            artifacts:
                homework:
                    path: ./homework.pdf
                    recipe: make homework
                woo:
                    path: ./something.pdf
            """
        ),
    )

    schema = PublicationSchema(
        required_artifacts=["homework"],
        metadata_schema={
            "required_keys": {
                "name": {"type": "string"},
                "due": {"type": "date"},
                "released": {"type": "date"},
            }
        },
    )

    # when
    with raises(DiscoveryError):
        read_publication_file(path, publication_schema=schema)


def test_allows_extra_artifact_when_allow_unspecified_given(
    write_file,
):
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-10
                released: ${ this.metadata.due }

            artifacts:
                homework:
                    path: ./homework.pdf
                    recipe: make homework
                woo:
                    path: ./something.pdf
            """
        ),
    )

    schema = PublicationSchema(
        required_artifacts=["homework"],
        metadata_schema={
            "required_keys": {
                "name": {"type": "string"},
                "due": {"type": "date"},
                "released": {"type": "date"},
            }
        },
        allow_unspecified_artifacts=True,
    )

    # when
    pub = read_publication_file(path, publication_schema=schema)

    assert "woo" in pub.artifacts


def test_with_relative_release_time(write_file):
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    path: ./homework.pdf
                    recipe: make homework
                solution:
                    path: ./solution.pdf
                    recipe: make solution
                    release_time: ${this.metadata.due}
            """
        ),
    )

    # when
    publication = read_publication_file(path)

    # then
    expected = publication.metadata["due"]
    assert isinstance(publication.artifacts["solution"], UnbuiltArtifact)
    assert publication.artifacts["solution"].release_time == expected


def test_with_relative_release_date_but_no_time_raises(write_file):
    # given
    # release_time must be a datetime, but it's a date here
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    path: ./homework.pdf
                    recipe: make homework
                solution:
                    path: ./solution.pdf
                    recipe: make solution
                    release_time: metadata.released
            """
        ),
    )

    # then
    with raises(DiscoveryError):
        read_publication_file(path)


def test_with_relative_release_time_after(write_file):
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    path: ./homework.pdf
                    recipe: make homework
                solution:
                    path: ./solution.pdf
                    recipe: make solution
                    release_time: 1 day after ${this.metadata.due}
            """
        ),
    )

    # when
    publication = read_publication_file(path)

    # then
    expected = publication.metadata["due"] + datetime.timedelta(days=1)
    assert isinstance(publication.artifacts["solution"], UnbuiltArtifact)
    assert publication.artifacts["solution"].release_time == expected


def test_with_relative_release_time_after_hours(write_file):
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    path: ./homework.pdf
                    recipe: make homework
                solution:
                    path: ./solution.pdf
                    recipe: make solution
                    release_time: 3 hours after ${this.metadata.due}
            """
        ),
    )

    # when
    publication = read_publication_file(path)

    # then
    expected = publication.metadata["due"] + datetime.timedelta(hours=3)
    assert isinstance(publication.artifacts["solution"], UnbuiltArtifact)
    assert publication.artifacts["solution"].release_time == expected


def test_with_relative_release_time_after_large(write_file):
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    path: ./homework.pdf
                    recipe: make homework
                solution:
                    path: ./solution.pdf
                    recipe: make solution
                    release_time: 11 days after ${this.metadata.due}
            """
        ),
    )

    # when
    publication = read_publication_file(path)

    # then
    expected = publication.metadata["due"] + datetime.timedelta(days=11)
    assert isinstance(publication.artifacts["solution"], UnbuiltArtifact)
    assert publication.artifacts["solution"].release_time == expected


def test_with_relative_release_time_after_large_hours(write_file):
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    path: ./homework.pdf
                    recipe: make homework
                solution:
                    path: ./solution.pdf
                    recipe: make solution
                    release_time: 1000 hours after ${this.metadata.due}
            """
        ),
    )

    # when
    publication = read_publication_file(path)

    # then
    expected = publication.metadata["due"] + datetime.timedelta(hours=1000)
    assert isinstance(publication.artifacts["solution"], UnbuiltArtifact)
    assert publication.artifacts["solution"].release_time == expected


def test_with_relative_release_date_before(write_file):
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    path: ./homework.pdf
                    recipe: make homework
                solution:
                    path: ./solution.pdf
                    recipe: make solution
                    release_time: 3 days before ${this.metadata.due}
            """
        ),
    )

    # when
    publication = read_publication_file(path)

    # then
    expected = publication.metadata["due"] - datetime.timedelta(days=3)
    assert isinstance(publication.artifacts["solution"], UnbuiltArtifact)
    assert publication.artifacts["solution"].release_time == expected


def test_with_relative_release_date_before_hours(write_file):
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    path: ./homework.pdf
                    recipe: make homework
                solution:
                    path: ./solution.pdf
                    recipe: make solution
                    release_time: 3 hours before ${this.metadata.due}
            """
        ),
    )

    # when
    publication = read_publication_file(path)

    # then
    expected = publication.metadata["due"] - datetime.timedelta(hours=3)
    assert publication.artifacts["solution"].release_time == expected


def test_with_relative_release_time_multiple_days(write_file):
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    path: ./homework.pdf
                    recipe: make homework
                solution:
                    path: ./solution.pdf
                    recipe: make solution
                    release_time: 3 days after ${this.metadata.due}
            """
        ),
    )

    # when
    publication = read_publication_file(path)

    # then
    expected = publication.metadata["due"] + datetime.timedelta(days=3)
    assert publication.artifacts["solution"].release_time == expected


def test_with_invalid_relative_date_raises(write_file):
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    path: ./homework.pdf
                    recipe: make homework
                solution:
                    path: ./solution.pdf
                    recipe: make solution
                    release_time: -1 days after ${this.metadata.due}
            """
        ),
    )

    # when
    with raises(DiscoveryError):
        read_publication_file(path)


def test_with_invalid_relative_date_variable_reference_raises(
    write_file,
):
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    path: ./homework.pdf
                    recipe: make homework
                solution:
                    path: ./solution.pdf
                    recipe: make solution
                    release_time: 1 days after ${this.metadata.foo}
            """
        ),
    )

    # when
    with raises(DiscoveryError):
        read_publication_file(path)


def test_with_absolute_release_time(write_file):
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-04 23:59:00
                released: 2020-09-01

            artifacts:
                homework:
                    path: ./homework.pdf
                    recipe: make homework
                solution:
                    path: ./solution.pdf
                    recipe: make solution
                    release_time: 2020-01-02 23:59:00
            """
        ),
    )

    # when
    publication = read_publication_file(path)

    # then
    expected = datetime.datetime(2020, 1, 2, 23, 59, 0)
    assert publication.artifacts["solution"].release_time == expected


# relative metadata
# --------------------------------------------------------------------------------------


def test_with_relative_dates_in_metadata(write_file):
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-10 23:59:00
                released: 7 days before ${this.metadata.due}

            artifacts:
                homework:
                    path: ./homework.pdf
                    recipe: make homework
                solution:
                    path: ./solution.pdf
                    recipe: make solution
                    release_time: 2020-01-02 23:59:00
            """
        ),
    )

    schema = PublicationSchema(
        required_artifacts=["homework", "solution"],
        metadata_schema={
            "required_keys": {
                "name": {"type": "string"},
                "due": {"type": "datetime"},
                "released": {"type": "datetime"},
            }
        },
    )

    # when
    publication = read_publication_file(path, publication_schema=schema)

    # then
    expected = datetime.datetime(2020, 9, 3, 23, 59, 0)
    assert publication.metadata["released"] == expected


def test_with_relative_dates_in_metadata_without_offset(write_file):
    # given
    # released should be a datetime, but it's going to be a date since its relative
    # to due, which is a date
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-09-10
                released: ${ this.metadata.due }

            artifacts:
                homework:
                    path: ./homework.pdf
                    recipe: make homework
                solution:
                    path: ./solution.pdf
                    recipe: make solution
                    release_time: 2020-01-02 23:59:00
            """
        ),
    )

    schema = PublicationSchema(
        required_artifacts=["homework", "solution"],
        metadata_schema={
            "required_keys": {
                "name": {"type": "string"},
                "due": {"type": "date"},
                "released": {"type": "date"},
            }
        },
    )

    # when
    publication = read_publication_file(path, publication_schema=schema)

    # then
    expected = datetime.date(2020, 9, 10)
    assert publication.metadata["released"] == expected


def test_with_unknown_relative_field_raises(write_file):
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 01
                due: 2020-12-01
                released: 7 days before duedate # <---- this field doesn't exist

            artifacts:
                homework:
                    path: ./homework.pdf
                    recipe: make homework
                solution:
                    path: ./solution.pdf
                    recipe: make solution
                    release_time: 2020-01-02 23:59:00
            """
        ),
    )

    schema = PublicationSchema(
        required_artifacts=["homework", "solution"],
        metadata_schema={
            "required_keys": {
                "name": {"type": "string"},
                "due": {"type": "date"},
                "released": {"type": "date"},
            }
        },
    )

    # when
    with raises(DiscoveryError):
        read_publication_file(path, publication_schema=schema)


# external variables
# --------------------------------------------------------------------------------------


def test_external_vars_simple_substitution(write_file):
    """Test that external vars can be substituted into publication file."""
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: ${vars.hw_name}

            artifacts:
                homework:
                    path: ./homework.pdf
                    recipe: ${vars.build_command}
            """
        ),
    )

    # when
    publication = read_publication_file(
        path,
        vars={"hw_name": "Homework 01", "build_command": "make homework"},
    )

    # then
    assert publication.metadata["name"] == "Homework 01"
    assert publication.artifacts["homework"].recipe == "make homework"


def test_external_vars_nested_substitution(write_file):
    """Test that nested external vars can be substituted."""
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: ${vars.course.assignment_name}
                instructor: ${vars.course.instructor}

            artifacts:
                homework:
                    path: ./homework.pdf
            """
        ),
    )

    # when
    publication = read_publication_file(
        path,
        vars={
            "course": {
                "assignment_name": "Final Project",
                "instructor": "Dr. Smith",
            }
        },
    )

    # then
    assert publication.metadata["name"] == "Final Project"
    assert publication.metadata["instructor"] == "Dr. Smith"


def test_external_vars_combined_with_this_reference(write_file):
    """Test that external vars work alongside this references."""
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: ${vars.prefix} Assignment
                full_name: ${this.metadata.name} - Advanced

            artifacts:
                homework:
                    path: ./homework.pdf
            """
        ),
    )

    # when
    publication = read_publication_file(path, vars={"prefix": "CS101"})

    # then
    assert publication.metadata["name"] == "CS101 Assignment"
    assert publication.metadata["full_name"] == "CS101 Assignment - Advanced"


def test_external_vars_missing_raises_error(write_file):
    """Test that referencing missing external vars raises an error."""
    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: ${vars.nonexistent}

            artifacts:
                homework:
                    path: ./homework.pdf
            """
        ),
    )

    # when/then
    with raises(DiscoveryError):
        read_publication_file(path, vars={})


# previous publication variable
# --------------------------------------------------------------------------------------


def test_previous_publication_metadata_reference(write_file):
    """Test that previous publication metadata can be referenced."""
    from automata.lib import Publication

    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Homework 02
                previous_name: ${previous.metadata.name}

            artifacts:
                homework:
                    path: ./homework.pdf
            """
        ),
    )

    previous = Publication(
        metadata={"name": "Homework 01", "due": datetime.date(2020, 9, 1)},
        artifacts={},
    )

    # when
    publication = read_publication_file(path, previous=previous)

    # then
    assert publication.metadata["name"] == "Homework 02"
    assert publication.metadata["previous_name"] == "Homework 01"


def test_previous_publication_with_vars(write_file):
    """Test that previous and vars can be used together."""
    from automata.lib import Publication

    # given
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: ${vars.course_code} - Homework 02
                follows: ${previous.metadata.name}

            artifacts:
                homework:
                    path: ./homework.pdf
            """
        ),
    )

    previous = Publication(
        metadata={"name": "CS101 - Homework 01"},
        artifacts={},
    )

    # when
    publication = read_publication_file(
        path,
        vars={"course_code": "CS101"},
        previous=previous,
    )

    # then
    assert publication.metadata["name"] == "CS101 - Homework 02"
    assert publication.metadata["follows"] == "CS101 - Homework 01"


# error message quality tests
# --------------------------------------------------------------------------------------


def test_error_message_includes_file_path(write_file):
    """Test that discovery errors include the path to the problematic file."""
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: ${vars.undefined_variable}
            artifacts:
                homework:
                    path: ./homework.pdf
            """
        ),
    )

    with raises(DiscoveryError) as exc_info:
        read_publication_file(path, vars={})

    error_message = str(exc_info.value)
    assert "publication.yaml" in error_message


def test_error_message_includes_keypath_for_resolution_error(write_file):
    """Test that resolution errors indicate which key failed."""
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Test
                nested:
                    deep:
                        value: ${vars.missing}
            artifacts:
                homework:
                    path: ./homework.pdf
            """
        ),
    )

    with raises(DiscoveryError) as exc_info:
        read_publication_file(path, vars={})

    error_message = str(exc_info.value)
    # Should indicate the keypath where the error occurred
    assert (
        "metadata" in error_message
        or "nested" in error_message
        or "deep" in error_message
    )


def test_error_message_for_invalid_yaml_syntax(write_file):
    """Test that YAML syntax errors are clearly reported."""
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Test
                bad_indent:
              wrong: indentation
            artifacts:
                homework:
                    path: ./homework.pdf
            """
        ),
    )

    with raises(DiscoveryError) as exc_info:
        read_publication_file(path)

    error_message = str(exc_info.value)
    assert "publication.yaml" in error_message


def test_error_message_for_schema_violation(write_file):
    """Test that schema violations indicate what went wrong."""
    path = write_file(
        "publication.yaml",
        contents=dedent(
            """
            metadata:
                name: Test
            """
        ),
    )

    with raises(DiscoveryError) as exc_info:
        read_publication_file(path)

    error_message = str(exc_info.value)
    assert "publication.yaml" in error_message
    # Should indicate the missing required key
    assert "artifacts" in error_message
