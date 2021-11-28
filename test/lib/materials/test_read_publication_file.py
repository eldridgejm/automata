from textwrap import dedent
import datetime

from pytest import raises, fixture, mark

from automata.materials.lib import (
    read_publication_file,
    DiscoveryError,
    PublicationSchema,
)


def test_example(write_file):
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
        publication = read_publication_file(path)


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
        publication = read_publication_file(path)


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
        publication = read_publication_file(path)


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
        publication = read_publication_file(path, publication_schema=schema)
