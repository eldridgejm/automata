"""Tests for the Automata public API."""

import json
from datetime import datetime
from textwrap import dedent, indent

import pytest

from automata import Automata
from automata.exceptions import Error
from automata.materials import Universe, serialize


@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal automata project."""
    project = tmp_path / "project"
    project.mkdir()

    # automata.yaml
    (project / "automata.yaml").write_text(
        dedent("""\
            website:
              theme:
                use: "default"
                config:
                  short_title: "Test"
                  long_title: "Test Course"
              content_directory: "content"
              build_directory: "_build"
        """)
    )

    # Content
    content = project / "content"
    content.mkdir()
    (content / "index.md").write_text("# Home")

    # A simple collection with one publication
    hw = project / "homeworks"
    hw.mkdir()
    (hw / "collection.yaml").write_text(
        dedent("""\
            publication_schema:
                required_artifacts:
                    - homework.pdf
        """)
    )

    pub = hw / "hw01"
    pub.mkdir()
    (pub / "publication.yaml").write_text(
        dedent("""\
            metadata:
                name: Homework 1

            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
        """)
    )

    return project


# Automata() ===========================================================================


def test_init_reads_config(project_dir):
    a = Automata(project_dir)
    assert a.config.website.build_directory == "_build"


def test_init_stores_path(project_dir):
    a = Automata(project_dir)
    assert a.path == project_dir


def test_init_initializes_hooks(project_dir):
    a = Automata(project_dir)
    assert a.hooks is not None


# discover() ===========================================================================


def test_discover_returns_universe(project_dir):
    a = Automata(project_dir)
    universe = a.discover()
    assert isinstance(universe, Universe)
    assert "homeworks" in universe.collections


# build_materials() ====================================================================


def test_build_materials_returns_built_universe(project_dir):
    a = Automata(project_dir)
    discovered = a.discover()
    built = a.build_materials(discovered, ignore_release_time=True, ignore_ready=True)
    assert isinstance(built, Universe)
    assert "homeworks" in built.collections


# export() =============================================================================


def test_export_writes_materials_json(project_dir):
    a = Automata(project_dir)
    discovered = a.discover()
    built = a.build_materials(discovered, ignore_release_time=True, ignore_ready=True)
    a.export(built)

    materials_json = project_dir / "_build" / "materials" / "materials.json"
    assert materials_json.exists()
    data = json.loads(materials_json.read_text())
    assert "homeworks" in data["collections"]


def test_export_returns_exported_universe(project_dir):
    a = Automata(project_dir)
    discovered = a.discover()
    built = a.build_materials(discovered, ignore_release_time=True, ignore_ready=True)
    exported = a.export(built)
    assert isinstance(exported, Universe)


# load_exported_materials() ============================================================


def test_load_exported_materials_returns_what_export_wrote(project_dir):
    # given
    a = Automata(project_dir)
    built = a.build_materials(a.discover(), ignore_release_time=True, ignore_ready=True)
    exported = a.export(built)

    # when
    loaded = Automata(project_dir).load_exported_materials()

    # then
    assert loaded == exported


def test_load_exported_materials_can_feed_render_website(project_dir):
    # given
    a = Automata(project_dir)
    built = a.build_materials(a.discover(), ignore_release_time=True, ignore_ready=True)
    a.export(built)

    # when
    a.render_website(a.load_exported_materials())

    # then
    assert (project_dir / "_build" / "index.html").exists()


def test_load_exported_materials_raises_if_nothing_was_exported(project_dir):
    with pytest.raises(Error) as excinfo:
        Automata(project_dir).load_exported_materials()

    message = str(excinfo.value)
    assert "materials.json" in message
    assert "export" in message


def test_load_exported_materials_raises_if_file_is_not_a_universe(project_dir):
    # given: a materials.json holding a single publication, not a universe
    a = Automata(project_dir)
    publication = a.discover().collections["homeworks"].publications["hw01"]
    materials_json = project_dir / "_build" / "materials" / "materials.json"
    materials_json.parent.mkdir(parents=True)
    materials_json.write_text(serialize(publication))

    # when / then
    with pytest.raises(Error) as excinfo:
        a.load_exported_materials()

    assert "materials.json" in str(excinfo.value)


# render_website() =====================================================================


def test_render_website_generates_html(project_dir):
    a = Automata(project_dir)
    discovered = a.discover()
    built = a.build_materials(discovered, ignore_release_time=True, ignore_ready=True)
    exported = a.export(built)
    a.render_website(exported)

    index = project_dir / "_build" / "index.html"
    assert index.exists()
    assert "Home" in index.read_text()


def test_render_website_uses_the_materials_it_is_given(project_dir):
    # given: exported materials, filtered in Python before generating
    (project_dir / "content" / "index.md").write_text(
        "{% for name in materials.collections %}[${ name }]{% endfor %}"
    )
    a = Automata(project_dir)
    built = a.build_materials(a.discover(), ignore_release_time=True, ignore_ready=True)
    exported = a.export(built)
    without_homeworks = a.filter(exported, lambda key, node: key != "homeworks")

    # when
    a.render_website(without_homeworks)

    # then
    index = (project_dir / "_build" / "index.html").read_text()
    assert "[homeworks]" not in index


# filter() =============================================================================


def test_filter_fires_filter_hooks(project_dir):
    # given
    a = Automata(project_dir)
    hits, misses = [], []

    @a.hooks.on_filter_hit.register()
    def on_hit(args):
        hits.append(args.key)

    @a.hooks.on_filter_miss.register()
    def on_miss(args):
        misses.append(args.key)

    # when
    filtered = a.filter(a.discover(), lambda key, node: key != "hw01")

    # then
    assert "hw01" in misses
    assert "homeworks" in hits
    assert "hw01" not in filtered.collections["homeworks"].publications


# build() ==============================================================================


def test_build_runs_full_pipeline(project_dir):
    a = Automata(project_dir)
    a.build()

    index = project_dir / "_build" / "index.html"
    assert index.exists()
    assert "Home" in index.read_text()

    materials_json = project_dir / "_build" / "materials" / "materials.json"
    assert materials_json.exists()


# cleaning the build directory =========================================================


def _write_release_project(
    project, build_directory="_build", content_directory="content", extra=""
):
    """Write a project with one homework released on 2025-01-10."""
    project.mkdir(exist_ok=True)
    (project / "automata.yaml").write_text(
        dedent(f"""\
            materials:
              homeworks:
                schema:
                  required_artifacts:
                    - homework.pdf
                publications:
                  hw01:
                    artifacts:
                      homework.pdf:
                        path: homeworks/hw01/homework.pdf
                        release_time: 2025-01-10 12:00:00

            website:
              theme:
                use: "default"
                config:
                  short_title: "Test"
                  long_title: "Test Course"
                  rebuild_tailwind: false
              content_directory: "{content_directory}"
              build_directory: "{build_directory}"
            {extra}
        """)
    )
    (project / "homeworks" / "hw01").mkdir(parents=True, exist_ok=True)
    (project / "homeworks" / "hw01" / "homework.pdf").write_text("hw1")
    content = project / content_directory
    content.mkdir(parents=True, exist_ok=True)
    (content / "index.md").write_text("# Home")
    return project


_BEFORE_RELEASE = datetime(2025, 1, 1)
_AFTER_RELEASE = datetime(2025, 2, 1)


def _released_files(build_dir):
    return [p for p in build_dir.rglob("homework.pdf")]


def test_build_removes_artifact_that_is_no_longer_released(tmp_path):
    # given: the homework was released and built
    project = _write_release_project(tmp_path / "project")
    Automata(project).build(current_time=_AFTER_RELEASE)
    assert _released_files(project / "_build")

    # when: the release is effectively withdrawn and the site is rebuilt
    Automata(project).build(current_time=_BEFORE_RELEASE)

    # then
    assert _released_files(project / "_build") == []


def test_build_removes_page_that_was_deleted(tmp_path):
    # given
    project = _write_release_project(tmp_path / "project")
    (project / "content" / "syllabus.md").write_text("# Syllabus")
    Automata(project).build(current_time=_AFTER_RELEASE)
    assert (project / "_build" / "syllabus.html").exists()

    # when
    (project / "content" / "syllabus.md").unlink()
    Automata(project).build(current_time=_AFTER_RELEASE)

    # then
    assert not (project / "_build" / "syllabus.html").exists()


def test_build_keeps_top_level_dot_entries_in_build_directory(tmp_path):
    # given
    project = _write_release_project(tmp_path / "project")
    build = project / "_build"
    (build / ".git").mkdir(parents=True)
    (build / ".git" / "HEAD").write_text("ref: refs/heads/gh-pages")
    (build / ".nojekyll").write_text("")
    (build / "stale.html").write_text("stale")

    # when
    Automata(project).build(current_time=_AFTER_RELEASE)

    # then
    assert (build / ".git" / "HEAD").read_text() == "ref: refs/heads/gh-pages"
    assert (build / ".nojekyll").exists()
    assert not (build / "stale.html").exists()


def test_build_does_not_clean_when_disabled(tmp_path):
    # given
    project = _write_release_project(
        tmp_path / "project", extra="  clean_build_directory: false"
    )
    (project / "_build").mkdir()
    (project / "_build" / "stale.html").write_text("stale")

    # when
    Automata(project).build(current_time=_AFTER_RELEASE)

    # then
    assert (project / "_build" / "stale.html").exists()


def test_clean_build_directory_defaults_to_true(project_dir):
    assert Automata(project_dir).config.website.clean_build_directory is True


def test_clean_build_directory_does_nothing_if_build_directory_missing(project_dir):
    Automata(project_dir).clean_build_directory()

    assert not (project_dir / "_build").exists()


@pytest.mark.parametrize(
    "build_directory, content_directory",
    [
        (".", "content"),  # the project root
        ("..", "content"),  # contains the project root
        ("content", "content"),  # the content directory
        ("website", "website/content"),  # contains the content directory
        ("content/_build", "content"),  # inside the content directory
    ],
)
def test_clean_build_directory_refuses_unsafe_build_directory(
    tmp_path, build_directory, content_directory
):
    # given
    project = _write_release_project(
        tmp_path / "project",
        build_directory=build_directory,
        content_directory=content_directory,
    )
    (project / build_directory).mkdir(parents=True, exist_ok=True)
    sentinel = project / build_directory / "keep-me.txt"
    sentinel.write_text("important")

    # when / then
    with pytest.raises(Error) as excinfo:
        Automata(project).clean_build_directory()

    assert "build_directory" in str(excinfo.value)
    assert sentinel.exists()


def test_clean_build_directory_refuses_directory_with_automata_yaml(tmp_path):
    # given: the build directory is another automata project
    other = _write_release_project(tmp_path / "other")
    project = _write_release_project(tmp_path / "project", build_directory=str(other))

    # when / then
    with pytest.raises(Error):
        Automata(project).clean_build_directory()

    assert (other / "automata.yaml").exists()


# script hooks =========================================================================


def test_build_runs_script_hooks_from_project_root(project_dir, tmp_path, monkeypatch):
    # given: an extension whose script hook writes a page using a path relative
    # to the project root, and a process running somewhere else
    ext_dir = project_dir / "extensions" / "pages"
    (ext_dir / "hooks").mkdir(parents=True)
    (ext_dir / "hooks" / "on_render_pre").write_text(
        "cat > /dev/null && echo '# Generated' > content/generated.md"
    )
    config = project_dir / "automata.yaml"
    config.write_text("extensions:\n  - extensions/pages\n" + config.read_text())
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    # when
    Automata(project_dir).build()

    # then
    assert "Generated" in (project_dir / "_build" / "generated.html").read_text()


# finding the project ==================================================================


def test_init_raises_helpful_error_without_automata_yaml(tmp_path):
    with pytest.raises(Error) as excinfo:
        Automata(tmp_path)

    message = str(excinfo.value)
    assert "automata.yaml" in message
    assert str(tmp_path) in message


def test_init_does_not_search_parent_directories(project_dir, monkeypatch):
    monkeypatch.chdir(project_dir / "content")

    with pytest.raises(Error):
        Automata()


# publish() ============================================================================


def _add_publish_targets(project_dir, targets: str):
    config = project_dir / "automata.yaml"
    config.write_text(config.read_text() + "publish:\n" + indent(dedent(targets), "  "))


def _record_publishes(project):
    """Register a 'recording' strategy on the project's hooks; return its log."""
    log = []

    def recording(build_dir, config, project_dir):
        log.append(("publish", build_dir, config, project_dir))

    @project.hooks.on_register_publishers.register()
    def add_recording(args):
        args.publishers["recording"] = recording
        return args

    @project.hooks.on_publish_pre.register()
    def pre(args):
        log.append(("pre", args.strategy))

    @project.hooks.on_publish_post.register()
    def post(args):
        log.append(("post", args.strategy))

    return log


