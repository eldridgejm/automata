Hook Reference
==============

Extensions register callables on hook points. Hooks are either **observers**
(fire-and-forget) or **pipelines** (transform data through a chain).


Website generation hooks
------------------------

These hooks are fired during website generation and are the primary way
extensions customize behavior.

``on_website_collect``
^^^^^^^^^^^^^^^^^^^^^^

**Type:** Pipeline

**Signature:** ``(WebsiteInputs) -> WebsiteInputs``

Called to gather website inputs from extensions. Each registered callable
receives the accumulated inputs and returns modified inputs. This is how themes
contribute templates, static files, and elements.

.. code-block:: python

    from automata.hooks import WebsiteInputs

    def collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.templates["page.html"] = "<html>${ content }</html>"
        inputs.static_files["style.css"] = "body { margin: 0; }"
        inputs.elements["greeting"] = GreetingElement
        inputs.pages["extra.html"] = "# Extra Page"
        return inputs

``WebsiteInputs`` fields:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Field
     - Description
   * - ``templates``
     - ``dict[str, str]`` --- template name to content.
   * - ``static_files``
     - ``dict[str, str | bytes | Traversable]`` --- static file path to content.
   * - ``elements``
     - ``dict[str, type[Element]]`` --- element name to class.
   * - ``pages``
     - ``dict[str, str]`` --- extra pages to render.

Extensions cannot add to the render context's ``vars``. Templates read an
extension's configuration through ``theme`` and ``extensions`` instead (see
:doc:`themes`).

``on_generate_pre``
^^^^^^^^^^^^^^^^^^^

**Type:** Pipeline

**Signature:** ``(GeneratePreHookArgs) -> GeneratePreHookArgs``

Called before website generation begins. Can transform ``extra_content``
(additional pages to include in the output).

.. code-block:: python

    from automata.hooks import GeneratePreHookArgs

    def pre_generate(args: GeneratePreHookArgs) -> GeneratePreHookArgs:
        extra = dict(args.extra_content or {})
        extra["generated.html"] = "# Auto-generated page"
        return GeneratePreHookArgs(
            build_directory=args.build_directory, extra_content=extra
        )

``on_generate_post``
^^^^^^^^^^^^^^^^^^^^

**Type:** Observer

**Signature:** ``(GeneratePostHookArgs) -> None``

Called after website generation completes. Useful for post-processing (e.g.,
CSS minification, image optimization).

.. code-block:: python

    from automata.hooks import GeneratePostHookArgs

    def post_generate(args: GeneratePostHookArgs) -> None:
        print(f"Website built at {args.build_directory}")


Materials hooks
---------------

These hooks are fired during material discovery, building, exporting, and
filtering. They are primarily used for logging and monitoring.

Discovery hooks (``DiscoverHooks``):

- ``on_discover_collection`` --- called when a collection is found. For
  materials defined inline in ``automata.yaml``, ``path`` is ``automata.yaml``
  and ``key`` is the collection name.
- ``on_discover_publication`` --- called when a publication is found.
- ``on_discover_skip`` --- called when a directory is skipped.

Build hooks (``BuildHooks``):

- ``on_build_node`` --- called when building a collection, publication, or artifact.
- ``on_build_too_soon`` --- called when an artifact's release time hasn't passed.
- ``on_build_not_ready`` --- called when an artifact has ``ready: false``.
- ``on_build_missing`` --- called when an artifact is missing but ``missing_ok: true``.
- ``on_build_recipe`` --- called when running an artifact's recipe.
- ``on_build_success`` --- called when a build succeeds.

Export hooks (``ExportHooks``):

- ``on_export_node`` --- called when exporting a node.
- ``on_export_copy`` --- called when copying a file.

Filter hooks (``FilterHooks``):

- ``on_filter_hit`` --- called when a node matches a filter predicate.
- ``on_filter_miss`` --- called when a node doesn't match.


Hook priority
-------------

Hooks are registered with a ``priority`` (default 0). Lower values run first;
hooks with equal priority run in the order they were registered. ``Automata``
registers the theme's hooks, then the other extensions' hooks, at priority 0
when it is constructed, so hooks registered afterward at priority 0 run after
them. Use a negative priority to run before them:

.. code-block:: python

    @project.hooks.on_generate_post.register(priority=-10)
    def my_hook(args):
        ...  # runs before extension hooks (priority 0)


Shell script hooks
------------------

Observer hooks (not pipeline hooks) can register shell scripts. The hook args
are serialized as JSON and piped to the command on stdin:

.. code-block:: python

    project = Automata()
    project.hooks.on_generate_post.register_shell_script(
        "cat | jq .build_directory",
        priority=200,
    )
    project.build()

Or from a script that processes the JSON payload:

.. code-block:: python

    project.hooks.on_build_success.register_shell_script(
        "python notify.py",
        priority=0,
    )

The script receives the hook args as a JSON object on stdin. For example,
``on_generate_post`` sends:

.. code-block:: json

    {
        "build_directory": "_build"
    }

Shell scripts can be disabled per-hook with ``allow_shell=False``.

Directory extensions can also provide shell script hooks as files in a
``hooks/`` subdirectory, each named after an observer hook point (see
:doc:`themes`).


Registering hooks in Python
----------------------------

Beyond extensions, hooks can be registered directly on a ``Hooks`` instance:

.. code-block:: python

    from automata import Automata
    from automata.hooks import GeneratePostHookArgs

    project = Automata()

    @project.hooks.on_generate_post.register()
    def my_hook(args: GeneratePostHookArgs) -> None:
        print("Build complete!")

    project.build()
