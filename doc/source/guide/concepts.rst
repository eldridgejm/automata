Core Concepts
=============

Before diving into the details of automata, it's helpful to understand its core
concepts.

The materials hierarchy
-----------------------

automata organizes your course materials into a three-level hierarchy consisting
of **artifacts**, **publications**, and **collections**.

**Artifacts** are individual files distributed to students: for example, a
homework PDF, a solution PDF, a starter code zipfile, etc.

**Publications** are coherent groupings of artifacts with metadata. For
example, "Homework 01" is a publication containing a homework PDF and a solution
PDF, with metadata like the due date and the topic.

**Collections** are groups of related publications. In a typical course,
"Homeworks," "Lectures," and "Exams" might be collections. You can create as many
collections with whatever names you like.

The **Universe** is the name automata gives to the top-level container holding
all collections.


The build pipeline
------------------

When you run ``automata build``, these steps happen in sequence:

0. **Clean.** The build directory is emptied (keeping entries such as
   ``.git``), so it holds only what this build produces.

1. **Discover.** automata finds all materials --- both from the filesystem
   (``collection.yaml`` / ``publication.yaml`` files) and from inline
   definitions in ``automata.yaml``.

2. **Build materials.** For filesystem materials with recipes, automata runs
   the shell commands to produce artifact files. Artifacts with future release
   times or ``ready: false`` are filtered out.

3. **Export.** The resulting artifacts are copied to the build directory and a
   ``materials.json`` manifest is written.

4. **Render website.** The website is rendered using the content directory,
   the exported materials, the theme templates, and any extensions.

.. _interpolation:

Variable interpolation
----------------------

automata uses a Jinja2-based interpolation system. Variables defined in the
``vars`` section of ``automata.yaml`` are available everywhere:

- In ``automata.yaml`` itself (including materials definitions)
- In ``collection.yaml`` and ``publication.yaml`` files
- In website pages (Markdown and HTML)

The template syntax uses ``${ ... }`` for variable substitution and
``{% ... %}`` for control flow:

.. code-block:: markdown

    # ${ vars.course_name }

    {% if vars.term == "Spring 2026" %}
    Office hours are on Tuesdays.
    {% endif %}

In configuration files (``automata.yaml``, ``collection.yaml``,
``publication.yaml``, and page frontmatter), a ``${ ... }`` inserts a single
value: a string, a number, a date, and so on. **Inserting a whole mapping or
list is an error**, since its text would be meaningless. Insert one of its keys
or elements instead, turn it into text with a filter, or, to copy the whole
value, write it with ``!splice``:

.. code-block:: yaml

    vars:
      course: {name: DSC 40B, topics: [Sorting, Graphs]}
      title: ${ vars.course }                      # error: a mapping
      name: ${ vars.course.name }                  # "DSC 40B"
      first_topic: ${ vars.course.topics[0] }      # "Sorting"
      topics: ${ vars.course.topics | join(", ") } # "Sorting, Graphs"
      copy: !splice vars.course                    # the whole mapping

A template (see :doc:`materials`) is used with ``!use`` instead. Error
messages call these by their function names, ``__splice__`` and ``__use__``.
