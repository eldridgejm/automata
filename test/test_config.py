"""Tests for automata.config module."""

import contextlib
from pathlib import Path
from textwrap import dedent

import pytest

from automata import exceptions
from automata.config import (
    Config,
    load_extensions,
    read_config,
    read_config_with_source_map,
)


def test_read_config_reads_valid_config(tmp_path: Path) -> None:
    """Test that read_config successfully reads a valid config file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            course:
              name: Test
              title: Test Course
              term: Fall 2025
              first_week_start: 2025-01-06
            vars:
              course_name: "DSC 101"
              semester: "Fall 2025"

            website:
              theme:
                use: "default"
                config:
                  short_title: "DSC 101"
                  long_title: "Introduction to Data Science"
              content_directory: "./content"
              build_directory: "./build"
            """
        )
    )

    config = read_config(config_file)

    assert isinstance(config, Config)
    assert config.vars["course_name"] == "DSC 101"
    assert config.vars["semester"] == "Fall 2025"
    assert config.website.content_directory == "./content"
    assert config.website.build_directory == "./build"
    assert config.website.theme["use"] == "default"
    assert config.website.theme["config"]["short_title"] == "DSC 101"


def test_read_config_applies_defaults(tmp_path: Path) -> None:
    """Test that read_config applies default values for optional fields."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            course:
              name: Test
              title: Test Course
              term: Fall 2025
              first_week_start: 2025-01-06
            website:
              theme: "default"
              content_directory: "./content"
              build_directory: "./build"
            """
        )
    )

    config = read_config(config_file)

    # vars should default to {}
    assert config.vars == {}

    # extensions should default to []
    assert config.extensions == []

    # no directories are ignored
    assert config.ignore == []

    # Other website defaults
    assert config.website.materials_directory_name == "materials"
    assert config.website.no_render_suffix == ".no_render"
    assert config.website.base_path == "/"


def test_read_config_raises_on_missing_file(tmp_path: Path) -> None:
    """Test that read_config raises FileNotFoundError for missing files."""
    config_file = tmp_path / "nonexistent.yaml"

    with pytest.raises(FileNotFoundError):
        read_config(config_file)


def test_read_config_raises_on_invalid_yaml(tmp_path: Path) -> None:
    """Test that read_config raises an error for invalid YAML."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("invalid: yaml: content: [")

    with pytest.raises(Exception):  # YAML parsing error
        read_config(config_file)


def test_read_config_raises_on_missing_required_fields(tmp_path: Path) -> None:
    """Test that read_config raises ResolutionError for missing required fields."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            vars:
              test: "value"
            # Missing required 'website' field
            """
        )
    )

    with pytest.raises(exceptions.Error):
        read_config(config_file)


def test_read_config_validates_nested_structure(tmp_path: Path) -> None:
    """Test that read_config validates nested configuration structure."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            course:
              name: Test
              title: Test Course
              term: Fall 2025
              first_week_start: 2025-01-06
            website:
              theme: "default"
              content_directory: "./content"
              # Missing required build_directory
            """
        )
    )

    with pytest.raises(exceptions.Error):
        read_config(config_file)


def test_read_config_with_empty_vars(tmp_path: Path) -> None:
    """Test that read_config handles empty vars dict."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            course:
              name: Test
              title: Test Course
              term: Fall 2025
              first_week_start: 2025-01-06
            vars: {}

            website:
              theme: "default"
              content_directory: "./content"
              build_directory: "./build"
            """
        )
    )

    config = read_config(config_file)

    assert config.vars == {}


def test_read_config_with_extensions_list(tmp_path: Path) -> None:
    """Test that read_config handles extensions as a list."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            course:
              name: Test
              title: Test Course
              term: Fall 2025
              first_week_start: 2025-01-06
            extensions:
              - "default"
              - "./custom-theme"
              - use: "my-ext"
                config:
                  key: "value"

            website:
              theme: "default"
              content_directory: "./content"
              build_directory: "./build"
            """
        )
    )

    config = read_config(config_file)

    assert len(config.extensions) == 3
    assert config.extensions[0] == "default"
    assert config.extensions[1] == "./custom-theme"
    assert config.extensions[2]["use"] == "my-ext"
    assert config.extensions[2]["config"]["key"] == "value"


def test_read_config_performs_variable_interpolation(tmp_path: Path) -> None:
    """Test that read_config performs variable interpolation from vars."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            course:
              name: Test
              title: Test Course
              term: Fall 2025
              first_week_start: 2025-01-06
            vars:
              course_name: "DSC 101"
              semester: "Fall 2025"

            website:
              theme:
                use: "default"
                config:
                  short_title: ${ vars.course_name }
                  long_title: "Introduction to Data Science - ${ vars.semester }"
              content_directory: "./content"
              build_directory: "./build"
            """
        )
    )

    config = read_config(config_file)

    assert config.vars["course_name"] == "DSC 101"
    assert config.vars["semester"] == "Fall 2025"
    assert config.website.theme["config"]["short_title"] == "DSC 101"
    assert (
        config.website.theme["config"]["long_title"]
        == "Introduction to Data Science - Fall 2025"
    )


def test_read_config_with_include(tmp_path: Path) -> None:
    """Test that read_config can include external files."""
    vars_file = tmp_path / "vars.yaml"
    vars_file.write_text(
        dedent(
            """
            course_name: "DSC 101"
            semester: "Fall 2025"
            """
        )
    )

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            course:
              name: Test
              title: Test Course
              term: Fall 2025
              first_week_start: 2025-01-06
            vars:
              __include__: vars.yaml

            website:
              theme:
                use: "default"
                config:
                  short_title: ${ vars.course_name }
              content_directory: "./content"
              build_directory: "./build"
            """
        )
    )

    config = read_config(config_file)

    assert config.vars["course_name"] == "DSC 101"
    assert config.vars["semester"] == "Fall 2025"
    assert config.website.theme["config"]["short_title"] == "DSC 101"


