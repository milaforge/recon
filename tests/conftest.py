"""
Pytest configuration and shared fixtures.
"""

import pytest
from pathlib import Path
from typing import Iterator

from tests.fixtures.git_repo import (
    temp_git_repo,
    temp_bare_repo,
    commit,
    write_file,
    delete_file,
    rename_file,
    create_branch,
    checkout,
    get_head_sha,
    get_remote_branches,
    get_local_branches,
    get_local_remote_refs,
    get_local_tags,
    is_shallow,
    make_shallow,
    push_to_remote,
    clone_repo,
    build_linear_history,
    build_branch_with_secret,
    build_shared_commit,
    build_remote_with_branches,
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
    "git_repo",
    "bare_repo",
    "remote_with_branches",
    "cloned_repo",
    "commit",
    "write_file",
    "delete_file",
    "rename_file",
    "create_branch",
    "checkout",
    "get_head_sha",
    "get_remote_branches",
    "get_local_branches",
    "get_local_remote_refs",
    "get_local_tags",
    "is_shallow",
    "make_shallow",
    "push_to_remote",
    "clone_repo",
    "build_linear_history",
    "build_branch_with_secret",
    "build_shared_commit",
    "build_remote_with_branches",
]