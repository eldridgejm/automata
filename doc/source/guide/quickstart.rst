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

    course:
      name: "DSC 80"
      title: "The Practice and Application of Data Science"
      term: "Spring 2026"
      first_week_start: 2026-03-30

    website:
      theme: default
      content_directory: content
      build_directory: _build

The ``course`` section is required: the site's titles come from it, and weeks
(in the schedule and ``automata calendar``) are numbered from
``first_week_start``.

And ``content/index.md``:

.. code-block:: markdown

    # Welcome to My Course

    This is the course homepage.


Building the site
-----------------

Run ``automata build`` from the project directory::

    cd my-course
    automata build

This discovers materials, builds them (running any recipes), exports them, and
renders the website in ``_build/``. Open ``_build/index.html`` in a browser to see the result.


Using the course and variables
------------------------------

The course's details are available everywhere as ``course``, and you can
define other values once in ``vars`` and use them throughout the site:

.. code-block:: yaml

    vars:
      office_hours: "Wednesdays, 2-4 PM"
      campuswire: https://campuswire.com/c/G123/feed

Then in your pages:

.. code-block:: markdown

    # ${ course.name }

    Welcome to **${ course.title }**, ${ course.term }.

    Office hours are ${ vars.office_hours }.


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
                release_time: 3 days after ${ vars.midterm_date } at 00:00:00

For materials that need build recipes (e.g., compiling LaTeX), use
:doc:`filesystem materials <materials>`.


Next steps
----------

- :doc:`concepts` --- understand the materials hierarchy
- :doc:`configuration` --- full configuration reference
- :doc:`materials` --- detailed guide to defining materials
- :doc:`website` --- creating pages and templates
- :doc:`schedule` --- configuring the weekly schedule
