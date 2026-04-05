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
        inputs.vars["theme_name"] = "my-theme"
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
     - ``dict[str, str | bytes | Path]`` --- extra pages to render.
   * - ``vars``
     - ``dict[str, Any]`` --- variables merged into the render context.

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
        return GeneratePreHookArgs(config=args.config, extra_content=extra)

``on_generate_post``
^^^^^^^^^^^^^^^^^^^^

**Type:** Observer

**Signature:** ``(GeneratePostHookArgs) -> None``

Called after website generation completes. Useful for post-processing (e.g.,
CSS minification, image optimization).

.. code-block:: python

    from automata.hooks import GeneratePostHookArgs

    def post_generate(args: GeneratePostHookArgs) -> None:
        print(f"Website built at {args.config.build_directory}")


Materials hooks
---------------

These hooks are fired during material discovery, building, exporting, and
filtering. They are primarily used for logging and monitoring.

Discovery hooks (``DiscoverHooks``):

- ``on_discover_collection`` --- called when a collection is found.
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

Hooks are registered with a ``priority`` (default 0). Lower values run first.
When loading theme extensions from directories, hooks are registered at priority
100, allowing user-registered hooks to run before (lower priority) or after
(higher priority) them.

.. code-block:: python

    @hooks.on_generate_post.register(priority=50)
    def my_hook(args):
        ...  # runs before theme hooks (priority 100)


Shell script hooks
------------------

Observer hooks (not pipeline hooks) can register shell scripts. The hook args
are serialized as JSON and piped to the command on stdin:

.. code-block:: python

    project = Automata()
    project.hooks.on_generate_post.register_shell_script(
        "cat | jq .config.build_directory",
        priority=200,
    )
    project.generate()

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
        "config": {
            "content_directory": "content",
            "build_directory": "_build",
            "materials_directory_name": "materials",
            "no_render_suffix": ".no_render",
            "base_path": "/"
        }
    }

Shell scripts can be disabled per-hook with ``allow_shell=False``.


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

    project.generate()
