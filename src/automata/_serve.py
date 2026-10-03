"""Serving the site locally, rebuilding it when the project changes.

A :class:`Rebuilder` watches the project's files (by polling their modification
times) and rebuilds what changed: a changed page only re-renders the website;
anything else reloads the project and builds it all. A small HTTP server
serves the build directory, adding to each HTML page a script that listens to
the server's events: the page reloads after each rebuild, and shows the error
when one fails (the last good build is still served).
"""

from __future__ import annotations

import datetime
import errno
import json
import os
import threading
import time
import urllib.parse
from collections.abc import Callable
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .exceptions import Error

if TYPE_CHECKING:
    from ._automata import Automata

# where pages listen for rebuilds
EVENTS_PATH = "/__automata__/events"


# the state of the builds ==============================================================


class LiveReload:
    """The latest build's version (which counts the builds) and error, if it
    failed, shared by the rebuilder and the server's event streams."""

    def __init__(self) -> None:
        self._changed = threading.Condition()
        self._version = 0
        self._error: str | None = None

    def state(self) -> tuple[int, str | None]:
        with self._changed:
            return self._version, self._error

    def built(self) -> None:
        self._update(None)

    def failed(self, error: str) -> None:
        self._update(error)

    def _update(self, error: str | None) -> None:
        with self._changed:
            self._version += 1
            self._error = error
            self._changed.notify_all()

    def wait(self, version: int | None, timeout: float) -> tuple[int, str | None]:
        """The state, once its version isn't *version* (or after *timeout*
        seconds)."""
        with self._changed:
            self._changed.wait_for(lambda: self._version != version, timeout)
            return self._version, self._error


# watching and rebuilding ==============================================================

Snapshot = dict[Path, tuple[int, int]]


def snapshot(root: Path, exclude: list[Path]) -> Snapshot:
    """Each file under *root*'s modification time and size, skipping the
    directories in *exclude*, and hidden files and directories (like .git)."""
    excluded = {path.resolve() for path in exclude}
    files: Snapshot = {}
    for directory, subdirectories, names in os.walk(root):
        subdirectories[:] = [
            name
            for name in subdirectories
            if not name.startswith(".")
            and name != "__pycache__"
            and (Path(directory) / name).resolve() not in excluded
        ]
        for name in names:
            if not name.startswith("."):
                path = Path(directory) / name
                try:
                    stat = path.stat()
                except FileNotFoundError:  # deleted since it was listed
                    continue
                files[path] = (stat.st_mtime_ns, stat.st_size)
    return files


class Rebuilder:
    """Builds the project, then rebuilds it when its files change.

    Parameters
    ----------
    load : Callable[[], Automata]
        Loads the project (again, for each full build, since its configuration
        may have changed).
    root, content_dir, build_dir : Path
        The project's directory, and its content and build directories.
    live : LiveReload
        Told of each build, and whether it failed.
    current_time : datetime.datetime | None
        The time to build for; by default, the time of each build.
    verbose : bool
        Whether recipes' output goes to the terminal.
    echo : Callable[[str], None]
        Reports each build.

    """

    def __init__(
        self,
        load: Callable[[], Automata],
        root: Path,
        content_dir: Path,
        build_dir: Path,
        live: LiveReload,
        current_time: datetime.datetime | None = None,
        verbose: bool = False,
        echo: Callable[[str], None] = print,
    ):
        self.load, self.root, self.live, self.echo = load, root, live, echo
        self.content_dir, self.build_dir = content_dir.resolve(), build_dir
        self.current_time, self.verbose = current_time, verbose
        self._project: Automata | None = None
        self._files: Snapshot = {}

    def build(self, full: bool = True) -> None:
        """Build the site: all of it, or (unless *full*) only the website."""
        current_time = self.current_time or datetime.datetime.now()
        try:
            if full or self._project is None:
                self._project = None
                project = self.load()
                project.build(current_time=current_time, verbose=self.verbose)
                self._project = project
            else:
                self._project.render_website(
                    self._project.load_exported_materials(), current_time=current_time
                )
        except Exception as e:
            # a failed full build leaves no project, so the next is full too
            self._project = None
            message = str(e) if isinstance(e, Error) else f"{type(e).__name__}: {e}"
            self.live.failed(message)
            self.echo(f"Error: {message}")
        else:
            self.live.built()
            what = "Built the site" if full else "Re-rendered the website"
            self.echo(f"{what} at {datetime.datetime.now():%H:%M:%S}.")
        # after the build, so that the files it writes (like recipes' outputs)
        # aren't taken for changes
        self._files = snapshot(self.root, exclude=[self.build_dir])

    def poll(self) -> bool:
        """Rebuild, if any file has changed since the last build; returns
        whether it did."""
        files = snapshot(self.root, exclude=[self.build_dir])
        changed = {
            path
            for path in files.keys() | self._files.keys()
            if files.get(path) != self._files.get(path)
        }
        if not changed:
            return False
        # new or changed pages only need the website re-rendered
        pages_only = all(
            path in files and path.resolve().is_relative_to(self.content_dir)
            for path in changed
        )
        self.build(full=not pages_only)
        return True


# serving ==============================================================================

