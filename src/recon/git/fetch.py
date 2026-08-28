"""
This module owns fetching and verification.
"""

from pathlib import Path
from .refs import RemoteBranch, get_remote_branches, get_remotes
from .repository import run_git, prepare_repository


def verify_branch(branch: RemoteBranch, cwd: Path | str | None = None) -> None:
    """Verify that the local remote-tracking ref matches the remote SHA."""
    actual_sha = run_git(
        "rev-parse",
        branch.remote_ref,
        cwd=cwd,
    ).strip()

    if actual_sha != branch.sha:
        raise RuntimeError(
            f"Fetch verification failed for {branch.display_name}: "
            f"expected {branch.sha}, got {actual_sha}"
        )

    # Verify that the commit object actually exists locally.
    run_git(
        "cat-file",
        "-e",
        f"{branch.sha}^{{commit}}",
        cwd=cwd,
    )


def fetch_branch(branch: RemoteBranch, cwd: Path | str | None = None) -> None:
    """Fetch one complete remote branch."""
    run_git(
        "fetch",
        branch.remote,
        f"refs/heads/{branch.name}:{branch.remote_ref}",
        cwd=cwd,
    )

    run_git(
        "cat-file",
        "-e",
        f"{branch.sha}^{{commit}}",
        cwd=cwd,
    )

    verify_branch(branch, cwd=cwd)


def fetch_remote(
    remote: str,
    branches: list[RemoteBranch],
    cwd: Path | str | None = None,
) -> None:
    """Fetch selected branches from one remote."""
    for branch in branches:
        fetch_branch(branch, cwd=cwd)

    # Tags may reference historical objects not reachable from branches.
    run_git(
        "fetch",
        remote,
        "--tags",
        cwd=cwd,
    )


def fetch_all(cwd: Path | str | None = None) -> list[RemoteBranch]:
    """
    Discover and fetch every branch from every configured remote.

    Returns the branches that were fetched.
    """
    fetched: list[RemoteBranch] = []

    prepare_repository(cwd=cwd)

    for remote in get_remotes(cwd=cwd):
        branches = get_remote_branches(remote, cwd=cwd)

        fetch_remote(
            remote,
            branches,
            cwd=cwd,
        )

        fetched.extend(branches)

    return fetched
