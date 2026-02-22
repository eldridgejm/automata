"""Tests for automata.resources."""

import json
import stat
from pathlib import Path

import pytest

from automata.hooks import BuildSuccessHookArgs, Hooks
from automata.materials import ExportedArtifact, ExportedMaterials, Universe, serialize
from automata.resources import (
    Resources,
    load_content,
    load_elements,
    load_hooks,
    load_templates,
)

# load_templates ===================================================================


def test_load_templates_reads_files(tmp_path: Path) -> None:
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "index.html").write_text("Index template")
    (templates_dir / "page.html").write_text("Page template")

    result = load_templates(templates_dir)

    assert result == {
        "index.html": "Index template",
        "page.html": "Page template",
    }


def test_load_templates_preserves_subdirectory_keys(tmp_path: Path) -> None:
    templates_dir = tmp_path / "templates"
    (templates_dir / "partials").mkdir(parents=True)
    (templates_dir / "base.html").write_text("Base")
    (templates_dir / "partials" / "nav.html").write_text("Nav")

    result = load_templates(templates_dir)

    assert result == {
        "base.html": "Base",
        "partials/nav.html": "Nav",
    }


def test_load_templates_empty_directory(tmp_path: Path) -> None:
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    result = load_templates(templates_dir)

    assert result == {}


# load_content =====================================================================


def test_load_content_markdown_files_are_pages(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "index.md").write_text("# Hello")

    pages, static_files = load_content(content_dir)

    assert pages == {"index.md": "# Hello"}
    assert static_files == {}


def test_load_content_html_files_are_pages(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "about.html").write_text("<h1>About</h1>")

    pages, static_files = load_content(content_dir)

    assert pages == {"about.html": "<h1>About</h1>"}
    assert static_files == {}


def test_load_content_other_files_are_static(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "style.css").write_text("body {}")
    (content_dir / "logo.png").write_bytes(b"\x89PNG")

    pages, static_files = load_content(content_dir)

    assert pages == {}
    assert static_files == {"style.css": "body {}", "logo.png": b"\x89PNG"}


