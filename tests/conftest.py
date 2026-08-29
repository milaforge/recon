"""
Pytest configuration and shared fixtures.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.fixtures.git_repo import (
    build_branch_with_secret,
    build_linear_history,
    build_remote_with_branches,
    build_shared_commit,
    checkout,
    clone_repo,
    commit,
    create_branch,
    delete_file,
    get_head_sha,
    get_local_branches,
    get_local_remote_refs,
    get_local_tags,
    get_remote_branches,
    is_shallow,
    make_shallow,
    push_to_remote,
    rename_file,
    temp_bare_repo,
    temp_git_repo,
    write_file,
)


@pytest.fixture
def git_repo() -> Iterator[Path]:
    """A temporary Git repository with main branch and test user config."""
    with temp_git_repo() as repo:
        yield repo


@pytest.fixture
def bare_repo() -> Iterator[Path]:
    """A temporary bare Git repository (for use as remote)."""
    with temp_bare_repo() as repo:
        yield repo


@pytest.fixture
def remote_with_branches(bare_repo: Path, git_repo: Path) -> list[tuple[str, str]]:
    """
    A bare remote with multiple branches pushed from a working repo.

    Returns list of (branch_name, sha) that were pushed.
    """
    return build_remote_with_branches(bare_repo, git_repo)


@pytest.fixture
def cloned_repo(bare_repo: Path, tmp_path: Path) -> Iterator[Path]:
    """A clone of the bare remote."""
    target = tmp_path / "cloned"
    clone_repo(bare_repo, target)
    yield target


# Re-export helpers for direct use in tests
__all__ = [
    "bare_repo",
    "build_branch_with_secret",
    "build_linear_history",
    "build_remote_with_branches",
    "build_shared_commit",
    "checkout",
    "clone_repo",
    "cloned_repo",
    "commit",
    "create_branch",
    "delete_file",
    "get_head_sha",
    "get_local_branches",
    "get_local_remote_refs",
    "get_local_tags",
    "get_remote_branches",
    "git_repo",
    "is_shallow",
    "make_shallow",
    "push_to_remote",
    "remote_with_branches",
    "rename_file",
    "write_file",
]