def test_read_config_website_elements_defaults_to_empty(tmp_path: Path) -> None:
    """Test that website.elements defaults to an empty dict."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            course:
              name: Test
              title: Test Course
              term: Fall 2025
              first_week_start: 2025-01-06
            website:
              theme: "default"
              content_directory: "./content"
              build_directory: "./build"
            """
        )
    )

    config = read_config(config_file)

    assert config.website.elements == {}


def test_read_config_reads_website_elements(tmp_path: Path) -> None:
    """Test that website.elements is read, interpolating vars but preserving
    !template strings for resolution at render time."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            course:
              name: Test
              title: Test Course
              term: Fall 2025
              first_week_start: 2025-01-06
            vars:
              course_name: "DSC 101"

            website:
              theme: "default"
              content_directory: "./content"
              build_directory: "./build"
              elements:
                listing:
                  title: ${ vars.course_name }
                  cell: !template "${ publication.metadata.name }"
            """
        )
    )

    config = read_config(config_file)

    listing = config.website.elements["listing"]
    assert listing["title"] == "DSC 101"
    assert listing["cell"] == {"__template__": "${ publication.metadata.name }"}


# load_extensions() ====================================================================


def _write_config(tmp_path: Path, website_theme: str, extensions: str = "[]") -> Path:
    config_file = tmp_path / "automata.yaml"
    config_file.write_text(
        dedent(
            """
            course:
              name: Test
              title: Test Course
              term: Fall 2025
              first_week_start: 2025-01-06
            extensions: {extensions}
            website:
              theme: {theme}
              content_directory: "./content"
              build_directory: "./build"
            """
        ).format(theme=website_theme, extensions=extensions)
    )
    return config_file


_DEFAULT_THEME = (
    '{use: default, config: {short_title: "DSC 101", long_title: "Intro", '
    "rebuild_tailwind: false}}"
)


def _make_extension_dir(path: Path, page_template: bool = False) -> None:
    (path / "templates").mkdir(parents=True)
    if page_template:
        (path / "templates" / "page.html").write_text("${ content }")


