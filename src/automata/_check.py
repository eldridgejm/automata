"""Checking a project for problems, without building anything."""

from __future__ import annotations

import dataclasses
import datetime
from typing import TYPE_CHECKING, Any

import jinja2
import smartconfig.exceptions

from .config import CONFIGURATION_FILENAME
from .exceptions import Error
from .hooks import WebsiteInputs
from .util.resolution import describe_config_error, local_time, resolve
from .website import Page, load_content_directory
from .website._frontmatter import FrontmatterError, read_frontmatter

if TYPE_CHECKING:
    from ._automata import Automata


@dataclasses.dataclass
class Problem:
    """A problem found by :meth:`automata.Automata.check`.

    Attributes
    ----------
    area : str
        What has the problem: ``"configuration"``, ``"materials"``,
        ``"pages"``, ``"templates"``, ``"elements"``, or ``"publish"``.
    message : str
        The problem, as the command that would fail on it reports it.

    """

    area: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        """The problem as JSON-ready data."""
        return {"area": self.area, "message": self.message}


def run_checks(project: Automata, current_time: datetime.datetime) -> list[Problem]:
    """Every problem in *project* that the checks find (see Automata.check)."""
    problems = _check_materials(project, local_time(current_time))
    problems += _check_pages(project)
    inputs = project.hooks.on_render_collect(WebsiteInputs())
    problems += _check_templates(inputs)
    problems += _check_elements(project, inputs)
    problems += _check_publish(project)
    return problems


# materials ============================================================================


def _check_materials(
    project: Automata, current_time: datetime.datetime
) -> list[Problem]:
    """Problems in the collections and publications, and released artifacts
    without their file (which would fail the build)."""
    errors: list[Error] = []
    discovered = project._discover(hooks=None, errors=errors)
    # (sorted, so they are in the order of their files)
    problems = sorted(
        (Problem("materials", str(e)) for e in errors), key=lambda p: p.message
    )

    for collection_key, collection in discovered.collections.items():
        for publication_key, publication in collection.publications.items():
            for artifact_key, artifact in publication.artifacts.items():
                released = (
                    artifact.release_time is None
                    or local_time(artifact.release_time) <= current_time
                )
                path = artifact.workdir / artifact.path
                if (
                    released
                    and artifact.ready
                    and artifact.recipe is None
                    and not artifact.missing_ok
                    and not path.exists()
                ):
                    key = f"{collection_key}/{publication_key}/{artifact_key}"
                    problems.append(
                        Problem(
                            "materials",
                            f"Artifact {key} has no recipe, and its file {path} "
                            f"does not exist.",
                        )
                    )
    return problems


# pages ================================================================================

# the page syntax, as rendering uses it (see website._render._interpolate)
_PAGE_ENVIRONMENT = jinja2.Environment(
    variable_start_string="${",
    variable_end_string="}",
    block_start_string="{%",
    block_end_string="%}",
)


def _check_pages(project: Automata) -> list[Problem]:
    """Problems in each page's frontmatter and template syntax."""
    website = project.config.website
    content_dir = project.path / website.content_directory
    if not content_dir.is_dir():
        return [
            Problem(
                "pages",
                f'website.content_directory "{website.content_directory}" does not '
                f"exist ({content_dir}).",
            )
        ]

    build_dir = project.path / website.build_directory
    try:
        pages, _ = load_content_directory(
            content_dir,
            build_dir / website.materials_directory_name,
            no_render_suffix=website.no_render_suffix,
        )
    except Error as e:
        return [Problem("pages", str(e))]

    problems = []
    for page in pages.values():
        problem = _check_page(page, project.config.vars)
        if problem is not None:
            problems.append(problem)
    return problems


def _check_page(page: Page, vars: dict[str, Any]) -> Problem | None:
    """The problem in a page's frontmatter or template syntax, if any."""
    path = page.source
    base_path = path.parent if path is not None else None
    try:
        _, content = read_frontmatter(page.content, base_path=base_path, vars=vars)
    except FrontmatterError as e:
        location = f"{path}:{e.line}" if e.line is not None else f"{path}"
        return Problem("pages", f"{location}: {e.message}")
    except Error as e:
        return Problem("pages", f"{path}: {e}")

    try:
        _PAGE_ENVIRONMENT.parse(content)
    except jinja2.TemplateSyntaxError as e:
        # lines before the content (the frontmatter), so lines are the file's
        offset = page.content[: len(page.content) - len(content)].count("\n")
        return Problem("pages", f"{path}:{e.lineno + offset}: {e.message}")
    return None


# templates and elements ===============================================================


def _check_templates(inputs: WebsiteInputs) -> list[Problem]:
    """Syntax errors in the templates the theme and extensions provide."""
    environment = jinja2.Environment(
        variable_start_string="${",
        variable_end_string="}",
        block_start_string="{%",
        block_end_string="%}",
    )
    problems = []
    for name in sorted(inputs.templates):
        try:
            environment.parse(inputs.templates[name])
        except jinja2.TemplateSyntaxError as e:
            problems.append(
                Problem("templates", f"template {name}, line {e.lineno}: {e.message}")
            )
    return problems


def _check_elements(project: Automata, inputs: WebsiteInputs) -> list[Problem]:
    """Problems in website.elements: unknown elements, and configurations that
    don't match their element's schema (whether or not a page uses them)."""
    configs = project.config.website.elements
    unknown = sorted(set(configs) - set(inputs.elements))
    problems = []
    if unknown:
        available = ", ".join(sorted(inputs.elements)) or "none"
        problems.append(
            Problem(
                "elements",
                f"website.elements configures unknown element(s): "
                f"{', '.join(unknown)}. Available elements: {available}.",
            )
        )

    for name, config in configs.items():
        schema = getattr(inputs.elements.get(name), "schema", None)
        if schema is None:
            continue
        try:
            resolve(config, schema)
        except smartconfig.exceptions.ResolutionError as e:
            message = describe_config_error(
                e.reason,
                ("website", "elements", name, *e.keypath),
                file=project.path / CONFIGURATION_FILENAME,
                source_map=project.source_map,
            )
            problems.append(Problem("elements", message))
    return problems


# publishing ===========================================================================


def _check_publish(project: Automata) -> list[Problem]:
    """Problems in the publish targets: their shape and strategy."""
    from ._automata import _check_publish_target

    publishers = project._publishers()
    problems = []
    for name, entry in project.config.publish.items():
        try:
            _check_publish_target(name, entry)
        except Error as e:
            problems.append(Problem("publish", str(e)))
            continue
        strategy = entry["strategy"]
        if strategy not in publishers:
            available = ", ".join(sorted(publishers)) or "(none)"
            problems.append(
                Problem(
                    "publish",
                    f"publish.{name}: Unknown publish strategy: {strategy!r}. "
                    f"Available: {available}",
                )
            )
    return problems
