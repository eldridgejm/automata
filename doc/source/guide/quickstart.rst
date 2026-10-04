Quickstart
==========

Installation
------------

Install automata from GitHub, either as a
command-line tool with uv::

    uv tool install git+https://github.com/eldridgejm/automata

or with pip::

    pip install git+https://github.com/eldridgejm/automata

.. warning::

    Don't run ``pip install automata``. The ``automata`` package on PyPI is
    an unrelated library.

.. note::

    automata requires Python 3.13 or later.


Example 1: A Simple Course
---------------------------

Chances are, you already have course materials, and you want a website for
them. Say your course's lectures are PowerPoint files:

.. code-block:: text

    my-course/
        lectures/
            01-introduction.pptx
            02-linear-regression.pptx
            03-gradient-descent.pptx

This example sets up a website that posts each lecture's slides on the day of
the lecture, without moving or changing any of these files.

**1. Initialize the project.** In the course's directory, run
``automata init``::

    $ cd my-course
    $ automata init
    Created automata.yaml
    Created website/content/index.md
    Created website/content/syllabus.md
    Created website/schedule.yaml

This adds a configuration file, ``automata.yaml``, and a ``website``
directory with a home page, a syllabus, and a schedule. Your lectures are left
as they are.

**2. Fill in the course's details.** At the top of ``automata.yaml``, replace
the placeholders:

.. code-block:: yaml

    course:
      name: "DSC 101"
      title: "Introduction to Data Science"
      term: "Fall 2026"
      first_week_start: 2026-09-21

Weeks are numbered from ``first_week_start``: here, the week of September 21 is
week 1.

**3. Describe the lectures.** Still in ``automata.yaml``, replace
``materials: {}`` with a ``lectures`` collection:

.. code-block:: yaml

    materials:
      lectures:
        schema:
          required_artifacts:
            - slides.pptx
          metadata_schema:
            required_keys:
              number: { type: integer }
              topic: { type: string }
              date: { type: date }
          is_ordered: true
        publications:
          01-introduction:
            metadata:
              number: 1
              topic: Introduction
              date: 2026-09-22
            artifacts:
              slides.pptx:
                path: lectures/01-introduction.pptx
                release_time: ${ this.metadata.date } at 08:00:00
          02-linear-regression:
            metadata:
              number: 2
              topic: Linear Regression
              date: first tuesday, thursday after ${ previous.metadata.date }
            artifacts:
              slides.pptx:
                path: lectures/02-linear-regression.pptx
                release_time: ${ this.metadata.date } at 08:00:00
          03-gradient-descent:
            metadata:
              number: 3
              topic: Gradient Descent
              date: first tuesday, thursday after ${ previous.metadata.date }
            artifacts:
              slides.pptx:
                path: lectures/03-gradient-descent.pptx
                release_time: ${ this.metadata.date } at 08:00:00

Each lecture is a *publication*: it has metadata (its number, topic, and date)
and one *artifact*, its slides. The ``schema`` says what every lecture must
have, so a lecture missing its slides or its date is an error, not a gap on the
website. Each artifact's ``path`` points to the existing file, and its
``release_time`` says when it goes online. ``this`` is the lecture itself, so
the slides go online at 8 AM on the day of the lecture.

Only the first lecture's date is written out. ``is_ordered: true`` means the
lectures come in order, so each can refer to the one before it as
``previous``: lecture 2 is on the first Tuesday or Thursday after lecture 1
(September 24), and lecture 3 the first after that (September 29). If the
first lecture moves, change its date, and the others move with it.

**4. Put the lectures on the schedule.** The home page shows the schedule,
configured in ``website/schedule.yaml``. Replace
``primary_activity_collections: []`` with:

.. code-block:: yaml

    primary_activity_collections:
      - collection: lectures
        for_each_publication:
          start_displaying_on: !template "${ publication.metadata.date }"
          title: !template "Lecture ${ publication.metadata.number }: ${ publication.metadata.topic }"
          resources:
            - type: artifact_links
              title: Slides
              icon: projector
              links:
                - text: PowerPoint
                  artifact: slides.pptx

For each lecture, this adds an entry to the week of its date, titled with its
number and topic, with a link to its slides. (``!template`` means the value is
filled in separately for each lecture.) You can also set each week's topic in
``week_topics``.

**5. See the website.** Run::

    $ automata serve

automata builds the site, opens it in your browser, and rebuilds it whenever a
file changes. Lectures whose release time hasn't come yet aren't on the site:
they appear on their own once it has. To see the site as it will be on a given
day, pass ``--current-time``::

    $ automata serve --current-time 2026-09-25T12:00:00

On September 25, the first two lectures are online, and the third isn't.

When the site looks right, ``automata publish`` puts it online (see
:doc:`deployment`). And as the course grows, adding a lecture is a matter of
adding its file and a few lines to ``automata.yaml``.


Example 2: Materials Built from Source
--------------------------------------

Now say your course has lectures and homeworks, all written in LaTeX, and each
homework has a solution:

.. code-block:: text

    my-course/
        lectures/
            01-introduction/
                slides.tex
            02-linear-regression/
                slides.tex
        homeworks/
            01/
                homework.tex
                solution.tex
            02/
                homework.tex
                solution.tex

