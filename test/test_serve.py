"""Tests for Automata.serve(): rebuilding on changes, and the live-reloading
server."""

import datetime
import json
import socket
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from automata import Automata
from automata._serve import LiveReload, Rebuilder, make_server, snapshot
from automata.exceptions import Error

_CONFIG = """\
course:
  name: DSC 40B
  title: Theoretical Foundations of Data Science II
  term: Winter 2025
  first_week_start: 2025-01-06
website:
  theme:
    use: default
    config: {rebuild_tailwind: false}
  content_directory: content
  build_directory: _build
  base_path: BASE
"""

NOW = datetime.datetime(2025, 1, 8, 12)


def _project(tmp_path: Path, base_path: str = '"/"') -> Path:
    project = tmp_path / "project"
    (project / "content").mkdir(parents=True)
    (project / "automata.yaml").write_text(_CONFIG.replace("BASE", base_path))
    (project / "content" / "index.md").write_text("# Home\n")
    return project


class _Loads:
    """Loads the project, counting how often (each load is a full build)."""

    def __init__(self, path: Path):
        self.path, self.count = path, 0

    def __call__(self) -> Automata:
        self.count += 1
        return Automata(self.path)


def _rebuilder(project: Path, load=None) -> tuple[Rebuilder, LiveReload, list[str]]:
    live, messages = LiveReload(), []
    rebuilder = Rebuilder(
        load or _Loads(project),
        root=project,
        content_dir=project / "content",
        build_dir=project / "_build",
        live=live,
        current_time=NOW,
        echo=messages.append,
    )
    return rebuilder, live, messages


def _index(project: Path) -> str:
    return (project / "_build" / "index.html").read_text()


# watching for changes =================================================================


def test_a_snapshot_skips_the_build_directory_and_hidden_files(tmp_path):
    project = _project(tmp_path)
    (project / "_build").mkdir()
    (project / "_build" / "index.html").write_text("x")
    (project / ".git").mkdir()
    (project / ".git" / "HEAD").write_text("x")

    files = snapshot(project, exclude=[project / "_build"])

    assert set(files) == {project / "automata.yaml", project / "content" / "index.md"}


# rebuilding ===========================================================================


def test_the_first_build_builds_the_site(tmp_path):
    project = _project(tmp_path)
    rebuilder, live, _ = _rebuilder(project)

    rebuilder.build()

    assert "Home" in _index(project)
    assert live.state() == (1, None)


def test_nothing_is_rebuilt_without_changes(tmp_path):
    project = _project(tmp_path)
    rebuilder, live, _ = _rebuilder(project)
    rebuilder.build()

    assert not rebuilder.poll()
    assert live.state() == (1, None)


def test_a_changed_page_only_rerenders_the_website(tmp_path):
    project = _project(tmp_path)
    loads = _Loads(project)
    rebuilder, live, _ = _rebuilder(project, loads)
    rebuilder.build()

    (project / "content" / "index.md").write_text("# Changed\n")
    (project / "content" / "new.md").write_text("# New\n")

    assert rebuilder.poll()
    assert "Changed" in _index(project)
    assert (project / "_build" / "new.html").exists()
    assert loads.count == 1
    assert live.state() == (2, None)


@pytest.mark.parametrize(
    "change",
    [
        lambda p: (p / "automata.yaml").write_text(
            (p / "automata.yaml").read_text() + "vars: {x: 1}\n"
        ),
        lambda p: (p / "content" / "index.md").unlink(),
        lambda p: (p / "notes.txt").write_text("outside the content directory"),
    ],
    ids=["configuration", "deleted page", "other file"],
)
def test_other_changes_reload_the_project_and_build_it_all(tmp_path, change):
    project = _project(tmp_path)
    loads = _Loads(project)
    rebuilder, live, _ = _rebuilder(project, loads)
    rebuilder.build()

    change(project)

    assert rebuilder.poll()
    assert loads.count == 2
    assert live.state()[0] == 2


