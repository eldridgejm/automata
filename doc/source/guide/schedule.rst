The Schedule Element
====================

The ``schedule`` element renders a week-by-week course schedule. It is one of
the most powerful features of automata, automatically organizing lectures,
homeworks, and other activities into a weekly view.


Basic usage
-----------

In ``automata.yaml``, configure the schedule under ``website.elements``:

.. code-block:: yaml

    website:
      elements:
        schedule:
          __include__: "schedule.yaml"

Then place it in a page:

.. code-block:: markdown

    ${ elements.schedule() }


Schedule configuration
----------------------

The schedule configuration is typically in a separate YAML file included via
``__include__``. Here is a complete example:

.. code-block:: yaml

    week_order: this_week_first

    week_topics:
      - Introduction
      - Data Structures
      - Algorithms
      - Graphs
      - Final Exams

    events:
      - name: Midterm Review
        date: "2026-04-18"
      - name: Midterm Exam
        date: "2026-04-20"

    announcements:
      - week: 2
        urgent: true
        content: |
          **Reminder:** Homework 1 is due Friday!

      - week: null
        content: |
          This appears in the latest (current) week.

    primary_activity_collections:
      - collection: lectures
        for_each_publication:
          start_displaying_on: !template "${ publication.metadata.date }"
          title: !template "Lecture ${ publication.metadata.number } - ${ publication.metadata.topic }"
          resources:
            - type: artifact_links
              title: Slides
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
                - text: Instructions
                  artifact: homework.pdf
                - text: Solution
                  artifact: solution.pdf


Configuration fields
--------------------

The weeks are numbered from the course's ``first_week_start`` and
``first_week_number``, in the ``course`` section of ``automata.yaml`` (see
:doc:`configuration`); the schedule has no settings of its own for them.
Activities are placed into weeks by their ``start_displaying_on`` dates.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Field
     - Description
   * - ``week_order``
     - Display order: ``"this_week_first"`` (most recent week at top) or
       ``"chronological"`` (week 1 first).
   * - ``week_topics``
     - List of topic labels, one per week. ``week_topics[0]`` is week 1's
       label.
   * - ``events``
     - List of ``{name, date}`` objects displayed as standalone events in
       the appropriate week.
   * - ``announcements``
     - List of ``{week, content}`` objects. ``week: null`` displays in the
       latest week. ``urgent: true`` adds emphasis. ``start_displaying_on`` (a
       date, optional) hides the announcement until that date; like a release
       time, it takes effect when the site is next built.


Activity collections
--------------------

Activities are derived from materials collections.
``primary_activity_collections`` appear prominently (e.g., lectures);
``secondary_activity_collections`` appear in a sidebar or compact form (e.g.,
homeworks).

Each entry maps a collection to a display format:

.. code-block:: yaml

    primary_activity_collections:
      - collection: lectures               # which collection
        for_each_publication:              # how to display each publication
          start_displaying_on: ...         # when to show it
          title: ...                       # display title
          resources: [...]                 # what to show


Resource types
--------------

Each activity can have multiple resources. The ``type`` field determines how
the resource is displayed:

``artifact_links``
^^^^^^^^^^^^^^^^^^

Links to artifact files:

.. code-block:: yaml

    - type: artifact_links
      title: Slides
      icon: projector
      links:
        - text: PDF
          artifact: slides.pdf
        - text: Markdown
          artifact: slides.md

Links to artifacts that don't exist yet (not released, not ready) are
automatically hidden.

``markdown``
^^^^^^^^^^^^

Rendered Markdown content:

.. code-block:: yaml

    - type: markdown
      title: Reading
      icon: book-open
      markdown: !template |
        [${ publication.metadata.reading.title }](${ publication.metadata.reading.url })

``html``
^^^^^^^^

Raw HTML content:

.. code-block:: yaml

    - type: html
      html: !template |
        ${ elements.button({"label": "Join Session", "url": "https://example.com"}) }

``links``
^^^^^^^^^

Static links (not tied to artifacts):

.. code-block:: yaml

    - type: links
      title: References
      icon: link
      links:
        - text: Textbook
          url: https://example.com/textbook
        - text: Python Docs
          url: https://docs.python.org

``metadata_links``
^^^^^^^^^^^^^^^^^^

Links derived from publication metadata (e.g., video links):

.. code-block:: yaml

    - type: metadata_links
      title: Videos
      icon: film
      metadata_key_for_links: videos
      for_each_link:
        text: !template "${ link.title }"
        url: !template "${ link.url }"


Extra activities
----------------

Activities not tied to a collection:

.. code-block:: yaml

    extra_primary_activities:
      - title: Exam Review Session
        start_displaying_on: "2026-04-18"
        resources:
          - type: markdown
            markdown: |
              Join us for a review session!

    extra_secondary_activities:
      - title: Extra Credit
        start_displaying_on: "2026-04-22"
        due_datetime: "2026-04-30 23:59:00"
        resources:
          - type: markdown
            markdown: |
              Complete the bonus exercise for extra credit.


Icons
-----

Resource entries can include an ``icon`` field. The default theme uses
`Lucide icons <https://lucide.dev/icons>`_. Use the icon name (e.g.,
``projector``, ``book-open``, ``film``, ``link``).
