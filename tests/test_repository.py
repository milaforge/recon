"""
Repository-level tests: detection, shallow, complete-history preparation.
"""

import pytest
from pathlib import Path

from recon.git.repository import (
    ensure_repository,
    repository_root,
    is_shallow_repository,
    is_partial_repository,
    prepare_repository,
    unshallow,
    GitError,
)


class TestRepositoryDetection:
    """Tests for repository detection and validation."""

    def test_ensure_repository_succeeds_in_git_repo(self, git_repo: Path) -> None:
        """ensure_repository should succeed inside a Git repository."""
        # Should not raise
        ensure_repository(cwd=git_repo)

    def test_ensure_repository_fails_outside_git_repo(self, tmp_path: Path) -> None:
        """ensure_repository should fail outside a Git repository."""
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            with pytest.raises(GitError, match="Not inside a Git repository"):
                ensure_repository()
        finally:
            os.chdir(original_cwd)

    def test_repository_root_returns_correct_path(self, git_repo: Path) -> None:
        """repository_root should return the repo root."""
        root = repository_root(cwd=git_repo)
        assert root == git_repo


class TestShallowRepository:
    """Tests for shallow repository detection and handling."""

    def test_is_shallow_repository_false_for_normal_repo(self, git_repo: Path) -> None:
        """Normal repository should not be shallow."""
        assert is_shallow_repository(cwd=git_repo) is False

    def test_is_shallow_repository_true_for_shallow_clone(self, git_repo: Path, tmp_path: Path) -> None:
        """Shallow clone should be detected as shallow."""
        import os
        import shutil

        original_cwd = os.getcwd()
        try:
            # Create a commit in the source repo so it can be cloned
            from tests.fixtures.git_repo import write_file, commit
            write_file(git_repo, "file.txt", "content\n")
            commit(git_repo, "initial")

            # Create a shallow clone
            shallow_dir = tmp_path / "shallow"
            from tests.fixtures.git_repo import run_git
            run_git("clone", "--depth", "1", "--no-single-branch", f"file://{git_repo.resolve()}", str(shallow_dir), cwd=Path.cwd())

            os.chdir(shallow_dir)
            assert is_shallow_repository() is True
        finally:
            os.chdir(original_cwd)

    def test_unshallow_converts_shallow_to_complete(self, git_repo: Path, tmp_path: Path) -> None:
        """unshallow should convert a shallow repository to complete."""
        import os
        import shutil

        original_cwd = os.getcwd()
        try:
            # Create a commit in the source repo so it can be cloned
            from tests.fixtures.git_repo import write_file, commit
            write_file(git_repo, "file.txt", "content\n")
            commit(git_repo, "initial")

            # Create a shallow clone
            shallow_dir = tmp_path / "shallow"
            from tests.fixtures.git_repo import run_git
            run_git("clone", "--depth", "1", "--no-single-branch", f"file://{git_repo.resolve()}", str(shallow_dir), cwd=Path.cwd())

            os.chdir(shallow_dir)
            assert is_shallow_repository() is True

            # The clone already has 'origin' remote, use it to unshallow
            unshallow()

            assert is_shallow_repository() is False
        finally:
            os.chdir(original_cwd)


class TestPartialRepository:
    """Tests for partial clone detection."""

    def test_is_partial_repository_false_for_normal_repo(self, git_repo: Path) -> None:
        """Normal repository should not be partial."""
        assert is_partial_repository(cwd=git_repo) is False


class TestPrepareRepository:
    """Tests for complete repository preparation."""

    def test_prepare_repository_succeeds_for_normal_repo(self, git_repo: Path) -> None:
        """prepare_repository should succeed for normal repo."""
        # Should not raise
        prepare_repository(cwd=git_repo)

    def test_prepare_repository_fails_for_shallow_repo(self, git_repo: Path, tmp_path: Path) -> None:
        """prepare_repository should fail for shallow repo without remote."""
        import os

        original_cwd = os.getcwd()
        try:
            shallow_dir = tmp_path / "shallow"
            from tests.fixtures.git_repo import run_git, write_file, commit
            
            # Create a commit in the source repo so it can be cloned
            write_file(git_repo, "file.txt", "content\n")
            commit(git_repo, "initial")
            
            run_git("clone", "--depth", "1", "--no-single-branch", f"file://{git_repo.resolve()}", str(shallow_dir), cwd=Path.cwd())

            os.chdir(shallow_dir)
            run_git("remote", "remove", "origin", cwd=shallow_dir)
            # No remote configured, so unshallow will fail
            with pytest.raises(GitError, match="shallow but has no configured remote"):
                prepare_repository(cwd=shallow_dir)
        finally:
            os.chdir(original_cwd)