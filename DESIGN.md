# Designing an Extensions System: Resources

This document outlines the design of an extensions system for automata, enabling users to customize and extend functionality through modular resources. The system supports both filesystem-based extensions and Python package extensions.

## Resources

There are (currently) five different "resources" that can be provided:

- **Templates**: Jinja2 templates for website generation.
- **Pages**: Markdown or HTML representing website pages, which will be rendered.
- **Static files**: Any static files (e.g. CSS, JS, images) to be copied to the output directory directly.
- **Elements**: Python classes representing page elements, which can be used in templates.
- **Hooks**: Python functions that can be registered to hook points.

The `Resources` structure is the universal unit of composition throughout automata. Everything that contributes to website generation — themes, extensions, and the user's own site content — is expressed as `Resources`.

The content specific to website generation is grouped into a `WebsiteContent`:

```python
@dataclass
class WebsiteContent:
    templates: dict[str, str] = field(default_factory=dict)
    pages: dict[str, str | bytes | Traversable] = field(default_factory=dict)
    static_files: dict[str, str | bytes | Traversable] = field(default_factory=dict)
    elements: dict[str, type[Element]] = field(default_factory=dict)
    materials: ExportedMaterials | None = None
```

A `Resources` composes `WebsiteContent` with hooks and vars:

```python
@dataclass
class Resources:
    content: WebsiteContent = field(default_factory=WebsiteContent)
    hooks: Hooks = field(default_factory=Hooks)
    vars: dict[str, Any] = field(default_factory=dict)
```

Multiple `Resources` can be composed. Templates, pages, static files, and elements merge with last-wins semantics on key conflicts. Hooks are additive — all registered hooks run, ordered by priority.

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
└── hooks/              # optional: hooks (scripts and/or Python)
    ├── __init__.py      # optional: if present, register() is called
    ├── on_build_success # executable script hook
    └── on_generate_post # executable script hook
```

All subdirectories and files are optional — an extension only needs to provide the resources it cares about.

The `content/` directory is walked recursively. Files with `.md` or `.html` extensions are loaded as pages; everything else is loaded as static files. Directory structure within `content/` is preserved as the key (e.g., `content/css/style.css` becomes the static file `css/style.css`).

The `elements/` directory must be a Python package (containing `__init__.py`) that defines an `elements` variable — a dict mapping element names to `Element` classes.

The `hooks/` directory provides hooks. Two mechanisms are supported simultaneously:

**Executable scripts** — any executable file named after a hook point is automatically registered as a script hook. The hook arguments are serialized as JSON and passed to the script on stdin. For example, `hooks/on_build_success` would receive `{"workdir": "...", "path": "...", "returncode": 0}`.

**Python package** — if `hooks/__init__.py` is present, it is loaded as a Python package and must export a `register(hooks)` function. This function receives a `Hooks` instance and registers implementations using the `automata.hooks` API:

```python
# hooks/__init__.py
from automata.hooks import Hooks, BuildSuccessHookArgs

def register(hooks: Hooks):
    @hooks.on_build_success.register(priority=10)
    def log_build(args: BuildSuccessHookArgs):
        print(f"Built {args.path}")
```

This gives full control over priorities, multiple registrations per hook point, and access to Python APIs.

Both mechanisms are composable — an extension can provide scripts, an `__init__.py`, or both. All registrations are additive.

### Python package extensions

A Python package extension is a Python package (a directory containing `__init__.py`) that exports a `resources` attribute containing a `Resources` instance. Unlike filesystem extensions, which are limited to the standard directory layout, package extensions construct their `Resources` programmatically in code. This allows them to generate templates dynamically, define elements as classes directly, register hooks as closures, etc.

A package extension can be provided in two ways:

**As a filesystem package** — a local directory containing `__init__.py`. This is useful for project-specific extensions that don't need to be installed.

**As an installed package** — discovered automatically via entry points. The package registers under the `automata.extensions` group:

```toml
# pyproject.toml
[project.entry-points."automata.extensions"]
my-extension = "my_extension"
```

## Themes

A theme is simply an extension registered under a different entry point group (`automata.themes` rather than `automata.extensions`). The only additional requirement is that a theme should provide a base template. Otherwise, the same `Resources` structure and loading conventions apply — a theme can provide templates, static files, elements, hooks, and content just like any extension.

## User content

The directory that the user points the website generator at is itself loaded as `Resources` using the same filesystem layout described above. Typically a user's site directory will contain just a `content/` directory with pages and static files, but the user can also provide `templates/` to override theme templates, `elements/` to define custom elements, or `hooks/` to run custom logic at any hook point. The same loading helpers and conventions apply uniformly.

## Implementation notes

The logic for loading individual resource types from the filesystem (templates from a directory, content from a directory, elements from a package, hooks from a directory) should be implemented as public helper functions. These helpers serve double duty: they are the building blocks used internally to load filesystem extensions, and they are available for package extensions to call when they want to load some of their resources from files rather than constructing them entirely in code. For example, a package extension might construct its hooks and elements programmatically but load its templates from a bundled directory using the same helper that filesystem extensions use.
