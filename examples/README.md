# Examples

Example automata projects. Each can be built with `automata build` (or seen
with `automata serve`) from its directory.

- **[simple-course](simple-course/)**: lectures as PowerPoint files, all
  described in `automata.yaml`. Example 1 in the quickstart.
- **[latex-course](latex-course/)**: lectures and homeworks written in LaTeX,
  described by `collection.yaml` and `publication.yaml` files, and built from
  source by `latexmk`. Example 2 in the quickstart.
- **[full-course](full-course/)**: a larger course, using most of automata's
  features: several collections, the schedule and calendar, and an extension.

The quickstart shows these files, and `test/test_examples.py` builds the
examples and checks what the quickstart says about them, so change them with
care: the documentation changes with them.
