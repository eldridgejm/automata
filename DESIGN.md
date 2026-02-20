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
