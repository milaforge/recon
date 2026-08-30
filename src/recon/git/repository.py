"""
Responsible only for executing Git and validating the repository.
"""

import subprocess
from pathlib import Path


class GitError(RuntimeError):
    """Raised when a Git operation fails."""


class IncompleteRepositoryError(GitError):
    """Raised when Recon cannot guarantee that repository history is complete."""


def run_git(*args: str, cwd: Path | str | None = None) -> str:
    """Execute a Git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        message = result.stderr.strip() or "Git command failed."
        raise GitError(message)

    return result.stdout


def ensure_repository(cwd: Path | str | None = None) -> None:
    """Raise GitError if the current directory is not a Git repository."""
    try:
        result = run_git(
            "rev-parse",
            "--is-inside-work-tree",
            cwd=cwd,
        )
    except GitError as exc:
        raise GitError("Not inside a Git repository.") from exc

    if result.strip() != "true":
        raise GitError("Not inside a Git working tree.")


def repository_root(cwd: Path | str | None = None) -> Path:
    """Return the root directory of the current Git repository."""
    ensure_repository(cwd=cwd)

    return Path(
        run_git(
            "rev-parse",
            "--show-toplevel",
            cwd=cwd,
        ).strip()
    )


def is_shallow_repository(cwd: Path | str | None = None) -> bool:
    """Return True if the repository is a shallow clone."""
    return (
        run_git(
            "rev-parse",
            "--is-shallow-repository",
            cwd=cwd,
        ).strip()
        == "true"
    )


def unshallow(cwd: Path | str | None = None) -> None:
    """Convert a shallow repository into a full repository."""
    if not is_shallow_repository(cwd=cwd):
        return

    remotes = [
        remote for remote in run_git("remote", cwd=cwd).splitlines() if remote.strip()
    ]

    if not remotes:
        raise IncompleteRepositoryError(
            "Repository is shallow but has no configured remote."
        )

    # Normally there is one remote. If there are several, explicitly
    # unshallow each one.
    for remote in remotes:
        print(f"Unshallowing repository from {remote}...")

        run_git(
            "fetch",
            "--unshallow",
            remote,
            cwd=cwd,
        )

    if is_shallow_repository(cwd=cwd):
        raise IncompleteRepositoryError(
            "Repository is still shallow after unshallowing."
        )


def is_partial_repository(cwd: Path | str | None = None) -> bool:
    """Return True if the repository is a Git partial clone."""
    # A partial clone is marked by extensions.partialClone.
    if get_git_config("extensions.partialClone", cwd=cwd):
        return True

    for remote in get_remotes(cwd=cwd):
        if get_git_config(f"remote.{remote}.promisor", cwd=cwd) == "true":
            return True

    return False


def ensure_complete_repository(cwd: Path | str | None = None) -> None:
    """
    Ensure the repository has complete, locally available Git history.

    Shallow repositories are handled separately by unshallow().
    Partial clones are currently unsupported because silently fetching
    missing objects would make the completeness guarantee ambiguous.
    """
    ensure_repository(cwd=cwd)

    if is_partial_repository(cwd=cwd):
        raise IncompleteRepositoryError(
            "Partial clone detected.\n\n"
            "recon requires a complete local Git object database for "
            "historical security analysis.\n\n"
            "Please reclone the repository without Git's partial-clone "
            "options such as --filter or --sparse."
        )

    if is_shallow_repository(cwd=cwd):
        raise IncompleteRepositoryError("Repository is still shallow.")

    ensure_unmodified_history(cwd=cwd)


def ensure_unmodified_history(cwd: Path | str | None = None) -> None:
    """Reject local mechanisms that replace the repository's recorded DAG."""
    replace_refs = run_git(
        "for-each-ref",
        "--format=%(refname)",
        "refs/replace/",
        cwd=cwd,
    ).splitlines()
    git_dir = Path(run_git("rev-parse", "--git-dir", cwd=cwd).strip())
    if not git_dir.is_absolute():
        base = Path(cwd) if cwd is not None else Path.cwd()
        git_dir = base / git_dir
    grafts_file = git_dir / "info" / "grafts"

    if replace_refs or (grafts_file.is_file() and grafts_file.stat().st_size > 0):
        raise IncompleteRepositoryError(
            "Modified Git history detected (replace refs or grafts).\n\n"
            "recon cannot guarantee complete historical analysis while Git's "
            "recorded commit graph is being rewritten locally. Remove the "
            "replace refs/grafts or scan a clean clone."
        )


def get_git_config(key: str, cwd: Path | str | None = None) -> str | None:
    """Return a Git config value, or None when the key is absent."""
    result = subprocess.run(
        ["git", "config", "--get", key],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode == 1:
        return None

    if result.returncode != 0:
        message = result.stderr.strip() or "Git config lookup failed."
        raise GitError(message)

    return result.stdout.strip()


def get_remotes(cwd: Path | str | None = None) -> list[str]:
    """Return all configured Git remotes."""
    return [
        remote.strip()
        for remote in run_git("remote", cwd=cwd).splitlines()
        if remote.strip()
    ]


def prepare_repository(cwd: Path | str | None = None) -> None:
    """Prepare the repository for complete historical analysis."""
    ensure_repository(cwd=cwd)

    if is_partial_repository(cwd=cwd):
        raise IncompleteRepositoryError(
            "Partial clone detected.\n\n"
            "recon requires a complete local Git object database for "
            "historical security analysis.\n\n"
            "Please reclone the repository without --filter or other "
            "partial-clone options."
        )

    unshallow(cwd=cwd)

    ensure_complete_repository(cwd=cwd)
