# Roadmap: Bringing `dev` to Feature Parity with `feature-hooks`

This document outlines the high-level changes needed to re-implement the functionality
from the `feature-hooks` proof-of-concept branch on a clean `dev` base. Sections are
ordered by implementation sequence.

## 1. Centralized Hook System

**New module**: `src/automata/hooks/`

Create a descriptor-based hook system with:
- `HooksBase` class holding a registry: `dict[hook_name, list[(priority, callable)]]`
- `HookDescriptor` using the descriptor protocol to return `HookInteractor` on access
- `HookInteractor` providing `.register(priority)` decorator and `__call__` execution
- `@hook` decorator to define hook points from function signatures

**Hook points to define** (16 total):
- Materials discovery: `discover_on_collection`, `discover_on_publication`, `discover_on_skip`
- Materials build: `build_on_start`, `build_on_too_soon`, `build_on_not_ready`, `build_on_missing`, `build_on_recipe`, `build_on_success`
- Materials export: `export_on_copy`, `export_on_node`
- Materials filter: `filter_on_hit`, `filter_on_miss`
- Resolution: `pre_resolve`
- Website: `pre_generate_website` (pipeline), `post_generate_website` (scriptable)

**Special execution modes**:
- Pipeline hooks: output of one becomes input to next
- Scriptable hooks: serialize args to JSON for shell script execution
- Result reducers: merge multiple hook results (e.g., `merge_resolve_results`)

## 2. Loader Utilities

**New module**: `src/automata/loaders.py`

Helper functions for loading extension components:
- `load_templates_from_directory(path) -> dict[str, str]`
- `load_files_from_directory(path) -> dict[str, Traversable]`
- `load_elements_from_directory(path) -> dict[str, type[Element]]`
- `load_hooks_from_directory(path) -> Registry`
- `load_website_components_from_directory(path) -> WebsiteComponents`

## 3. Extension System

**New module**: `src/automata/extensions.py`

Implement extension loading with two supported formats:

**Filesystem extensions** (no `__init__.py`):
```
extension/
├── templates/      # Jinja2 templates
├── content/        # Pages (.md/.html) and static files
├── assets/         # Additional static files
├── elements/       # Python package exporting `elements` dict
├── hooks/          # Python package with `hooks` registry OR script files
└── schema.json     # Smartconfig configuration schema
```

**Python package extensions** (with `__init__.py`):
- Export an `extension` attribute containing an `Extension` dataclass

**Extension data structure**:
- `templates: dict[str, str]`
- `static_files: dict[str, Traversable]`
- `elements: dict[str, type[Element]]`
- `hooks: Registry`
- `pages: dict[str, str]`
- `schema: dict | None`

**Merging**: Later extensions override earlier (except hooks accumulate).

## 4. API Layer Refactor

**Reorganize**: `src/automata/_api/`

- `_load.py`: Load config, theme, site extension, and plugins; merge into single Extension
- `_build.py`: Orchestrate full build (materials pipeline + website generation with hooks)
- Move `_resolve.py` into `_api/`

**Configuration**: Rename `config.py` → `_config.py`, update schema for new extension format

## 5. Materials Pipeline Integration

Update each materials module to accept and invoke hooks:

**`_discover.py`**:
- Accept `hooks: Hooks | None` parameter
- Call `hooks.discover_on_collection()`, `discover_on_publication()`, `discover_on_skip()`

**`_build.py`**:
- Accept `hooks: Hooks | None` parameter
- Call appropriate hooks at each build event

**`_filter.py`**:
- Accept `hooks: Hooks | None` parameter
- Call `hooks.filter_on_hit()` and `filter_on_miss()`

**`_export.py`**:
- Accept `hooks: Hooks | None` parameter
- Call `hooks.export_on_copy()` and `export_on_node()`

## 6. Website Generation Refactor

**Simplify** `_generate.py`:
- Remove theme loading logic (moved to `_api/_load.py`)
- Accept pre-merged Extension containing all templates/elements/hooks
- Implement `pre_generate_website` pipeline hook for content transformation
- Implement `post_generate_website` hook after file generation

**Remove**: `_theme.py` (functionality absorbed into extension system)

## 7. Default Theme Updates

Update `src/automata/website/themes/default/`:
- Rename `static/` → `assets/`
- Convert `hooks.py` → `hooks/__init__.py` package
- Implement post-build Tailwind CSS rebuild hook (priority 100)
- Add `rebuild_tailwind` variable support to disable hook

## 8. Package Exports and Tests

Update `src/automata/__init__.py` to export:
- Core: `build`, `load`, `resolve`
- Extensions: `Extension`, `merge_extensions`
- Loaders: `load_templates_from_directory`, `load_files_from_directory`, etc.
- Hooks: `Hooks`, `HooksBase`, `HookInteractor`, `hook`, `Registry`, etc.

Add comprehensive tests for:
- Hook registration, priority ordering, and execution modes
- Extension loading from filesystem and Python packages
- Hook integration with materials pipeline
- Website generation with pre/post hooks
