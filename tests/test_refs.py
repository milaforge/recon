"""
Refs tests: remote branch discovery, local refs, tags.
"""

import pytest
from pathlib import Path

from recon.git.refs import (
    get_remotes,
    get_remote_branches,
    get_local_remote_refs,
    get_local_tags,
    RemoteBranch,
)


class TestRemotes:
    """Tests for remote discovery."""

    def test_get_remotes_returns_configured_remotes(self, git_repo: Path) -> None:
        """get_remotes should return configured remotes."""
        # Initially no remotes
        remotes = get_remotes(cwd=git_repo)
        assert remotes == []

        # Add a remote
        from tests.fixtures.git_repo import run_git
        run_git("remote", "add", "origin", "https://example.com/repo.git", cwd=git_repo)

        remotes = get_remotes(cwd=git_repo)
        assert "origin" in remotes


class TestRemoteBranches:
    """Tests for remote branch discovery."""

    def test_get_remote_branches_discovers_all_branches(
        self, bare_repo: Path, git_repo: Path
    ) -> None:
        """get_remote_branches should discover all branches on a remote."""
        from tests.fixtures.git_repo import build_remote_with_branches

        pushed = build_remote_with_branches(bare_repo, git_repo)

        # Remote "origin" is already added by build_remote_with_branches
        branches = get_remote_branches("origin", cwd=git_repo)

        assert len(branches) == 3
        branch_names = {b.name for b in branches}
        assert branch_names == {"main", "feature/busd", "feature/security-config"}

        # Verify SHAs match
        for branch in branches:
            expected_sha = next(s for n, s in pushed if n == branch.name)
            assert branch.sha == expected_sha

    def test_remote_branch_properties(self, bare_repo: Path, git_repo: Path) -> None:
        """RemoteBranch should have correct properties."""
        from tests.fixtures.git_repo import build_remote_with_branches

        build_remote_with_branches(bare_repo, git_repo)

        # Remote "origin" is already added by build_remote_with_branches
        branches = get_remote_branches("origin", cwd=git_repo)
        branch = branches[0]

        assert branch.remote == "origin"
        assert branch.remote_ref == f"refs/remotes/origin/{branch.name}"
        assert branch.display_name == f"origin/{branch.name}"


class TestLocalRefs:
    """Tests for local ref discovery."""

    def test_get_local_remote_refs_returns_tracking_refs(self, git_repo: Path) -> None:
        """get_local_remote_refs should return remote-tracking refs."""
        from tests.fixtures.git_repo import run_git, temp_bare_repo, write_file, commit

        # Create a commit so we have something to push
        write_file(git_repo, "a.txt", "a\n")
        commit(git_repo, "A")

        # Create a bare remote and push to it
        with temp_bare_repo() as bare_repo:
            run_git("remote", "add", "origin", str(bare_repo), cwd=git_repo)
            run_git("push", "origin", "main", cwd=git_repo)
            run_git("fetch", "origin", cwd=git_repo)

            refs = get_local_remote_refs(cwd=git_repo)
            assert len(refs) >= 1
            assert all(r.startswith("refs/remotes/") for r in refs)

    def test_get_local_tags_returns_tags(self, git_repo: Path) -> None:
        """get_local_tags should return tag refs."""
        from tests.fixtures.git_repo import run_git, commit, write_file

        write_file(git_repo, "a.txt", "a\n")
        commit(git_repo, "A")

        run_git("tag", "v1.0", cwd=git_repo)

        tags = get_local_tags(cwd=git_repo)
        assert "refs/tags/v1.0" in tags