# Designing an Extensions System: Resources

This document outlines the design of an extensions system for automata, enabling users to customize and extend functionality through modular resources. The system supports both filesystem-based extensions and Python package extensions.

## Resources

There are (currently) five different "resources" that can be provided:

- **Templates**: Jinja2 templates for website generation.
- **Pages**: Markdown or HTML representing website pages, which will be rendered.
- **Static files**: Any static files (e.g. CSS, JS, images) to be copied to the output directory directly.
- **Elements**: Python classes representing page elements, which can be used in templates.
- **Hooks**: Python functions that can be registered to hook points.

The first four are the "website resources", which are loaded and passed to the website generator. A **builtin** is a set of resources provided by automata itself (e.g., the default theme). An **extension** is a set of resources provided externally.

The first four resources are grouped into a `WebsiteResources`:

```python
@dataclass
class WebsiteResources:
    templates: dict[str, str] = field(default_factory=dict)
    pages: dict[str, str | bytes | Traversable] = field(default_factory=dict)
    static_files: dict[str, str | bytes | Traversable] = field(default_factory=dict)
    elements: dict[str, type[Element]] = field(default_factory=dict)
```

A `Resources` extends `WebsiteResources` with hooks:

```python
@dataclass
class Resources(WebsiteResources):
    hooks: ThemeHooks = field(default_factory=ThemeHooks)
```

Multiple `Resources` can be composed. Templates, pages, static files, and elements merge with last-wins semantics on key conflicts. Hooks are additive — all registered hooks run, ordered by priority.

On the filesystem, pages and static files are provided together in a single `content/` directory (rather than separate `pages/` and `static/` directories). When content is loaded, the file extension determines which attribute a file is assigned to: `.md` and `.html` files become pages; all other files become static files.

## Extensions

An extension is simply a `Resources` provided externally. Extensions can be defined in two ways: as a filesystem directory, or as an installed Python package.

### Filesystem extensions

A filesystem extension is a directory with the following layout:

```
my-extension/
├── templates/          # optional: Jinja2 templates
├── content/            # optional: pages (.md) and static files
├── elements/           # optional: Python package exporting element classes
│   ├── __init__.py
│   └── ...
└── hooks.py            # optional: pre_generate / post_generate functions
```

All subdirectories and files are optional — an extension only needs to provide the resources it cares about.

The `content/` directory is walked recursively. Files with `.md` or `.html` extensions are loaded as pages; everything else is loaded as static files. Directory structure within `content/` is preserved as the key (e.g., `content/css/style.css` becomes the static file `css/style.css`).

The `elements/` directory must be a Python package (containing `__init__.py`) that defines an `elements` variable — a dict mapping element names to `Element` classes.

The `hooks.py` file may define `pre_generate` and/or `post_generate` functions.

### Python package extensions

A Python package extension is a Python package (a directory containing `__init__.py`) that exports a `resources` attribute containing a `Resources` instance. By convention, the package uses `Resources.from_directory` on its own package directory, so it can use the same standard layout as a filesystem extension internally:

```python
# my_extension/__init__.py
import importlib.resources
from automata import Resources

resources = Resources.from_directory(importlib.resources.files(__name__))
```

A package extension can be provided in two ways:

**As a filesystem package** — a local directory containing `__init__.py`. This is useful for project-specific extensions that don't need to be installed:

```
my-extension/
├── __init__.py          # exports `resources` via Resources.from_directory
├── templates/
├── content/
├── elements/
│   ├── __init__.py
│   └── ...
└── hooks.py
```

**As an installed package** — discovered automatically via entry points. The package registers under the `automata.extensions` group:

```toml
# pyproject.toml
[project.entry-points."automata.extensions"]
my-extension = "my_extension"
```
