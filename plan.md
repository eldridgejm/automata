# Plan: Modify `generate()` API to remove theme dependency

## Context

`generate()` currently loads and resolves themes internally via `config.theme`, `_get_theme()`, `_resolve_theme_config()`, etc. We want to simplify `generate()` so it no longer handles theme loading — the caller is responsible for assembling a fully-prepared `WebsiteResources` with theme templates, static files, elements, and hooks already merged in.

This change only modifies the API of `generate()` and its internal helpers. The production call site (`_build.py`) and theme configuration system will be updated separately later.

## Todo

### 1. Create a `make_resources` helper in `test_generate.py`

**File:** `test/test_website/test_generate.py`

Add a helper function (or fixture) that creates a `WebsiteResources` with a minimal toy theme. The toy template is just something like:

```python
MINIMAL_TEMPLATE = "<html><body>${ content }</body></html>"

def make_resources(tmpsite, **overrides):
    """Build a WebsiteResources with a minimal toy theme and tmpsite materials."""
    defaults = dict(
        templates={"page.html": MINIMAL_TEMPLATE},
        pages={},
        static_files={},
        elements={},
        materials=tmpsite.load_materials(),  # from SiteBuilder
        hooks=GenerateHooks(),
    )
    defaults.update(overrides)
    return WebsiteResources(**defaults)
```

This gives every test a baseline and lets individual tests override specific fields (templates, elements, hooks, etc.) as needed. `SiteBuilder.resources` is left unchanged — it continues to provide only materials.

### 2. Update the `config` fixture

**File:** `test/test_website/test_generate.py`

The `config` fixture (line 8-22) constructs `WebsiteConfig` with `theme=ThemeConfig(...)`. Remove the `theme` keyword:

```python
@fixture
def config(tmpsite):
    return automata.website.WebsiteConfig(
        content_directory=tmpsite.content_directory,
        build_directory=tmpsite.build_directory,
    )
```

### 3. Update all tests that used the `config` fixture with default theme

**File:** `test/test_website/test_generate.py`

Tests that currently call `automata.website.generate(config, tmpsite.resources)` need to instead pass resources from `make_resources(tmpsite)`. This covers the bulk of the tests: basic rendering, frontmatter, url_for, extra_content, materials, error handling, etc.

Change pattern: `tmpsite.resources` → `make_resources(tmpsite)`.

### 4. Update tests that construct custom themes via directory path

**File:** `test/test_website/test_generate.py`

These tests create a theme directory and pass it via `ThemeConfig(use=str(theme_dir))`. Instead, they put templates/static_files directly into `make_resources(tmpsite, templates={...})`.

Tests to update:
- `test_generate_can_use_custom_theme_via_directory_path` (line 407) — put custom template in resources; rename to `test_generate_uses_custom_template` (no longer about directory paths)
- `test_generate_supports_template_inheritance` (line 436) — put both templates in resources
- `test_generate_uses_frontmatter_template` (line 473) — put both templates in resources
- `test_generate_errors_for_missing_frontmatter_template` (line 507) — put only `page.html` in resources
- `test_generate_requires_base_template_in_theme` (line 532) — put a template without `page.html` in resources, verify `generate()` raises

### 5. Update or remove tests about theme overrides

**File:** `test/test_website/test_generate.py`

Theme overrides (`config.theme.overrides`) was a mechanism for merging templates/static on top of a base theme. Since `generate()` no longer handles override merging, these tests no longer test `generate()` behavior. Remove them.

Tests to remove:
- `test_generate_can_override_theme_template` (line 552)
- `test_generate_overrides_template_can_extend_builtin_template` (line 576)
- `test_generate_can_override_only_static_files` (line 614)

### 6. Update tests that formerly used `extra_themes`

**File:** `test/test_website/test_generate.py`

These tests pass `extra_themes={"name": theme}` to `generate()`. Instead, put the theme's content directly into resources via `make_resources(...)`.

Tests to update:
- `test_generate_handles_all_static_file_types` (line 660) — `make_resources(tmpsite, static_files={...})`
- `test_generate_supports_theme_elements` (line 693) — `make_resources(tmpsite, templates={...}, elements={...})`
- `test_generate_with_template_element` (line 721) — same

### 7. Remove theme config validation tests

**File:** `test/test_website/test_generate.py`

These test that `generate()` validates `config.theme.config` against a theme schema. That's no longer `generate()`'s responsibility.

Tests to remove:
- `test_generate_validates_theme_config_against_schema` (line 767)
- `test_generate_raises_on_invalid_theme_config` (line 801)
- `test_generate_skips_validation_when_schema_is_none` (line 832)
- `test_generate_updates_config_with_resolved_theme_config` (line 864)

### 8. Update theme hook tests to use `GenerateHooks` directly

**File:** `test/test_website/test_generate.py`

These tests create themes with `hooks.py` on disk and pass via `ThemeConfig(use=str(theme_dir))`. They test the old `ThemeHooks` → `GenerateHooks` adapter. Rewrite them to register hooks directly on `GenerateHooks` and pass via `make_resources(tmpsite, hooks=hooks)`.

Tests to update:
- `test_generate_executes_pre_generate_hook` (line 902)
- `test_pre_generate_hook_can_return_extra_content` (line 936)
- `test_pre_generate_extra_content_is_overridden_by_explicit_extra_content` (line 965)
- `test_generate_executes_post_generate_hook` (line 1000)
- `test_generate_executes_both_hooks_in_order` (line 1034)
- `test_generate_continues_without_hooks` (line 1073)
- `test_generate_raises_on_pre_generate_hook_error` (line 1097)
- `test_generate_raises_on_post_generate_hook_error` (line 1125)

