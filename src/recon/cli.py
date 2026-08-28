import typer

from importlib.metadata import version as package_version
from .git import fetch, fetch_all, history_exposed_secrets

app = typer.Typer(
    name="recon",
    help="Git security reconnaissance utilities.",
)

git_app = typer.Typer(
    help="Git repository reconnaissance commands.",
)

app.add_typer(git_app, name="git")

@app.command()
def version() -> None:
    """Show the Recon version."""
    typer.echo(f"recon {package_version('recon')}")

@git_app.command("fetch")
def fetch_command() -> None:
    """Interactively select remote branches to fetch."""
    fetch()

@git_app.command("fetch-all")
def fetch_all_command() -> None:
    """Fetch all branches from all configured remotes."""
    fetch_all()


@git_app.command("history-exposed-secrets")
def history_exposed_secrets_command(
    paths: list[str] = typer.Argument(
        ...,
        help="Files to search for in Git history.",
    ),
) -> None:
    """Search Git history for changes to potentially sensitive paths."""
    history_exposed_secrets(paths)

if __name__ == "__main__":
    app()