"""Unit tests for the listing element's table data (template_vars)."""

import datetime

import jinja2
import pytest

import automata.materials
from automata.builtin.elements import Listing
from automata.website import RenderContext
from automata.website.exceptions import WebsiteError


def _publication(metadata, artifacts=()):
    return automata.materials.Publication(
        metadata=metadata,
        artifacts={
            name: automata.materials.ExportedArtifact(path=f"/{name}")
            for name in artifacts
        },
    )


@pytest.fixture
def listing():
    """A Listing over a 'homeworks' collection of three publications."""
    materials = automata.materials.Universe(
        collections={
            "homeworks": automata.materials.Collection(
                publication_schema=None,
                publications={
                    # deliberately out of order: rows are sorted by key
                    "hw02": _publication(
                        {"name": "Homework 2", "due": None}, artifacts=["homework.pdf"]
                    ),
                    "hw01": _publication(
                        {"name": "Homework 1", "due": "Jan 10"},
                        artifacts=["homework.pdf", "solution.pdf"],
                    ),
                    "hw03": _publication({"name": "Homework 3"}),
                },
            )
        }
    )
    context = RenderContext(
        materials=materials,
        url_for=lambda path: path,
        current_time=datetime.datetime(2024, 1, 15),
    )
    return Listing(jinja2.Environment(loader=jinja2.DictLoader({})), context)


def _config(*columns, numbered=False):
    return {"collection": "homeworks", "columns": list(columns), "numbered": numbered}


def _column(heading, cell_content, requires=None):
    return {"heading": heading, "cell_content": cell_content, "requires": requires}


def _requires(**kwargs):
    requires = {
        "artifacts": [],
        "metadata": [],
        "non_null_metadata": [],
        "cell_content_if_missing": None,
    }
    requires.update(kwargs)
    return requires


def test_headings_come_from_the_columns(listing):
    tvars = listing.template_vars(_config(_column("Name", "x"), _column("Due", "y")))

    assert tvars["headings"] == ["Name", "Due"]


def test_one_row_per_publication_sorted_by_key_and_numbered(listing):
    tvars = listing.template_vars(
        _config(_column("Name", "${ publication.metadata.name }"), numbered=True)
    )

    assert [row.number for row in tvars["rows"]] == [1, 2, 3]
    assert [row.cells for row in tvars["rows"]] == [
        ["Homework 1"],
        ["Homework 2"],
        ["Homework 3"],
    ]
    assert tvars["numbered"] is True


def test_cells_use_the_missing_content_when_a_required_artifact_is_missing(listing):
    column = _column(
        "Solution",
        "<a href='${ publication.artifacts[\"solution.pdf\"].path }'>Solution</a>",
        requires=_requires(
            artifacts=["solution.pdf"], cell_content_if_missing="Not yet"
        ),
    )

    cells = [row.cells[0] for row in listing.template_vars(_config(column))["rows"]]

    assert cells == ["<a href='/solution.pdf'>Solution</a>", "Not yet", "Not yet"]


def test_cells_use_the_missing_content_for_missing_or_null_metadata(listing):
    column = _column(
        "Due",
        "${ publication.metadata.due }",
        requires=_requires(non_null_metadata=["due"], cell_content_if_missing="TBA"),
    )

    cells = [row.cells[0] for row in listing.template_vars(_config(column))["rows"]]

    # hw01 has a due date; hw02's is null; hw03 has no due key at all
    assert cells == ["Jan 10", "TBA", "TBA"]


def test_missing_content_can_use_the_publication(listing):
    column = _column(
        "Status",
        "ready",
        requires=_requires(
            artifacts=["solution.pdf"],
            cell_content_if_missing="${ publication.metadata.name } pending",
        ),
    )

    cells = [row.cells[0] for row in listing.template_vars(_config(column))["rows"]]

    assert cells == ["ready", "Homework 2 pending", "Homework 3 pending"]


def test_without_missing_content_the_normal_content_is_used(listing):
    column = _column(
        "Name",
        "${ publication.metadata.name }",
        requires=_requires(artifacts=["solution.pdf"]),
    )

    cells = [row.cells[0] for row in listing.template_vars(_config(column))["rows"]]

    assert cells == ["Homework 1", "Homework 2", "Homework 3"]


def test_an_error_in_a_cell_names_the_column_and_publication(listing):
    column = _column("Grade", "${ publication.metadata.grade }")

    with pytest.raises(WebsiteError) as excinfo:
        listing.template_vars(_config(column))

    message = str(excinfo.value)
    assert '"Grade"' in message
    assert '"hw01"' in message
    assert "grade" in message