# added to each served page: it reloads the page after a rebuild, and shows the
# error when one fails
RELOAD_SCRIPT = f"""<script>
(function () {{
  var seen = null, overlay = null;
  function show(error) {{
    if (!error) {{
      if (overlay) overlay.remove();
      overlay = null;
      return;
    }}
    if (!overlay) {{
      overlay = document.createElement("div");
      overlay.style.cssText = "position: fixed; left: 0; right: 0; bottom: 0; " +
        "max-height: 50vh; overflow: auto; z-index: 2147483647; margin: 0; " +
        "padding: 16px 20px; background: #1e1e2e; color: #f5f5f5; " +
        "border-top: 4px solid #e15759; font: 13px/1.5 ui-monospace, monospace;";
      document.body.appendChild(overlay);
    }}
    overlay.innerHTML = "<strong>automata: the build failed</strong> " +
      "<span style='opacity: 0.7'>(showing the last good build)</span>" +
      "<pre style='white-space: pre-wrap; margin: 8px 0 0'></pre>";
    overlay.querySelector("pre").textContent = error;
  }}
  var events = new EventSource("{EVENTS_PATH}");
  events.addEventListener("state", function (event) {{
    var state = JSON.parse(event.data);
    if (seen !== null && state.version !== seen && !state.error) {{
      location.reload();
      return;
    }}
    seen = state.version;
    show(state.error);
  }});
}})();
</script>
"""


def inject_reload_script(html: bytes) -> bytes:
    """*html*, with the reload script added before its ``</body>``."""
    script = RELOAD_SCRIPT.encode()
    end = html.lower().rfind(b"</body>")
    if end == -1:
        return html + script
    return html[:end] + script + html[end:]


def _prefix(base_path: str) -> str:
    """The path the site is served under: *base_path*'s, if it is absolute
    (``"/course/"``, or a URL's), else the root."""
    path = urllib.parse.urlsplit(base_path).path
    if not path.startswith("/"):
        return "/"
    return path if path.endswith("/") else path + "/"


def make_server(
    build_dir: Path,
    base_path: str,
    live: LiveReload,
    port: int,
    host: str = "127.0.0.1",
) -> ThreadingHTTPServer:
    """A server for the site in *build_dir*, under *base_path*, whose pages
    reload after each build *live* is told of. Raises
    :class:`~automata.exceptions.Error` if *port* is in use."""
    prefix = _prefix(base_path)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any):
            super().__init__(*args, directory=str(build_dir), **kwargs)

        def log_message(self, format: str, *args: Any) -> None:
            pass  # the terminal is for the builds

        def end_headers(self) -> None:
            # always the latest build
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def do_GET(self) -> None:
            path = urllib.parse.urlsplit(self.path).path
            if path == EVENTS_PATH:
                self._events()
                return
            if not path.startswith(prefix):
                if path == "/":
                    self._redirect(prefix)
                else:
                    self.send_error(404)
                return

            # serve the build directory as if it were at the root
            self.path = "/" + self.path[len(prefix) :]
            file = Path(self.translate_path(self.path))
            if file.is_dir():
                if not path.endswith("/"):
                    self._redirect(path + "/")
                    return
                file = file / "index.html"
            if file.suffix == ".html" and file.is_file():
                self._page(file)
            else:
                super().do_GET()

        def _redirect(self, location: str) -> None:
            self.send_response(302)
            self.send_header("Location", location)
            self.end_headers()

        def _page(self, file: Path) -> None:
            body = inject_reload_script(file.read_bytes())
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _events(self) -> None:
            """Server-sent events: the builds' state when a page connects, and
            whenever it changes."""
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            version = None
            while True:
                state = live.wait(version, timeout=15)
                if state[0] == version:
                    message = ": still here\n\n"  # keeps the connection open
                else:
                    version = state[0]
                    data = json.dumps({"version": state[0], "error": state[1]})
                    message = f"event: state\ndata: {data}\n\n"
                try:
                    self.wfile.write(message.encode())
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    return  # the page closed

    try:
        return ThreadingHTTPServer((host, port), Handler)
    except OSError as e:
        if e.errno == errno.EADDRINUSE:
            raise Error(f"Port {port} is in use: choose another with --port.") from None
        raise


def serve(
    path: Path,
    port: int,
    current_time: datetime.datetime | None,
    verbose: bool,
    echo: Callable[[str], None],
    open_url: Callable[[str], object] | None = None,
    interval: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Build the project at *path*, serve it (opening it with *open_url*, if
    given), and rebuild it when it changes, until interrupted (with Ctrl-C)."""
    from ._automata import Automata

    project = Automata(path)
    website = project.config.website
    live = LiveReload()
    # before building, so that a port in use is reported right away
    server = make_server(path / website.build_directory, website.base_path, live, port)
    rebuilder = Rebuilder(
        lambda: Automata(path),
        root=path,
        content_dir=path / website.content_directory,
        build_dir=path / website.build_directory,
        live=live,
        current_time=current_time,
        verbose=verbose,
        echo=echo,
    )
    rebuilder.build()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}{_prefix(website.base_path)}"
    echo(f"Serving at {url}")
    echo("Rebuilding when files change. Press Ctrl-C to stop.")
    if open_url is not None:
        open_url(url)
    try:
        while True:
            sleep(interval)
            rebuilder.poll()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
