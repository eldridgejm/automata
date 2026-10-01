"""Tests for directory extensions that include Python code (extension.py)."""

from pathlib import Path
from textwrap import dedent

import pytest

from automata import Automata
from automata._extension import apply_extension, extension_from_directory
from automata.config import load_extensions, read_config
from automata.exceptions import Error
from automata.hooks import Hooks, RenderPostHookArgs, WebsiteInputs


def _write_project(project: Path, extensions: str) -> Path:
    """Write a minimal project listing the given extensions."""
    project.mkdir(parents=True, exist_ok=True)
    (project / "automata.yaml").write_text(
        dedent("""\
            extensions:
            {extensions}
            website:
              theme:
                use: "default"
                config:
                  short_title: "Test"
                  long_title: "Test Course"
                  rebuild_tailwind: false
              content_directory: "content"
              build_directory: "_build"
        """).format(extensions=extensions)
    )
    (project / "content").mkdir(exist_ok=True)
    (project / "content" / "index.md").write_text("# Home")
    return project


def _write_extension(directory: Path, files: dict[str, str]) -> Path:
    for relative, content in files.items():
        path = directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dedent(content))
    return directory


def _load(project: Path):
    """Load the project's extensions (theme first)."""
    theme, extensions = load_extensions(
        read_config(project / "automata.yaml"), cwd=project
    )
    return theme, extensions


def _collect(ext) -> WebsiteInputs:
    hooks = Hooks()
    apply_extension(ext, hooks)
    return hooks.on_render_collect(WebsiteInputs())


_GREETING_ELEMENT = """\
    from automata._extension import Extension
    from automata.website import Element


    class Greeting(Element):
        def __call__(self, config=None):
            return f"<p class='greeting'>Hello, {config['name']}!</p>"


    def make_extension(config):
        def collect(inputs):
            inputs.elements["greeting"] = Greeting
            return inputs

        return Extension(
            name="greeter", hooks={"on_render_collect": collect}, config=config
        )
"""


# basic behavior =======================================================================


def test_extension_py_can_provide_an_element_used_in_a_page(tmp_path):
    # given
    project = _write_project(tmp_path / "project", "  - extensions/greeter")
    _write_extension(
        project / "extensions" / "greeter", {"extension.py": _GREETING_ELEMENT}
    )
    (project / "content" / "index.md").write_text(
        '${ elements.greeting({"name": "DSC 40B"}) }'
    )

    # when
    Automata(project).build()

    # then
    index = (project / "_build" / "index.html").read_text()
    assert "Hello, DSC 40B!" in index


def test_extension_is_named_after_its_directory(tmp_path):
    project = _write_project(tmp_path / "project", "  - extensions/greeter")
    _write_extension(
        project / "extensions" / "greeter", {"extension.py": _GREETING_ELEMENT}
    )

    _, (ext,) = _load(project)

    assert ext.name == "greeter"


def test_directory_without_extension_py_is_just_files(tmp_path):
    project = _write_project(tmp_path / "project", "  - extensions/plain")
    _write_extension(
        project / "extensions" / "plain",
        {"templates/extra.html": "extra", "helpers.py": "raise RuntimeError()"},
    )

    _, (ext,) = _load(project)

    assert _collect(ext).templates == {"extra.html": "extra"}


# config ===============================================================================


def test_make_extension_receives_config_validated_against_module_schema(tmp_path):
    project = _write_project(
        tmp_path / "project",
        "  - use: extensions/configured\n    config: {title: Hi}",
    )
    _write_extension(
        project / "extensions" / "configured",
        {
            "extension.py": """\
                from automata._extension import Extension

                schema = {
                    "type": "dict",
                    "required_keys": {"title": {"type": "string"}},
                    "optional_keys": {"size": {"type": "integer", "default": 3}},
                }

                def make_extension(config):
                    return Extension(name="configured", hooks={}, config=config)
            """
        },
    )

    _, (ext,) = _load(project)

    assert ext.config == {"title": "Hi", "size": 3}


