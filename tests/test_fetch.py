"""
Fetch tests: fetch-all with bare remote fixture.
"""

import pytest
from pathlib import Path

from recon.git.fetch import fetch_all, fetch_branch, verify_branch, fetch_remote
from recon.git.refs import RemoteBranch, get_remote_branches
from recon.git.repository import run_git, GitError


class TestFetchBranch:
    """Tests for fetching a single branch."""

    def test_fetch_branch_fetches_and_verifies(
        self, bare_repo: Path, git_repo: Path
    ) -> None:
        """fetch_branch should fetch and verify a branch."""
        from tests.fixtures.git_repo import build_remote_with_branches

        pushed = build_remote_with_branches(bare_repo, git_repo)

        branches = get_remote_branches("origin", cwd=git_repo)
        main_branch = next(b for b in branches if b.name == "main")

        fetch_branch(main_branch, cwd=git_repo)

        verify_branch(main_branch, cwd=git_repo)

        run_git("cat-file", "-e", f"{main_branch.sha}^{{commit}}", cwd=git_repo)


class TestFetchAll:
    """Tests for fetch-all."""

    def test_fetch_all_fetches_all_branches(
        self, bare_repo: Path, git_repo: Path
    ) -> None:
        """fetch_all should fetch every branch from every remote."""
        from tests.fixtures.git_repo import build_remote_with_branches

        pushed = build_remote_with_branches(bare_repo, git_repo)

        fetched = fetch_all(cwd=git_repo)

        assert len(fetched) == 3
        fetched_names = {b.name for b in fetched}
        assert fetched_names == {"main", "feature/busd", "feature/security-config"}

        # Verify each branch tip matches remote
        for branch in fetched:
            expected_sha = next(s for n, s in pushed if n == branch.name)
            assert branch.sha == expected_sha

            # Verify local ref matches
            actual_sha = run_git(
                "rev-parse", branch.remote_ref, cwd=git_repo
            ).strip()
            assert actual_sha == branch.sha

            # Verify commit object exists locally
            run_git("cat-file", "-e", f"{branch.sha}^{{commit}}", cwd=git_repo)

    def test_fetch_all_returns_fetched_branches(
        self, bare_repo: Path, git_repo: Path
    ) -> None:
        """fetch_all should return the branches that were fetched."""
        from tests.fixtures.git_repo import build_remote_with_branches

        build_remote_with_branches(bare_repo, git_repo)

        fetched = fetch_all(cwd=git_repo)

        assert isinstance(fetched, list)
        assert all(isinstance(b, RemoteBranch) for b in fetched)
        assert len(fetched) == 3

    def test_fetch_all_fails_on_shallow_without_remote(self, tmp_path: Path) -> None:
        """fetch_all should fail on shallow repo without remote."""
        import os
        from tests.fixtures.git_repo import temp_git_repo, make_shallow, run_git, write_file, commit

        original_cwd = os.getcwd()
        try:
            with temp_git_repo() as git_repo:
                # Create a commit so the repo can be cloned
                write_file(git_repo, "file.txt", "content\n")
                commit(git_repo, "initial")
                
                make_shallow(git_repo)
                os.chdir(git_repo)

                # Remove the remote that make_shallow creates
                run_git("remote", "remove", "origin", cwd=git_repo)

                with pytest.raises(GitError, match="shallow but has no configured remote"):
                    fetch_all(cwd=git_repo)
        finally:
            os.chdir(original_cwd)


class TestFetchRemote:
    """Tests for fetching from a specific remote."""

    def test_fetch_remote_fetches_selected_branches(
        self, bare_repo: Path, git_repo: Path
    ) -> None:
        """fetch_remote should fetch only selected branches."""
        from tests.fixtures.git_repo import build_remote_with_branches

        pushed = build_remote_with_branches(bare_repo, git_repo)

        branches = get_remote_branches("origin", cwd=git_repo)
        main_branch = next(b for b in branches if b.name == "main")
        busd_branch = next(b for b in branches if b.name == "feature/busd")

        # Record SHAs before fetch
        main_sha_before = run_git("rev-parse", main_branch.remote_ref, cwd=git_repo).strip()
        busd_sha_before = run_git("rev-parse", busd_branch.remote_ref, cwd=git_repo).strip()

        fetch_remote("origin", [main_branch], cwd=git_repo)

        # Main branch should be updated to match remote
        actual_sha = run_git("rev-parse", main_branch.remote_ref, cwd=git_repo).strip()
        assert actual_sha == main_branch.sha

        # Other branch refs should exist but not be updated (still point to old SHAs)
        busd_sha_after = run_git("rev-parse", busd_branch.remote_ref, cwd=git_repo).strip()
        assert busd_sha_after == busd_sha_before