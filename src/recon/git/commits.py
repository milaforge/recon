"""
This is the beginning of our historical traversal abstraction.
"""

from datetime import datetime
from collections.abc import Iterable
from pathlib import Path

from ..git.diff import get_file_diffs
from .repository import run_git, GitError
from ..models.diff import Commit, CommitDiff


def get_commit(sha: str, cwd: Path | str | None = None) -> Commit:
    """Return metadata for a commit."""
    output = run_git(
        "show",
        "-s",
        "--format=%H%x00%an <%ae>%x00%aI%x00%s",
        sha,
        cwd=cwd,
    )

    parts = output.rstrip("\n").split("\x00")

    if len(parts) != 4:
        raise RuntimeError(f"Unable to parse commit metadata for {sha}")

    (commit_sha, author, timestamp, subject) = parts

    return Commit(
        sha=commit_sha,
        author=author,
        timestamp=datetime.fromisoformat(timestamp),
        subject=subject,
    )


def get_reachable_commits(ref: str, cwd: Path | str | None = None) -> list[str]:
    """
    Return every commit reachable from a ref.

    Git's output is newest-first.
    """
    output = run_git(
        "rev-list",
        "--full-history",
        ref,
        cwd=cwd,
    )

    return [sha for sha in output.splitlines() if sha.strip()]


def get_all_reachable_commits(
    refs: list[str],
    cwd: Path | str | None = None,
) -> list[str]:
    """
    Return the unique commits reachable from all supplied refs.
    """

    refs = list(refs)

    if not refs:
        return []

    try:
        output = run_git(
            "rev-list",
            "--full-history",
            *refs,
            cwd=cwd,
        )
    except GitError as exc:
        # Empty repository: no commits reachable
        if "ambiguous argument" in str(exc) and "HEAD" in str(exc):
            return []
        raise

    return [sha for sha in output.splitlines() if sha.strip()]


def get_commit_diff(sha: str, cwd: Path | str | None = None) -> CommitDiff:
    """
    Return a complete CommitDiff.

    This is the primary bridge between Git history and the scanner.
    """

    commit = get_commit(sha, cwd=cwd)
    files = get_file_diffs(sha, cwd=cwd)

    return CommitDiff(
        commit=commit,
        files=tuple(files),
    )
