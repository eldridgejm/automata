Development Setup
=================

Prerequisites
-------------

- Python 3.14+
- `uv <https://docs.astral.sh/uv/>`_ (recommended) or pip
- Node.js (optional, for Tailwind CSS rebuilds in the default theme)


Getting started
---------------

Clone the repository and install in development mode::

    git clone https://github.com/eldridgejm/automata.git
    cd automata
    uv sync --all-extras

This installs all dependencies including dev tools (pytest, ruff, mypy).


Running checks
--------------

::

    # Run the test suite (excludes integration tests)
    uv run pytest

    # Run integration tests too
    uv run pytest -m integration

    # Lint
    uv run ruff check src/ test/

    # Type check
    uv run mypy src/

    # Test coverage
    uv run pytest --cov=automata --cov-report=term-missing


Building the docs
-----------------

::

    cd doc
    make html

Open ``doc/build/html/index.html`` in a browser.