def test_load_extensions_returns_theme_and_extensions_separately(
    tmp_path: Path,
) -> None:
    _make_extension_dir(tmp_path / "extensions" / "practice-problems")
    config = read_config(
        _write_config(tmp_path, _DEFAULT_THEME, "[extensions/practice-problems]")
    )

    theme, extensions = load_extensions(config, cwd=tmp_path)

    assert theme.name == "default"
    assert theme.config["short_title"] == "DSC 101"
    assert [ext.name for ext in extensions] == ["practice-problems"]


def test_load_extensions_names_directory_theme_by_basename(tmp_path: Path) -> None:
    _make_extension_dir(tmp_path / "themes" / "my-theme", page_template=True)
    config = read_config(_write_config(tmp_path, "themes/my-theme/"))

    theme, _ = load_extensions(config, cwd=tmp_path)

    assert theme.name == "my-theme"


def test_load_extensions_raises_on_duplicate_names(tmp_path: Path) -> None:
    _make_extension_dir(tmp_path / "a" / "tools")
    _make_extension_dir(tmp_path / "b" / "tools")
    config = read_config(_write_config(tmp_path, _DEFAULT_THEME, "[a/tools, b/tools]"))

    with pytest.raises(exceptions.Error) as excinfo:
        load_extensions(config, cwd=tmp_path)

    assert '"tools"' in str(excinfo.value)


def test_load_extensions_raises_if_theme_listed_as_extension(tmp_path: Path) -> None:
    config = read_config(_write_config(tmp_path, _DEFAULT_THEME, "[default]"))

    with pytest.raises(exceptions.Error) as excinfo:
        load_extensions(config, cwd=tmp_path)

    assert "website.theme" in str(excinfo.value)


def test_load_extensions_raises_if_theme_lacks_page_template(tmp_path: Path) -> None:
    _make_extension_dir(tmp_path / "themes" / "bare")
    config = read_config(_write_config(tmp_path, "themes/bare"))

    with pytest.raises(exceptions.Error) as excinfo:
        load_extensions(config, cwd=tmp_path)

    message = str(excinfo.value)
    assert '"bare"' in message
    assert "page.html" in message


def test_load_extensions_rejects_an_extension_spec_of_the_wrong_type(
    tmp_path: Path,
) -> None:
    config = read_config(_write_config(tmp_path, _DEFAULT_THEME, "[42]"))

    with pytest.raises(exceptions.Error) as excinfo:
        load_extensions(config, cwd=tmp_path)

    assert "Invalid extension spec" in str(excinfo.value)


# find_config() ========================================================================


def test_find_config_searches_upward_from_a_file(tmp_path: Path) -> None:
    from automata.config import find_config

    (tmp_path / "automata.yaml").write_text("")
    page = tmp_path / "content" / "index.md"
    page.parent.mkdir()
    page.write_text("# Home")

    assert find_config(page) == tmp_path / "automata.yaml"


# YAML errors ==========================================================================


