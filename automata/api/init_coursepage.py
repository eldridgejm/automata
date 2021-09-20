import pathlib
import urllib.request
import zipfile
import io

DEFAULT_THEME_URL = "https://github.com/eldridgejm/automata-theme-default/archive/refs/heads/master.zip"


def _extract_zip_bytes(bytes, path):
    """Extracts a Bytes object containing a Zip file to the path."""
    zipfile.ZipFile(io.BytesIO(bytes)).extractall(path=path)


def init_coursepage(path):
    """Creates a starter coursepage at the path.

    Parameters
    ----------
    path : pathlib.Path
        Path to a directory that will contain the course page. If it doesn't exist, it
        will be created.

    """
    path = pathlib.Path(path)
    path.mkdir(exist_ok=True, parents=True)

    print('Downloading default template...')

    # download the default theme as a zip
    response = urllib.request.urlopen(DEFAULT_THEME_URL)

    # extract the zip
    _extract_zip_bytes(response.read(), path)

    # the zip contains a single top-level directory named automata-theme-default-master
    # move it to theme/
    (path / 'automata-theme-default-master').rename(path / 'theme')

    # use the default config from the theme
    (path / 'theme' / 'default-config.yaml').rename(path / 'config.yaml')

    # make the pages directory and place an index.md file within
    (path / 'pages').mkdir()
    with (path / 'pages' / 'index.md').open('w') as fileobj:
        fileobj.write('\n'.join([
                '# Welcome!',
                'You can change this page by editing `pages/index.md`.',
                'This file is converted from markdown to HTML.',
                'See the documentation for how to add *elements* to the page. Elements',
                'are useful for displaying the course schedule, all course materials, etc.'
            ]))