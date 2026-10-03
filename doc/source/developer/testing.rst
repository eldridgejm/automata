Testing
=======

Test organization
-----------------

Tests are in the ``test/`` directory, mirroring the source structure:

.. code-block:: text

    test/
    ├── conftest.py                # Shared fixtures (CourseBuilder, etc.)
    ├── test_automata.py           # Automata class API tests
    ├── test_config.py             # Configuration loading tests
    ├── test_extension.py          # Extension + apply_extension tests
    ├── test_inline_materials.py   # Inline materials tests
    ├── test_integration.py        # End-to-end integration tests
    │
    ├── test_materials/            # Materials pipeline tests
    │   ├── test_build.py
    │   ├── test_discover.py
    │   ├── test_export.py
    │   ├── test_filter.py
    │   └── ...
    │
    ├── test_website/              # Website generation tests
    │   ├── conftest.py            # SiteBuilder fixture
    │   ├── test_render.py         # Core rendering tests
    │   ├── test_theme.py          # Extension loading from directories
    │   ├── test_elements.py       # Element base class tests
    │   │
    │   ├── test_default_theme/    # Default theme element tests
    │   │   ├── conftest.py
    │   │   ├── test_schedule.py
    │   │   ├── test_listing.py
    │   │   ├── test_people.py
    │   │   └── ...
    │   │
    │   └── test_builtin_elements/ # Builtin element unit tests
    │
    └── test_util/                 # Utility function tests


Running tests
-------------

::

    # All unit tests (excludes integration)
    uv run pytest

    # Integration tests only
    uv run pytest -m integration

    # Both
    uv run pytest -m "" test/

    # Specific file
    uv run pytest test/test_automata.py

    # With coverage
    uv run pytest --cov=automata --cov-report=term-missing


Key fixtures
------------

``CourseBuilder`` (``conftest.py``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Utility for creating temporary course projects with collections and
publications:

.. code-block:: python

    def test_something(temporary_course):
        temporary_course.create_collection("homeworks", """
            publication_schema:
                required_artifacts: [homework.pdf]
        """)
        temporary_course.create_publication("homeworks", "hw01", """
            metadata:
                name: Homework 1
            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
        """)

``SiteBuilder`` (``test/test_website/utils/sitebuilder.py``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Utility for creating temporary website projects:

.. code-block:: python

    def test_something(tmpsite):
        tmpsite.make_page("index.md", "# Home")
        # ... call render() ...
        output = tmpsite.get_output("index.html")
        assert "Home" in output


Integration tests
-----------------

Integration tests (marked with ``@pytest.mark.integration``) run real
programs or the full pipeline: the example project built end-to-end, and the
gh-pages publish strategy run with real ``git`` against a local bare
repository. A test that needs a tool that may not be installed (such as the
Tailwind rebuild, which needs ``npm``, and installs Tailwind from the npm
registry) is also skipped when the tool is missing.

These tests are slower and are excluded from the default test run. Run them
explicitly with ``-m integration`` (``make checks`` runs both).


Fakes, not patching
-------------------

Tests do not patch code with ``mock.patch`` or ``monkeypatch.setattr``. Code
that calls an external program or service takes the dependency as a parameter
whose default is the real thing, and tests pass a fake:

.. code-block:: python

    def publish(build_directory, config, project_directory, *, run=subprocess.run):
        ...

    def test_rsync_mirrors_the_build(tmp_path):
        commands = []
        publish(..., run=lambda cmd, **kw: commands.append(cmd))
        assert commands == [["rsync", ...]]

Examples: ``materials.build(run=..., exists=...)``, the rsync strategy's
``run``, and the default theme's ``make_extension(config, *, run=...)``.

Using the real filesystem is fine (``tmp_path``), as is setting up the process
environment with ``monkeypatch.chdir`` or ``monkeypatch.setenv``. Check log
messages with pytest's ``caplog`` rather than by replacing a logger.


Writing tests for extensions
----------------------------

To test an extension's ``on_render_collect`` hook:

.. code-block:: python

    from automata.extensions import Extension, apply_extension
    from automata.hooks import RenderHooks, WebsiteInputs

    def test_my_extension():
        ext = Extension(
            name="test",
            hooks={"on_render_collect": my_collect_fn},
        )
        hooks = RenderHooks()
        apply_extension(ext, hooks)

        inputs = hooks.on_render_collect(WebsiteInputs())
        assert "page.html" in inputs.templates

To test website generation with a custom theme:

.. code-block:: python

    def test_with_custom_theme(tmpsite):
        theme = extension_from_directory("test", theme_dir)
        pages, static_content = tmpsite.load_content()

        automata.website.render(
            tmpsite.build_directory,
            tmpsite.materials_directory,
            pages=pages,
            static_content=static_content,
            theme=theme,
        )
        assert "expected content" in tmpsite.get_output("index.html")

When ``hooks`` is omitted, ``render`` creates them and registers the theme
and extensions itself.
