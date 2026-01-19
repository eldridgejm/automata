# Automata Overview

Automata is a Python tool for automating the publication of course materials (homeworks, lectures, labs) with time-based release scheduling. It provides a pipeline for discovering, building, filtering, and exporting course content, plus a static website generator.

## Design Philosophy

### Unified Content Model

A key architectural insight is that **extensions, themes, and websites all share the same structure**:

```
<any-of-these>/
├── content/             # Pages (.md/.html) and other files
├── assets/              # Static files (CSS, JS, images, fonts)
├── templates/           # Jinja2 templates
├── elements/            # Custom HTML components (Python package)
└── hooks/               # Hook implementations
```

This uniformity means:

1. **Themes are just extensions** - loaded from the `automata.website.themes` entry point group instead of `automata.extensions`, but otherwise identical.

2. **A website is a special case of an extension** - the site directory (parent of `content_directory`) is loaded as an extension and merged with the theme.

3. **Layered composition** - Multiple extensions merge together, with later layers overriding earlier ones. The merge order is: theme → site → plugins → config hooks.

This design allows themes to provide sensible defaults that sites can selectively override, and plugins to inject additional functionality without modifying either.

### Materials as a Tree

The materials system models course content as a hierarchical tree with generic node types:

```
Universe[ArtifactType]
└── Collection[ArtifactType]      (e.g., "homeworks", "lectures")
    └── Publication[ArtifactType] (e.g., "hw01", "lecture-03")
        └── ArtifactType          (e.g., "homework.pdf", "solution.pdf")
```

All tree nodes share a common interface:
- `_children` - property exposing child nodes
- `_replace_children(new_children)` - creates a new node with different children

This enables **immutable tree transformations**: operations like `build()`, `filter()`, and `export()` return new trees rather than mutating the original.

### Artifact Lifecycle

The generic `ArtifactType` parameter tracks artifact state through the pipeline:

| State | Description | Key Fields |
|-------|-------------|------------|
| `UnbuiltArtifact` | Discovered from YAML | `recipe`, `release_time`, `ready` |
| `BuiltArtifact` | After recipe execution | `returncode`, `stdout`, `stderr` |
| `ExportedArtifact` | After copying to output | `path` (final location) |

The pipeline transforms the tree's type: `Universe[UnbuiltArtifact]` → `Universe[BuiltArtifact]` → `Universe[ExportedArtifact]`

### Hooks as Extension Points

The hook system uses Python descriptors to provide type-safe, prioritized extension points:

```python
hooks = Hooks()

@hooks.build_on_success.register(priority=10)
def log_build(artifact: BuiltArtifact) -> None:
    print(f"Built: {artifact.path}")
```

Hooks are accumulated (not overridden) during extension merging, allowing multiple extensions to observe or transform the same events.

## Project Structure

A typical automata project:

```
project/
├── automata.yaml              # Main configuration
│
├── homeworks/                  # A collection
│   ├── collection.yaml        # Collection schema
│   ├── hw01/                  # A publication
│   │   ├── publication.yaml   # Metadata + artifact definitions
│   │   └── build/             # Build outputs
│   └── hw02/
│
├── site/                       # Website source (an extension)
│   ├── content/               # Pages (.md/.html) + static files
│   │   ├── index.md
│   │   ├── about.html
│   │   └── images/logo.png
│   ├── assets/                # More static files (CSS, JS, fonts)
│   ├── templates/             # Override theme templates
│   └── elements/              # Custom elements
│       └── __init__.py
│
└── _build/                    # Generated output
    ├── index.html
    ├── about.html
    ├── images/logo.png
    └── materials/
        ├── materials.json
        └── homeworks/hw01/homework.pdf
```

## Extension Structure

Extensions can be either **filesystem directories** or **Python packages**.

### Filesystem Extension

```
my_extension/
├── content/             # Pages and static files (split by extension)
│   ├── index.md        #   .md/.html → rendered as pages
│   └── data.json       #   other → copied as static files
├── assets/              # Static files (merged with content static files)
├── templates/           # Jinja2 templates
├── elements/            # Python package, must export `elements` dict
│   └── __init__.py
├── hooks/               # Python package exporting `hooks` registry,
│   └── __init__.py      #   OR directory with executable scripts
└── schema.json          # Optional smartconfig schema
```

### Python Package Extension

```
my_extension/
├── __init__.py          # Must export `extension = Extension(...)`
└── ...                  # Organize however you like
```

### Loading Extensions

Extensions can be loaded by:
- **Path**: `Extension.from_directory(Path("./my_extension"))`
- **Entry point**: `Extension.from_entry_point("my_extension")`
- **Spec string**: `Extension.from_spec("./path")` or `Extension.from_spec("entry_point_name")`

### Merging Extensions

```python
merged = merge_extensions([theme, site, plugin1, plugin2])
```

- Templates, static files, elements, pages: **later overrides earlier**
- Hooks: **accumulated** (all run in priority order)

## Configuration

### automata.yaml

