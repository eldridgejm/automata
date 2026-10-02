"""Tests for Automata.status()."""

import json
from datetime import datetime
from pathlib import Path
from textwrap import dedent

from automata import Automata


def write_status_project(project: Path) -> Path:
    """A project whose homeworks are in every state, as of 2025-01-15.

    - hw01/homework.txt: released on 2025-01-01
    - hw01/solution.txt: scheduled for 2025-02-01
    - hw02/homework.txt: scheduled for 2025-01-20 09:00
    - hw03/homework.txt: not ready
    - hw04/homework.txt: missing (no recipe and no file, but missing_ok)
    """
    project.mkdir(parents=True)
    (project / "automata.yaml").write_text(
        dedent("""\
            website:
              theme:
                use: default
                config: {short_title: T, long_title: Test, rebuild_tailwind: false}
              content_directory: content
              build_directory: _build
        """)
    )
    (project / "content").mkdir()
    (project / "content" / "index.md").write_text("# Home")

    hw = project / "hw"
    hw.mkdir()
    (hw / "collection.yaml").write_text(
        "publication_schema:\n"
        "  required_artifacts: [homework.txt]\n"
        "  optional_artifacts: [solution.txt]\n"
    )
    publications = {
        "hw01": """\
            artifacts:
              homework.txt: {release_time: 2025-01-01 00:00:00}
              solution.txt: {release_time: 2025-02-01 00:00:00}
        """,
        "hw02": """\
            artifacts:
              homework.txt: {release_time: 2025-01-20 09:00:00}
        """,
        "hw03": """\
            artifacts:
              homework.txt: {ready: false}
        """,
        "hw04": """\
            artifacts:
              homework.txt: {missing_ok: true}
        """,
    }
    for name, publication_yaml in publications.items():
        (hw / name).mkdir()
        (hw / name / "publication.yaml").write_text(dedent(publication_yaml))
        if name != "hw04":
            (hw / name / "homework.txt").write_text(name)
    (hw / "hw01" / "solution.txt").write_text("solution")
    return project


JAN_15 = datetime(2025, 1, 15, 12, 0)
FEB_2 = datetime(2025, 2, 2, 12, 0)


def _states(status):
    return {a.key: a.state for a in status.artifacts}


def test_status_gives_the_state_of_each_artifact(tmp_path):
    project = write_status_project(tmp_path / "project")

    status = Automata(project).status(current_time=JAN_15)

    assert _states(status) == {
        "hw/hw01/homework.txt": "released",
        "hw/hw01/solution.txt": "scheduled",
        "hw/hw02/homework.txt": "scheduled",
        "hw/hw03/homework.txt": "not ready",
        "hw/hw04/homework.txt": "missing",
    }


def test_status_counts_the_artifacts_in_each_state(tmp_path):
    project = write_status_project(tmp_path / "project")

    status = Automata(project).status(current_time=JAN_15)

    assert status.counts == {
        "released": 1,
        "scheduled": 2,
        "not ready": 1,
        "missing": 1,
    }


def test_status_lists_the_next_releases_in_order(tmp_path):
    project = write_status_project(tmp_path / "project")

    status = Automata(project).status(current_time=JAN_15)

    assert [(a.key, a.release_time) for a in status.next_releases] == [
        ("hw/hw02/homework.txt", datetime(2025, 1, 20, 9, 0)),
        ("hw/hw01/solution.txt", datetime(2025, 2, 1, 0, 0)),
    ]


def test_status_builds_nothing_and_runs_no_recipes(tmp_path):
    project = write_status_project(tmp_path / "project")
    (project / "hw" / "hw01" / "publication.yaml").write_text(
        "artifacts:\n  homework.txt:\n    recipe: touch ran.txt && touch homework.txt\n"
    )

    Automata(project).status(current_time=JAN_15)

    assert not (project / "hw" / "hw01" / "ran.txt").exists()
    assert not (project / "_build").exists()


def test_status_as_a_dict_is_json(tmp_path):
    project = write_status_project(tmp_path / "project")

    data = Automata(project).status(current_time=JAN_15).to_dict()

    assert json.loads(json.dumps(data)) == data
    assert data["current_time"] == "2025-01-15T12:00:00"
    assert data["counts"]["scheduled"] == 2
    assert data["next_releases"] == ["hw/hw02/homework.txt", "hw/hw01/solution.txt"]
    assert data["artifacts"][1] == {
        "key": "hw/hw01/solution.txt",
        "collection": "hw",
        "publication": "hw01",
        "artifact": "solution.txt",
        "state": "scheduled",
        "release_time": "2025-02-01T00:00:00",
    }


def test_status_does_not_depend_on_the_build(tmp_path):
    # the site may be built elsewhere (e.g. by a remote runner), so status
    # reports only what the materials say
    project = write_status_project(tmp_path / "project")
    before = Automata(project).status(current_time=JAN_15).to_dict()

    Automata(project).build(current_time=JAN_15)
    after = Automata(project).status(current_time=JAN_15).to_dict()

    assert after == before


def test_status_classes_and_problem_are_exported_from_automata():
    import automata
    from automata import _check, _status

    assert automata.Status is _status.Status
    assert automata.ArtifactStatus is _status.ArtifactStatus
    assert automata.Problem is _check.Problem
    assert {"Status", "ArtifactStatus", "Problem"} <= set(automata.__all__)
