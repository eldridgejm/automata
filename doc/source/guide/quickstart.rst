Quickstart
==========

Installation
------------

Install automata from `GitHub <https://github.com/eldridgejm/automata>`_,
either as a command-line tool with uv::

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

.. tip::

    The finished example is in the automata repository, in
    `examples/simple-course
    <https://github.com/eldridgejm/automata/tree/main/examples/simple-course>`_.

Let's say you already have some course materials and you'd like to use automata
to turn them into a course webpage. In the simplest case your materials are
just files, like PowerPoint slides, that don't need to be built from source.

For example, say your course's lectures are PowerPoint files in the following
directory structure:

.. code-block:: text

    my-course/
        lectures/
            01-introduction.pptx
            02-linear-regression.pptx
            03-gradient-descent.pptx

Let's set up a website that posts each lecture's slides on the day of the
lecture, without moving or changing any of these files.

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
as they are. Notice that the pages are all `Markdown
<https://commonmark.org>`_ files -- automata
will convert them to HTML for the website.

**2. Fill in the course's details.** At the top of ``automata.yaml``, replace
the placeholders:

.. literalinclude:: ../../../examples/simple-course/automata.yaml
   :language: yaml
   :caption: automata.yaml
   :start-at: course:
   :end-before: # values defined once


These details will be used throughout the site, as we'll see when we edit the
syllabus in a later step.


**3. Describe the lectures.** Still in ``automata.yaml``, replace
``materials: {}`` with a ``lectures`` collection like so:

.. literalinclude:: ../../../examples/simple-course/automata.yaml
   :language: yaml
   :caption: automata.yaml
   :start-at: materials:
   :end-before: website:

The ``schema`` entry says what every lecture must have: a number, a topic, a
date, and slides. Schemas help ensure that all of your materials are described
consistently, and that that you don't forget to include important information.
You can read more about defining schemas in :ref:`the materials guide
<publication-schemas>`.

After the schema, we have described each of our three lectures. In the parlance
of automata, each lecture is a *publication*. It has metadata (its number,
topic, and date) and *artifacts* (in this case, just one: the PowerPoint
file). Each artifact's ``path`` points to the existing file, and its
``release_time`` says when it goes online.

In this simple example, we already see one of the most powerful features of automata: the
ability to define values relative to other values in the configuration. For example,
each lecture's slides are released at
``${ this.metadata.date } at 08:00:00``: ``this`` is the lecture itself, so the
slides go online at 8 AM on the day of the lecture, whatever that day is. And
because the collection is ordered (``is_ordered: true``), each lecture can refer
to the one before it as ``previous``. Only the first lecture's number and date
are written out: every other lecture's number is
``${ previous.metadata.number + 1 }``, and its date is the
``first tuesday, thursday after ${ previous.metadata.date }`` --- September 24
for lecture 2, and September 29 for lecture 3. So if the first lecture moves to
a different day, you change one date, and every lecture after it moves too, its
slides' release time along with it. And if you add a lecture in the middle, the
lectures after it are renumbered and rescheduled on their own.

**4. Put the lectures on the schedule.** By default, the front page
of the website shows the *schedule*. The schedule is configured in
``automata.yaml`` under the ``website.elements.schedule`` key, but you'll see that in
this example we have written an *include*:

.. literalinclude:: ../../../examples/simple-course/automata.yaml
   :language: yaml
   :caption: automata.yaml
   :start-at: website:
   :end-before: # where `automata publish` deploys

The schedule's configuration is ``website.elements.schedule``, and
``!include`` says to read it from another file: ``website/schedule.yaml``,
relative to ``automata.yaml``. It's as if that file's contents were written
here. ``!include`` works anywhere in the configuration, and keeps
``automata.yaml`` short.

Now let's look at the ``website/schedule.yaml``. In this file, the
``primary_activity_collections`` key lists the materials that are the main
activities of the course. In this example, the lectures are the primary
activities, so we replace ``primary_activity_collections: []`` with:

.. literalinclude:: ../../../examples/simple-course/website/schedule.yaml
   :language: yaml
   :caption: website/schedule.yaml
   :start-at: primary_activity_collections:
   :end-before: secondary_activity_collections:

For each lecture, this adds an entry to the week of its date, titled with its
number and topic, with a link to its slides. You can also set each week's topic
in ``week_topics``.

Notice the ``!template`` before some of the values. Normally, a ``${ ... }`` in
the configuration is filled in when the file is read. But
``${ publication.metadata.date }`` can't be: there are three lectures, and it
should be a different date for each. ``!template`` says to leave the value as it
is when the file is read, and fill it in later, by whatever uses it. Here, that's
the schedule: under ``for_each_publication``, it fills in each template once
for every lecture, with ``publication`` being that lecture. So lecture 2's entry
is titled "Lecture 2: Linear Regression", and is shown starting on its date.

If you leave out a ``!template``, automata reports that ``publication`` is
undefined, and suggests adding it. (The materials don't need ``!template`` for
``this`` and ``previous``: automata fills those in for each publication
itself.)