```yaml
vars:
  course_name: "CS 101"
  semester: "Fall 2024"

website:
  content_directory: site/content
  build_directory: _build
  materials_directory_name: materials
  base_path: /
  theme:
    use: default            # Entry point or path

hooks:
  post_generate_website:
    command: "python scripts/deploy.py"
    priority: 50

plugins:
  - ./my_plugin
```

### collection.yaml

Defines the schema for publications in a collection:

```yaml
publication_schema:
  required_artifacts: [homework.pdf]
  optional_artifacts: [solution.pdf]
  metadata_schema:
    name: { type: string }
    due: { type: datetime }
  is_ordered: true
  allow_unspecified_artifacts: false
```

### publication.yaml

Defines a single publication's metadata and artifacts:

```yaml
metadata:
  name: "Homework 01"
  due: 2024-09-20 23:59:00

artifacts:
  homework.pdf:
    path: ./build/homework.pdf
    recipe: make homework
    release_time: 2024-09-15
    ready: true
    missing_ok: false
```

## Hook Reference

### Materials Hooks

| Hook | When | Arguments |
|------|------|-----------|
| `discover_on_collection` | Collection found | `path`, `collection` |
| `discover_on_publication` | Publication found | `path`, `publication` |
| `discover_on_skip` | Directory skipped | `path` |
| `build_on_start` | Build begins | `key`, `node` |
| `build_on_too_soon` | Release time not reached | `artifact` |
| `build_on_not_ready` | Artifact not ready | `artifact` |
| `build_on_recipe` | Recipe executing | `artifact` |
| `build_on_missing` | Missing but missing_ok | `artifact` |
| `build_on_success` | Build succeeded | `artifact` |
| `export_on_copy` | File being copied | `src`, `dst` |
| `export_on_node` | Node being exported | `key`, `node` |
| `filter_on_hit` | Predicate matched | `key`, `node` |
| `filter_on_miss` | Predicate didn't match | `key`, `node` |

### Resolution Hooks

| Hook | When | Returns |
|------|------|---------|
| `pre_resolve` | Before config resolution | `ResolveOverrides` (functions, variables) |

### Website Hooks

| Hook | When | Returns |
|------|------|---------|
| `pre_generate_website` | Before generation (pipeline) | `WebsiteContent` |
| `post_generate_website` | After generation (scriptable) | None |

## Website Rendering

Pages are processed through:

1. **Frontmatter parsing** - YAML between `---` delimiters
2. **Variable interpolation** - Jinja2 with `${ }` / `{% %}` syntax
3. **Markdown rendering** - For `.md` files only
4. **Template wrapping** - Using the template specified in frontmatter (default: `page.html`)

### Frontmatter

```markdown
---
template: custom.html
vars:
  title: "My Page"
  show_sidebar: true
---

# Page Content

Access variables: ${ frontmatter.vars.title }
Access materials: ${ materials.collections.homeworks.publications }
Generate URLs: ${ url_for('about.html') }
```

## Module Organization

```
automata/
├── __init__.py          # Public API: build, load, Hooks, Extension, loaders
├── _api/                # High-level orchestration
│   ├── _build.py        #   build() - full pipeline
│   ├── _load.py         #   load() - config + extensions
│   └── _resolve.py      #   resolve() - config resolution
├── _config.py           # Configuration schema (Config, WebsiteConfig, etc.)
├── materials/           # Core materials pipeline
│   ├── _types.py        #   Data types: Universe, Collection, Publication, Artifact*
│   ├── _discover.py     #   discover() - find collections/publications
│   ├── _build.py        #   build() - execute recipes
│   ├── _filter.py       #   filter() - select by predicate
│   └── _export.py       #   export() - copy to output
├── website/             # Static site generation
│   ├── _generate.py     #   generate() - render pages
│   ├── _frontmatter.py  #   Frontmatter parsing
│   └── _elements.py     #   Element base class
├── hooks/               # Hook system
│   ├── _base.py         #   HookDescriptor, HookInteractor, HooksBase
│   └── __init__.py      #   Hooks class with all hook definitions
├── extensions.py        # Extension class and merge_extensions()
├── loaders.py           # load_*_from_directory() helpers
└── util/                # Shared utilities
    ├── resolution.py    #   Config resolution helpers
    ├── markdown.py      #   Markdown rendering
    └── yaml.py          #   YAML parsing
```

## Public API

```python
# High-level
from automata import build, load, resolve

# Extensions
from automata import Extension, merge_extensions

# Hooks
from automata import Hooks, hook, HooksBase
from automata import WebsiteContent, ResolveOverrides

# Loaders (for building extensions)
from automata import (
    load_templates_from_directory,
    load_files_from_directory,
    load_elements_from_directory,
    load_hooks_from_directory,
)

# Materials (low-level)
from automata.materials import (
    discover, build, filter, export,
    Universe, Collection, Publication,
    UnbuiltArtifact, BuiltArtifact, ExportedArtifact,
    serialize, deserialize,
)

# Website (low-level)
from automata.website import generate
```
