import pathlib
import shutil
import datetime
import lxml.html
from textwrap import dedent

from pytest import raises, fixture, mark

import automata.api.coursepage

# basic tests
# --------------------------------------------------------------------------------------


class Demo:
    def __init__(self, path: pathlib.Path):
        self.path = path
        self.builddir = self.path / "_build"
        (path / "pages").mkdir()
        (path / "static").mkdir()
        (path / "config.yaml").touch()

        shutil.copytree(pathlib.Path(__file__).parent / "basic_theme", path / "theme")

        self.add_to_config(
            """
            theme:
                page_title: "example theme"
            """
        )

    def use_example_published(self, s):
        src = pathlib.Path(__file__).parent / s
        dst = self.builddir / "published"
        shutil.copytree(src, dst)
        return dst

    def use_example_theme(self, s):
        src = pathlib.Path(__file__).parent / s
        dst = self.path / "theme"
        shutil.copytree(src, dst)
        return dst

    def make_page(self, name, content):
        path = self.path / "pages" / name
        with path.open("w") as fileobj:
            fileobj.write(content)

    def make_theme_page(self, name, content):
        path = self.path / "theme" / "pages" / name
        with path.open("w") as fileobj:
            fileobj.write(content)

    def get_output(self, name):
        with (self.builddir / name).open() as fileobj:
            return fileobj.read()

    def add_to_config(self, content):
        with (self.path / "config.yaml").open("a") as fileobj:
            fileobj.write(dedent(content))


@fixture
def demo(tmpdir):
    return Demo(pathlib.Path(tmpdir))


def test_converts_pages_from_markdown_to_html(demo):
    # given
    demo.make_page("one.md", "# This is a header\n**this is bold!**")

    # when
    automata.api.coursepage.build(demo.path, demo.builddir)

    # then
    assert '<h1 id="this-is-a-header">This is a header</h1>' in demo.get_output(
        "one.html"
    )


def test_pages_have_access_to_published_artifacts(demo):
    # given
    contents = dedent(
        """
        {{ materials.collections.homeworks.publications["01-intro"].artifacts["homework.pdf"].path }}
        """
    )
    demo.make_page("one.md", contents)
    demo.use_example_published("basic_published")

    # when
    automata.api.coursepage.build(
        demo.path, demo.builddir, materials_path=demo.builddir / "published"
    )

    # then
    assert "published/homeworks/01-intro/homework.pdf" in demo.get_output("one.html")


def test_pages_have_access_to_elements(demo):
    # given
    demo.make_page("one.md", "{{ elements.announcement_box(config['announcement']) }}")
    config = dedent(
        """
        announcement:
            contents: This is a test.
            urgent: true
        """
    )
    demo.add_to_config(config)

    # when
    automata.api.coursepage.build(demo.path, demo.builddir)

    # then
    assert "This is a test" in demo.get_output("one.html")


def test_pages_are_rendered_in_base_template(demo):
    # given
    demo.make_page("one.md", "this is the page")

    # when
    automata.api.coursepage.build(demo.path, demo.builddir)

    # then
    assert "<html>" in demo.get_output("one.html")


def test_raises_if_an_unknown_variable_is_accessed_during_page_render(demo):
    # given
    demo.make_page("one.md", "{{ foo }}")

    # when
    with raises(automata.api.coursepage.PageError) as excinfo:
        automata.api.coursepage.build(demo.path, demo.builddir)

    assert "one.md" in str(excinfo.value)


def test_raises_if_an_unknown_attribute_is_accessed_during_page_render(demo):
    # given
    demo.make_page("one.md", "{{ config.this_dont_exist }}")

    # when
    with raises(automata.api.coursepage.PageError) as excinfo:
        automata.api.coursepage.build(demo.path, demo.builddir)

    assert "one.md" in str(excinfo.value)


def test_raises_if_an_unknown_attribute_is_accessed_during_element_render(demo):
    # given

    # x is in the element evaluation context, but y is not
    demo.add_to_config(
        dedent(
            """
        announcement:
            contents: Here ${ y } is
        """
        )
    )
    demo.make_page("one.md", "{{ elements.announcement_box(config['announcement']) }}")

    # when
    with raises(Exception) as excinfo:
        automata.api.coursepage.build(demo.path, demo.builddir)


def test_accepts_vars(demo):
    # given
    demo.make_page("test.md", "{{ vars.foo }}")

    # when
    automata.api.coursepage.build(demo.path, demo.builddir, vars={"foo": "barbaz"})

    # then
    assert "barbaz" in demo.get_output("test.html")


def test_vars_available_in_config_file(demo):
    # given
    demo.add_to_config(
        dedent(
            """
                announcement:
                    contents: My name is ${ vars.name }
                """
        )
    )
    demo.make_page("one.md", "{{ elements.announcement_box(config['announcement']) }}")

    # when
    automata.api.coursepage.build(
        demo.path, demo.builddir, vars={"name": "Zaphod Beeblebrox"}
    )

    # then
    assert "Zaphod Beeblebrox" in demo.get_output("one.html")