def test_load_content_preserves_directory_keys(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    (content_dir / "css").mkdir(parents=True)
    (content_dir / "posts").mkdir()
    (content_dir / "css" / "style.css").write_text("body {}")
    (content_dir / "posts" / "first.md").write_text("# First")

    pages, static_files = load_content(content_dir)

    assert pages == {"posts/first.md": "# First"}
    assert static_files == {"css/style.css": "body {}"}


def test_load_content_empty_directory(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    content_dir.mkdir()

    pages, static_files = load_content(content_dir)

    assert pages == {}
    assert static_files == {}


# load_elements ====================================================================


def test_load_elements_loads_element_dict(tmp_path: Path) -> None:
    elements_dir = tmp_path / "elements"
    elements_dir.mkdir()
    (elements_dir / "__init__.py").write_text(
        "def my_element(config, context):\n"
        "    return 'hello'\n"
        "\n"
        'elements = {"my": my_element}\n'
    )

    result = load_elements(elements_dir)

    assert "my" in result
    assert callable(result["my"])


def test_load_elements_no_init_py_raises(tmp_path: Path) -> None:
    elements_dir = tmp_path / "elements"
    elements_dir.mkdir()

    with pytest.raises(ValueError):
        load_elements(elements_dir)


def test_load_elements_with_submodules(tmp_path: Path) -> None:
    elements_dir = tmp_path / "elements"
    elements_dir.mkdir()
    (elements_dir / "_button.py").write_text(
        "def button(config, context):\n"
        "    return f\"<button>{config['label']}</button>\"\n"
    )
    (elements_dir / "_card.py").write_text(
        "def card(config, context):\n"
        "    return f\"<div class='card'>{config['title']}</div>\"\n"
    )
    (elements_dir / "__init__.py").write_text(
        "from ._button import button\n"
        "from ._card import card\n"
        "\n"
        'elements = {"button": button, "card": card}\n'
    )

    result = load_elements(elements_dir)

    assert result["button"]({"label": "Click"}, None) == "<button>Click</button>"
    assert result["card"]({"title": "Hello"}, None) == "<div class='card'>Hello</div>"


def test_load_elements_missing_elements_variable_raises(tmp_path: Path) -> None:
    elements_dir = tmp_path / "elements"
    elements_dir.mkdir()
    (elements_dir / "__init__.py").write_text("x = 1\n")

    with pytest.raises(ValueError):
        load_elements(elements_dir)


# load_hooks =======================================================================


def test_load_hooks_registers_executable_script(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    output_file = tmp_path / "output.json"
    script = hooks_dir / "on_build_success"
    script.write_text(f"#!/bin/sh\ncat > {output_file}\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)

    result = load_hooks(hooks_dir)
    result.on_build_success(
        BuildSuccessHookArgs(
            workdir=tmp_path,
            path="site",
            returncode=0,
        )
    )

    assert output_file.exists()
    output = json.loads(output_file.read_text())
    assert output["path"] == "site"
    assert output["returncode"] == 0


def test_load_hooks_with_submodules(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "_logging.py").write_text(
        "def make_hook(output_file):\n"
        "    def hook(args):\n"
        "        with open(output_file, 'w') as f:\n"
        "            f.write('hook ran')\n"
        "    return hook\n"
    )
    (hooks_dir / "__init__.py").write_text(
        "from pathlib import Path\n"
        "from ._logging import make_hook\n"
        "\n"
        "def register(hooks):\n"
        f"    hook = make_hook('{tmp_path / 'hook_output.txt'}')\n"
        "    hooks.on_generate_post.register(priority=0)(hook)\n"
    )

    result = load_hooks(hooks_dir)
    result.on_generate_post(None)

    assert (tmp_path / "hook_output.txt").read_text() == "hook ran"


def test_load_hooks_registers_python_hooks(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "__init__.py").write_text(
        "def register(hooks):\n"
        "    @hooks.on_generate_post.register(priority=0)\n"
        "    def my_hook(args):\n"
        "        pass\n"
    )

    result = load_hooks(hooks_dir)

    assert isinstance(result, Hooks)
    assert len(result.on_generate_post.implementations) > 0


def test_load_hooks_raises_on_unknown_hook_script(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    script = hooks_dir / "on_bild_success"
    script.write_text("#!/bin/sh\necho ok\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)

    with pytest.raises(ValueError, match="does not match any known hook point"):
        load_hooks(hooks_dir)


def test_load_hooks_raises_on_unsupported_shell_hook(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    script = hooks_dir / "on_generate_pre"
    script.write_text("#!/bin/sh\necho ok\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)

    with pytest.raises(ValueError, match="does not support shell scripts"):
        load_hooks(hooks_dir)


def test_load_hooks_raises_on_missing_register_function(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "__init__.py").write_text("x = 1\n")

    with pytest.raises(ValueError, match="must define a `register`"):
        load_hooks(hooks_dir)


def test_load_hooks_empty_directory(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()

    result = load_hooks(hooks_dir)

    assert isinstance(result, Hooks)


# Resources.from_directory =========================================================


def test_from_directory_loads_all_resources(tmp_path: Path) -> None:
    ext_dir = tmp_path / "my-extension"
    templates_dir = ext_dir / "templates"
    content_dir = ext_dir / "content"
    elements_dir = ext_dir / "elements"

    templates_dir.mkdir(parents=True)
    content_dir.mkdir()
    elements_dir.mkdir()

    (templates_dir / "base.html").write_text("<html></html>")
    (content_dir / "index.md").write_text("# Home")
    (content_dir / "style.css").write_text("body {}")
    (elements_dir / "__init__.py").write_text(
        'elements = {"noop": lambda c, ctx: ""}\n'
    )

    result = Resources.from_directory(ext_dir)

    assert isinstance(result, Resources)
    assert "base.html" in result.templates
    assert "index.md" in result.pages
    assert "style.css" in result.static_files
    assert "noop" in result.elements


def test_from_directory_skips_missing_subdirectories(tmp_path: Path) -> None:
    ext_dir = tmp_path / "my-extension"
    templates_dir = ext_dir / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "base.html").write_text("<html></html>")

    result = Resources.from_directory(ext_dir)

    assert "base.html" in result.templates
    assert result.pages == {}
    assert result.static_files == {}
    assert result.elements == {}


def test_from_directory_empty_directory(tmp_path: Path) -> None:
    ext_dir = tmp_path / "my-extension"
    ext_dir.mkdir()

    result = Resources.from_directory(ext_dir)

    assert isinstance(result, Resources)
    assert result.templates == {}
    assert result.pages == {}
    assert result.static_files == {}
    assert result.elements == {}
    assert result.materials is None


def test_from_directory_loads_materials(tmp_path: Path) -> None:
    ext_dir = tmp_path / "my-extension"
    ext_dir.mkdir()

    universe = Universe(
        collections={
            "homeworks": _make_collection({"hw01": "hw01.pdf", "hw02": "hw02.pdf"}),
        }
    )
    (ext_dir / "materials.json").write_text(serialize(universe))

    result = Resources.from_directory(ext_dir)

    assert result.materials is not None
    assert isinstance(result.materials, ExportedMaterials)
    assert result.materials.root == ext_dir
    assert "homeworks" in result.materials.universe.collections
    collection = result.materials.universe.collections["homeworks"]
    hw01 = collection.publications["hw01"].artifacts["hw01"]
    assert hw01.path == "hw01.pdf"


def test_from_directory_materials_defaults_to_none(tmp_path: Path) -> None:
    ext_dir = tmp_path / "my-extension"
    ext_dir.mkdir()

    result = Resources.from_directory(ext_dir)

    assert result.materials is None


# helpers ===========================================================================


def _make_collection(publications: dict[str, str]):
    """Create a Collection[ExportedArtifact] from a {pub_key: artifact_path} mapping."""
    from automata.materials import Collection, Publication, PublicationSchema

    return Collection(
        publication_schema=PublicationSchema(required_artifacts=[]),
        publications={
            key: Publication(
                metadata={},
                artifacts={key: ExportedArtifact(path=path)},
            )
            for key, path in publications.items()
        },
    )
