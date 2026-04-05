automata
========

**automata** is a static site generator for course webpages. It takes annotated
course materials --- homework PDFs, lecture slides, lab notebooks --- and
generates a complete course website with scheduled releases, a weekly schedule,
and a consistent theme.

Key features:

- **Scheduled releases.** Artifacts are released automatically based on
  configurable dates and times.
- **Materials hierarchy.** Organize materials into collections (homeworks,
  lectures, labs) and publications (hw01, hw02, ...) with typed metadata.
- **Variable interpolation.** Define dates, course names, and other values once
  and reference them everywhere.
- **Extensible.** Themes and plugins are *extensions* --- collections of hooks
  that customize behavior.
- **Two ways to define materials.** Simple materials can be defined inline in
  ``automata.yaml``; complex materials with build recipes use the filesystem.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   guide/index
   reference/index
   extensions/index
   developer/index
