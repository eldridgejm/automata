<picture>
  <source media="(prefers-color-scheme: dark)" srcset="branding/automata-lockup-dark.svg">
  <img alt="automata" src="branding/automata-lockup.svg" width="320">
</picture>

Automatically generate course webpages from annotated materials.

## Installation

```bash
uv sync --all-extras
```

## Development

```bash
# Run all checks (lint, typecheck, test, coverage)
make checks

# Or run individual checks:
make lint       # Run ruff linter
make typecheck  # Run mypy type checker
make test       # Run pytest
make coverage   # Run pytest with coverage report
```

## Usage

See the documentation in `doc/` for detailed usage instructions.