These may overlap with the existing "hooks parameter" tests (lines 1410-1517) which already test `GenerateHooks` directly. Deduplicate as appropriate.

### 9. Update hooks parameter tests

**File:** `test/test_website/test_generate.py`

These tests pass `hooks=GenerateHooks()` as a separate parameter to `generate()`. Since the `hooks` param is being removed, put hooks on resources instead via `make_resources(tmpsite, hooks=hooks)`.

Tests to update:
- `test_generate_accepts_hooks_parameter` (line 1410)
- `test_user_pre_generate_hook_is_called` (line 1423)
- `test_user_post_generate_hook_is_called` (line 1441)
- `test_user_pre_generate_hook_can_add_extra_content` (line 1458)
- `test_pre_generate_pipeline_chains_transformations` (line 1476)
- `test_hooks_receive_correct_config` (line 1502)

### 10. Remove or rework tailwind rebuild tests

**File:** `test/test_website/test_generate.py`

These tests depend on the default theme and `config.theme.config`. Remove them from `test_generate.py` — they belong in the default theme's own test suite (`test_default_theme/`), not in the `generate()` API tests.

Tests to remove:
- `test_default_theme_tailwind_rebuild_with_npx_available` (line 1190)
- `test_default_theme_fallback_when_npx_not_available` (line 1233)

### 11. Remove `test_generate_uses_default_theme_by_default`

**File:** `test/test_website/test_generate.py`

This test (line 398) asserts that `generate()` uses the default theme. Since `generate()` no longer loads themes, this test is no longer meaningful.

### 12. Update extra_content interpolation test

**File:** `test/test_website/test_generate.py`

`test_extra_content_with_string_supports_variable_interpolation` (line 1315) renders `${ website_config.theme.config.short_title }`. Since `config.theme` is removed, change the interpolation target to a different `WebsiteConfig` attribute (e.g., `${ website_config.base_path }`).

### 13. Do NOT modify default theme element tests or builtin elements tests

These files will fail after `ThemeConfig` is removed, but we intentionally leave them unmodified for now. They will be updated separately when we handle the default theme's integration with the new resources system.

**Files left as-is (expected to fail):**
- `test/test_website/test_default_theme/test_listing.py`
- `test/test_website/test_default_theme/test_schedule.py`
- `test/test_website/test_default_theme/test_people.py`
- `test/test_website/test_default_theme/test_date_pill.py`
- `test/test_website/test_builtin_elements/test_builtin_schedule.py`

### 15. Update `test/test_config.py`

**File:** `test/test_config.py`

Remove assertions on `config.website.theme.*`. Since `WebsiteConfig` will no longer have a `theme` attribute, lines asserting on it need to be removed. The YAML files in these tests still have `theme:` keys — the config parser may need to tolerate unknown keys, or the YAML content may need updating.

Tests to update:
- `test_read_config_reads_valid_config` — remove lines 41-42
- `test_read_config_applies_defaults` — remove lines 64-66
- `test_read_config_with_complex_theme_config` — remove lines 171-174 (or remove entire test)
- `test_read_config_performs_variable_interpolation` — remove lines 204-208
- `test_read_config_with_include` — remove line 247

### 16. Remove `ThemeConfig` from `WebsiteConfig`

**File:** `src/automata/website/_config.py`

Delete the `ThemeConfig` class and remove `theme: ThemeConfig = ThemeConfig()` from `WebsiteConfig`.

### 17. Update `__init__.py` exports

**File:** `src/automata/website/__init__.py`

Remove `ThemeConfig` from the import and `__all__`.

### 18. Simplify `generate()` signature

**File:** `src/automata/website/_generate.py`

Remove parameters:
- `extra_themes: dict[str, Theme] | None = None`
- `hooks: GenerateHooks | None = None`

### 19. Remove theme helper functions from `_generate.py`

**File:** `src/automata/website/_generate.py`

Delete:
- `_get_theme()` (lines 116-175)
- `_resolve_theme_config()` (lines 83-113)
- `_register_theme_hooks()` (lines 223-258)

### 20. Adapt remaining helper functions

**File:** `src/automata/website/_generate.py`

- `_copy_theme_static_files(theme, build_dir)` → `_copy_static_files(static_files, build_dir)` taking the dict directly
- `_create_render_context(...)` → remove `theme` and `jinja_environment` params, take `elements` dict directly

### 21. Rewrite `generate()` body

**File:** `src/automata/website/_generate.py`

Replace theme loading block with reads from `resources.*`:
- `hooks = resources.hooks` (instead of `hooks or GenerateHooks()`)
- Create Jinja env from `resources.templates` (instead of `theme.create_jinja_environment()`)
- Validate `page.html` exists in `resources.templates`
- Copy `resources.static_files` to build dir (instead of `_copy_theme_static_files(theme, ...)`)
- Bind `resources.elements` in render context (instead of `theme.elements`)
- Remove `_register_theme_hooks` call
- Remove `_resolve_theme_config` call

### 22. Remove Theme import from `_generate.py`

**File:** `src/automata/website/_generate.py`

Remove `from ._theme import Theme`. Also remove unused imports (`smartconfig`, `smartconfig.exceptions`, `smartconfig.types`) if they were only needed for theme config validation.

### 23. Update `generate()` docstring

**File:** `src/automata/website/_generate.py`

Remove the "Themes" and "Theme Overrides" sections. Update `Parameters` to reflect removed params. Update the description of `resources` to note it should include templates, static files, elements, and hooks.

### 24. Run tests and fix

Run `python -m pytest test/test_website/test_generate.py test/test_config.py` and iterate on any failures.
