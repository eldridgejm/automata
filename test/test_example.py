import pathlib

import automata.materials
import automata.website


def test_build_example_site(tmp_path):
    # Setup paths
    root_dir = pathlib.Path(__file__).parent.parent
    example_dir = root_dir / "example"
    output_dir = tmp_path / "output"

    # 0. read automata.yaml
    # TODO

    # 1. Discover materials
    universe = automata.materials.discover(example_dir)
    built_universe = automata.materials.build(universe)
    _ = automata.materials.export(built_universe, output_dir)

    # automata.website.generate(
    #     input_path=website_input,
    #     output_path=output_dir,
    #     materials_path=published_dir,
    #     vars=vars,
    #     now=lambda: datetime.datetime(2024, 9, 25, 12, 0, 0)  # Mock time during
    #     semester
    # )

    # # 5. Assertions
    # assert (output_dir / "index.html").exists()
    # assert (output_dir / "syllabus.html").exists()
    #
    # # Check syllabus content
    # syllabus_content = (output_dir / "syllabus.html").read_text()
    # assert "CS101" in syllabus_content
    # assert "Fall 2024" in syllabus_content
    #
    # # Check index content (Schedule)
    # index_content = (output_dir / "index.html").read_text()
    # # Schedule should be rendered.
    # # Based on example/lectures/collection.yaml and publications, there
    # # should be lectures.
    # # "Introduction" is 01-introduction.
    # assert "Introduction" in index_content
