automata
========

*automata* is a static site generator for course webpages. Instead of manually
updating your course website each time your course materials change, have
*automata* automatically generate your course website for you.

**Features**

- **Reduce drudgery**: Changed your lecture slides or fixed a typo in your
  homework? Simply run :code:`automata deploy` and your course website is
  updated with the latest materials (even rebuilding them in the process, if
  necessary).

- **Publish materials on a schedule**: Annotate your course
  materials with release dates, and *automata* will only publish materials that
  are dated before the current date. If you re-run *automata* regularly, you
  can use this feature to automatically publish new materials (like homework
  solutions) on a schedule.

- **Streamline beginning-of-the-quarter course setup**. Because *automata*
  allows you to specify release dates relative to one another, your
  beginning-of-the-quarter wesbite setup can be as simple as specifying the
  start date of your course. If you run *automata* regularly after this, you
  don't need to touch the website again until the next quarter.

- **Integrate with GitHub Actions**: Automate the deployment of your course
  website with GitHub Actions, so that simply pushing to your course repository
  or making a change to a file through GitHub updates your course website with
  the latest materials.


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   tutorial/index.rst
   reference/index.rst
   developer/index.rst
