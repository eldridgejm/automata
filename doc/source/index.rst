automata
========

*automata* is a static site generator for course webpages. Instead of manually
updating your course website each time your course materials change, have
*automata* automatically generate your course website for you.

**Features**

- **Reduce drudgery**: Changed your lecture slides or fixed a typo in your
  homework? Simply run :code:`automata publish` and your most up-to-date course
  materials are automatically published to the internet. If your materials are
  built from source code (like LaTeX or Markdown), *automata* will rebuild your
  materials before publishing them.

- **Publish materials on a schedule**: Annotate your course materials with
  release dates, and *automata* will only publish materials that are dated
  before the current date. If you re-run *automata* regularly, you can use this
  feature to automatically publish new materials (like homework solutions) on a
  predetermined schedule. This gives you the option of entirely automating your
  course webpage: after the initial setup, you can sit back and watch all of
  your course materials appear automatically as the course progresses.

- **Streamline beginning-of-the-quarter course setup**. *Automata* provides a
  powerful templating system that allows you to specify details about your
  course (such as the date of the first lecture, the room number, and the
  instructor's name) in a configuration file. This information is then used to
  populate your course website pages (like the syllabus) with the correct
  details. Moreover, dates, times, and numbers can be specified *relative* to
  one another, so that, for example, each homework can be configured to release
  7 days after the previous one, and each lecture can be released on the first
  Tuesday or Thursday after the previous lecture. In principle, this means that
  beginning-of-the-quarter website setup can be as simple as changing one line
  in a configuration file to update the start date of your course.

- **Integrate with GitHub Actions**: Automate the deployment of your course
  website with GitHub Actions, so that a simple ``git push`` updates your
  course website with the latest materials. By making your course materials
  discoverable, `automata` enables *continuous integration* for courses. Have
  your course staff submit pull requests to update the course materials, and
  these changes will automatically be tested and deployed only if they don't
  break the website.


Find the project on GitHub at http://github.com/eldridgejm/automata.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   tutorial/index.rst
   reference/index.rst
   developer/index.rst