def test_read_config_reports_a_yaml_syntax_error_with_file_and_line(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "automata.yaml"
    config_file.write_text("website:\n  theme: default\n   content_directory: x\n")

    with pytest.raises(exceptions.Error) as excinfo:
        read_config(config_file)

    message = str(excinfo.value)
    assert f"Invalid YAML in {config_file}, line 3" in message


def test_read_config_reports_a_syntax_error_in_an_included_file(tmp_path: Path) -> None:
    (tmp_path / "schedule.yaml").write_text("a: [1, 2\nb: 3\n")
    config_file = _write_config(tmp_path, _DEFAULT_THEME)
    config_file.write_text(
        "vars:\n  schedule:\n    __include__: schedule.yaml\n" + config_file.read_text()
    )

    with pytest.raises(exceptions.Error) as excinfo:
        read_config(config_file)

    assert f"Invalid YAML in {tmp_path / 'schedule.yaml'}, line 2" in str(excinfo.value)


def test_read_config_reports_a_missing_included_file(tmp_path: Path) -> None:
    config_file = _write_config(tmp_path, _DEFAULT_THEME)
    config_file.write_text(
        "vars:\n  schedule:\n    __include__: missing.yaml\n" + config_file.read_text()
    )

    with pytest.raises(exceptions.Error) as excinfo:
        read_config(config_file)

    message = str(excinfo.value)
    assert "missing.yaml" in message
    assert "not found" in message


# extension specs ======================================================================


@pytest.mark.parametrize(
    "theme, extensions, expected",
    [
        (
            "{config: {short_title: T}}",
            "[]",
            'website.theme must have a "use" key',
        ),
        (_DEFAULT_THEME, "[{config: {}}]", 'extensions.0 must have a "use" key'),
        (_DEFAULT_THEME, "[{use: 5}]", '"use" in extensions.0 must be a string'),
        (
            "{use: default, confg: {short_title: T}}",
            "[]",
            'website.theme has unknown key "confg"',
        ),
    ],
)
def test_load_extensions_reports_malformed_specs(
    tmp_path: Path, theme: str, extensions: str, expected: str
) -> None:
    config = read_config(_write_config(tmp_path, theme, extensions))

    with pytest.raises(exceptions.Error) as excinfo:
        load_extensions(config, cwd=tmp_path)

    assert expected in str(excinfo.value)


def test_read_config_reports_an_empty_file(tmp_path: Path) -> None:
    config_file = tmp_path / "automata.yaml"
    config_file.write_text("")

    with pytest.raises(exceptions.Error) as excinfo:
        read_config(config_file)

    assert f"{config_file} is empty" in str(excinfo.value)


# where configuration errors are ======================================================


def test_automata_yaml_errors_name_the_file_and_keypath(tmp_path: Path) -> None:
    config_file = _write_config(tmp_path, _DEFAULT_THEME)
    config_file.write_text(config_file.read_text() + "  contnt: x\n")

    with pytest.raises(exceptions.Error) as excinfo:
        read_config(config_file)

    assert str(excinfo.value) == (
        f"{config_file}:12: website.contnt: Dictionary contains unexpected extra key "
        f'"contnt".'
    )


def test_theme_config_errors_give_the_full_keypath(tmp_path: Path) -> None:
    config_file = _write_config(
        tmp_path,
        "{use: default, config: {short_title: T, long_title: T, "
        "navigation: [{text: Home}]}}",
    )
    config, source_map = read_config_with_source_map(config_file)

    with pytest.raises(exceptions.Error) as excinfo:
        load_extensions(config, cwd=tmp_path, source_map=source_map)

    assert str(excinfo.value) == (
        f"{config_file}:9: website.theme.config.navigation.0.url: Dictionary is "
        f'missing required key "url".'
    )


def test_extension_config_errors_give_the_full_keypath(tmp_path: Path) -> None:
    ext_dir = tmp_path / "extensions" / "sized"
    ext_dir.mkdir(parents=True)
    (ext_dir / "schema.json").write_text(
        '{"type": "dict", "optional_keys": {"size": {"type": "integer", "default": 1}}}'
    )
    config_file = _write_config(
        tmp_path, _DEFAULT_THEME, "[{use: extensions/sized, config: {size: big}}]"
    )
    config, source_map = read_config_with_source_map(config_file)

    with pytest.raises(exceptions.Error) as excinfo:
        load_extensions(config, cwd=tmp_path, source_map=source_map)

    assert str(excinfo.value) == (
        f"{config_file}:7: extensions.0.config.size: Cannot convert to integer: 'big'."
    )


def test_errors_in_included_files_give_that_file_and_line(tmp_path: Path) -> None:
    (tmp_path / "theme.yaml").write_text(
        "short_title: T\nlong_title: T\nnavigation:\n  - text: Home\n"
    )
    config_file = _write_config(
        tmp_path, "{use: default, config: {__include__: theme.yaml}}"
    )
    config, source_map = read_config_with_source_map(config_file)

    with pytest.raises(exceptions.Error) as excinfo:
        load_extensions(config, cwd=tmp_path, source_map=source_map)

    assert str(excinfo.value) == (
        f"{tmp_path / 'theme.yaml'}:4: website.theme.config.navigation.0.url: "
        f'Dictionary is missing required key "url".'
    )


def test_nested_includes_are_relative_to_the_including_file(tmp_path: Path) -> None:
    (tmp_path / "site").mkdir()
    (tmp_path / "site" / "theme.yaml").write_text(
        "short_title: T\nlong_title: T\nnavigation:\n  __include__: nav.yaml\n"
    )
    (tmp_path / "site" / "nav.yaml").write_text(
        "- text: Home\n  url: /\n- text: Notes\n"
    )
    config_file = _write_config(
        tmp_path, "{use: default, config: {__include__: site/theme.yaml}}"
    )
    config, source_map = read_config_with_source_map(config_file)

    with pytest.raises(exceptions.Error) as excinfo:
        load_extensions(config, cwd=tmp_path, source_map=source_map)

    assert str(excinfo.value) == (
        f"{tmp_path / 'site' / 'nav.yaml'}:3: website.theme.config.navigation.1.url: "
        f'Dictionary is missing required key "url".'
    )


@pytest.mark.parametrize(
    "schema_json, expected",
    [
        (
            '{"type": "dict", "required_keys": {"a": {"type": 5}}}',
            ":1: required_keys.a.type:",
        ),
        ('{"type": "dict",}', ": Invalid JSON:"),
        (
            '{\n  "type": "dict",\n  "required_keys": {\n    "a": {"type": 5}\n  }\n}',
            ":4: required_keys.a.type:",
        ),
    ],
)
def test_schema_json_errors_name_the_file(
    tmp_path: Path, schema_json: str, expected: str
) -> None:
    ext_dir = tmp_path / "extensions" / "broken"
    ext_dir.mkdir(parents=True)
    schema_file = ext_dir / "schema.json"
    schema_file.write_text(schema_json)
    config = read_config(_write_config(tmp_path, _DEFAULT_THEME, "[extensions/broken]"))

    with pytest.raises(exceptions.Error) as excinfo:
        load_extensions(config, cwd=tmp_path)

    assert str(excinfo.value).startswith(f"{schema_file}{expected}")


# undefined names ======================================================================


def _template_hint(example: str) -> str:
    return (
        "Either:\n"
        "  - it's a typo; or\n"
        "  - this value is meant to be evaluated by whatever uses it, not when "
        "this file\n"
        "    is read: write it as\n"
        f"      {example}"
    )


def _write_yaml(path: Path, text: str) -> Path:
    path.write_text(dedent(text))
    return path


_WEBSITE = """\
    course:
      name: Test
      title: Test Course
      term: Fall 2025
      first_week_start: 2025-01-06
    website:
      theme: default
      content_directory: "./content"
      build_directory: "./build"
"""


def test_an_undefined_name_suggests_a_typo_or_a_template(tmp_path: Path) -> None:
    config_file = tmp_path / "automata.yaml"
    config_file.write_text(
        dedent(_WEBSITE)
        + "  elements:\n"
        + "    listing:\n"
        + "      collection: homeworks\n"
        + "      columns:\n"
        + "        - heading: Topic\n"
        + '          cell_content: "${ publication.metadata.topic }"\n'
    )

    with pytest.raises(exceptions.Error) as excinfo:
        read_config(config_file)

    assert str(excinfo.value) == (
        f"{config_file}:15: website.elements.listing.columns.0.cell_content: "
        "'publication' is undefined. "
        + _template_hint('cell_content: !template "${ publication.metadata.topic }"')
    )


def test_an_undefined_name_in_an_included_file_shows_its_value(tmp_path: Path) -> None:
    _write_yaml(
        tmp_path / "schedule.yaml",
        """\
        primary_activity_collections:
          - collection: lectures
            for_each_publication:
              title: "Lecture ${ publication.metadata.number }"
        """,
    )
    config_file = tmp_path / "automata.yaml"
    config_file.write_text(
        dedent(_WEBSITE)
        + "  elements:\n"
        + "    schedule:\n"
        + "      __include__: schedule.yaml\n"
    )

    with pytest.raises(exceptions.Error) as excinfo:
        read_config(config_file)

    assert str(excinfo.value) == (
        f"{tmp_path / 'schedule.yaml'}:4: website.elements.schedule."
        "primary_activity_collections.0.for_each_publication.title: "
        "'publication' is undefined. "
        + _template_hint('title: !template "Lecture ${ publication.metadata.number }"')
    )


def test_an_undefined_name_in_a_list_shows_a_list_item(tmp_path: Path) -> None:
    config_file = _write_yaml(
        tmp_path / "automata.yaml",
        'vars:\n  items: ["${ item.name }"]\n' + dedent(_WEBSITE),
    )

    with pytest.raises(exceptions.Error) as excinfo:
        read_config(config_file)

    assert str(excinfo.value) == (
        f"{config_file}:2: vars.items.0: 'item' is undefined. "
        + _template_hint('- !template "${ item.name }"')
    )


def test_an_undefined_name_close_to_a_defined_one_is_a_typo(tmp_path: Path) -> None:
    config_file = _write_yaml(
        tmp_path / "automata.yaml",
        'vars:\n  course: DSC 40B\n  title: "${ vrs.course }"\n' + dedent(_WEBSITE),
    )

    with pytest.raises(exceptions.Error) as excinfo:
        read_config(config_file)

    assert str(excinfo.value) == (
        f"{config_file}:3: vars.title: 'vrs' is undefined. Did you mean \"vars\"?"
    )


def test_a_missing_key_gets_no_template_hint(tmp_path: Path) -> None:
    config_file = _write_yaml(
        tmp_path / "automata.yaml",
        'vars:\n  course: DSC 40B\n  title: "${ vars.cours }"\n' + dedent(_WEBSITE),
    )

    with pytest.raises(exceptions.Error) as excinfo:
        read_config(config_file)

    assert str(excinfo.value) == (
        f'{config_file}:3: vars.title: "vars" has no key "cours". '
        'Did you mean "course"?'
    )


def test_merge_keys_are_allowed_in_automata_yaml(tmp_path: Path) -> None:
    config_file = tmp_path / "automata.yaml"
    config_file.write_text(
        dedent(
            """\
            course:
              name: Test
              title: Test Course
              term: Fall 2025
              first_week_start: 2025-01-06
            vars:
              dirs: &dirs
                content_directory: "./content"
                build_directory: "./build"
            website:
              <<: *dirs
              theme: default
            """
        )
    )

    config = read_config(config_file)

    assert config.website.build_directory == "./build"


def test_numeric_keys_are_read_as_strings(tmp_path: Path) -> None:
    config_file = _write_config(tmp_path, _DEFAULT_THEME)
    config_file.write_text(
        "vars:\n  topics: {1: Intro, 2: Sorting}\n" + config_file.read_text()
    )

    config = read_config(config_file)

    assert config.vars == {"topics": {"1": "Intro", "2": "Sorting"}}


def test_errors_in_a_file_included_at_the_root_give_that_file(tmp_path: Path) -> None:
    (tmp_path / "real.yaml").write_text(
        dedent(
            """\
            course:
              name: Test
              title: Test Course
              term: Fall 2025
              first_week_start: 2025-01-06
            website:
              theme: default
              contnt_directory: "./content"
              build_directory: "./build"
            """
        )
    )
    config_file = tmp_path / "automata.yaml"
    config_file.write_text("__include__: real.yaml\n")

    with pytest.raises(exceptions.Error) as excinfo:
        read_config(config_file)

    assert str(excinfo.value).startswith(
        f"{tmp_path / 'real.yaml'}:6: website.content_directory: "
    )


def test_nested_includes_work_with_a_relative_project_path(tmp_path: Path) -> None:
    project = tmp_path / "course"
    (project / "site").mkdir(parents=True)
    (project / "site" / "website.yaml").write_text(
        dedent(
            """\
            theme:
              __include__: theme.yaml
            content_directory: content
            build_directory: _build
            """
        )
    )
    (project / "site" / "theme.yaml").write_text("default\n")
    (project / "automata.yaml").write_text(
        "course: {name: T, title: Test, term: Fall 2025,\n"
        "         first_week_start: 2025-01-06}\n"
        "website:\n  __include__: site/website.yaml\n"
    )

    with contextlib.chdir(tmp_path):
        config = read_config(Path("course") / "automata.yaml")

    assert config.website.theme == "default"
