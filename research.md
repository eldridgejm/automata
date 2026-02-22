# Research: Removing `theme` from WebsiteConfig

## Current State

### What `Theme` provides (`_theme.py`)

The `Theme` dataclass has these fields:

| Field          | Type                                          | Purpose                                      |
| -------------- | --------------------------------------------- | -------------------------------------------- |
| `templates`    | `dict[str, str]`                              | Jinja2 templates (keys are relative paths)   |
| `static_files` | `dict[str, str \| bytes \| Traversable]`      | Static files to copy to build dir            |
| `elements`     | `dict[str, type[Element]]`                    | Element classes for rendering                |
| `schema`       | `smartconfig.types.Schema \| None`            | Config schema for theme config validation    |
| `hooks`        | `ThemeHooks`                                  | Pre/post generate hooks                      |

`Theme` also has:
- `from_directory()` — loads from a filesystem directory with `templates/`, `static/`, `elements/`, `hooks.py`, `schema.json`
- `from_entry_point()` — loads from `automata.themes` entry point group
- `create_jinja_environment()` — creates a Jinja2 env from its templates

`ThemeHooks` is a simple dataclass with two optional callables:
- `pre_generate(config: WebsiteConfig) -> ExtraContent | None`
- `post_generate(config: WebsiteConfig) -> None`

### What `WebsiteResources` provides (`resources.py`)

The `WebsiteResources` dataclass has these fields:

| Field          | Type                                              | Purpose                                      |
| -------------- | ------------------------------------------------- | -------------------------------------------- |
| `templates`    | `dict[str, str]`                                  | Jinja2 templates                             |
| `pages`        | `dict[str, str \| bytes \| Traversable]`          | Page content (md/html)                       |
| `static_files` | `dict[str, str \| bytes \| Traversable]`          | Static files                                 |
| `elements`     | `dict[str, type[Element]]`                        | Element classes                              |
| `materials`    | `ExportedMaterials \| None`                        | Materials data + root path                   |
| `hooks`        | `GenerateHooks`                                   | Generate-phase hooks                         |

`Resources(WebsiteResources)` extends it with:
- `hooks: Hooks` (the full hook set, overriding the narrower `GenerateHooks`)
- `from_directory()` — loads from filesystem with `templates/`, `content/`, `elements/`, `hooks/`, `materials.json`
- `from_entry_point()` — loads from `automata.extensions` entry point group

### Overlap between Theme and WebsiteResources

Both already provide:
- **templates** — same type (`dict[str, str]`)
- **static_files** — same type (`dict[str, str | bytes | Traversable]`)
- **elements** — same type (`dict[str, type[Element]]`)
- **hooks** — different mechanism: Theme uses `ThemeHooks` (old-style pre/post callables); Resources uses `GenerateHooks` (the new pipeline/observer hook system)

What Theme has that Resources does NOT:
- **schema** — `smartconfig.types.Schema | None` for validating theme config

What Resources has that Theme does NOT:
- **pages** — content pages
- **materials** — `ExportedMaterials`

### What `ThemeConfig` provides (`_config.py`)

`ThemeConfig` (on `WebsiteConfig.theme`) has:

| Field       | Type            | Purpose                                              |
| ----------- | --------------- | ---------------------------------------------------- |
| `use`       | `str`           | Theme name (entry point) or path (if contains `/`)   |
| `overrides` | `str \| None`   | Path to override directory for templates/static       |
| `config`    | `Any`           | Arbitrary config passed to theme (validated by schema)|

## How `theme` flows through `generate()`

In `_generate.py`, the `generate()` function:

