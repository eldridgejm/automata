"""Common test fixtures for the automata package."""

import pathlib
from textwrap import dedent

from pytest import fixture


@fixture
def write_file(tmpdir):
    """A fixture providing a function that writes a file to a temporary directory."""
    tmpdir = pathlib.Path(tmpdir)

    def inner(filename, contents):
        path = tmpdir / filename
        with path.open("w") as fileobj:
            fileobj.write(contents)
        return path

    return inner


class CourseBuilder:
    """A class that helps in building an example course."""

    def __init__(self, path: pathlib.Path):
        self.path = pathlib.Path(path)

    def create_collection(self, name, collection_yaml):
        """Create a collection in the example course."""
        (self.path / name).mkdir(parents=True, exist_ok=True)

        collection_yaml = dedent(collection_yaml).strip()

        with (self.path / name / "collection.yaml").open("w") as fileobj:
            fileobj.write(collection_yaml)

    def create_publication(self, collection_name, publication_name, publication_yaml):
        """Create a publication in the example course."""
        publication_path = self.path / collection_name / publication_name
        publication_path.mkdir(parents=True, exist_ok=True)

        publication_yaml = dedent(publication_yaml).strip()

        with (publication_path / "publication.yaml").open("w") as fileobj:
            fileobj.write(publication_yaml)


@fixture
def temporary_course(tmpdir) -> CourseBuilder:
    """Creates an example course in a temporary directory."""
    return CourseBuilder(tmpdir)


@fixture
def default_example_course(temporary_course) -> CourseBuilder:
    """Creates a default example course with valid collections and publications."""

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
                            type: datetime
                        released:
                            type: date
                    optional_keys:
                        author:
                            type: date

                is_ordered: true
        """,
    )

    temporary_course.create_publication(
        "homeworks",
        "01-intro",
        """
            metadata:
                name: Homework 01
                due: 2020-09-10 23:59:00
                released: 2020-09-01

            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
                solution.pdf:
                    recipe: touch solution.pdf
        """,
    )

    temporary_course.create_publication(
        "homeworks",
        "02-python",
        """
            metadata:
                name: Homework 02
                due: 2020-09-10 23:59:00
                released: 2020-09-01

            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
                solution.pdf:
                    recipe: mkdir build && touch build/solution.pdf
                    path: ./build/solution.pdf
                    ready: false
        """,
    )

    temporary_course.create_publication(
        "homeworks",
        "03-not_ready",
        """
            metadata:
                name: Homework 03
                due: 2020-09-10 23:59:00
                released: 2020-09-01

            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
                    ready: false
                solution.pdf:
                    recipe: mkdir build && touch build/solution.pdf
                    path: ./build/solution.pdf
        """,
    )

    temporary_course.create_publication(
        "homeworks",
        "04-normal_publication",
        """
            metadata:
                name: Homework 04
                due: 2020-09-10 23:59:00
                released: 2020-09-01

            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
                    ready: false
                solution.pdf:
                    recipe: mkdir build && touch build/solution.pdf
                    path: ./build/solution.pdf
        """,
    )

    return temporary_course