**5. Edit the syllabus.** ``automata init`` created two pages in
``website/content``: ``index.md``, the home page, which shows the schedule, and
``syllabus.md``. Replace the syllabus's placeholder text with your own:

.. literalinclude:: ../../../examples/simple-course/website/content/syllabus.md
   :language: markdown
   :caption: website/content/syllabus.md

You may notice the ``${ ... }`` syntax in the syllabus. That's
*interpolation*: when the page is built, automata replaces each ``${ ... }``
with the value of the expression inside it. ``${ course.name }`` becomes "DSC
101", ``${ course.title }`` becomes "Introduction to Data Science", and so on,
all filled in from ``automata.yaml``. So the syllabus always agrees with the
course's details: change the term in ``automata.yaml``, and every page that
shows it changes too. An expression can also call a function:
``url_for("index.html")`` gives a link to the home page that works wherever the
site is published.

It's the same interpolation you've seen in the configuration, as in
``${ previous.metadata.date }``, and it works everywhere: in ``automata.yaml``,
in the materials, and in every page. See :ref:`interpolation` for more,
including ``{% ... %}`` for conditions and loops.

.. admonition:: How interpolation works
   :class: note

   Technically speaking, when automata encounters ``${ ... }``, it evaluates
   the expression inside it, and replaces the ``${ ... }`` with the result. The
   expression is a `Jinja <https://jinja.palletsprojects.com>`_ expression, so
   it can do more than name a value: it can do arithmetic
   (``${ previous.metadata.number + 1 }``), call functions
   (``${ url_for("index.html") }``), and apply filters
   (``${ course.title | upper }``).
   After the value is calculated, it is converted to the field's expected type as
   specified in the schema.

   For more details about interpolation, see :ref:`interpolation`.


Each file in ``website/content`` becomes a page of the website:
``syllabus.md`` becomes ``syllabus.html``, which the navigation
(``website.theme.config.navigation``, above) links to. To add a page, add a
Markdown file, and a link to it in the navigation. See :doc:`website` for more.

**6. See the website.** Run::

    $ automata serve

automata builds the site, opens it in your browser, and rebuilds it whenever a
file changes. Lectures whose release time hasn't come yet aren't on the site:
they appear on their own once it has.

.. _quickstart-publish:

**7. Publish the website.** So far, the website is only on your computer. To
put it online, tell automata where to publish it, under ``publish`` in
``automata.yaml``. Here, we'll use `GitHub Pages <https://pages.github.com>`_,
which hosts websites from a GitHub repository for free.

First, the course needs a git repository with a remote on GitHub. Create an
empty repository on GitHub, then, in the course's directory::

    $ git init
    $ git remote add origin git@github.com:your-name/dsc101.git

Then add a publish target to ``automata.yaml``:

.. literalinclude:: ../../../examples/simple-course/automata.yaml
   :language: yaml
   :caption: automata.yaml
   :start-at: publish:

and publish::

    $ automata publish

automata builds the site and pushes it to the ``gh-pages`` branch of the
repository on GitHub, replacing whatever was there. Your course's own files
aren't pushed: only the built website is. The first time, turn GitHub Pages on
in the repository's settings (*Settings*, then *Pages*), deploying from the
``gh-pages`` branch. The site will be at
``https://your-name.github.io/dsc101/``.

.. note::

    On a free GitHub account, GitHub Pages needs a public repository, so
    anything you push to it is public. ``automata publish`` only pushes the
    built website, which has only released materials, but if you also push
    your course's files (say, to back them up), push them to a separate,
    private repository. Or publish the website to its own repository: add it as
    another remote, say ``git remote add website ...``, and set ``remote:
    website``.

The website is a set of static files, so a lecture whose release time has
passed appears only when the site is next published. Run ``automata publish``
after each release, or have GitHub Actions run it on a schedule, as described
in :doc:`deployment`.

Not using GitHub? If you have a web server you can reach over SSH, automata
can copy the website to it with ``rsync`` instead:

.. code-block:: yaml

    publish:
      server:
        strategy: rsync
        config:
          host: example.ucsd.edu
          remote_path: /var/www/dsc101

``automata publish`` publishes to every target listed, and ``automata publish
server`` to just one. See :doc:`deployment` for all of the options.


Example 2: Materials Built from Source
--------------------------------------

.. tip::

    The finished example is in the automata repository, in
    `examples/latex-course
    <https://github.com/eldridgejm/automata/tree/main/examples/latex-course>`_.

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

You could list all of these in ``automata.yaml``, as in Example 1, but with
more than a few lectures and homeworks, that quickly becomes cluttered.
Instead, you can describe each lecture and homework in a small file next to its
source: a ``publication.yaml``. Each collection of them --- the lectures, the
homeworks --- gets a ``collection.yaml``. automata finds these files on its
own, and builds each PDF from its source before releasing it, so the PDF on the
website is never out of date.

Start as in Example 1: run ``automata init``, and fill in the course's details
in ``automata.yaml``. Then add the date of the first lecture to ``vars``, so
that every other date can be defined from it:

