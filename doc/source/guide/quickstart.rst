Quickstart
==========

Installation
------------

Install automata with pip (or uv)::

    pip install automata

.. note::

    automata requires Python 3.14 or later.


Creating a project
------------------

An automata project is a directory containing an ``automata.yaml`` file. Here is
the simplest possible project:

.. code-block:: text

    my-course/
        automata.yaml
        content/
            index.md

The configuration file:

.. code-block:: yaml

    extensions:
      - default

    website:
      content_directory: content
      build_directory: _build

And ``content/index.md``:

.. code-block:: markdown

    # Welcome to My Course

    This is the course homepage.


Building the site
-----------------

Run ``automata generate`` from the project directory::

    cd my-course
    automata generate

This discovers materials, builds them, exports them, and generates the website
in ``_build/``. Open ``_build/index.html`` in a browser to see the result.


Adding variables
----------------

Variables let you define values once and reference them throughout the site:

.. code-block:: yaml

    vars:
      course_name: "DSC 80"
      course_title: "The Practice and Application of Data Science"
      term: "Spring 2026"

    extensions:
      - use: default
        config:
          short_title: ${ vars.course_name }
          long_title: ${ vars.course_title }

    website:
      content_directory: content
      build_directory: _build

Then in your pages:

.. code-block:: markdown

    # ${ vars.course_name }

    Welcome to **${ vars.course_title }**, ${ vars.term }.


Adding materials
----------------

For simple materials (no build recipes needed), define them inline:

.. code-block:: yaml

    vars:
      midterm_date: 2026-04-15

    materials:
      exams:
        schema:
          required_artifacts: [exam.pdf]
          optional_artifacts: [solution.pdf]
        publications:
          midterm:
            metadata:
              name: "Midterm Exam"
              date: ${ vars.midterm_date }
            artifacts:
              exam.pdf:
                path: exams/midterm/exam.pdf
                release_time:
                  __datetime.offset__:
                    after: ${ vars.midterm_date }
                    by: "3 days"

For materials that need build recipes (e.g., compiling LaTeX), use
:doc:`filesystem materials <materials>`.


Next steps
----------

- :doc:`concepts` --- understand the materials hierarchy
- :doc:`configuration` --- full configuration reference
- :doc:`materials` --- detailed guide to defining materials
- :doc:`website` --- creating pages and templates
- :doc:`schedule` --- configuring the weekly schedule
