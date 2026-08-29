from importlib.metadata import version as package_version

import typer

from .commands.search_exposure import app as search_exposure_app
from .git import GitError, fetch_all

app = typer.Typer(
    name="recon",
    help="Git security reconnaissance utilities.",
)

git_app = typer.Typer(
    help="Git repository operations.",
)

app.add_typer(git_app, name="git")
app.add_typer(search_exposure_app, name="search_exposure")


@app.command()
def version() -> None:
    """Show the Recon version."""
    typer.echo(f"recon {package_version('recon')}")


@git_app.command("fetch-all")
def fetch_all_command() -> None:
    """Fetch every branch from every configured remote."""
    try:
        branches = fetch_all()
    except GitError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Fetched and verified {len(branches)} branches.")


if __name__ == "__main__":
    app()
