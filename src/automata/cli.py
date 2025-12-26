import typer

app = typer.Typer()


@app.command()
def build():
    """Build course materials."""
    print("Hello world")


@app.command()
def status():
    """Check status of course materials."""
    print("All good.")


def main():
    app()


if __name__ == "__main__":
    main()