def test_make_extension_config_can_be_validated_by_schema_json(tmp_path):
    project = _write_project(tmp_path / "project", "  - extensions/configured")
    _write_extension(
        project / "extensions" / "configured",
        {
            "schema.json": '{"type": "dict", "optional_keys": '
            '{"size": {"type": "integer", "default": 3}}}',
            "extension.py": """\
                from automata._extension import Extension

                def make_extension(config):
                    return Extension(name="configured", hooks={}, config=config)
            """,
        },
    )

    _, (ext,) = _load(project)

    assert ext.config == {"size": 3}


def test_schema_in_both_extension_py_and_schema_json_is_an_error(tmp_path):
    project = _write_project(tmp_path / "project", "  - extensions/configured")
    _write_extension(
        project / "extensions" / "configured",
        {
            "schema.json": '{"type": "dict"}',
            "extension.py": """\
                from automata._extension import Extension

                schema = {"type": "dict"}

                def make_extension(config):
                    return Extension(name="configured", hooks={}, config=config)
            """,
        },
    )

    with pytest.raises(Error) as excinfo:
        _load(project)

    assert "configured" in str(excinfo.value)
    assert "schema" in str(excinfo.value)


# combining files and Python ===========================================================


def test_python_collect_runs_after_files_are_collected(tmp_path):
    project = _write_project(tmp_path / "project", "  - extensions/combined")
    _write_extension(
        project / "extensions" / "combined",
        {
            "templates/extra.html": "from file",
            "extension.py": """\
                from automata._extension import Extension

                def make_extension(config):
                    def collect(inputs):
                        seen = inputs.templates["extra.html"]
                        inputs.templates["seen.html"] = f"python saw: {seen}"
                        return inputs

                    return Extension(
                        name="combined", hooks={"on_render_collect": collect}
                    )
            """,
        },
    )

    _, (ext,) = _load(project)
    templates = _collect(ext).templates

    assert templates["extra.html"] == "from file"
    assert templates["seen.html"] == "python saw: from file"


def test_script_hook_and_python_hook_for_same_point_both_run(tmp_path, monkeypatch):
    # given
    project = _write_project(tmp_path / "project", "  - extensions/both")
    _write_extension(
        project / "extensions" / "both",
        {
            "hooks/on_render_post": "cat > /dev/null && touch script-ran",
            "extension.py": """\
                from pathlib import Path

                from automata._extension import Extension

                def make_extension(config):
                    def post(args):
                        Path("python-ran").touch()

                    return Extension(name="both", hooks={"on_render_post": post})
            """,
        },
    )
    _, (ext,) = _load(project)
    hooks = Hooks()
    apply_extension(ext, hooks)

    # when: the python hook writes relative to the process cwd, so run there
    monkeypatch.chdir(project)
    hooks.on_render_post(RenderPostHookArgs(build_directory=project / "_build"))

    # then
    assert (project / "script-ran").exists()
    assert (project / "python-ran").exists()


def test_python_extension_can_declare_dependencies(tmp_path):
    project = _write_project(tmp_path / "project", "  - extensions/dependent")
    _write_extension(
        project / "extensions" / "dependent",
        {
            "extension.py": """\
                from automata._extension import Extension

                helper = Extension(name="helper-ext", hooks={}, config={"x": 1})

                def make_extension(config):
                    return Extension(
                        name="dependent", hooks={}, dependencies=[helper]
                    )
            """,
        },
    )
    (project / "content" / "index.md").write_text(
        '${ extensions["helper-ext"].config.x }'
    )

    Automata(project).build()

    assert "1" in (project / "_build" / "index.html").read_text()


def test_extension_py_can_export_a_plain_extension(tmp_path):
    project = _write_project(tmp_path / "project", "  - extensions/plainpy")
    _write_extension(
        project / "extensions" / "plainpy",
        {
            "extension.py": """\
                from automata._extension import Extension

                def _collect(inputs):
                    inputs.templates["plain.html"] = "plain"
                    return inputs

                extension = Extension(
                    name="plainpy", hooks={"on_render_collect": _collect}
                )
            """,
        },
    )

    _, (ext,) = _load(project)

    assert _collect(ext).templates["plain.html"] == "plain"


