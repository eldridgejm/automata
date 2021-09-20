import pathlib

import automata.api.coursepage

from pytest import fixture

@fixture
def output_directory(tmpdir):
    output_path = pathlib.Path(tmpdir) / "output"
    output_path.mkdir()
    return output_path

def test_creates_coursepage(output_directory):
    automata.api.coursepage.create(output_directory / 'website')

    assert (output_directory / 'website').exists()
    assert (output_directory / 'website' / 'theme' / 'base.html').exists()
    assert (output_directory / 'website' / 'config.yaml').exists()
    assert (output_directory / 'website' / 'pages').is_dir()
