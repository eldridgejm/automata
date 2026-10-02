Defining Materials
==================

Materials can be defined in two ways: **inline** in ``automata.yaml`` for
simple cases, or on the **filesystem** using ``collection.yaml`` and
``publication.yaml`` files for more complex needs (build recipes, relative
references between publications, templates).


Inline materials
----------------

Define materials directly in ``automata.yaml`` under the ``materials`` key.
Each top-level key is a collection name:

.. code-block:: yaml

    materials:
      exams:
        schema:
          required_artifacts: [exam.pdf]
          optional_artifacts: [solution.pdf]
          metadata_schema:
            required_keys:
              name: { type: string }
              date: { type: date }
          is_ordered: true
        publications:
          midterm:
            metadata:
              name: "Midterm Exam"
              date: ${ vars.midterm_date }
            artifacts:
              exam.pdf:
                path: exams/midterm/exam.pdf
              solution.pdf:
                path: exams/midterm/solution.pdf
                release_time: 3 days after ${ vars.midterm_date }

**Inline materials cannot have recipes.** If you need to run a build command to
produce an artifact (e.g., compiling LaTeX), use filesystem materials instead.

**Inline materials do not support** ``previous`` **references.** The
``${ previous.metadata.date }`` pattern (referencing the previous publication
in an ordered collection) is only available in filesystem materials.

Each artifact requires at least a ``path`` (relative to the project root).
Optional fields:

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Field
     - Default
     - Description
   * - ``path``
     - *(required)*
     - Path to the artifact file, relative to the project root.
   * - ``release_time``
     - ``null``
     - When the artifact becomes visible. Before this time, it is excluded
       from built materials.
   * - ``ready``
     - ``true``
     - If ``false``, the artifact is excluded from built materials regardless
       of release time.
   * - ``missing_ok``
     - ``false``
     - If ``true``, no error is raised when the file doesn't exist.


Filesystem materials
--------------------

For more complex materials, define them on the filesystem. automata discovers
materials by walking the project directory looking for ``collection.yaml`` and
``publication.yaml`` files.

Directory structure
^^^^^^^^^^^^^^^^^^^

.. code-block:: text

    my-course/
        automata.yaml
        homeworks/
            collection.yaml
            hw01/
                publication.yaml
                homework.tex
            hw02/
                publication.yaml
                homework.tex
        lectures/
            collection.yaml
            01-introduction/
                publication.yaml
                slides.tex

Each collection directory contains a ``collection.yaml`` and one or more
subdirectories, each containing a ``publication.yaml``.


``collection.yaml``
^^^^^^^^^^^^^^^^^^^

Defines the schema for all publications in the collection:

.. code-block:: yaml

    publication_schema:
      required_artifacts:
        - homework.pdf
        - solution.pdf

      optional_artifacts:
        - template.zip

      metadata_schema:
        required_keys:
          number: { type: integer }
          due: { type: datetime }
          topic: { type: string }
        optional_keys:
          weight: { type: float, default: 1.0 }

      is_ordered: true

Fields:

- ``required_artifacts``: Artifact names that must exist in every publication.
- ``optional_artifacts``: Artifact names that may exist.
- ``metadata_schema``: A smartconfig schema defining required and optional
  metadata keys with types.
- ``allow_unspecified_artifacts``: If ``true``, publications may contain
  artifacts not listed above. Default: ``false``.
- ``is_ordered``: If ``true``, publications are processed in directory-name
  order and each has access to a ``previous`` variable. Default: ``false``.

Collections may also define **templates** that are available to publications
during resolution:

.. code-block:: yaml

    publication_schema:
      ...

    templates:
      standard_recipe: "latexmk -pdf ${ publication.metadata.topic }.tex"

Publications reference templates with ``${ templates.standard_recipe }``.


``publication.yaml``
^^^^^^^^^^^^^^^^^^^^

Defines a single publication's metadata and artifacts:

.. code-block:: yaml

    metadata:
      number: 1
      due: 2026-01-15 23:59:00
      topic: "Introduction"

    artifacts:
      homework.pdf:
        recipe: latexmk -pdf homework.tex
        path: homework.pdf
      solution.pdf:
        recipe: latexmk -pdf solution.tex
        path: solution.pdf
        ready: false

Artifact fields:

.. list-table::
   :header-rows: 1
   :widths: 20 15 65

   * - Field
     - Default
     - Description
   * - ``path``
     - artifact key
     - Path to the produced file, relative to the publication directory.
   * - ``recipe``
     - ``null``
     - Shell command to build the artifact. Run from the publication directory.
   * - ``release_time``
     - ``null``
     - When the artifact becomes visible.
   * - ``ready``
     - ``true``
     - Set to ``false`` to exclude this artifact from the build output.
   * - ``missing_ok``
     - ``false``
     - If ``true``, no error when the file doesn't exist after building.


Relative dates with ``previous``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In ordered collections (``is_ordered: true``), each publication has access to
the previous publication via the ``previous`` variable. This enables computing
dates relative to each other:

.. code-block:: yaml

    # lectures/02-time_complexity/publication.yaml
    metadata:
      number: 2
      date: first tuesday, thursday after ${ previous.metadata.date }
      topic: "Time Complexity"

This computes the date of lecture 2 as the first Tuesday or Thursday after the
date of lecture 1. By defining lecture 1's date in terms of
``${ vars.date_of_first_lecture }``, changing one variable in ``automata.yaml``
cascades through the entire lecture schedule.


.. _date-phrases:

Date phrases
------------

Any field whose type is ``date`` or ``datetime`` accepts, besides an ISO date
like ``2026-10-06`` (for a ``date``) or ``2026-10-06 23:59:00`` (for a
``datetime``), a *date phrase*. This includes
``release_time`` and any metadata key declared ``type: date`` or
``type: datetime`` in ``collection.yaml``:

.. code-block:: yaml

    metadata:
      due: ${ vars.first_homework_due } at 23:59:00
      released: 7 days before ${ this.metadata.due } at 00:00:00
    artifacts:
      solution.pdf:
        release_time: 1 day after ${ this.metadata.due }

The forms are:

- **Offsets:** ``3 days after <date>``, ``2 weeks before <date>``.
- **Weekdays:** ``first tuesday, thursday after <date>`` (or
  ``first tuesday or thursday after <date>``).
- **A time of day:** any form may end with ``at HH:MM:SS``, e.g.
  ``2026-10-06 at 23:59:00``.

A string that is a valid ISO date is always read as that date; only other
strings are read as phrases. If a phrase can't be read, the error names the
field and shows the text, e.g. ``Cannot read "7 dyas before 2026-10-06" as a
date or a date phrase``.

Datetimes need a time
^^^^^^^^^^^^^^^^^^^^^

A ``datetime`` field must say what time it means. A date alone is an error,
whether quoted or not, and so is a phrase that gives only a date, since
midnight is often not what was meant (for a due date, say):

.. code-block:: yaml

    due: 2026-10-06                      # error: no time
    due: 3 days after 2026-10-06         # error: no time
    due: 2026-10-06 23:59:00             # fine
    due: 3 days after 2026-10-06 at 23:59:00   # fine

A phrase can also take its time from the datetime it starts from, so it needs
no ``at``. Here ``release_time`` is 3 days after the midterm, at the same time
of day:

.. code-block:: yaml

    metadata:
      midterm: 2026-06-10 13:00:00
    artifacts:
      solution.pdf:
        release_time: 3 days after ${ this.metadata.midterm }   # 2026-06-13 13:00:00

This works whenever the referenced value is a datetime, including one at
midnight. If it is only a date (say, a variable ``midterm: 2026-06-10``), the
phrase gives only a date, and needs an ``at``.

Phrases are recognized only in fields typed as dates. Elsewhere, such as in
``vars`` or a field of type ``any``, a phrase is kept as a string; it is read
as a date where it is used in a date field. To get a date in an untyped place,
use the explicit function ``__datetime.parse__`` (or the YAML tag
``!datetime.parse``), which accepts the same phrases.


Inline publications in ``collection.yaml``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Publications can also be defined inline within ``collection.yaml`` itself,
instead of as separate directories with ``publication.yaml`` files:

.. code-block:: yaml

    publication_schema:
      required_artifacts: []
      metadata_schema:
        required_keys:
          name: { type: string }

    publications:
      item1:
        metadata:
          name: "First Item"
        artifacts: {}
      item2:
        metadata:
          name: "Second Item"
        artifacts: {}

.. note::

    You cannot mix inline publications in ``collection.yaml`` with
    filesystem ``publication.yaml`` files in the same collection.


Merging inline and filesystem materials
---------------------------------------

Inline materials (in ``automata.yaml``) and filesystem materials are merged
during discovery. A collection can appear in one or the other, but not both ---
if a collection name appears in both ``automata.yaml`` and on the filesystem,
discovery will raise an error.