_TWO_TARGETS = """\
      first:
        strategy: recording
        config: {label: one}
      second:
        strategy: recording
        config: {label: two}
"""


def test_publish_builds_then_publishes_the_named_target(project_dir):
    # given
    _add_publish_targets(project_dir, _TWO_TARGETS)
    project = Automata(project_dir)
    log = _record_publishes(project)

    # when
    published = project.publish("second")

    # then
    assert published == ["second"]
    assert (project_dir / "_build" / "index.html").exists()
    assert log == [
        ("pre", "recording"),
        ("publish", project_dir / "_build", {"label": "two"}, project_dir),
        ("post", "recording"),
    ]


def test_publish_without_a_target_publishes_every_target(project_dir):
    _add_publish_targets(project_dir, _TWO_TARGETS)
    project = Automata(project_dir)
    log = _record_publishes(project)

    published = project.publish()

    assert sorted(published) == ["first", "second"]
    labels = [entry[2]["label"] for entry in log if entry[0] == "publish"]
    assert sorted(labels) == ["one", "two"]


@pytest.mark.xfail(
    reason="smartconfig 0.5.3 does not preserve the order of free-form dict keys "
    "(see TODO: smartconfig key order)",
    strict=False,
)
def test_publish_without_a_target_publishes_in_configured_order(project_dir):
    _add_publish_targets(project_dir, _TWO_TARGETS)
    project = Automata(project_dir)
    _record_publishes(project)

    assert project.publish() == ["first", "second"]


def test_publish_unknown_target_is_an_error(project_dir):
    _add_publish_targets(project_dir, _TWO_TARGETS)
    project = Automata(project_dir)
    _record_publishes(project)

    with pytest.raises(Error) as excinfo:
        project.publish("third")

    message = str(excinfo.value)
    assert "third" in message
    assert "first" in message and "second" in message


def test_publish_unknown_strategy_is_an_error(project_dir):
    _add_publish_targets(project_dir, "      site:\n        strategy: carrier-pigeon\n")
    project = Automata(project_dir)

    with pytest.raises(Error) as excinfo:
        project.publish()

    message = str(excinfo.value)
    assert "carrier-pigeon" in message
    assert "gh-pages" in message  # lists what is available


def test_publish_without_publish_targets_is_an_error(project_dir):
    with pytest.raises(Error) as excinfo:
        Automata(project_dir).publish()

    assert "publish" in str(excinfo.value)


def test_publish_checks_the_target_before_building(project_dir):
    _add_publish_targets(project_dir, _TWO_TARGETS)
    project = Automata(project_dir)
    _record_publishes(project)

    with pytest.raises(Error):
        project.publish("third")

    assert not (project_dir / "_build").exists()
