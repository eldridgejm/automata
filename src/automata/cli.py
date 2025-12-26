import typer

from . import _build

app = typer.Typer()


@app.command()
def build():
    """Build course materials."""
    _build.build()


@app.command()
def status():
    """Check status of course materials."""
    print("All good.")


def main():
    app()


if __name__ == "__main__":
    main()
