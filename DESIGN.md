# Designing an Extensions System: Components

This document outlines the design of an extensions system for automata, enabling users to customize and extend functionality through modular components. The system supports both filesystem-based extensions and Python package extensions.

## "Components"

There are (currently) five different "components" that extensions can provide:

- **Templates**: Jinja2 templates for website generation.
- **Pages**: Markdown or HTML representing website pages, which will be rendered.
- **Static files**: Any static files (e.g. CSS, JS, images) to be copied to the output directory directly.
- **Elements**: Python classes representing page elements, which can be used in templates.
- **Hooks**: Python functions that can be registered to hook points.

The first four are the "website components", which are loaded and passed to the website generator.

## Bundles

A **bundle** is the data container for a set of components. A **builtin bundle** is a bundle provided by automata itself (e.g., the default theme). An **extension** is a bundle provided externally.

The first four components are grouped into a `WebsiteBundle`:

```python
@dataclass
class WebsiteBundle:
    templates: dict[str, str] = field(default_factory=dict)
    pages: dict[str, str | bytes | Traversable] = field(default_factory=dict)
    static_files: dict[str, str | bytes | Traversable] = field(default_factory=dict)
    elements: dict[str, type[Element]] = field(default_factory=dict)
```

A `Bundle` extends `WebsiteBundle` with hooks:

```python
@dataclass
class Bundle(WebsiteBundle):
    hooks: ThemeHooks = field(default_factory=ThemeHooks)
```

Multiple bundles can be composed. Templates, pages, static files, and elements merge with last-bundle-wins semantics on key conflicts. Hooks are additive — all registered hooks run, ordered by priority.
