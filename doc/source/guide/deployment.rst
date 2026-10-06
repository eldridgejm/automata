Deployment
==========

After running ``automata build``, the ``_build/`` directory contains a
complete static website that can be deployed to any static hosting provider.


Local preview
-------------

Open ``_build/index.html`` directly in a browser, or use a local server::

    python -m http.server -d _build 8000

Then visit ``http://localhost:8000``.

.. tip::

    Set ``base_path: "."`` in your config for local preview with relative URLs.
    For production, set it to the appropriate path (e.g., ``"/course/"``).


Publishing with ``automata publish``
------------------------------------

``automata publish`` builds the site and deploys it to the targets configured
under ``publish:`` in ``automata.yaml``. Each target names a *strategy* and its
config:

.. code-block:: yaml

    publish:
      github:
        strategy: gh-pages
        config:
          # optional; by default, the project's own repository (its origin)
          repository: dsc-courses/dsc40b-2026-fa
          branch: gh-pages     # default
          # optional; by default, the project's git identity
          user_name: github-actions[bot]
          user_email: github-actions[bot]@users.noreply.github.com
      mirror:
        strategy: git
        config:
          url: https://git.example.edu/dsc40b/site.git
          branch: main         # required
      server:
        strategy: rsync
        config:
          host: example.ucsd.edu
          remote_path: /var/www/dsc40b
          user: deploy         # optional
          delete: true         # default: remove files not in the build

``automata publish`` with no argument publishes to every target, in order;
``automata publish github`` publishes to one. A misspelled target or strategy
is reported before anything is built.

Built-in strategies:

- ``gh-pages`` --- replaces the contents of a branch (by default,
  ``gh-pages``) of a GitHub repository with the build directory, in a single
  commit (no commit if nothing changed). The repository is ``repository``,
  written ``org/name`` and pushed to over SSH
  (``git@github.com:org/name.git``), or, by default, the project's own
  ``origin``. A separate repository is useful when the course's own is
  private but its site must be public; it needn't be a remote of the
  project's repository, so nothing has to be set up in each clone (or on CI).
  ``repository`` can use ``vars``, e.g. ``${ vars.public_repo }``.
- ``git`` --- the same, for any git repository and branch: ``url`` is the
  repository's URL (e.g. over HTTPS, with a token, or on another host; a
  relative local path is relative to the project), or ``remote`` names one of
  the project's remotes (by default, ``origin``). ``branch`` is required, and
  giving both ``url`` and ``remote`` is an error.

  For both, the whole branch is replaced, so files that must stay on it (such
  as a ``CNAME`` for a custom domain) belong in the site's content. The
  commit's ``message`` can be set, and its author is ``user_name``/
  ``user_email`` from the config if given, otherwise the project's git identity
  (``git config user.name`` and ``user.email``), or the
  ``GIT_COMMITTER_NAME``/``GIT_COMMITTER_EMAIL`` environment variables. If none
  is set --- typical on a fresh CI machine --- publishing stops with an error
  saying how to set one; on GitHub Actions, setting ``user_name`` and
  ``user_email`` as above is the simplest fix.
- ``rsync`` --- mirrors the build directory to ``host:remote_path`` over SSH,
  deleting files on the server that are no longer in the build, so withdrawn
  materials and deleted pages don't linger. Requires ``rsync`` to be installed.

To see what publishing would change without publishing, use ``automata
publish --dry-run``: it builds the site and lists, for each target, the files
that would be added, modified, or deleted (``--json`` gives the list as JSON;
see :doc:`/reference/cli`). It changes nothing where the site is published,
and needs no git identity, so it can run on CI for each pull request. A
publish says what it changed, too.

An extension can add a strategy from an ``on_register_publishers`` hook. A
strategy is a function called as ``publisher(build_directory, config,
project_directory)``. It returns the files it changed, as a list of
``automata.publish.Change(status, path)``, where ``status`` is ``"added"``,
``"modified"``, or ``"deleted"`` and ``path`` is relative to the site's root,
or ``None`` if it doesn't say. To support ``--dry-run``, it also takes a
``dry_run`` keyword argument, and when that is ``True``, it publishes nothing
and returns the list of changes it would make. (A strategy without
``dry_run`` can't do a dry run.)

.. code-block:: python

    from automata.publish import Change

    def publish_to_s3(build_directory, config, project_directory, *, dry_run=False):
        if dry_run:
            return [Change("added", "index.html"), ...]
        ...

    def register(args):
        args.publishers["s3"] = publish_to_s3
        return args

    extension = Extension(name="s3", hooks={"on_register_publishers": register})


GitHub Pages
------------

The recommended deployment method is GitHub Pages with GitHub Actions.

1. Create a ``.github/workflows/deploy.yml`` file:

   .. code-block:: yaml

       name: Deploy course website

       on:
         push:
           branches: [main]
         schedule:
           # Rebuild daily at 6am UTC to release scheduled materials
           - cron: "0 6 * * *"
         workflow_dispatch:

       permissions:
         contents: read
         pages: write
         id-token: write

       jobs:
         build:
           runs-on: ubuntu-latest
           steps:
             - uses: actions/checkout@v4

             - uses: actions/setup-python@v5
               with:
                 python-version: "3.14"

             - run: pip install git+https://github.com/eldridgejm/automata

             - run: automata build

             - uses: actions/upload-pages-artifact@v3
               with:
                 path: _build

         deploy:
           needs: build
           runs-on: ubuntu-latest
           environment:
             name: github-pages
             url: ${{ steps.deployment.outputs.page_url }}
           steps:
             - id: deployment
               uses: actions/deploy-pages@v4

2. Enable GitHub Pages in the repository settings (Settings > Pages > Source:
   GitHub Actions).

3. Set ``base_path`` in ``automata.yaml`` to match the GitHub Pages URL path:

   .. code-block:: yaml

       website:
         base_path: "/my-repo-name/"


Scheduled releases
------------------

The key to scheduled releases is running ``automata build`` on a schedule.
The ``cron`` trigger in the GitHub Actions workflow above rebuilds the site
daily at 6am UTC. Materials with ``release_time`` in the future are
automatically excluded.

You can also trigger a rebuild manually via ``workflow_dispatch``.


Time override
-------------

To preview what the site looks like at a different time::

    # Absolute time
    automata build --current-time "2026-02-15T12:00:00"

    # Relative (5 days in the future)
    automata build --current-time "+5"

    # Relative (3 days in the past)
    automata build --current-time "-3"
