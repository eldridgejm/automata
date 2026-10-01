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

             - run: pip install automata

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
