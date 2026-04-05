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
    │   ├── test_generate.py       # Core generation tests
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
        # ... call generate() ...
        output = tmpsite.get_output("index.html")
        assert "Home" in output


Integration tests
-----------------

Integration tests (marked with ``@pytest.mark.integration``) run the full
pipeline against the example project. They verify that:

1. The example project builds end-to-end.
2. Materials are discovered, built, and exported correctly.
3. The website is generated with the correct content.

These tests are slower and are excluded from the default test run. Run them
explicitly with ``-m integration``.


Writing tests for extensions
----------------------------

To test an extension's ``on_website_collect`` hook:

.. code-block:: python

    from automata._extension import Extension, apply_extension
    from automata.hooks import GenerateHooks, WebsiteInputs

    def test_my_extension():
        ext = Extension(
            name="test",
            hooks={"on_website_collect": my_collect_fn},
        )
        hooks = GenerateHooks()
        apply_extension(ext, hooks)

        inputs = hooks.on_website_collect(WebsiteInputs())
        assert "page.html" in inputs.templates

To test website generation with a custom theme:

.. code-block:: python

    def test_with_custom_theme(tmpsite):
        config = automata.website.WebsiteConfig(
            content_directory=tmpsite.content_directory,
            build_directory=tmpsite.build_directory,
        )

        hooks = GenerateHooks()
        ext = extension_from_directory("test", theme_dir)
        apply_extension(ext, hooks)

        automata.website.generate(config, tmpsite.materials_directory, hooks=hooks)
        assert "expected content" in tmpsite.get_output("index.html")