Rather than list everything in ``automata.yaml``, you can describe each
lecture and homework in a small file next to its source: a
``publication.yaml``. Each collection of them --- the lectures, the homeworks
--- gets a ``collection.yaml``. automata finds these files on its own, and
builds each PDF from its source before releasing it, so the PDF on the website
is never out of date.

Start as in Example 1: run ``automata init``, and fill in the course's details
in ``automata.yaml``. Then add the date of the first lecture to ``vars``, so
that every other date can be defined from it:

.. code-block:: yaml

    vars:
      first_lecture: 2026-09-22

**1. Describe the collections.** ``lectures/collection.yaml`` says what every
lecture has:

.. code-block:: yaml

    publication_schema:
      required_artifacts:
        - slides.pdf
      metadata_schema:
        required_keys:
          number: { type: integer }
          topic: { type: string }
          date: { type: date }
      is_ordered: true

``is_ordered: true`` means the lectures come in order (the order of their
directories' names), so each one can refer to the one before it.

``homeworks/collection.yaml`` is similar. Each homework has two PDFs, and dates
for its release and due date:

.. code-block:: yaml

    publication_schema:
      required_artifacts:
        - homework.pdf
        - solution.pdf
      metadata_schema:
        required_keys:
          number: { type: integer }
          released: { type: datetime }
          due: { type: datetime }

**2. Describe each lecture.** ``lectures/01-introduction/publication.yaml``:

.. code-block:: yaml

    metadata:
      number: 1
      topic: Introduction
      date: ${ vars.first_lecture }

    artifacts:
      slides.pdf:
        recipe: latexmk -pdf slides.tex
        release_time: ${ this.metadata.date } at 08:00:00

The ``recipe`` is the command that builds the slides. It's run in the
lecture's directory, and should produce ``slides.pdf``. ``this`` is the lecture
itself, so the slides are released at 8 AM on the day of the lecture.

``lectures/02-linear-regression/publication.yaml`` is the same, except for its
date:

.. code-block:: yaml

    metadata:
      number: 2
      topic: Linear Regression
      date: first tuesday, thursday after ${ previous.metadata.date }

    artifacts:
      slides.pdf:
        recipe: latexmk -pdf slides.tex
        release_time: ${ this.metadata.date } at 08:00:00

Lecture 2 is on the first Tuesday or Thursday after lecture 1: Thursday,
September 24. If the first lecture moves, change ``first_lecture``, and every
lecture moves with it.

**3. Describe each homework.** ``homeworks/01/publication.yaml``:

.. code-block:: yaml

    metadata:
      number: 1
      released: ${ vars.first_lecture } at 12:00:00
      due: 7 days after ${ this.metadata.released } at 23:59:00

    artifacts:
      homework.pdf:
        recipe: latexmk -pdf homework.tex
        release_time: ${ this.metadata.released }
      solution.pdf:
        recipe: latexmk -pdf solution.tex
        release_time: 1 day after ${ this.metadata.due } at 00:00:00

The homework is released at noon on the day of the first lecture and due a
week later, and its solution is released at midnight after the due date.
``homeworks/02/publication.yaml`` is the same, but released a week later:

.. code-block:: yaml

    metadata:
      number: 2
      released: 7 days after ${ vars.first_lecture } at 12:00:00
      due: 7 days after ${ this.metadata.released } at 23:59:00

    # artifacts: as for homework 1

**4. Put them on the schedule.** In ``website/schedule.yaml``, the lectures
are the primary activities, as in Example 1, and the homeworks are secondary
ones:

.. code-block:: yaml

    primary_activity_collections:
      - collection: lectures
        for_each_publication:
          start_displaying_on: !template "${ publication.metadata.date }"
          title: !template "Lecture ${ publication.metadata.number }: ${ publication.metadata.topic }"
          resources:
            - type: artifact_links
              title: Slides
              icon: projector
              links:
                - text: PDF
                  artifact: slides.pdf

    secondary_activity_collections:
      - collection: homeworks
        for_each_publication:
          start_displaying_on: !template "${ publication.metadata.released }"
          due_datetime: !template "${ publication.metadata.due }"
          title: !template "Homework ${ publication.metadata.number }"
          resources:
            - type: artifact_links
              links:
                - text: Homework
                  artifact: homework.pdf
                - text: Solution
                  artifact: solution.pdf

Each homework shows its due date, and its solution link appears once the
solution is released.

**5. Check, and see the website.** ``automata status`` shows what's released
and what's coming, here as of October 1::

    $ automata status --current-time 2026-10-01T12:00:00
    Running as if it is currently 2026-10-01 12:00:00
    Artifacts  ● 5 released  ◷ 1 scheduled

    Next releases
      homeworks/02/solution.pdf   Wed 2026-10-07 00:00   in 5 days

Then ``automata serve`` builds the site, running each recipe, and opens it.
Only released artifacts are built: homework 2's solution isn't compiled, let
alone posted, until October 7.


Next steps
----------

- :doc:`concepts` --- understand the materials hierarchy
- :doc:`configuration` --- full configuration reference
- :doc:`materials` --- detailed guide to defining materials
- :doc:`website` --- creating pages and templates
- :doc:`schedule` --- configuring the weekly schedule