def test_files_written_by_the_build_itself_are_not_changes(tmp_path):
    # recipes write their outputs into the materials' directories
    project = _project(tmp_path)

    class WritesAFile(_Loads):
        def __call__(self):
            automata = super().__call__()
            build = automata.build

            def build_and_write(**kwargs):
                build(**kwargs)
                (project / "homework.pdf").write_text("built by a recipe")

            automata.build = build_and_write
            return automata

    rebuilder, _, _ = _rebuilder(project, WritesAFile(project))
    rebuilder.build()

    assert not rebuilder.poll()


def test_a_failed_build_is_reported_and_cleared_by_the_next(tmp_path):
    project = _project(tmp_path)
    rebuilder, live, messages = _rebuilder(project)
    rebuilder.build()
    config = project / "automata.yaml"
    good = config.read_text()

    config.write_text(good.replace("  term: Winter 2025\n", ""))
    rebuilder.poll()

    version, error = live.state()
    assert version == 2
    assert 'missing required key "term"' in error
    assert any('missing required key "term"' in m for m in messages)
    assert "Home" in _index(project)  # the last good build is still there

    config.write_text(good)
    rebuilder.poll()

    assert live.state() == (3, None)


# serving ==============================================================================


@pytest.fixture
def serve(tmp_path):
    """Serve a built project; returns a function that GETs a path from it."""
    servers = []

    def start(base_path='"/"'):
        project = _project(tmp_path, base_path)
        rebuilder, live, _ = _rebuilder(project)
        rebuilder.build()
        (project / "_build" / "style.css").write_text("body {}")
        server = make_server(project / "_build", base_path.strip('"'), live, port=0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        port = server.server_address[1]

        def get(path):
            return urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5)

        return get, live

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def test_served_pages_reload_themselves(serve):
    get, _ = serve()

    html = get("/index.html").read().decode()

    assert "Home" in html
    assert "/__automata__/events" in html


def test_other_files_are_served_as_they_are(serve):
    get, _ = serve()

    assert get("/style.css").read() == b"body {}"


def test_directories_serve_their_index(serve):
    get, _ = serve()

    assert "/__automata__/events" in get("/").read().decode()


def test_nothing_is_cached(serve):
    get, _ = serve()

    assert get("/style.css").headers["Cache-Control"] == "no-store"


def test_the_site_is_served_under_its_base_path(serve):
    get, _ = serve('"/course/"')

    response = get("/")

    assert response.url.endswith("/course/")
    assert "Home" in response.read().decode()
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        get("/elsewhere/index.html")
    assert excinfo.value.code == 404


def test_the_events_say_the_builds_version_and_error(serve):
    get, live = serve()
    events = get("/__automata__/events")

    first = _next_event(events)
    live.failed("It broke.")
    second = _next_event(events)

    assert first == {"version": 1, "error": None}
    assert second == {"version": 2, "error": "It broke."}


def _next_event(response):
    lines = []
    while (line := response.readline().decode()) != "\n":
        lines.append(line)
    data = next(line for line in lines if line.startswith("data: "))
    return json.loads(data.removeprefix("data: "))


def test_serve_reports_a_port_in_use(tmp_path):
    project = _project(tmp_path)
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]

        with pytest.raises(Error) as excinfo:
            Automata(project).serve(port=port)

    assert f"Port {port} is in use" in str(excinfo.value)


def _serve_once(project, **kwargs):
    """Run serve() until its first wait for changes."""
    from automata._serve import serve

    def stop(seconds):
        raise KeyboardInterrupt

    serve(
        project,
        port=0,
        current_time=NOW,
        verbose=False,
        echo=lambda m: None,
        sleep=stop,
        **kwargs,
    )


def test_serve_opens_the_site_in_a_browser(tmp_path):
    project = _project(tmp_path, '"/course/"')
    opened = []

    _serve_once(project, open_url=opened.append)

    assert len(opened) == 1
    assert opened[0].startswith("http://127.0.0.1:")
    assert opened[0].endswith("/course/")


def test_serve_can_leave_the_browser_alone(tmp_path):
    project = _project(tmp_path)

    _serve_once(project, open_url=None)  # (nothing to open it with)
