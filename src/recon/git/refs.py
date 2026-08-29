"""
This module handles refs and remote discovery.
"""

from dataclasses import dataclass
from pathlib import Path

from .repository import run_git


@dataclass(frozen=True)
class RemoteBranch:
    """A branch advertised by a Git remote."""

    remote: str
    name: str
    sha: str

    @property
    def remote_ref(self) -> str:
        return f"refs/remotes/{self.remote}/{self.name}"

    @property
    def display_name(self) -> str:
        return f"{self.remote}/{self.name}"


def get_remotes(cwd: Path | str | None = None) -> list[str]:
    """Return configured Git remotes."""
    return [remote for remote in run_git("remote", cwd=cwd).splitlines() if remote.strip()]


def get_remote_branches(remote: str, cwd: Path | str | None = None) -> list[RemoteBranch]:
    """
    Discover every branch currently advertised by a remote.
    """
    output = run_git(
        "ls-remote",
        "--heads",
        remote,
        cwd=cwd,
    )

    branches: list[RemoteBranch] = []

    for line in output.splitlines():
        if not line.strip():
            continue

        sha, ref = line.split("\t", 1)

        if not ref.startswith("refs/heads/"):
            continue

        name = ref.removeprefix("refs/heads/")

        branches.append(
            RemoteBranch(
                remote=remote,
                name=name,
                sha=sha,
            )
        )

    return branches


def get_local_remote_refs(cwd: Path | str | None = None) -> list[str]:
    """Return all local remote-tracking refs."""
    output = run_git(
        "for-each-ref",
        "--format=%(refname)",
        "refs/remotes/",
        cwd=cwd,
    )

    return [ref for ref in output.splitlines() if ref.strip()]


def get_local_tags(cwd: Path | str | None = None) -> list[str]:
    """Return all local tag refs."""
    output = run_git(
        "for-each-ref",
        "--format=%(refname)",
        "refs/tags/",
        cwd=cwd,
    )

    return [ref for ref in output.splitlines() if ref.strip()]