.. literalinclude:: ../../../examples/latex-course/automata.yaml
   :language: yaml
   :caption: automata.yaml
   :start-at: vars:
   :end-before: # your materials

**1. Describe the collections.** In automata, publications are organized into
*collections*. In the previous example, there was just one collection
(lectures), but here we have two: lectures and homeworks. Each collection has a
``collection.yaml`` that describes the publications in it. Its location in the
filesystem is important: when automata finds a ``collection.yaml`` in a
directory, any publication in that directory or its subdirectories is assumed
to be part of that collection.

Each collection file specifies the schema for its publications, and any other
properties that apply to the entire collection. For example,
``lectures/collection.yaml`` says what every lecture has:

.. literalinclude:: ../../../examples/latex-course/lectures/collection.yaml
   :language: yaml
   :caption: lectures/collection.yaml

We can specify any number of artifacts with whatever names we like. Likewise,
we can require that each lecture have whatever metadata we want. In this
example, each lecture has a number, a topic, and a date. ``is_ordered: true``
says that the lectures are an ordered collection. This allows us to sensibly refer
to the "previous" lecture later on when annotating each lecture's publication.

``homeworks/collection.yaml`` is similar. Each homework has two PDFs, and dates
for its release and due date:

.. literalinclude:: ../../../examples/latex-course/homeworks/collection.yaml
   :language: yaml
   :caption: homeworks/collection.yaml

**2. Describe each lecture.** We next need to describe each lecture in a way
that automata understands. We will do this by creating a ``publication.yaml``
for each lecture, starting with ``lectures/01-introduction/publication.yaml``:

.. literalinclude:: ../../../examples/latex-course/lectures/01-introduction/publication.yaml
   :language: yaml
   :caption: lectures/01-introduction/publication.yaml

Any ``publication.yaml`` will have these two top-level keys: ``metadata`` and
``artifacts``. Notice that their structure matches the schema in
``lectures/collection.yaml``.

Notice that the ``date`` field under metadata expects a date according to the
schema, but we haven't written a literal date; instead, we've written ``${
vars.first_lecture }``. Here, ``vars`` refers to the ``vars`` section of
``automata.yaml``, and ``first_lecture`` is the date we set there. This means
that if we change the date of the first lecture in ``automata.yaml``, the change
will automatically be reflected in the lecture's metadata.

The ``recipe`` is the command that builds the slides. It's run in the
lecture's directory, and should produce ``slides.pdf``. ``this`` is the lecture
itself, so the slides are released at 8 AM on the day of the lecture.

``lectures/02-linear-regression/publication.yaml`` is the same, except for its
number and date:

.. literalinclude:: ../../../examples/latex-course/lectures/02-linear-regression/publication.yaml
   :language: yaml
   :caption: lectures/02-linear-regression/publication.yaml

When publications are part of an ordered collection, they can refer to the
previous one as ``previous``. In the publication shown above, the number is one
more than lecture 1's, and it's on the first Tuesday or Thursday after lecture
1, which resolves to Thursday, September 24. If the first lecture moves, change
``first_lecture``, and every lecture moves with it.

**3. Describe each homework.** ``homeworks/01/publication.yaml``:

.. literalinclude:: ../../../examples/latex-course/homeworks/01/publication.yaml
   :language: yaml
   :caption: homeworks/01/publication.yaml

The homework is released at noon on the day of the first lecture and due a
week later, and its solution is released at midnight after the due date.
Homework 2 is the same, but released a week later; its artifacts are the same
as homework 1's:

.. literalinclude:: ../../../examples/latex-course/homeworks/02/publication.yaml
   :language: yaml
   :caption: homeworks/02/publication.yaml
   :end-before: artifacts:

**4. Put them on the schedule.** In ``website/schedule.yaml``, the lectures
are the primary activities, as in Example 1, and the homeworks are secondary
ones:

.. literalinclude:: ../../../examples/latex-course/website/schedule.yaml
   :language: yaml
   :caption: website/schedule.yaml
   :start-at: primary_activity_collections:
   :end-before: # one-off events

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

**6. Publish the website.** This works just as in :ref:`Example 1
<quickstart-publish>`: add a publish target to ``automata.yaml``,

.. literalinclude:: ../../../examples/latex-course/automata.yaml
   :language: yaml
   :caption: automata.yaml
   :start-at: publish:

and run ``automata publish``. Publishing builds the site first, so it runs the
recipes: each released PDF is compiled from its latest source before it's
pushed. So the machine you publish from needs LaTeX installed --- including
GitHub Actions, if it publishes on a schedule (see :doc:`deployment`).


Next steps
----------

The above should hopefully be enough to get you started. For more details, see the following:

- :doc:`concepts` --- understand the materials hierarchy
- :doc:`configuration` --- full configuration reference
- :doc:`materials` --- detailed guide to defining materials
- :doc:`website` --- creating pages and templates
- :doc:`schedule` --- configuring the weekly schedule