1. **Resolves the theme** via `_get_theme(config, extra_themes, cwd)`:
   - If `config.theme.use` contains `/` or `\`: loads from directory path
   - Otherwise: checks `extra_themes` dict, then falls back to entry point
   - If `config.theme.overrides` is set: loads override dir and merges templates/static_files
   - Validates that `page.html` template exists

2. **Validates theme config**: `config.theme.config = _resolve_theme_config(config.theme.config, theme.schema)`

3. **Registers theme hooks** onto the `GenerateHooks` instance via `_register_theme_hooks(hooks, theme)`:
   - Wraps `ThemeHooks.pre_generate` as a `PipelineHook` registration at priority 100
   - Wraps `ThemeHooks.post_generate` as an `ObserverHook` registration at priority 100

4. **Creates Jinja environment**: `theme.create_jinja_environment()`

5. **Copies theme static files**: `_copy_theme_static_files(theme, build_directory)`

6. **Creates render context** with theme elements: `_create_render_context(..., theme, jinja_environment)` — binds `theme.elements` to the context

## Where `config.theme` is accessed

### In production code:
- `_generate.py:146` — `config.theme.use` (to determine path vs entry point)
- `_generate.py:148` — `config.theme.use` (directory path)
- `_generate.py:151-152` — `config.theme.use` (entry point lookup)
- `_generate.py:157` — `config.theme.overrides` (override directory)
- `_generate.py:717` — `config.theme.config` (validate/resolve against schema)
- `builtin/themes/default/hooks.py:29` — `config.theme.config.get("rebuild_tailwind", True)`

### In tests (heavily used):
- `test_config.py` — asserts on `config.website.theme.*` fields
- `test_generate.py` — constructs `WebsiteConfig` with `theme=ThemeConfig(...)` in ~25 places
- `test_default_theme/test_hooks.py` — mocks `config.theme.config`
- `test_default_theme/test_*.py` — constructs configs with ThemeConfig

## The `extra_themes` parameter

`generate()` accepts `extra_themes: dict[str, Theme]` which is checked before entry points. Used in tests to inject themes without installing packages.

## Design Constraint

The theme should be loaded and validated **before** calling `generate()`. This simplifies `generate()`'s concerns — it no longer does theme resolution, override merging, or config schema validation. The caller is responsible for assembling a fully-prepared `WebsiteResources` (with theme templates, static files, elements, and hooks already merged in).

## Key Observations

1. **Resources already has everything Theme has** (templates, static_files, elements) plus more (pages, materials). The only thing missing is `schema`.

2. **ThemeHooks is the old hook system**; `GenerateHooks` is the new one. The `_register_theme_hooks` adapter bridges the two by wrapping ThemeHooks callables into GenerateHooks registrations.

3. **`config.theme.config`** is theme-specific configuration (e.g., `short_title`, `rebuild_tailwind`). After removal of ThemeConfig, this would need a new home — perhaps as a `vars`-like mechanism or on the Resources instance itself.

4. **`config.theme.use`** controls which theme to load. If the theme is folded into Resources, this routing logic moves elsewhere (the caller would load the right Resources).

5. **`config.theme.overrides`** applies template/static overrides on top of a theme. This merging behavior could happen at the Resources level instead.

6. **The default theme's `hooks.py`** accesses `config.theme.config` directly to check `rebuild_tailwind`. This would need to be adapted.

7. **`generate()` already takes `resources: WebsiteResources`** — so the infrastructure for passing resources is already in place. The theme's contributions (templates, static_files, elements) could be merged into resources before `generate()` is called, or generate() could consume them directly from resources.

## What this means for `generate()`

With theme loading moved out of `generate()`, the following can be **removed** from `generate()` and `_generate.py`:

| What                        | Current location                    | Disposition                                                  |
| --------------------------- | ----------------------------------- | ------------------------------------------------------------ |
| `_get_theme()`              | `_generate.py:116-175`             | Remove entirely — caller loads the theme into Resources      |
| `_resolve_theme_config()`   | `_generate.py:83-113`              | Remove — caller validates config before calling generate()   |
| `_register_theme_hooks()`   | `_generate.py:223-258`             | Remove — hooks are already on `resources.hooks`              |
| `_copy_theme_static_files()`| `_generate.py:178-206`             | Adapt — still needed, but reads from `resources.static_files`|
| `extra_themes` param        | `generate()` signature              | Remove — no longer needed                                    |
| `theme` local variable      | throughout `generate()`             | Replace with reads from `resources.*`                        |
| `ThemeConfig` import        | `_config.py`, `__init__.py`         | Remove from WebsiteConfig; may keep class for loading logic  |
| `theme` attribute           | `WebsiteConfig.theme`              | Remove                                                       |

What `generate()` **still does** with the contents that were formerly on Theme:

1. **templates** — creates Jinja environment (`theme.create_jinja_environment()` → use `resources.templates` directly)
2. **static_files** — copies to build dir (`_copy_theme_static_files` → use `resources.static_files`)
3. **elements** — binds to render context (`_create_render_context` → use `resources.elements`)
4. **hooks** — runs pre/post generate (`resources.hooks` already has them, no adapter needed)

### The `config.theme.config` problem

The default theme's `hooks.py` accesses `config.theme.config.get("rebuild_tailwind", True)`. With `theme` removed from `WebsiteConfig`, this data needs a new home. Options:

- Move it into `vars` (the general-purpose variable bag already passed to `generate()`)
- The hook could receive the config through a different mechanism (e.g., closure or hook args)
- This is a concern for the theme loading layer, not for `generate()` itself