# imports ==============================================================================


def test_extension_py_can_import_sibling_modules_relatively(tmp_path):
    project = _write_project(tmp_path / "project", "  - extensions/greeter")
    _write_extension(
        project / "extensions" / "greeter",
        {
            "elements.py": _GREETING_ELEMENT.split("def make_extension")[0],
            "extension.py": """\
                from automata._extension import Extension

                from .elements import Greeting

                def make_extension(config):
                    def collect(inputs):
                        inputs.elements["greeting"] = Greeting
                        return inputs

                    return Extension(
                        name="greeter", hooks={"on_render_collect": collect}
                    )
            """,
        },
    )

    _, (ext,) = _load(project)

    assert "greeting" in _collect(ext).elements


def test_two_extensions_with_same_module_names_do_not_collide(tmp_path):
    def files(value):
        return {
            "helpers.py": f"VALUE = {value!r}\n",
            "extension.py": """\
                from automata._extension import Extension

                from .helpers import VALUE

                def make_extension(config):
                    def collect(inputs):
                        inputs.templates[VALUE + ".html"] = VALUE
                        return inputs

                    return Extension(name=VALUE, hooks={"on_render_collect": collect})
            """,
        }

    project = _write_project(
        tmp_path / "project", "  - extensions/first\n  - extensions/second"
    )
    _write_extension(project / "extensions" / "first", files("first"))
    _write_extension(project / "extensions" / "second", files("second"))

    _, (first, second) = _load(project)

    assert "first.html" in _collect(first).templates
    assert "second.html" in _collect(second).templates


def test_reloading_picks_up_changes_to_extension_py(tmp_path):
    project = _write_project(tmp_path / "project", "  - extensions/changing")
    ext_dir = project / "extensions" / "changing"

    def write(value):
        _write_extension(
            ext_dir,
            {
                "helpers.py": f"VALUE = {value!r}\n",
                "extension.py": """\
                    from automata._extension import Extension

                    from .helpers import VALUE

                    def make_extension(config):
                        return Extension(name="changing", hooks={}, config={"v": VALUE})
                """,
            },
        )

    write("before")
    _, (ext_before,) = _load(project)
    write("after")
    _, (ext_after,) = _load(project)

    assert ext_before.config == {"v": "before"}
    assert ext_after.config == {"v": "after"}


# errors ===============================================================================


def test_extension_py_without_factory_or_extension_is_an_error(tmp_path):
    project = _write_project(tmp_path / "project", "  - extensions/empty")
    _write_extension(project / "extensions" / "empty", {"extension.py": "x = 1\n"})

    with pytest.raises(Error) as excinfo:
        _load(project)

    message = str(excinfo.value)
    assert "empty" in message
    assert "make_extension" in message


def test_error_while_importing_extension_py_names_the_extension(tmp_path):
    project = _write_project(tmp_path / "project", "  - extensions/broken")
    _write_extension(
        project / "extensions" / "broken",
        {"extension.py": "import a_module_that_does_not_exist\n"},
    )

    with pytest.raises(Error) as excinfo:
        _load(project)

    message = str(excinfo.value)
    assert "broken" in message
    assert "a_module_that_does_not_exist" in message


# extension_from_directory(allow_python=...) ===========================================


def test_extension_from_directory_ignores_extension_py_by_default(tmp_path):
    ext_dir = _write_extension(
        tmp_path / "theme",
        {"templates/page.html": "${ content }", "extension.py": "raise RuntimeError()"},
    )

    ext = extension_from_directory("theme", ext_dir)

    assert _collect(ext).templates == {"page.html": "${ content }"}


def test_extension_from_directory_loads_extension_py_when_allowed(tmp_path):
    ext_dir = _write_extension(
        tmp_path / "greeter", {"extension.py": _GREETING_ELEMENT}
    )

    ext = extension_from_directory(
        "greeter", ext_dir, require_templates=False, allow_python=True
    )

    assert "greeting" in _collect(ext).elements
